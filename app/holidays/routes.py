"""
app/holidays/routes.py
======================
RUB Holiday Plan — 2026 Academic Year
URL prefix: /holidays

Smart countdown rules:
  holiday_days > 12  → notify 4 days before
  holiday_days > 7   → notify 3 days before
  holiday_days > 3   → notify 2 days before
  holiday_days <= 3  → notify 1 day before
"""

from flask import Blueprint, jsonify, render_template
from datetime import date

holidays_bp = Blueprint('holidays', __name__)

# ─────────────────────────────────────────────────────────────────────────────
# HOLIDAY DATA — 2026 Academic Year
# Source: Rabindra University Bangladesh — Academic Calendar 2026
# Fields:
#   id         : unique string key
#   name_en    : English name
#   name_bn    : Bengali name
#   start      : "YYYY-MM-DD"
#   end        : "YYYY-MM-DD" (same as start for single-day)
#   days_class : class holiday count
#   days_office: office holiday count
#   category   : religious | national | academic | cultural
#   moon_dep   : True if moon-sighting dependent (*)
# ─────────────────────────────────────────────────────────────────────────────
HOLIDAYS = [
    {
        "id":          "shab_e_miraj",
        "name_en":     "Shab-e-Miraj",
        "name_bn":     "শব-ই-মিরাজ",
        "start":       "2026-01-17",
        "end":         "2026-01-17",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "saraswati_puja",
        "name_en":     "Shri Shri Saraswati Puja",
        "name_bn":     "শ্রী শ্রী সরস্বতী পূজা",
        "start":       "2026-01-23",
        "end":         "2026-01-23",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "shab_e_barat",
        "name_en":     "Shab-e-Barat",
        "name_bn":     "শব-ই-বরাত",
        "start":       "2026-02-04",
        "end":         "2026-02-04",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "shaheed_dibas",
        "name_en":     "Shaheed Dibas & International Mother Language Day",
        "name_bn":     "শহিদ দিবস ও আন্তর্জাতিক মাতৃভাষা দিবস",
        "start":       "2026-02-21",
        "end":         "2026-02-21",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "eid_ul_fitr",
        "name_en":     "Jumatul Bida, Shab-e-Qadr & Eid-ul-Fitr",
        "name_bn":     "জুমাতুল বিদা, শব-ই-কদর ও ঈদ-উল-ফিতর",
        "start":       "2026-03-15",
        "end":         "2026-03-24",
        "days_class":  10,
        "days_office": 10,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "independence_day",
        "name_en":     "Independence & National Day",
        "name_bn":     "স্বাধীনতা ও জাতীয় দিবস",
        "start":       "2026-03-26",
        "end":         "2026-03-26",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "easter_sunday",
        "name_en":     "Easter Sunday",
        "name_bn":     "ইস্টার সানডে",
        "start":       "2026-04-05",
        "end":         "2026-04-05",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "bangla_new_year",
        "name_en":     "Bangla New Year (Pohela Boishakh)",
        "name_bn":     "বাংলা নববর্ষ",
        "start":       "2026-04-14",
        "end":         "2026-04-14",
        "days_class":  1,
        "days_office": 1,
        "category":    "cultural",
        "moon_dep":    False,
    },
    {
        "id":          "may_day_buddha",
        "name_en":     "May Day & Buddha Purnima",
        "name_bn":     "মে দিবস ও বুদ্ধ পূর্ণিমা (বৈশাখী পূর্ণিমা)",
        "start":       "2026-05-01",
        "end":         "2026-05-01",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "eid_ul_adha",
        "name_en":     "Eid-ul-Adha (Qurbani Eid)",
        "name_bn":     "ঈদ-উল-আযহা (কুরবানির ঈদ)",
        "start":       "2026-05-24",
        "end":         "2026-06-08",
        "days_class":  12,
        "days_office": 12,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "ashura",
        "name_en":     "Ashura",
        "name_bn":     "আশুরা",
        "start":       "2026-06-26",
        "end":         "2026-06-26",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "summer_vacation",
        "name_en":     "Summer Vacation",
        "name_bn":     "গ্রীষ্মকালীন অবকাশ",
        "start":       "2026-07-12",
        "end":         "2026-07-16",
        "days_class":  5,
        "days_office": 5,
        "category":    "academic",
        "moon_dep":    False,
    },
    {
        "id":          "university_day",
        "name_en":     "University Day (26 July)",
        "name_bn":     "বিশ্ববিদ্যালয় দিবস",
        "start":       "2026-07-26",
        "end":         "2026-07-26",
        "days_class":  0,
        "days_office": 0,
        "category":    "academic",
        "moon_dep":    False,
    },
    {
        "id":          "july_uprising",
        "name_en":     "July Mass Uprising Day",
        "name_bn":     "জুলাই গণঅভ্যুত্থান দিবস",
        "start":       "2026-08-05",
        "end":         "2026-08-05",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "akhari_chahar",
        "name_en":     "Akheri Chahar Shamba",
        "name_bn":     "আখেরি চাহার শম্বা",
        "start":       "2026-08-12",
        "end":         "2026-08-12",
        "days_class":  1,
        "days_office": 0,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "eid_milad",
        "name_en":     "Eid-e-Miladunnabi (S.A.W.)",
        "name_bn":     "ঈদ-ই-মিলাদুন্নবী (সা.)",
        "start":       "2026-08-26",
        "end":         "2026-08-26",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "janmashtami",
        "name_en":     "Janmashtami",
        "name_bn":     "জন্মাষ্টমী",
        "start":       "2026-09-04",
        "end":         "2026-09-04",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "fateha_e_yazdaham",
        "name_en":     "Fateha-e-Yazdaham",
        "name_bn":     "ফাতেহা-ই-ইয়াজদহম",
        "start":       "2026-09-24",
        "end":         "2026-09-24",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    True,
    },
    {
        "id":          "durga_puja",
        "name_en":     "Shri Shri Durga Puja",
        "name_bn":     "শ্রী শ্রী দুর্গাপূজা",
        "start":       "2026-10-18",
        "end":         "2026-10-22",
        "days_class":  5,
        "days_office": 5,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "probarana_lakshmi",
        "name_en":     "Probarana Purnima & Shri Shri Lakshmi Puja",
        "name_bn":     "প্রবারণা পূর্ণিমা ও শ্রী শ্রী লক্ষ্মী পূজা",
        "start":       "2026-10-25",
        "end":         "2026-10-25",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "shyama_puja",
        "name_en":     "Shri Shri Shyama Puja",
        "name_bn":     "শ্রী শ্রী শ্যামাপূজা",
        "start":       "2026-11-08",
        "end":         "2026-11-08",
        "days_class":  1,
        "days_office": 0,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "shaheed_buddhijibi",
        "name_en":     "Shaheed Buddhijibi Dibas",
        "name_bn":     "শহিদ বুদ্ধিজীবী দিবস",
        "start":       "2026-12-14",
        "end":         "2026-12-14",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "victory_day",
        "name_en":     "Victory Day",
        "name_bn":     "বিজয় দিবস",
        "start":       "2026-12-16",
        "end":         "2026-12-16",
        "days_class":  1,
        "days_office": 1,
        "category":    "national",
        "moon_dep":    False,
    },
    {
        "id":          "christmas",
        "name_en":     "Christmas Day",
        "name_bn":     "যীশু খ্রিস্টের জন্মদিন (বড়দিন)",
        "start":       "2026-12-25",
        "end":         "2026-12-25",
        "days_class":  1,
        "days_office": 1,
        "category":    "religious",
        "moon_dep":    False,
    },
    {
        "id":          "winter_vacation",
        "name_en":     "Winter Vacation",
        "name_bn":     "শীতকালীন অবকাশ",
        "start":       "2026-12-27",
        "end":         "2026-12-31",
        "days_class":  5,
        "days_office": 5,
        "category":    "academic",
        "moon_dep":    False,
    },
]


