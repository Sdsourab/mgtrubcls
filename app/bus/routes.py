"""
app/bus/routes.py
=================
UniSync Transport — Bus Schedule Blueprint
URL prefix: /bus

Edit BUS_DATA to update the schedule. Zero DB dependency.
Effective: 06 April 2026 | Ref: রবিবা/প্রশা/পরিবহণপুল/২৯২/২০১৯

HOUR FORMAT: 24h internally (6=6AM, 16=4PM, 17=5PM). Display is 12h in template JS.
"""

from flask import Blueprint, jsonify, render_template

bus_bp = Blueprint('bus', __name__)

# ─────────────────────────────────────────────────────────────────────────────
# BUS_DATA — Edit this block to update the schedule
# active_days: 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu  (5=Fri 6=Sat = weekend, no service)
# h = 24-hour integer  (6 = 6:00 AM,  16 = 4:00 PM,  17 = 5:00 PM)
# ─────────────────────────────────────────────────────────────────────────────
BUS_DATA = [
    {
        "id":           "chitra",
        "name":         "Chitra",
        "name_bn":      "চিত্রা",
        "reg":          "Dhaka Metro Sa 11-0504",
        "type":         "Standard",
        "origin_stop":  "dilruba",
        "color_key":    "terra",
        "active_days":  [0, 4],           # Sunday & Thursday only
        "day_label":    "Sun & Thu only",
        "est_duration": 45,               # ride duration in minutes
        "trips": [
            # Week-start (Sunday)
            {"h": 6,  "m": 0,  "from": "Dilruba Bus Stand",   "to": "Chandaikona, Bogura", "session": "morning",   "days": [0]},
            {"h": 7,  "m": 30, "from": "Chandaikona, Bogura", "to": "Dilruba Bus Stand",   "session": "morning",   "days": [0]},
            # Week-end (Thursday)  — 4:15 PM = h:16, 5:45 PM = h:17
            {"h": 16, "m": 15, "from": "Dilruba Bus Stand",   "to": "Chandaikona, Bogura", "session": "afternoon", "days": [4]},
            {"h": 17, "m": 45, "from": "Chandaikona, Bogura", "to": "Dilruba Bus Stand",   "session": "afternoon", "days": [4]},
        ],
    },
    {
        "id":           "khyanika",
        "name":         "Khyanika",
        "name_bn":      "ক্ষণিকা",
        "reg":          "Dhaka Metro Sa 11-0604",
        "type":         "Standard",
        "origin_stop":  "dilruba",
        "color_key":    "golden",
        "active_days":  [0, 1, 2, 3, 4],
        "day_label":    "Sun – Thu (Daily)",
        "est_duration": 30,
        "trips": [
            {"h": 6,  "m": 0,  "from": "Dilruba Bus Stand", "to": "Sirajganj",           "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "Sirajganj",          "to": "Dilruba Bus Stand",  "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "Dilruba Bus Stand", "to": "Sirajganj",           "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "Sirajganj",          "to": "Dilruba Bus Stand",  "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
    {
        "id":           "balaka",
        "name":         "Balaka",
        "name_bn":      "বলাকা",
        "reg":          "Dhaka Metro Sa 11-0505",
        "type":         "Standard",
        "origin_stop":  "bisik",
        "color_key":    "green",
        "active_days":  [0, 1, 2, 3, 4],
        "day_label":    "Sun – Thu (Daily)",
        "est_duration": 35,
        "trips": [
            {"h": 6,  "m": 0,  "from": "BISIK Bus Stand", "to": "Ataikula",           "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "Ataikula",         "to": "BISIK Bus Stand",   "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "BISIK Bus Stand", "to": "Ataikula",           "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "Ataikula",         "to": "BISIK Bus Stand",   "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
    {
        "id":           "ac_coaster",
        "name":         "AC Coaster",
        "name_bn":      "এসি কোস্টার",
        "reg":          "Dhaka Metro Jha 11-1390 / Sirajganj Jha 11-0003",
        "type":         "AC",
        "origin_stop":  "bisik",
        "color_key":    "olive",
        "active_days":  [0, 1, 2, 3, 4],
        "day_label":    "Sun – Thu (Daily)",
        "est_duration": 40,
        "trips": [
            {"h": 6,  "m": 0,  "from": "BISIK Bus Stand",     "to": "Belkuchi, Sirajganj", "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 7,  "m": 30, "from": "Belkuchi, Sirajganj", "to": "BISIK Bus Stand",     "session": "morning",   "days": [0,1,2,3,4]},
            {"h": 16, "m": 15, "from": "BISIK Bus Stand",     "to": "Belkuchi, Sirajganj", "session": "afternoon", "days": [0,1,2,3,4]},
            {"h": 17, "m": 45, "from": "Belkuchi, Sirajganj", "to": "BISIK Bus Stand",     "session": "afternoon", "days": [0,1,2,3,4]},
        ],
    },
]

EFFECTIVE_DATE = "06 April 2026"
MEMO_REF       = "রবিবা/প্রশা/পরিবহণপুল/২৯২/২০১৯"


@bus_bp.route('/')
def bus_page():
    return render_template(
        'modules/bus_schedule.html',
        buses=BUS_DATA,
        effective_date=EFFECTIVE_DATE,
        memo_ref=MEMO_REF,
    )

@bus_bp.route('/api/schedule')
def get_schedule():
    return jsonify({'success': True, 'buses': BUS_DATA,
                    'effective_date': EFFECTIVE_DATE})