"""Sales forecasting pipeline.

Deliberately honest about data sparsity: with few historical order-days, the
naive seasonal baseline alone IS the forecast. A model is only trained and
blended in once there's enough history to trust it, and the blend weight on
the model rises gradually with data sufficiency. No component here ever
claims near-100% confidence.
"""
import datetime
import importlib.util

np = None
pd = None


def _get_ml_deps():
    global np, pd
    if np is None or pd is None:
        try:
            import numpy as _np
            import pandas as _pd
            np = _np
            pd = _pd
        except ImportError:
            return None, None
    return np, pd


def _check_ml_deps():
    if np is not None and pd is not None:
        return True
    try:
        return bool(importlib.util.find_spec('numpy') and importlib.util.find_spec('pandas'))
    except Exception:
        return False


class _MLDepsChecker:
    def __bool__(self):
        return _check_ml_deps()


_HAS_ML_DEPS = _MLDepsChecker()

from .seasonal import boost_weight_for_date, get_events_in_range

SUFFICIENCY_THRESHOLDS = {
    'insufficient': (0, 14),
    'low': (14, 46),
    'moderate': (46, 121),
    'good': (121, float('inf')),
}
CONFIDENCE_CAP = {
    'insufficient': 20,
    'low': 50,
    'moderate': 75,
    'good': 90,
}
MODEL_BLEND_WEIGHT = {
    'insufficient': 0.0,
    'low': 0.30,
    'moderate': 0.60,
    'good': 0.85,
}


def load_daily_sales(cur):
    _get_ml_deps()
    cur.execute(
        """
        SELECT TRUNC(order_date) AS day, SUM(total_amount) AS total
        FROM Orders
        WHERE status != 'cancelled'
        GROUP BY TRUNC(order_date)
        ORDER BY day
        """
    )
    rows = cur.fetchall()
    if not rows:
        today = datetime.date.today()
        idx = pd.date_range(today - datetime.timedelta(days=29), today, freq='D')
        return pd.Series(0.0, index=idx)

    dates = [r[0].date() if hasattr(r[0], 'date') else r[0] for r in rows]
    totals = [float(r[1]) for r in rows]
    s = pd.Series(totals, index=pd.to_datetime(dates))
    full_idx = pd.date_range(s.index.min(), max(s.index.max(), pd.Timestamp.today().normalize()), freq='D')
    return s.reindex(full_idx, fill_value=0.0)


def data_sufficiency(daily_series):
    distinct_order_days = int((daily_series > 0).sum())
    level = 'insufficient'
    for lvl, (lo, hi) in SUFFICIENCY_THRESHOLDS.items():
        if lo <= distinct_order_days < hi:
            level = lvl
            break
    lo, hi = SUFFICIENCY_THRESHOLDS[level]
    hi = hi if hi != float('inf') else lo + 120
    progress_in_band = min(1.0, (distinct_order_days - lo) / max(1, hi - lo))
    prev_cap = 0 if level == 'insufficient' else list(CONFIDENCE_CAP.values())[list(CONFIDENCE_CAP).index(level) - 1]
    confidence_pct = prev_cap + progress_in_band * (CONFIDENCE_CAP[level] - prev_cap)
    return {
        'level': level,
        'days_of_history': int(len(daily_series)),
        'distinct_order_days': distinct_order_days,
        'confidence_pct': round(confidence_pct, 1),
    }


def naive_seasonal_baseline(daily_series, cur, target_date):
    weekday = target_date.weekday()
    same_weekday = daily_series[daily_series.index.dayofweek == weekday]
    base = float(same_weekday.tail(8).mean()) if len(same_weekday) else float(daily_series.mean() or 0.0)
    events = get_events_in_range(cur, target_date - datetime.timedelta(days=1), target_date + datetime.timedelta(days=1))
    weight = boost_weight_for_date(events, target_date)
    return base * weight


