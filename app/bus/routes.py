"""
app/bus/routes.py
═════════════════
UniSync Transport Module — Bus Schedule
URL prefix: /bus

Routes:
  GET /bus/                → bus schedule page
  GET /bus/api/schedule    → JSON schedule data (for future admin editing)

Bus data is hardcoded here for zero-DB-dependency.
To update schedules, edit BUS_DATA below and redeploy.

Effective: ০৬ এপ্রিল ২০২৬ (স্মারক: রবিবা/প্রশা/পরিবহণপুল/২৯২/২০১৯)
"""

from flask import Blueprint, jsonify, render_template

bus_bp = Blueprint('bus', __name__)

# ══════════════════════════════════════════════════════════════
# BUS DATA — Edit this to update schedules
# activeDays: 0=রবিবার, 1=সোমবার, 2=মঙ্গলবার, 3=বুধবার, 4=বৃহস্পতিবার
# Weekend (শুক্র=5, শনি=6) never runs.
# ══════════════════════════════════════════════════════════════

BUS_DATA = [
    {
        "id":          "chitra",
        "name":        "চিত্রা",
        "reg":         "ঢাকা মেট্রো স ১১ ০৫০৪",
        "origin":      "dilruba",
        "color_key":   "terra",
        # সপ্তাহের ১ম দিন = রবিবার (0), শেষ দিন = বৃহস্পতিবার (4)
        "activeDays":  [0, 4],
        "day_label":   "রবি ও বৃহঃ",
        "trips": [
            # সপ্তাহের ১ম দিন (রবিবার)
            {"h": 6,  "m": 0,  "from": "দিলরুবা বাসস্ট্যান্ড",  "to": "চান্দাইকোনা, বগুড়া",   "session": "morning",   "days": [0]},
            {"h": 7,  "m": 30, "from": "চান্দাইকোনা, বগুড়া",    "to": "দিলরুবা বাসস্ট্যান্ড", "session": "morning",   "days": [0]},
            # সপ্তাহের শেষের দিন (বৃহস্পতিবার)
            {"h": 16, "m": 15, "from": "দিলরুবা বাসস্ট্যান্ড",  "to": "চান্দাইকোনা, বগুড়া",   "session": "afternoon", "days": [4]},
            {"h": 17, "m": 45, "from": "চান্দাইকোনা, বগুড়া",    "to": "দিলরুবা বাসস্ট্যান্ড", "session": "afternoon", "days": [4]},
        ],
    },
    {
        "id":          "khyanika",
        "name":        "ক্ষণিকা",
        "reg":         "ঢাকা মেট্রো স ১১ ০৬০৪",
        "origin":      "dilruba",
        "color_key":   "golden",
        "activeDays":  [0, 1, 2, 3, 4],
        "day_label":   "রবি–বৃহঃ (প্রতিদিন)",
        "trips": [
            {"h": 6,  "m": 0,  "from": "দিলরুবা বাসস্ট্যান্ড",  "to": "সিরাজগঞ্জ",            "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "সিরাজগঞ্জ",              "to": "দিলরুবা বাসস্ট্যান্ড", "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "দিলরুবা বাসস্ট্যান্ড",  "to": "সিরাজগঞ্জ",            "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "সিরাজগঞ্জ",              "to": "দিলরুবা বাসস্ট্যান্ড", "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
    {
        "id":          "balaka",
        "name":        "বলাকা",
        "reg":         "ঢাকা মেট্রো স ১১ ০৫০৫",
        "origin":      "bisik",
        "color_key":   "green",
        "activeDays":  [0, 1, 2, 3, 4],
        "day_label":   "রবি–বৃহঃ (প্রতিদিন)",
        "trips": [
            {"h": 6,  "m": 0,  "from": "বিসিক বাসস্ট্যান্ড",    "to": "আতাইকুলা",              "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "আতাইকুলা",               "to": "বিসিক বাসস্ট্যান্ড",   "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "বিসিক বাসস্ট্যান্ড",    "to": "আতাইকুলা",              "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "আতাইকুলা",               "to": "বিসিক বাসস্ট্যান্ড",   "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
    {
        "id":          "ac_coaster",
        "name":        "এসি কোস্টার",
        "reg":         "ঢাকা মেট্রো ঝ ১১ ১৩৯০ / সিরাজগঞ্জ ঝ ১১ ০০০৩",
        "origin":      "bisik",
        "color_key":   "olive",
        "activeDays":  [0, 1, 2, 3, 4],
        "day_label":   "রবি–বৃহঃ (প্রতিদিন)",
        "trips": [
            {"h": 6,  "m": 0,  "from": "বিসিক বাসস্ট্যান্ড",    "to": "বেলকুচি, সিরাজগঞ্জ",   "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "বেলকুচি, সিরাজগঞ্জ",    "to": "বিসিক বাসস্ট্যান্ড",   "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "বিসিক বাসস্ট্যান্ড",    "to": "বেলকুচি, সিরাজগঞ্জ",   "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "বেলকুচি, সিরাজগঞ্জ",    "to": "বিসিক বাসস্ট্যান্ড",   "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
]

EFFECTIVE_DATE = "০৬ এপ্রিল ২০২৬"
MEMO_REF       = "রবিবা/প্রশা/পরিবহণপুল/২৯২/২০১৯"


# ── Routes ────────────────────────────────────────────────────

@bus_bp.route('/')
def bus_page():
    return render_template('modules/bus_schedule.html',
                           buses=BUS_DATA,
                           effective_date=EFFECTIVE_DATE,
                           memo_ref=MEMO_REF)


@bus_bp.route('/api/schedule', methods=['GET'])
def get_schedule():
    """Return schedule as JSON — useful for future admin editing."""
    return jsonify({
        'success':        True,
        'effective_date': EFFECTIVE_DATE,
        'memo_ref':       MEMO_REF,
        'buses':          BUS_DATA,
    })