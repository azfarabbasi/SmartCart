import datetime
import json

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from blueprints.auth.decorators import admin_required
from db import get_db
from extensions import limiter
from security import log_admin_action
from validators import validate_required_text

from . import churn as churn_mod
from . import forecast as forecast_mod
from .seasonal import get_upcoming_events

analytics_bp = Blueprint('analytics', __name__, url_prefix='/admin')


@analytics_bp.route('/analytics')
@admin_required
def dashboard():
    cur = get_db().cursor()
    cur.execute(
        "SELECT horizon, predicted_total, pct_change, confidence_pct, sufficiency_level, "
        "details_json, generated_at "
        "FROM ForecastCache WHERE cache_id IN ("
        "  SELECT MAX(cache_id) FROM ForecastCache GROUP BY horizon"
        ")"
    )
    cached_rows = cur.fetchall()
    cached = {row[0]: row for row in cached_rows}
    if not cached:
        flash('No forecast generated yet - click "Refresh Forecast" to generate one.', 'info')

    upcoming = get_upcoming_events(cur, datetime.date.today())
    upcoming_events = [
        {'name': e[1], 'start_date': e[2], 'end_date': e[3], 'boost_weight': float(e[4]),
         'is_approximate': bool(e[5])}
        for e in upcoming
    ]

    week_series = json.loads(cached['week'][5]) if 'week' in cached and cached['week'][5] else {}
    month_series = json.loads(cached['month'][5]) if 'month' in cached and cached['month'][5] else {}

    return render_template(
        'admin/analytics.html', cached=cached, upcoming_events=upcoming_events,
        week_series=week_series, month_series=month_series,
    )


@analytics_bp.route('/analytics/refresh', methods=['POST'])
@admin_required
@limiter.limit('5 per minute')
def refresh_forecast():
    cur = get_db().cursor()
    result = forecast_mod.forecast_next_week_and_month(cur)

    for horizon in ('week', 'month'):
        cur.execute(
            """
            INSERT INTO ForecastCache (cache_id, generated_at, horizon, predicted_total, pct_change,
                                        confidence_pct, sufficiency_level, details_json)
            VALUES (forecastcache_seq.NEXTVAL, SYSDATE, :h, :pt, :pc, :conf, :suff, :dj)
            """,
            {
                'h': horizon,
                'pt': result[horizon]['total'],
                'pc': result[horizon]['pct_change'],
                'conf': result['confidence_pct'],
                'suff': result['sufficiency_level'],
                'dj': json.dumps(result[horizon]['daily_breakdown']),
            },
        )
    log_admin_action(cur, session['user_id'], 'analytics.refresh')
    get_db().commit()
    flash('Forecast refreshed.', 'success')
    return redirect(url_for('analytics.dashboard'))


# ── SEASONAL EVENTS ──────────────────────────────────────────────
@analytics_bp.route('/seasonal-events')
@admin_required
def seasonal_events():
    cur = get_db().cursor()
    cur.execute(
        "SELECT event_id, event_name, start_date, end_date, boost_weight, is_approximate, notes "
        "FROM SeasonalEvents ORDER BY start_date"
    )
    return render_template('admin/seasonal_events.html', events=cur.fetchall())


@analytics_bp.route('/seasonal-events/add', methods=['POST'])
@admin_required
def add_seasonal_event():
    name = request.form.get('event_name', '').strip()
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    boost = request.form.get('boost_weight', '1.2')
    notes = request.form.get('notes', '').strip()

    ok, err = validate_required_text(name, 'Event name', min_len=2, max_len=100)
    if ok and not (start_date and end_date):
        ok, err = False, 'Start and end dates are required.'
    if not ok:
        flash(err, 'error')
        return redirect(url_for('analytics.seasonal_events'))

    cur = get_db().cursor()
    cur.execute(
        "INSERT INTO SeasonalEvents (event_id, event_name, start_date, end_date, boost_weight, "
        "is_approximate, notes) VALUES (seasonalevents_seq.NEXTVAL, :n, TO_DATE(:sd,'YYYY-MM-DD'), "
        "TO_DATE(:ed,'YYYY-MM-DD'), :b, 0, :notes)",
        {'n': name, 'sd': start_date, 'ed': end_date, 'b': float(boost), 'notes': notes},
    )
    log_admin_action(cur, session['user_id'], 'seasonal_event.create', 'SeasonalEvents', None, f'name={name}')
    get_db().commit()
    flash('Seasonal event added.', 'success')
    return redirect(url_for('analytics.seasonal_events'))


@analytics_bp.route('/seasonal-events/<int:event_id>/delete', methods=['POST'])
@admin_required
def delete_seasonal_event(event_id):
    cur = get_db().cursor()
    cur.execute("DELETE FROM SeasonalEvents WHERE event_id = :id", {'id': event_id})
    log_admin_action(cur, session['user_id'], 'seasonal_event.delete', 'SeasonalEvents', event_id)
    get_db().commit()
    flash('Seasonal event removed.', 'success')
    return redirect(url_for('analytics.seasonal_events'))


# ── CUSTOMER INSIGHTS (abandoned checkouts + churn) ──────────────
@analytics_bp.route('/customer-insights')
@admin_required
def customer_insights():
    cur = get_db().cursor()
    abandoned = churn_mod.get_abandoned_checkouts(cur)

    cur.execute(
        "SELECT user_id, risk_score, risk_level, reason_summary, generated_at "
        "FROM ChurnScoreCache WHERE generated_at = (SELECT MAX(generated_at) FROM ChurnScoreCache)"
    )
    churn_rows = cur.fetchall()
    if churn_rows:
        cur.execute("SELECT user_id, name, email FROM Users WHERE role = 'customer'")
        user_map = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        churn_scores = [
            {
                'user_id': r[0], 'name': user_map.get(r[0], ('Unknown', ''))[0],
                'email': user_map.get(r[0], ('', ''))[1],
                'risk_score': r[1], 'risk_level': r[2], 'reason_summary': r[3],
            }
            for r in churn_rows
        ]
        churn_scores.sort(key=lambda r: r['risk_score'], reverse=True)
        generated_at = churn_rows[0][4]
    else:
        churn_scores = []
        generated_at = None
        flash('No churn scores generated yet - click "Refresh Churn Scores" to generate them.', 'info')

    return render_template(
        'admin/customer_insights.html', abandoned=abandoned, churn_scores=churn_scores,
        generated_at=generated_at,
    )


@analytics_bp.route('/customer-insights/refresh', methods=['POST'])
@admin_required
@limiter.limit('5 per minute')
def refresh_churn():
    cur = get_db().cursor()
    result = churn_mod.compute_churn_scores(cur)
    for row in result['scores']:
        cur.execute(
            """
            INSERT INTO ChurnScoreCache (cache_id, generated_at, user_id, risk_score, risk_level, reason_summary)
            VALUES (churnscorecache_seq.NEXTVAL, SYSDATE, :p_uid, :score, :p_level, :reason)
            """,
            {'p_uid': row['user_id'], 'score': row['risk_score'], 'p_level': row['risk_level'],
             'reason': row['reason_summary']},
        )
    log_admin_action(cur, session['user_id'], 'churn.refresh')
    get_db().commit()
    flash('Churn scores refreshed.', 'success')
    return redirect(url_for('analytics.customer_insights'))
