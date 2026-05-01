"""
core/holidays.py
════════════════
Shared holiday utilities — imported by:
  - app/academic/routes.py  → is_holiday(), get_upcoming_holidays()
  - app/__init__.py (cron)  → is_holiday()
  - app/holidays/routes.py  → get_all_enriched()

Holiday data: RUB Academic Calendar 2026
"""

from datetime import date

# ─────────────────────────────────────────────────────────────
# HOLIDAY DATA — 2026
# Source: Rabindra University Bangladesh Academic Calendar
# ─────────────────────────────────────────────────────────────
HOLIDAYS = [
    {"id": "shab_e_miraj",       "name_en": "Shab-e-Miraj",
     "name_bn": "শব-ই-মিরাজ",
     "start": "2026-01-17", "end": "2026-01-17",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": True},

    {"id": "saraswati_puja",     "name_en": "Shri Shri Saraswati Puja",
     "name_bn": "শ্রী শ্রী সরস্বতী পূজা",
     "start": "2026-01-23", "end": "2026-01-23",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": False},

    {"id": "shab_e_barat",       "name_en": "Shab-e-Barat",
     "name_bn": "শব-ই-বরাত",
     "start": "2026-02-04", "end": "2026-02-04",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": True},

    {"id": "shaheed_dibas",      "name_en": "Shaheed Dibas & International Mother Language Day",
     "name_bn": "শহিদ দিবস ও আন্তর্জাতিক মাতৃভাষা দিবস",
     "start": "2026-02-21", "end": "2026-02-21",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "eid_ul_fitr",        "name_en": "Jumatul Bida, Shab-e-Qadr & Eid-ul-Fitr",
     "name_bn": "জুমাতুল বিদা, শব-ই-কদর ও ঈদ-উল-ফিতর",
     "start": "2026-03-15", "end": "2026-03-24",
     "days_class": 10, "days_office": 10, "category": "religious", "moon_dep": True},

    {"id": "independence_day",   "name_en": "Independence & National Day",
     "name_bn": "স্বাধীনতা ও জাতীয় দিবস",
     "start": "2026-03-26", "end": "2026-03-26",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "easter_sunday",      "name_en": "Easter Sunday",
     "name_bn": "ইস্টার সানডে",
     "start": "2026-04-05", "end": "2026-04-05",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": False},

    {"id": "bangla_new_year",    "name_en": "Bangla New Year (Pohela Boishakh)",
     "name_bn": "বাংলা নববর্ষ",
     "start": "2026-04-14", "end": "2026-04-14",
     "days_class": 1, "days_office": 1, "category": "cultural", "moon_dep": False},

    {"id": "may_day_buddha",     "name_en": "May Day & Buddha Purnima",
     "name_bn": "মে দিবস ও বুদ্ধ পূর্ণিমা (বৈশাখী পূর্ণিমা)",
     "start": "2026-05-01", "end": "2026-05-01",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "eid_ul_adha",        "name_en": "Eid-ul-Adha (Qurbani Eid)",
     "name_bn": "ঈদ-উল-আযহা (কুরবানির ঈদ)",
     "start": "2026-05-24", "end": "2026-06-08",
     "days_class": 12, "days_office": 12, "category": "religious", "moon_dep": True},

    {"id": "ashura",             "name_en": "Ashura",
     "name_bn": "আশুরা",
     "start": "2026-06-26", "end": "2026-06-26",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": True},

    {"id": "summer_vacation",    "name_en": "Summer Vacation",
     "name_bn": "গ্রীষ্মকালীন অবকাশ",
     "start": "2026-07-12", "end": "2026-07-16",
     "days_class": 5, "days_office": 5, "category": "academic", "moon_dep": False},

    {"id": "university_day",     "name_en": "University Day (26 July)",
     "name_bn": "বিশ্ববিদ্যালয় দিবস",
     "start": "2026-07-26", "end": "2026-07-26",
     "days_class": 0, "days_office": 0, "category": "academic", "moon_dep": False},

    {"id": "july_uprising",      "name_en": "July Mass Uprising Day",
     "name_bn": "জুলাই গণঅভ্যুত্থান দিবস",
     "start": "2026-08-05", "end": "2026-08-05",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "akhari_chahar",      "name_en": "Akheri Chahar Shamba",
     "name_bn": "আখেরি চাহার শম্বা",
     "start": "2026-08-12", "end": "2026-08-12",
     "days_class": 1, "days_office": 0, "category": "religious", "moon_dep": True},

    {"id": "eid_milad",          "name_en": "Eid-e-Miladunnabi (S.A.W.)",
     "name_bn": "ঈদ-ই-মিলাদুন্নবী (সা.)",
     "start": "2026-08-26", "end": "2026-08-26",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": True},

    {"id": "janmashtami",        "name_en": "Janmashtami",
     "name_bn": "জন্মাষ্টমী",
     "start": "2026-09-04", "end": "2026-09-04",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": False},

    {"id": "fateha_e_yazdaham",  "name_en": "Fateha-e-Yazdaham",
     "name_bn": "ফাতেহা-ই-ইয়াজদহম",
     "start": "2026-09-24", "end": "2026-09-24",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": True},

    {"id": "durga_puja",         "name_en": "Shri Shri Durga Puja",
     "name_bn": "শ্রী শ্রী দুর্গাপূজা",
     "start": "2026-10-18", "end": "2026-10-22",
     "days_class": 5, "days_office": 5, "category": "religious", "moon_dep": False},

    {"id": "probarana_lakshmi",  "name_en": "Probarana Purnima & Shri Shri Lakshmi Puja",
     "name_bn": "প্রবারণা পূর্ণিমা ও শ্রী শ্রী লক্ষ্মী পূজা",
     "start": "2026-10-25", "end": "2026-10-25",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": False},

    {"id": "shyama_puja",        "name_en": "Shri Shri Shyama Puja",
     "name_bn": "শ্রী শ্রী শ্যামাপূজা",
     "start": "2026-11-08", "end": "2026-11-08",
     "days_class": 1, "days_office": 0, "category": "religious", "moon_dep": False},

    {"id": "shaheed_buddhijibi", "name_en": "Shaheed Buddhijibi Dibas",
     "name_bn": "শহিদ বুদ্ধিজীবী দিবস",
     "start": "2026-12-14", "end": "2026-12-14",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "victory_day",        "name_en": "Victory Day",
     "name_bn": "বিজয় দিবস",
     "start": "2026-12-16", "end": "2026-12-16",
     "days_class": 1, "days_office": 1, "category": "national", "moon_dep": False},

    {"id": "christmas",          "name_en": "Christmas Day",
     "name_bn": "যীশু খ্রিস্টের জন্মদিন (বড়দিন)",
     "start": "2026-12-25", "end": "2026-12-25",
     "days_class": 1, "days_office": 1, "category": "religious", "moon_dep": False},

    {"id": "winter_vacation",    "name_en": "Winter Vacation",
     "name_bn": "শীতকালীন অবকাশ",
     "start": "2026-12-27", "end": "2026-12-31",
     "days_class": 5, "days_office": 5, "category": "academic", "moon_dep": False},
]


# ── Internal helpers ──────────────────────────────────────────

def _total_days(h: dict) -> int:
    s = date.fromisoformat(h["start"])
    e = date.fromisoformat(h["end"])
    return (e - s).days + 1


def _threshold(total: int) -> int:
    if total > 12: return 4
    if total > 7:  return 3
    if total > 3:  return 2
    return 1


# ── Public API ────────────────────────────────────────────────

def is_holiday(check_date: date) -> tuple:
    """
    Returns (True, holiday_name_en) if check_date falls within any
    holiday range. Returns (False, '') otherwise.

    Used by:
      - app/academic/routes.py  — skip class schedule on holidays
      - app/__init__.py cron    — skip daily email on holidays
    """
    for h in HOLIDAYS:
        start = date.fromisoformat(h["start"])
        end   = date.fromisoformat(h["end"])
        if start <= check_date <= end:
            return True, h["name_en"]
    return False, ""


def get_upcoming_holidays(days_ahead: int = 30) -> list:
    """
    Returns holidays whose start date is within the next `days_ahead`
    days (inclusive of today), sorted by start date.

    Used by:
      - app/academic/routes.py  — /api/holiday-check endpoint
    """
    today = date.today()
    result = []
    for h in HOLIDAYS:
        start      = date.fromisoformat(h["start"])
        days_until = (start - today).days
        if 0 <= days_until <= days_ahead:
            result.append({
                "id":         h["id"],
                "name_en":    h["name_en"],
                "name_bn":    h["name_bn"],
                "start":      h["start"],
                "end":        h["end"],
                "category":   h["category"],
                "days_until": days_until,
            })
    result.sort(key=lambda x: x["start"])
    return result


def get_all_enriched() -> list:
    """
    Returns all holidays enriched with status, countdown, days_until,
    days_left, show_countdown, total_days, countdown_threshold.

    Used by:
      - app/holidays/routes.py
    """
    today = date.today()
    result = []
    for h in HOLIDAYS:
        out   = dict(h)
        start = date.fromisoformat(h["start"])
        end   = date.fromisoformat(h["end"])
        total = _total_days(h)
        thr   = _threshold(total)

        out["total_days"]          = total
        out["countdown_threshold"] = thr

        days_until     = (start - today).days
        out["days_until"] = days_until

        if today > end:
            out["status"] = "past"
        elif today >= start:
            out["status"]    = "ongoing"
            out["days_left"] = (end - today).days + 1
        else:
            out["status"]         = "upcoming"
            out["show_countdown"] = 0 <= days_until <= thr

        result.append(out)
    return result