def _days_gap(h: dict) -> int:
    """Total calendar days of the holiday (inclusive)."""
    s = date.fromisoformat(h["start"])
    e = date.fromisoformat(h["end"])
    return (e - s).days + 1


def _countdown_threshold(days_total: int) -> int:
    """
    How many days BEFORE the holiday we should start showing the countdown.
      > 12 days holiday → 4 days before
      >  7 days holiday → 3 days before
      >  3 days holiday → 2 days before
      <= 3 days         → 1 day before
    """
    if days_total > 12:
        return 4
    if days_total > 7:
        return 3
    if days_total > 3:
        return 2
    return 1


def _enrich(h: dict) -> dict:
    out = dict(h)
    total = _days_gap(h)
    out["total_days"]           = total
    out["countdown_threshold"]  = _countdown_threshold(total)

    today = date.today()
    start = date.fromisoformat(h["start"])
    end   = date.fromisoformat(h["end"])

    days_until = (start - today).days
    out["days_until"] = days_until

    if today > end:
        out["status"] = "past"
    elif today >= start:
        days_left = (end - today).days + 1
        out["status"]    = "ongoing"
        out["days_left"] = days_left
    else:
        out["status"] = "upcoming"
        # Show countdown if within threshold
        out["show_countdown"] = (0 <= days_until <= _countdown_threshold(total))

    return out


# ── Routes ────────────────────────────────────────────────────

@holidays_bp.route('/')
def holidays_page():
    return render_template('modules/holidays.html')


@holidays_bp.route('/api/holidays')
def api_holidays():
    enriched = [_enrich(h) for h in HOLIDAYS]
    return jsonify({
        'success': True,
        'data':    enriched,
        'total':   len(enriched),
    })


@holidays_bp.route('/api/holidays/upcoming')
def api_upcoming():
    """Return next 5 upcoming + ongoing holidays, enriched."""
    today = date.today()
    enriched = [_enrich(h) for h in HOLIDAYS]
    active = [h for h in enriched if h['status'] in ('upcoming', 'ongoing')]
    active.sort(key=lambda h: h['start'])
    return jsonify({'success': True, 'data': active[:5]})


@holidays_bp.route('/api/holidays/countdown')
def api_countdown():
    """
    Return holidays that are within their countdown window
    (to show banner/countdown card on dashboard & profile).
    """
    today = date.today()
    enriched = [_enrich(h) for h in HOLIDAYS]
    in_window = [
        h for h in enriched
        if h['status'] == 'upcoming'
        and h.get('show_countdown')
    ]
    in_window.sort(key=lambda h: h['start'])
    return jsonify({'success': True, 'data': in_window})