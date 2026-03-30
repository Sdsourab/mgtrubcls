"""
core/excel_parser.py
════════════════════
Routine seed data — effective from 25 March 2026.
Source: Department of Management, Rabindra University, Bangladesh.

IMPORTANT: pandas is NOT imported at module level (lazy import).
"""
import re
from typing import List, Dict

# ── Routine effective date ────────────────────────────────────
ROUTINE_UPDATED_DATE = "25 March 2026"

# ── Course → (program, year, semester) ───────────────────────
# Based on the routine image course list at bottom:
#   BBA 2nd Year 1st Sem  (Session: 2023-24)
#   BBA 3rd Year 1st Sem  (Session: 2022-23)
#   BBA 3rd Year 2nd Sem  (Session: 2021-22)
#   MBA 2nd Sem           (Session: 2023-24)
#   MBA 1st Sem           (Session: 2024-25)

COURSE_META = {
    # BBA 2nd Year, 1st Semester
    'MGT-2101': ('BBA', 2, 1),
    'GED-2102': ('BBA', 2, 1),
    'GED-2103': ('BBA', 2, 1),
    'GED-2104': ('BBA', 2, 1),
    'MGT-2105': ('BBA', 2, 1),
    # BBA 3rd Year, 1st Semester
    'MGT-3101': ('BBA', 3, 1),
    'MGT-3102': ('BBA', 3, 1),
    'MGT-3103': ('BBA', 3, 1),
    'MGT-3104': ('BBA', 3, 1),
    'MGT-3105': ('BBA', 3, 1),
    # BBA 3rd Year, 2nd Semester
    'MGT-3201': ('BBA', 3, 2),
    'MGT-3202': ('BBA', 3, 2),
    'MGT-3203': ('BBA', 3, 2),
    'MGT-3204': ('BBA', 3, 2),
    'MGT-3205': ('BBA', 3, 2),
    'GED-3203': ('BBA', 3, 2),
    # MBA 2nd Semester  (Session: 2023-24) — labeled "MBA 2nd Semester Courses"
    'HRM-5201': ('MBA', 2, 1),
    'HRM-5202': ('MBA', 2, 1),
    'HRM-5203': ('MBA', 2, 1),
    'HRM-5204': ('MBA', 2, 1),
    'HRM-5205': ('MBA', 2, 1),
    # MBA 1st Semester  (Session: 2024-25) — labeled "MBA 1st Semester Courses"
    'HRM-5101': ('MBA', 1, 1),
    'HRM-5102': ('MBA', 1, 1),
    'HRM-5103': ('MBA', 1, 1),
    'HRM-5104': ('MBA', 1, 1),
    'HRM-5105': ('MBA', 1, 1),
}

TIME_SLOTS = [
    {"label": "9:00 AM–10:30 AM",  "start": "09:00", "end": "10:30"},
    {"label": "10:30 AM–12:00 PM", "start": "10:30", "end": "12:00"},
    {"label": "12:00 PM–1:30 PM",  "start": "12:00", "end": "13:30"},
    {"label": "2:00 PM–3:30 PM",   "start": "14:00", "end": "15:30"},
    {"label": "3:30 PM–5:00 PM",   "start": "15:30", "end": "17:00"},
]


