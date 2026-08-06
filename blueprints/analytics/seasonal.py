def get_events_in_range(cur, start_date, end_date):
    """Events whose [start_date, end_date] overlaps the given range."""
    cur.execute(
        """
        SELECT event_id, event_name, start_date, end_date, boost_weight, is_approximate, notes
        FROM SeasonalEvents
        WHERE start_date <= :end_d AND end_date >= :start_d
        ORDER BY start_date
        """,
        {'start_d': start_date, 'end_d': end_date},
    )
    return cur.fetchall()


def get_upcoming_events(cur, from_date, horizon_days=35):
    import datetime
    to_date = from_date + datetime.timedelta(days=horizon_days)
    cur.execute(
        """
        SELECT event_id, event_name, start_date, end_date, boost_weight, is_approximate, notes
        FROM SeasonalEvents
        WHERE start_date BETWEEN :from_d AND :to_d
        ORDER BY start_date
        """,
        {'from_d': from_date, 'to_d': to_date},
    )
    return cur.fetchall()


def boost_weight_for_date(events, target_date):
    """Multiplicative demand boost applicable to target_date, 1.0 if no event covers it."""
    weight = 1.0
    for _id, _name, start, end, boost, *_ in events:
        start_d = start.date() if hasattr(start, 'date') else start
        end_d = end.date() if hasattr(end, 'date') else end
        if start_d <= target_date <= end_d:
            weight = max(weight, float(boost))
    return weight
