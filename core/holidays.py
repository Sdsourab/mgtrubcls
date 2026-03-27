"""
Bangladesh Government Holiday List (2026)
Add or remove dates here as needed.
Format: 'YYYY-MM-DD'
"""

BD_HOLIDAYS = {
    # ── National & Public Holidays 2026 ──────────────────────
    "2026-02-21": "International Mother Language Day",
    "2026-03-17": "Birth Anniversary of Bangabandhu",
    "2026-03-26": "Independence Day",
    "2026-04-14": "Bengali New Year (Pahela Baishakh)",
    "2026-05-01": "May Day (Labour Day)",
    "2026-08-15": "National Mourning Day",
    "2026-12-16": "Victory Day",
    "2026-12-25": "Christmas Day",

    # ── Eid ul Fitr 2026 (approximate) ───────────────────────
    "2026-03-20": "Eid ul Fitr",
    "2026-03-21": "Eid ul Fitr Holiday",
    "2026-03-22": "Eid ul Fitr Holiday",

    # ── Eid ul Adha 2026 (approximate) ───────────────────────
    "2026-05-27": "Eid ul Adha",
    "2026-05-28": "Eid ul Adha Holiday",
    "2026-05-29": "Eid ul Adha Holiday",

    # ── Other Religious Holidays ──────────────────────────────
    "2026-04-02": "Shab-e-Barat",
    "2026-04-27": "Shab-e-Qadr",
    "2026-06-16": "Eid-e-Miladunnabi",
    "2026-10-02": "Durga Puja (Maha Dashami)",
    "2026-11-15": "Shab-e-Ashura",
}


def is_holiday(date_obj=None):
    """
    Check if a given date is a Bangladesh government holiday.
    Returns (bool, holiday_name_or_None).
    If date_obj is None, checks today.
    """
    from datetime import date
    if date_obj is None:
        date_obj = date.today()
    key = date_obj.strftime('%Y-%m-%d')
    name = BD_HOLIDAYS.get(key)
    return (True, name) if name else (False, None)


def get_holiday_info(date_str: str):
    """
    date_str: 'YYYY-MM-DD'
    Returns {'is_holiday': bool, 'name': str|None}
    """
    name = BD_HOLIDAYS.get(date_str)
    return {'is_holiday': bool(name), 'name': name}


def get_upcoming_holidays(days_ahead: int = 30):
    """Return holidays in the next N days."""
    from datetime import date, timedelta
    today = date.today()
    result = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        key = d.strftime('%Y-%m-%d')
        if key in BD_HOLIDAYS:
            result.append({'date': key, 'name': BD_HOLIDAYS[key]})
    return result