def get_seed_routines() -> List[Dict]:
    """
    Routine effective from 25 March 2026.
    Parsed directly from the official routine image.

    Format: (Day, RoomNo, TimeSlot, TimeStart, TimeEnd, CourseCode, TeacherCode)
    Room 1001 = Computer Lab
    """
    raw = [
        # ══════════ SUNDAY ══════════════════════════════════════
        # Room 101
        ("Sunday", "101", "10:30-12:00", "10:30", "12:00", "MGT-3102", "PKP"),
        ("Sunday", "101", "12:00-1:30",  "12:00", "13:30", "GED-2102", "PKP"),
        ("Sunday", "101", "2:00-3:30",   "14:00", "15:30", "GED-2103", "KHR"),
        ("Sunday", "101", "3:30-5:00",   "15:30", "17:00", "GED-3203", "HR"),
        # Room 201
        ("Sunday", "201", "9:00-10:30",  "09:00", "10:30", "MGT-2105", "THT"),
        ("Sunday", "201", "12:00-1:30",  "12:00", "13:30", "MGT-3103", "KHR"),
        ("Sunday", "201", "2:00-3:30",   "14:00", "15:30", "MGT-3201", "AH"),
        ("Sunday", "201", "3:30-5:00",   "15:30", "17:00", "HRM-5205", "AH"),
        # Room 1001 (Computer Lab) — no classes Sunday

        # ══════════ MONDAY ══════════════════════════════════════
        # Room 101
        ("Monday", "101", "9:00-10:30",  "09:00", "10:30", "GED-2102", "PKP"),
        ("Monday", "101", "10:30-12:00", "10:30", "12:00", "HRM-5105", "KHR"),
        ("Monday", "101", "12:00-1:30",  "12:00", "13:30", "HRM-5101", "THT"),
        ("Monday", "101", "2:00-3:30",   "14:00", "15:30", "HRM-5102", "PKP"),
        # Room 201
        ("Monday", "201", "9:00-10:30",  "09:00", "10:30", "HRM-5205", "AH"),
        ("Monday", "201", "10:30-12:00", "10:30", "12:00", "GED-2104", "AH"),
        ("Monday", "201", "12:00-1:30",  "12:00", "13:30", "MGT-2101", "HR"),
        ("Monday", "201", "2:00-3:30",   "14:00", "15:30", "MGT-3204", "MK"),
        # Room 1001 (Computer Lab)
        ("Monday", "1001", "10:30-12:00", "10:30", "12:00", "HRM-5203", "PKP"),
        ("Monday", "1001", "12:00-1:30",  "12:00", "13:30", "HRM-5202", "KHR"),

        # ══════════ TUESDAY ═════════════════════════════════════
        # Room 101
        ("Tuesday", "101", "9:00-10:30",  "09:00", "10:30", "HRM-5103", "MK"),
        ("Tuesday", "101", "10:30-12:00", "10:30", "12:00", "HRM-5102", "PKP"),
        ("Tuesday", "101", "12:00-1:30",  "12:00", "13:30", "MGT-2105", "THT"),
        ("Tuesday", "101", "2:00-3:30",   "14:00", "15:30", "MGT-3102", "PKP"),
        ("Tuesday", "101", "3:30-5:00",   "15:30", "17:00", "MGT-3105", "AH"),
        # Room 201
        ("Tuesday", "201", "9:00-10:30",  "09:00", "10:30", "MGT-3205", "FA"),
        ("Tuesday", "201", "10:30-12:00", "10:30", "12:00", "MGT-3104", "HR"),
        ("Tuesday", "201", "12:00-1:30",  "12:00", "13:30", "MGT-3202", "KHR"),
        ("Tuesday", "201", "2:00-3:30",   "14:00", "15:30", "GED-2104", "AH"),
        ("Tuesday", "201", "3:30-5:00",   "15:30", "17:00", "MGT-2101", "HR"),
        # Room 1001 (Computer Lab)
        ("Tuesday", "1001", "9:00-10:30",  "09:00", "10:30", "HRM-5203", "PKP"),
        ("Tuesday", "1001", "10:30-12:00", "10:30", "12:00", "HRM-5202", "KHR"),
        ("Tuesday", "1001", "12:00-1:30",  "12:00", "13:30", "HRM-5204", "HR"),

        # ══════════ WEDNESDAY ═══════════════════════════════════
        # Room 101
        ("Wednesday", "101", "10:30-12:00", "10:30", "12:00", "MGT-3204", "HR"),
        ("Wednesday", "101", "12:00-1:30",  "12:00", "13:30", "GED-3203", "HR"),
        ("Wednesday", "101", "2:00-3:30",   "14:00", "15:30", "MGT-3104", "HR"),
        ("Wednesday", "101", "3:30-5:00",   "15:30", "17:00", "MGT-3101", "THT"),
        # Room 201
        ("Wednesday", "201", "9:00-10:30",  "09:00", "10:30", "MGT-3205", "FA"),
        ("Wednesday", "201", "10:30-12:00", "10:30", "12:00", "MGT-3204", "MK"),
        ("Wednesday", "201", "12:00-1:30",  "12:00", "13:30", "HRM-5201", "MK"),
        ("Wednesday", "201", "2:00-3:30",   "14:00", "15:30", "HRM-5201", "MK"),
        # Room 1001 (Computer Lab)
        ("Wednesday", "1001", "9:00-10:30",  "09:00", "10:30", "HRM-5104", "AH"),
        ("Wednesday", "1001", "10:30-12:00", "10:30", "12:00", "HRM-5105", "KHR"),
        ("Wednesday", "1001", "12:00-1:30",  "12:00", "13:30", "HRM-5101", "THT"),

        # ══════════ THURSDAY ════════════════════════════════════
        # Room 101
        ("Thursday", "101", "10:30-12:00", "10:30", "12:00", "MGT-3202", "KHR"),
        ("Thursday", "101", "12:00-1:30",  "12:00", "13:30", "MGT-3103", "KHR"),
        ("Thursday", "101", "2:00-3:30",   "14:00", "15:30", "MGT-3105", "AH"),
        ("Thursday", "101", "3:30-5:00",   "15:30", "17:00", "MGT-3101", "THT"),
        # Room 201
        ("Thursday", "201", "9:00-10:30",  "09:00", "10:30", "MGT-3205", "FA"),
        ("Thursday", "201", "12:00-1:30",  "12:00", "13:30", "MGT-3201", "AH"),
        ("Thursday", "201", "2:00-3:30",   "14:00", "15:30", "GED-2103", "KHR"),
        # Room 1001 (Computer Lab)
        ("Thursday", "1001", "9:00-10:30",  "09:00", "10:30", "HRM-5103", "MK"),
        ("Thursday", "1001", "10:30-12:00", "10:30", "12:00", "HRM-5104", "AH"),
    ]

    result = []
    for r in raw:
        cc   = r[5]
        meta = COURSE_META.get(cc, ('ALL', 0, 0))
        result.append({
            "day":             r[0],
            "room_no":         r[1],
            "time_slot":       r[2],
            "time_start":      r[3],
            "time_end":        r[4],
            "course_code":     cc,
            "teacher_code":    r[6],
            "program":         meta[0],
            "course_year":     meta[1],
            "course_semester": meta[2],
            "session":         "2025-26",
        })
    return result


