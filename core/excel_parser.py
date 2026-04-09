"""
core/excel_parser.py
════════════════════
Routine seed data — effective from 06 April 2026.
Source: Department of Management, Rabindra University, Bangladesh.

IMPORTANT: pandas is NOT imported at module level (lazy import).
"""
import re
from typing import List, Dict

# ── Routine effective date ────────────────────────────────────
ROUTINE_UPDATED_DATE = "06 April 2026"

# ── Course → (program, year, semester) ───────────────────────
# Based on the routine image course list at bottom:
#   BBA 1st Year 1st Sem  (Session: 2023-24)
#   BBA 1st Year 2nd Sem  (Session: 2022-23)
#   BBA 3rd Year 1st Sem  (Session: 2021-22)
#   MBA 2nd Semester      (Session: 2023-24)
#   MBA 1st Semester      (Session: 2024-25)

COURSE_META = {
    # BBA 2nd Year, 1st Semester (Session: 2023-24)
    'MGT-2101': ('BBA', 2, 1),
    'GED-2102': ('BBA', 2, 1),
    'GED-2103': ('BBA', 2, 1),
    'GED-2104': ('BBA', 2, 1),
    'MGT-2105': ('BBA', 2, 1),
    # BBA 3rd Year, 1st Semester (Session: 2022-23)
    'MGT-3101': ('BBA', 3, 1),
    'MGT-3102': ('BBA', 3, 1),
    'MGT-3103': ('BBA', 3, 1),
    'MGT-3104': ('BBA', 3, 1),
    'MGT-3105': ('BBA', 3, 1),
    # BBA 3rd Year, 2nd Semester (Session: 2021-22)
    'MGT-3201': ('BBA', 3, 2),
    'MGT-3202': ('BBA', 3, 2),
    'MGT-3203': ('BBA', 3, 2),
    'MGT-3204': ('BBA', 3, 2),
    'MGT-3205': ('BBA', 3, 2),
    'GED-3203': ('BBA', 3, 2),
    # MBA 2nd Semester (Session: 2023-24)
    'HRM-5201': ('MBA', 2, 1),
    'HRM-5202': ('MBA', 2, 1),
    'HRM-5203': ('MBA', 2, 1),
    'HRM-5204': ('MBA', 2, 1),
    'HRM-5205': ('MBA', 2, 1),
    # MBA 1st Semester (Session: 2024-25)
    'HRM-5101': ('MBA', 1, 1),
    'HRM-5102': ('MBA', 1, 1),
    'HRM-5103': ('MBA', 1, 1),
    'HRM-5104': ('MBA', 1, 1),
    'HRM-5105': ('MBA', 1, 1),
}

# ── New time slots effective 06 April 2026 ────────────────────
# Old: 9:00-10:30 | 10:30-12:00 | 12:00-1:30 | 2:00-3:30 | 3:30-5:00
# New: 9:00-10:10 | 10:15-11:25 | 11:30-12:40 | (Prayer & Lunch 12:40-1:35) | 1:35-2:45 | 2:50-4:00
TIME_SLOTS = [
    {"label": "9:00 AM–10:10 AM",  "start": "09:00", "end": "10:10"},
    {"label": "10:15 AM–11:25 AM", "start": "10:15", "end": "11:25"},
    {"label": "11:30 AM–12:40 PM", "start": "11:30", "end": "12:40"},
    {"label": "1:35 PM–2:45 PM",   "start": "13:35", "end": "14:45"},
    {"label": "2:50 PM–4:00 PM",   "start": "14:50", "end": "16:00"},
]


