import pandas as pd
import re
from typing import List, Dict, Optional

TIME_SLOTS = [
    {"label": "9:00-10:30",  "start": "09:00", "end": "10:30"},
    {"label": "10:30-12:00", "start": "10:30", "end": "12:00"},
    {"label": "12:00-1:30",  "start": "12:00", "end": "13:30"},
    {"label": "2:00-3:30",   "start": "14:00", "end": "15:30"},
    {"label": "3:30-5:00",   "start": "15:30", "end": "17:00"},
]

def parse_cell(cell_value: str) -> Optional[Dict]:
    """
    Parse a routine cell like 'KHR (MGT-3103)' into
    {'teacher_code': 'KHR', 'course_code': 'MGT-3103'}.
    Returns None if cell is empty.
    """
    if not cell_value or str(cell_value).strip() in ['', 'nan', 'NaN']:
        return None
    cell_str = str(cell_value).strip()
    match = re.match(r'^([A-Z]+)\s*\(([A-Z]+-\d+)\)$', cell_str)
    if match:
        return {
            'teacher_code': match.group(1),
            'course_code': match.group(2)
        }
    return None

def parse_routine_excel(filepath: str) -> List[Dict]:
    """
    Parse a routine Excel file and return a list of routine rows
    ready to be inserted into the Supabase 'routines' table.
    Expected columns: Day, Room No, slot1, slot2, slot3, slot4(lunch), slot5, slot6
    """
    df = pd.read_excel(filepath, header=0)
    entries = []

    current_day = None
    for _, row in df.iterrows():
        day_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        if day_val and day_val.lower() not in ['nan', '']:
            current_day = day_val

        room = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        if not room or room.lower() == 'nan':
            continue

        # Columns 2-4: slots 1-3, column 5: lunch (skip), columns 6-7: slots 4-5
        slot_indices = [2, 3, 4, 6, 7]  # skip index 5 (lunch)
        for i, slot_idx in enumerate(slot_indices):
            try:
                cell = row.iloc[slot_idx]
            except IndexError:
                continue
            parsed = parse_cell(str(cell) if pd.notna(cell) else '')
            if parsed:
                entries.append({
                    'day': current_day,
                    'room_no': room,
                    'time_slot': TIME_SLOTS[i]['label'],
                    'time_start': TIME_SLOTS[i]['start'],
                    'time_end': TIME_SLOTS[i]['end'],
                    'course_code': parsed['course_code'],
                    'teacher_code': parsed['teacher_code'],
                    'session': ''
                })

    return entries

def get_seed_routines() -> List[Dict]:
    """Returns the hardcoded routine data from the class schedule image."""
    raw = [
        # Sunday
        ("Sunday", "101", "9:00-10:30",  "09:00","10:30", "MGT-3103","KHR"),
        ("Sunday", "101", "10:30-12:00", "10:30","12:00", "MGT-3102","PKP"),
        ("Sunday", "101", "12:00-1:30",  "12:00","13:30", "GED-2102","PKP"),
        ("Sunday", "101", "2:00-3:30",   "14:00","15:30", "GED-2103","KHR"),
        ("Sunday", "101", "3:30-5:00",   "15:30","17:00", "GED-5203","HR"),
        ("Sunday", "201", "9:00-10:30",  "09:00","10:30", "MGT-2105","THT"),
        ("Sunday", "201", "2:00-3:30",   "14:00","15:30", "MGT-3201","AH"),
        ("Sunday", "201", "3:30-5:00",   "15:30","17:00", "HRM-5205","AH"),
        # Monday
        ("Monday", "101", "9:00-10:30",  "09:00","10:30", "GED-2102","PKP"),
        ("Monday", "101", "10:30-12:00", "10:30","12:00", "HRM-5105","KHR"),
        ("Monday", "101", "12:00-1:30",  "12:00","13:30", "HRM-5101","THT"),
        ("Monday", "101", "2:00-3:30",   "14:00","15:30", "HRM-5102","PKP"),
        ("Monday", "201", "9:00-10:30",  "09:00","10:30", "HRM-5205","AH"),
        ("Monday", "201", "10:30-12:00", "10:30","12:00", "GED-2104","AH"),
        ("Monday", "201", "12:00-1:30",  "12:00","13:30", "MGT-2101","HR"),
        ("Monday", "201", "2:00-3:30",   "14:00","15:30", "MGT-3204","MK"),
        ("Monday", "201", "3:30-5:00",   "15:30","17:00", "MGT-3202","KHR"),
        ("Monday", "100", "10:30-12:00", "10:30","12:00", "HRM-5203","PKP"),
        ("Monday", "100", "12:00-1:30",  "12:00","13:30", "HRM-5202","KHR"),
        # Tuesday
        ("Tuesday","101", "9:00-10:30",  "09:00","10:30", "HRM-5103","MK"),
        ("Tuesday","101", "10:30-12:00", "10:30","12:00", "HRM-5102","PKP"),
        ("Tuesday","101", "12:00-1:30",  "12:00","13:30", "MGT-2105","THT"),
        ("Tuesday","101", "2:00-3:30",   "14:00","15:30", "MGT-3102","PKP"),
        ("Tuesday","101", "3:30-5:00",   "15:30","17:00", "MGT-3105","AH"),
        ("Tuesday","201", "9:00-10:30",  "09:00","10:30", "MGT-3205","FA"),
        ("Tuesday","201", "10:30-12:00", "10:30","12:00", "MGT-3104","HR"),
        ("Tuesday","201", "2:00-3:30",   "14:00","15:30", "GED-2104","AH"),
        ("Tuesday","201", "3:30-5:00",   "15:30","17:00", "MGT-2101","HR"),
        ("Tuesday","100", "9:00-10:30",  "09:00","10:30", "HRM-5203","PKP"),
        ("Tuesday","100", "10:30-12:00", "10:30","12:00", "HRM-5202","KHR"),
        ("Tuesday","100", "12:00-1:30",  "12:00","13:30", "HRM-5204","HR"),
        # Wednesday
        ("Wednesday","101","10:30-12:00","10:30","12:00", "MGT-3204","HR"),
        ("Wednesday","101","12:00-1:30", "12:00","13:30", "GED-3203","HR"),
        ("Wednesday","101","2:00-3:30",  "14:00","15:30", "MGT-3104","HR"),
        ("Wednesday","101","3:30-5:00",  "15:30","17:00", "MGT-3101","THT"),
        ("Wednesday","201","9:00-10:30", "09:00","10:30", "MGT-3205","FA"),
        ("Wednesday","201","10:30-12:00","10:30","12:00", "MGT-3204","MK"),
        ("Wednesday","201","12:00-1:30", "12:00","13:30", "HRM-5201","MK"),
        ("Wednesday","201","2:00-3:30",  "14:00","15:30", "HRM-5201","MK"),
        ("Wednesday","100","9:00-10:30", "09:00","10:30", "HRM-5104","AH"),
        ("Wednesday","100","10:30-12:00","10:30","12:00", "HRM-5105","KHR"),
        ("Wednesday","100","12:00-1:30", "12:00","13:30", "HRM-5101","THT"),
        # Thursday
        ("Thursday","101","10:30-12:00", "10:30","12:00", "MGT-3202","KHR"),
        ("Thursday","101","12:00-1:30",  "12:00","13:30", "MGT-3103","KHR"),
        ("Thursday","101","2:00-3:30",   "14:00","15:30", "MGT-3105","AH"),
        ("Thursday","101","3:30-5:00",   "15:30","17:00", "MGT-3101","THT"),
        ("Thursday","201","9:00-10:30",  "09:00","10:30", "MGT-3205","FA"),
        ("Thursday","201","12:00-1:30",  "12:00","13:30", "MGT-3201","AH"),
        ("Thursday","201","2:00-3:30",   "14:00","15:30", "GED-2103","KHR"),
        ("Thursday","100","9:00-10:30",  "09:00","10:30", "HRM-5103","MK"),
        ("Thursday","100","10:30-12:00", "10:30","12:00", "HRM-5104","AH"),
    ]

    return [
        {
            "day": r[0], "room_no": r[1], "time_slot": r[2],
            "time_start": r[3], "time_end": r[4],
            "course_code": r[5], "teacher_code": r[6], "session": "2025-26"
        }
        for r in raw
    ]

