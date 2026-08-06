def log_activity(cur, user_id, event_type, product_id=None, order_id=None):
    """Record a customer activity event (logged-in users only).

    Used to power the admin abandoned-checkout list and churn scoring.
    Best-effort: any failure here should never break the caller's request.
    """
    if not user_id:
        return
    try:
        cur.execute(
            """
            INSERT INTO CustomerActivityLog (activity_id, user_id, event_type, product_id, order_id, created_at)
            VALUES (customeractivitylog_seq.NEXTVAL, :p_uid, :p_event, :p_product, :p_order, SYSDATE)
            """,
            {'p_uid': user_id, 'p_event': event_type, 'p_product': product_id, 'p_order': order_id},
        )
    except Exception:
        pass