def get_seed_routines() -> List[Dict]:
    """
    Routine effective from 06 April 2026.
    Parsed directly from the official routine image.

    New Time Slots:
      9:00–10:10  | 10:15–11:25 | 11:30–12:40
      (Prayer & Lunch: 12:40–1:35)
      1:35–2:45   | 2:50–4:00

    Format: (Day, RoomNo, TimeSlot, TimeStart, TimeEnd, CourseCode, TeacherCode)
    Room 1001 = Computer Lab
    """
    raw = [
        # ══════════ SUNDAY ══════════════════════════════════════
        # Room 101
        ("Sunday", "101", "10:15-11:25", "10:15", "11:25", "PKP",  "MGT-3102"),
        ("Sunday", "101", "11:30-12:40", "11:30", "12:40", "PKP",  "GED-2102"),
        ("Sunday", "101", "13:35-14:45", "13:35", "14:45", "KHR",  "GED-2103"),
        ("Sunday", "101", "14:50-16:00", "14:50", "16:00", "HR",   "GED-3203"),
        # Room 201
        ("Sunday", "201", "10:15-11:25", "10:15", "11:25", "KHR",  "MGT-2105"),
        ("Sunday", "201", "11:30-12:40", "11:30", "12:40", "KHR",  "MGT-3103"),
        ("Sunday", "201", "13:35-14:45", "13:35", "14:45", "AH",   "MGT-3201"),
        ("Sunday", "201", "14:50-16:00", "14:50", "16:00", "AH",   "HRM-5205"),

        # ══════════ MONDAY ══════════════════════════════════════
        # Room 101
        ("Monday", "101", "09:00-10:10", "09:00", "10:10", "PKP",  "GED-2102"),
        ("Monday", "101", "10:15-11:25", "10:15", "11:25", "KHR",  "HRM-5105"),
        ("Monday", "101", "11:30-12:40", "11:30", "12:40", "THT",  "HRM-5101"),
        ("Monday", "101", "13:35-14:45", "13:35", "14:45", "PKP",  "HRM-5102"),
        # Room 201
        ("Monday", "201", "09:00-10:10", "09:00", "10:10", "AH",   "HRM-5205"),
        ("Monday", "201", "10:15-11:25", "10:15", "11:25", "AH",   "GED-2104"),
        ("Monday", "201", "11:30-12:40", "11:30", "12:40", "HR",   "MGT-2101"),
        ("Monday", "201", "13:35-14:45", "13:35", "14:45", "MK",   "MGT-3204"),
        # Room 1001 (Computer Lab)
        ("Monday", "1001", "09:00-10:10", "09:00", "10:10", "PKP", "HRM-5203"),
        ("Monday", "1001", "10:15-11:25", "10:15", "11:25", "KHR", "HRM-5202"),

        # ══════════ TUESDAY ═════════════════════════════════════
        # Room 101
        ("Tuesday", "101", "09:00-10:10", "09:00", "10:10", "MK",  "HRM-5103"),
        ("Tuesday", "101", "10:15-11:25", "10:15", "11:25", "PKP", "HRM-5102"),
        ("Tuesday", "101", "11:30-12:40", "11:30", "12:40", "THT", "MGT-2105"),
        ("Tuesday", "101", "13:35-14:45", "13:35", "14:45", "PKP", "MGT-3102"),
        ("Tuesday", "101", "14:50-16:00", "14:50", "16:00", "AH",  "MGT-3105"),
        # Room 201
        ("Tuesday", "201", "09:00-10:10", "09:00", "10:10", "FA",  "MGT-3205"),
        ("Tuesday", "201", "10:15-11:25", "10:15", "11:25", "HR",  "MGT-3104"),
        ("Tuesday", "201", "11:30-12:40", "11:30", "12:40", "KHR", "MGT-3202"),
        ("Tuesday", "201", "13:35-14:45", "13:35", "14:45", "AH",  "GED-2104"),
        ("Tuesday", "201", "14:50-16:00", "14:50", "16:00", "HR",  "MGT-2101"),
        # Room 1001 (Computer Lab)
        ("Tuesday", "1001", "09:00-10:10", "09:00", "10:10", "PKP", "HRM-5203"),
        ("Tuesday", "1001", "10:15-11:25", "10:15", "11:25", "KHR", "HRM-5202"),
        ("Tuesday", "1001", "11:30-12:40", "11:30", "12:40", "HR",  "HRM-5204"),

        # ══════════ WEDNESDAY ═══════════════════════════════════
        # Room 101
        ("Wednesday", "101", "10:15-11:25", "10:15", "11:25", "HR",  "HRM-5204"),
        ("Wednesday", "101", "11:30-12:40", "11:30", "12:40", "HR",  "GED-3203"),
        ("Wednesday", "101", "13:35-14:45", "13:35", "14:45", "HR",  "MGT-3104"),
        ("Wednesday", "101", "14:50-16:00", "14:50", "16:00", "THT", "MGT-3101"),
        # Room 201
        ("Wednesday", "201", "09:00-10:10", "09:00", "10:10", "FA",  "MGT-3205"),
        ("Wednesday", "201", "10:15-11:25", "10:15", "11:25", "MK",  "MGT-3204"),
        ("Wednesday", "201", "11:30-12:40", "11:30", "12:40", "MK",  "HRM-5201"),
        # Room 1001 (Computer Lab)
        ("Wednesday", "1001", "09:00-10:10", "09:00", "10:10", "AH",  "HRM-5104"),
        ("Wednesday", "1001", "10:15-11:25", "10:15", "11:25", "KHR", "HRM-5105"),
        ("Wednesday", "1001", "11:30-12:40", "11:30", "12:40", "THT", "HRM-5101"),
        ("Wednesday", "1001", "13:35-14:45", "13:35", "14:45", "MK",  "HRM-5201"),

        # ══════════ THURSDAY ════════════════════════════════════
        # Room 101
        ("Thursday", "101", "10:15-11:25", "10:15", "11:25", "KHR", "MGT-3202"),
        ("Thursday", "101", "11:30-12:40", "11:30", "12:40", "KHR", "MGT-3103"),
        ("Thursday", "101", "13:35-14:45", "13:35", "14:45", "AH",  "MGT-3105"),
        ("Thursday", "101", "14:50-16:00", "14:50", "16:00", "THT", "MGT-3101"),
        # Room 201
        ("Thursday", "201", "09:00-10:10", "09:00", "10:10", "FA",  "MGT-3205"),
        ("Thursday", "201", "11:30-12:40", "11:30", "12:40", "AH",  "MGT-3201"),
        ("Thursday", "201", "13:35-14:45", "13:35", "14:45", "KHR", "GED-2103"),
        # Room 1001 (Computer Lab)
        ("Thursday", "1001", "09:00-10:10", "09:00", "10:10", "MK",  "HRM-5103"),
        ("Thursday", "1001", "10:15-11:25", "10:15", "11:25", "AH",  "HRM-5104"),
    ]

    result = []
    for r in raw:
        # Note: raw tuple order is (Day, Room, TimeSlot, TimeStart, TimeEnd, TeacherCode, CourseCode)
        teacher_code = r[5]
        cc = r[6]
        meta = COURSE_META.get(cc, ('ALL', 0, 0))
        result.append({
            "day":             r[0],
            "room_no":         r[1],
            "time_slot":       r[2],
            "time_start":      r[3],
            "time_end":        r[4],
            "course_code":     cc,
            "teacher_code":    teacher_code,
            "program":         meta[0],
            "course_year":     meta[1],
            "course_semester": meta[2],
            "session":         "2025-26",
        })
    return result