def get_seed_mappings() -> List[Dict]:
    teachers = [
        ("FA",  "Professor Dr. Feroz Ahmed",       "teacher"),
        ("HR",  "Habibur Rahaman",                 "teacher"),
        ("MK",  "Malina Khatun",                   "teacher"),
        ("PKP", "Prashanta Kumar Podder",           "teacher"),
        ("TI",  "Md. Tarequl Islam",               "teacher"),
        ("AH",  "Alamgir Hossain",                 "teacher"),
        ("KHR", "Md. Kazi Hafizur Rahman",         "teacher"),
        ("THT", "Tamima Hasan Taishi",             "teacher"),
    ]
    courses = [
        # BBA 2nd Year 1st Sem
        ("MGT-2101", "Organization Behavior",                   "course"),
        ("GED-2102", "Statistics-I",                            "course"),
        ("GED-2103", "Commercial Law",                          "course"),
        ("GED-2104", "Macro Economics",                         "course"),
        ("MGT-2105", "Financial Management",                    "course"),
        # BBA 3rd Year 1st Sem
        ("MGT-3101", "Bank Management",                         "course"),
        ("MGT-3102", "Industrial Law",                          "course"),
        ("MGT-3103", "Insurance and Risk Management",           "course"),
        ("MGT-3104", "Taxation & Auditing",                     "course"),
        ("MGT-3105", "Innovation & Change Management",          "course"),
        # BBA 3rd Year 2nd Sem
        ("MGT-3201", "Industrial Relations",                    "course"),
        ("MGT-3202", "Management Information System",           "course"),
        ("MGT-3203", "Management Science",                      "course"),
        ("MGT-3204", "Business Ethics and CSR",                 "course"),
        ("MGT-3205", "Entrepreneurship and SME Management",     "course"),
        ("GED-3203", "Business Ethics and CSR",                 "course"),
        # MBA 1st Sem
        ("HRM-5101", "Human Resource Planning and Policy",      "course"),
        ("HRM-5102", "Training and Development",                "course"),
        ("HRM-5103", "Compensation Management",                 "course"),
        ("HRM-5104", "Conflict Management",                     "course"),
        ("HRM-5105", "Strategic Human Resource Management",     "course"),
        # MBA 2nd Sem
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