def _engineer_features(daily_series):
    _get_ml_deps()
    df = pd.DataFrame({'total': daily_series.values}, index=daily_series.index)
    df['dow'] = df.index.dayofweek
    df['day_num'] = np.arange(len(df))
    dow_dummies = pd.get_dummies(df['dow'], prefix='dow')
    features = pd.concat([df[['day_num']], dow_dummies], axis=1)
    return features, df['total']


def train_model(daily_series):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X, y = _engineer_features(daily_series)
    if len(X) < 14 or y.sum() == 0:
        return None
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(X, y)
    return model


def _predict_with_model(model, daily_series, target_date):
    _get_ml_deps()
    day_num = (pd.Timestamp(target_date) - daily_series.index.min()).days
    row = {'day_num': day_num}
    for d in range(7):
        row[f'dow_{d}'] = 1 if target_date.weekday() == d else 0
    X_cols, _ = _engineer_features(daily_series)
    X_pred = pd.DataFrame([row]).reindex(columns=X_cols.columns, fill_value=0)
    pred = model.predict(X_pred)[0]
    return max(0.0, float(pred))


def blend_forecast(naive_value, model_value, level):
    w = MODEL_BLEND_WEIGHT[level]
    if model_value is None:
        return naive_value
    return (1 - w) * naive_value + w * model_value


def forecast_next_week_and_month(cur):
    _get_ml_deps()
    if not _HAS_ML_DEPS or pd is None or np is None:
        return {
            'sufficiency_level': 'unavailable',
            'confidence_pct': 0,
            'days_of_history': 0,
            'distinct_order_days': 0,
            'week': {'total': 0, 'pct_change': 0, 'daily_breakdown': {}},
            'month': {'total': 0, 'pct_change': 0, 'daily_breakdown': {}},
            'upcoming_events': [],
            'error': 'Forecast unavailable: ML dependencies not installed.',
        }
    daily_series = load_daily_sales(cur)
    sufficiency = data_sufficiency(daily_series)
    model = train_model(daily_series) if sufficiency['level'] != 'insufficient' else None

    today = datetime.date.today()
    daily_breakdown = {}
    for i in range(1, 31):
        d = today + datetime.timedelta(days=i)
        naive_v = naive_seasonal_baseline(daily_series, cur, d)
        model_v = _predict_with_model(model, daily_series, d) if model is not None else None
        blended = blend_forecast(naive_v, model_v, sufficiency['level'])
        daily_breakdown[d.isoformat()] = round(blended, 2)

    week_total = sum(v for k, v in daily_breakdown.items() if k <= (today + datetime.timedelta(days=7)).isoformat())
    month_total = sum(daily_breakdown.values())

    trailing_week = float(daily_series.tail(7).sum())
    trailing_month = float(daily_series.tail(30).sum())

    def pct_change(new, old):
        if old <= 0:
            return 0.0
        return round((new - old) / old * 100, 1)

    upcoming = get_events_in_range(cur, today, today + datetime.timedelta(days=35))
    upcoming_events = [
        {
            'name': e[1],
            'start_date': (e[2].date() if hasattr(e[2], 'date') else e[2]).isoformat(),
            'end_date': (e[3].date() if hasattr(e[3], 'date') else e[3]).isoformat(),
            'boost_weight': float(e[4]),
            'is_approximate': bool(e[5]),
        }
        for e in upcoming
    ]

    return {
        'sufficiency_level': sufficiency['level'],
        'confidence_pct': sufficiency['confidence_pct'],
        'days_of_history': sufficiency['days_of_history'],
        'distinct_order_days': sufficiency['distinct_order_days'],
        'week': {
            'total': round(week_total, 2),
            'pct_change': pct_change(week_total, trailing_week),
            'daily_breakdown': {k: v for k, v in list(daily_breakdown.items())[:7]},
        },
        'month': {
            'total': round(month_total, 2),
            'pct_change': pct_change(month_total, trailing_month),
            'daily_breakdown': daily_breakdown,
        },
        'upcoming_events': upcoming_events,
    }