def get_seed_mappings() -> List[Dict]:
    teachers = [
        ("FA",  "Prof. Dr. Feroz Ahmed",       "teacher"),
        ("HR",  "Habibur Rahaman",              "teacher"),
        ("MK",  "Malina Khatun",               "teacher"),
        ("PKP", "Proshanta Kumar Podder",       "teacher"),
        ("TI",  "Md. Tarequl Islam",           "teacher"),
        ("AH",  "Alamgir Hossain",             "teacher"),
        ("KHR", "Md. Kazi Hafizur Rahman",     "teacher"),
        ("THT", "Tamima Hasan Taishi",         "teacher"),
    ]
    courses = [
        # BBA 2nd Year 1st Sem (Session: 2023-24)
        ("MGT-2101", "Organization Behavior",                   "course"),
        ("GED-2102", "Statistics-I",                            "course"),
        ("GED-2103", "Commercial Law",                          "course"),
        ("GED-2104", "Macro Economics",                         "course"),
        ("MGT-2105", "Financial Management",                    "course"),
        # BBA 3rd Year 1st Sem (Session: 2022-23)
        ("MGT-3101", "Bank Management",                         "course"),
        ("MGT-3102", "Industrial Law",                          "course"),
        ("MGT-3103", "Insurance and Risk Management",           "course"),
        ("MGT-3104", "Taxation & Auditing",                     "course"),
        ("MGT-3105", "Innovation & Change Management",          "course"),
        # BBA 3rd Year 2nd Sem (Session: 2021-22)
        ("MGT-3201", "Industrial Relations",                    "course"),
        ("MGT-3202", "Management Information System",           "course"),
        ("MGT-3203", "Management Science",                      "course"),
        ("MGT-3204", "Management Science",                      "course"),
        ("MGT-3205", "Entrepreneurship and SME Management",     "course"),
        ("GED-3203", "Business Ethics and CSR",                 "course"),
        # MBA 1st Sem (Session: 2024-25)
        ("HRM-5101", "Human Resource Planning and Policy",      "course"),
        ("HRM-5102", "Training and Development",                "course"),
        ("HRM-5103", "Compensation Management",                 "course"),
        ("HRM-5104", "Conflict Management",                     "course"),
        ("HRM-5105", "Strategic Human Resource Management",     "course"),
        # MBA 2nd Sem (Session: 2023-24)
        ("HRM-5201", "International Human Resource Management", "course"),
        ("HRM-5202", "Human Resource Information System",       "course"),
        ("HRM-5203", "Career Planning and Development",         "course"),
        ("HRM-5204", "Performance Management",                  "course"),
        ("HRM-5205", "Contemporary Issues in HRM",              "course"),
    ]
    return [{"code": t[0], "full_name": t[1], "type": t[2]}
            for t in teachers + courses]


