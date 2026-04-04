"""
core/schedule_utils.py
──────────────────────
Bangladesh Standard Time (BST = UTC+6) schedule utilities.

Time Window Logic:
  07:00 – 18:59 BST  →  show TODAY's classes
  19:00 – 06:59 BST  →  show TOMORROW's classes

This mirrors the cron pattern already in app/__init__.py (BST = timezone(+6)).
"""

from datetime import datetime, timedelta, timezone, date as date_type

# ── Timezone ──────────────────────────────────────────────────────────────────
BST = timezone(timedelta(hours=6))

# ── Boundary (7 PM = start of "show tomorrow" window) ─────────────────────────
_TOMORROW_WINDOW_START_HOUR = 19  # 19:00 BST → show tomorrow
_TODAY_WINDOW_START_HOUR    = 7   # 07:00 BST → show today


def get_bst_now() -> datetime:
    """Return the current datetime in Bangladesh Standard Time."""
    return datetime.now(BST)


def get_schedule_target() -> dict:
    """
    Core time-window resolver.

    Returns a dict with:
      - day_name   (str)  : 'Monday', 'Tuesday', …
      - date       (date) : the actual calendar date
      - mode       (str)  : 'today' | 'tomorrow'
      - bst_now    (datetime)
      - bst_time   (str)  : 'HH:MM' in BST
      - display_label (str): human-readable label for the UI header
    """
    now_bst = get_bst_now()
    hour    = now_bst.hour

    if _TODAY_WINDOW_START_HOUR <= hour < _TOMORROW_WINDOW_START_HOUR:
        # 07:00 – 18:59 → today
        target_date = now_bst.date()
        mode        = 'today'
    else:
        # 19:00 – 06:59 → tomorrow
        target_date = (now_bst + timedelta(days=1)).date()
        mode        = 'tomorrow'

    day_name = target_date.strftime('%A')   # 'Monday', 'Tuesday' …
    bst_time = now_bst.strftime('%H:%M')    # '14:35'

    # Human-readable label for the widget header
    if mode == 'today':
        display_label = f"Today's Classes — {day_name}"
    else:
        date_str      = target_date.strftime('%d %b')   # '15 Jan'
        display_label = f"Tomorrow's Classes — {day_name}, {date_str}"

    return {
        'day_name':      day_name,
        'date':          target_date,
        'mode':          mode,
        'bst_now':       now_bst,
        'bst_time':      bst_time,
        'display_label': display_label,
    }


def fmt12h(t: str) -> str:
    """Convert 'HH:MM' (24h) → '9:00 AM' / '2:30 PM'."""
    try:
        h, m = map(int, t.split(':'))
        period = 'AM' if h < 12 else 'PM'
        h12    = h % 12 or 12
        return f"{h12}:{m:02d} {period}"
    except Exception:
        return t


def classify_class_status(time_start: str, time_end: str, bst_time: str, mode: str) -> dict:
    """
    Determine a class's status relative to the current BST time.
    Only meaningful when mode == 'today'.

    Returns:
      status  : 'upcoming' | 'live' | 'done'
      progress: 0–100 (percentage of class elapsed, for live classes)
      mins_until: minutes until class starts (for upcoming)
      mins_left : minutes remaining (for live)
    """
    def to_mins(t: str) -> int:
        try:
            h, m = map(int, t.split(':'))
            return h * 60 + m
        except Exception:
            return 0

    now_m   = to_mins(bst_time)
    start_m = to_mins(time_start)
    end_m   = to_mins(time_end)
    duration = max(end_m - start_m, 1)

    if mode == 'tomorrow':
        return {'status': 'upcoming', 'progress': 0, 'mins_until': None, 'mins_left': None}

    if now_m < start_m:
        return {
            'status':     'upcoming',
            'progress':   0,
            'mins_until': start_m - now_m,
            'mins_left':  None,
        }
    elif now_m <= end_m:
        elapsed  = now_m - start_m
        progress = min(100, round(elapsed / duration * 100))
        return {
            'status':     'live',
            'progress':   progress,
            'mins_until': 0,
            'mins_left':  end_m - now_m,
        }
    else:
        return {'status': 'done', 'progress': 100, 'mins_until': None, 'mins_left': None}