def get_seed_mappings() -> List[Dict]:
    """Returns teacher and course code mappings."""
    teachers = [
        ("FA",  "Professor Dr. Feroz Ahmed",    "teacher"),
        ("HR",  "Habibur Rahaman",              "teacher"),
        ("MK",  "Malina Khatun",                "teacher"),
        ("PKP", "Prashanta Kumar Podder",       "teacher"),
        ("TI",  "Md. Tarequl Islam",            "teacher"),
        ("AH",  "Alamgir Hossain",              "teacher"),
        ("KHR", "Md. Kazi Hafizur Rahman",      "teacher"),
        ("THT", "Tamima Hasan Taishi",          "teacher"),
    ]
    courses = [
        ("MGT-2101","Organization Behavior",                    "course"),
        ("GED-2102", "Statistics-I",                            "course"),
        ("GED-2103", "Commercial Law",                          "course"),
        ("GED-2104", "Macro Economics",                         "course"),
        ("MGT-2105", "Financial Management",                    "course"),
        ("MGT-3101", "Bank Management",                         "course"),
        ("MGT-3102", "Industrial Law",                          "course"),
        ("MGT-3103", "Insurance and Risk Management",           "course"),
        ("MGT-3104", "Taxation & Auditing",                     "course"),
        ("MGT-3105", "Innovation & Change Management",          "course"),
        ("MGT-3201", "Industrial Relations",                    "course"),
        ("MGT-3202", "Management Information System",           "course"),
        ("MGT-3203", "Management Science",                      "course"),
        ("MGT-3204", "Business Ethics and CSR",                 "course"),
        ("MGT-3205", "Entrepreneurship and SME Management",     "course"),
        ("HRM-5101", "Human Resource Planning and Policy",      "course"),
        ("HRM-5102", "Training and Development",                "course"),
        ("HRM-5103", "Compensation Management",                 "course"),
        ("HRM-5104", "Conflict Management",                     "course"),
        ("HRM-5105", "Strategic Human Resource Management",     "course"),
        ("HRM-5201", "International Human Resource Management", "course"),
        ("HRM-5202", "Human Resource Information System",       "course"),
        ("HRM-5203", "Career Planning and Development",         "course"),
        ("HRM-5204", "Performance Management",                  "course"),
        ("HRM-5205", "Contemporary Issues in HRM",              "course"),
        ("GED-3203", "Business Ethics and CSK",                 "course"),
        ("GED-5203", "Advanced Business Communication",         "course"),
    ]
    return [{"code": t[0], "full_name": t[1], "type": t[2]} for t in teachers + courses]