def parse_routine_excel(file_path: str) -> List[Dict]:
    """Admin uploaded Excel file parser (lazy pandas import)."""
    import pandas as pd

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}")

    required = {'day', 'room_no', 'time_start', 'time_end', 'course_code', 'teacher_code'}
    cols = {c.strip().lower() for c in df.columns}
    if not required.issubset(cols):
        raise ValueError(f"Missing columns: {required - cols}")

    df.columns = [c.strip().lower() for c in df.columns]
    entries = []
    for _, row in df.iterrows():
        try:
            cc   = str(row.get('course_code', '')).strip().upper()
            meta = COURSE_META.get(cc, ('ALL', 0, 0))
            ts   = str(row.get('time_start', '')).strip()
            te   = str(row.get('time_end',   '')).strip()

            def norm(t):
                p = t.split(':')
                return f"{p[0].zfill(2)}:{p[1].zfill(2)}" if len(p) == 2 else t

            entry = {
                "day":             str(row.get('day', '')).strip(),
                "room_no":         str(row.get('room_no', '')).strip(),
                "time_slot":       f"{ts}-{te}",
                "time_start":      norm(ts),
                "time_end":        norm(te),
                "course_code":     cc,
                "teacher_code":    str(row.get('teacher_code', '')).strip().upper(),
                "program":         meta[0],
                "course_year":     meta[1],
                "course_semester": meta[2],
                "session":         str(row.get('session', '2025-26')).strip(),
            }
            if entry["day"] and entry["course_code"]:
                entries.append(entry)
        except Exception:
            continue
    return entries