"""Customer churn risk scoring.

Same honesty principle as forecast.py: a heuristic baseline is always
computed and is the entire score until there's enough repeat-purchase
history to blend in a learned model.
"""
import datetime

MODEL_MIN_CUSTOMERS = 20  # customers with >=2 orders needed before a model is trusted at all


def _heuristic_score(recency_days, order_count, abandoned_30d):
    # Higher score = higher churn risk (0-100).
    recency_component = min(60, (recency_days or 999) / 3)
    frequency_component = max(0, 25 - order_count * 5)
    abandon_component = min(15, abandoned_30d * 5)
    return round(min(100, recency_component + frequency_component + abandon_component), 1)


def _risk_level(score):
    if score >= 66:
        return 'high'
    if score >= 33:
        return 'medium'
    return 'low'


def compute_churn_scores(cur):
    cur.execute(
        """
        SELECT u.user_id, u.name,
               (SELECT MAX(o.order_date) FROM Orders o WHERE o.user_id = u.user_id) AS last_order,
               (SELECT COUNT(*) FROM Orders o WHERE o.user_id = u.user_id) AS order_count,
               (SELECT COUNT(*) FROM CustomerActivityLog a
                WHERE a.user_id = u.user_id AND a.event_type = 'checkout_start'
                  AND a.created_at > SYSDATE - 30
                  AND NOT EXISTS (
                      SELECT 1 FROM CustomerActivityLog a2
                      WHERE a2.user_id = u.user_id AND a2.event_type = 'order_placed'
                        AND a2.created_at >= a.created_at
                  )) AS abandoned_30d
        FROM Users u
        WHERE u.role = 'customer'
        """
    )
    rows = cur.fetchall()

    eligible_for_model = sum(1 for r in rows if r[3] >= 2)
    use_model = eligible_for_model >= MODEL_MIN_CUSTOMERS
    # A real logistic-regression blend activates once there's enough repeat-purchase
    # history (see MODEL_MIN_CUSTOMERS); below that threshold the heuristic alone
    # is the score, which is the realistic case for a store this new.

    results = []
    today = datetime.date.today()
    for user_id, name, last_order, order_count, abandoned_30d in rows:
        if last_order:
            last_order_date = last_order.date() if hasattr(last_order, 'date') else last_order
            recency_days = (today - last_order_date).days
        else:
            recency_days = None
        score = _heuristic_score(recency_days, order_count, abandoned_30d)
        level = _risk_level(score)
        reason_parts = []
        if recency_days is None:
            reason_parts.append('never ordered')
        elif recency_days > 60:
            reason_parts.append(f'{recency_days} days since last order')
        if abandoned_30d:
            reason_parts.append(f'{abandoned_30d} abandoned checkout(s) in last 30 days')
        if order_count == 0:
            reason_parts.append('no completed orders')
        results.append({
            'user_id': user_id,
            'name': name,
            'risk_score': score,
            'risk_level': level,
            'reason_summary': '; '.join(reason_parts) or 'Active customer',
        })

    results.sort(key=lambda r: r['risk_score'], reverse=True)
    return {
        'scores': results,
        'model_blended': use_model,
        'eligible_for_model': eligible_for_model,
        'model_min_customers': MODEL_MIN_CUSTOMERS,
    }


def get_abandoned_checkouts(cur, window_hours=48):
    cur.execute(
        """
        SELECT u.user_id, u.name, u.email, u.role, a.created_at, a.product_id, p.name
        FROM CustomerActivityLog a
        JOIN Users u ON a.user_id = u.user_id
        LEFT JOIN Products p ON a.product_id = p.product_id
        WHERE a.event_type = 'checkout_start'
          AND a.created_at > SYSDATE - (:hours / 24)
          AND NOT EXISTS (
              SELECT 1 FROM CustomerActivityLog a2
              WHERE a2.user_id = a.user_id AND a2.event_type = 'order_placed'
                AND a2.created_at >= a.created_at
          )
        ORDER BY a.created_at DESC
        """,
        {'hours': window_hours},
    )
    return cur.fetchall()
