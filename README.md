# UniSync — Academic Portal
### Department of Management · Rabindra University, Bangladesh
**Class Schedule effective: 25 March 2026**

---

## ⚡ Quickstart (3 steps)

### 1 — Add your Supabase API Keys

Open `.env` and paste your keys from  
**Supabase Dashboard → Project Settings → API**

```env
SUPABASE_URL=https://akitkwaeotifdujkoykd.supabase.co
SUPABASE_ANON_KEY=<your anon/public key>
SUPABASE_SERVICE_KEY=<your service_role key>
```

### 2 — Run the SQL Schema

Open **Supabase Dashboard → SQL Editor**, paste the full contents of `supabase_schema.sql` and run it.  
This creates all 5 tables with Row Level Security policies.

### 3 — Launch the App

**Windows:**
```
Double-click start.bat
```

**Linux / Mac:**
```bash
bash start.sh
```

**Manual:**
```bash
pip install -r requirements.txt
python run.py
```

Open → **http://localhost:5000**

---

## 🌱 First-Time Database Seed

1. Register at `/auth/register`  
2. In Supabase SQL Editor, promote yourself to admin:
   ```sql
   UPDATE profiles SET role = 'admin' WHERE email = 'your@email.com';
   ```
3. Go to `/admin/` → click **"Seed Routine & Mappings"**  
4. The complete class schedule (51 entries, 8 teachers, 27 courses) loads instantly ✅

---

## 📁 Project Structure

```
UniSync_Final/
├── app/
│   ├── __init__.py              Flask App Factory + Error Handlers
│   ├── auth/routes.py           Login · Register · Logout (Supabase JWT)
│   ├── academic/routes.py       Routine · Live Tracker · Time Search · Mappings
│   ├── productivity/routes.py   Tasks CRUD · UniCover Generator
│   ├── campus/routes.py         Study Resources
│   └── admin/routes.py          Excel Upload · DB Seeder · Stats
│
├── core/
│   ├── supabase_client.py       Anon + Service Role clients
│   └── excel_parser.py          Excel parser + full seed data (51 routines)
│
├── static/
│   ├── css/style.css            Full design system (dark theme, CSS variables)
│   ├── css/modules/auth.css     Login/register page styles
│   └── js/
│       ├── main.js              Auth state · Toast · Sidebar · Profile modal
│       ├── live_engine.js       Real-time class tracker (polls every 60s)
│       └── admin_tools.js       Upload drag-drop UX
│
├── templates/
│   ├── base.html                Sidebar · Mobile nav · Toast container
│   ├── dashboard.html           Live card · Stats · Tasks · Time search
│   ├── auth/login.html
│   ├── auth/register.html
│   ├── errors/404.html
│   ├── errors/500.html
│   └── modules/
│       ├── routine.html         Weekly schedule table + faculty legend
│       ├── tasks.html           Task board with priority + deadline
│       ├── courses.html         Course catalog with filter
│       ├── resources.html       Study materials gallery
│       ├── unicover.html        A4 cover page generator (print-ready)
│       └── admin.html           Seed DB · Upload routine · Stats panel
│
├── .env                         ← Your Supabase keys go here
├── .env.example                 Template reference
├── config.py                    Dev / Production config
├── run.py                       Entry point
├── requirements.txt             All Python dependencies
├── supabase_schema.sql          Run once in Supabase SQL Editor
├── start.sh                     Linux/Mac one-click launcher
└── start.bat                    Windows one-click launcher
```

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Body |
|--------|----------|------|
| POST | `/auth/api/login` | `{email, password}` |
| POST | `/auth/api/register` | `{email, password, full_name, dept, batch}` |
| POST | `/auth/api/logout` | — |

### Academic
| Method | Endpoint | Params |
|--------|----------|--------|
| GET | `/academic/api/routine` | `?day=Monday` |
| GET | `/academic/api/live-class` | `?day=Monday&time=10:00` |
| GET | `/academic/api/time-search` | `?time=11:30&day=Monday` |
| GET | `/academic/api/mappings` | — |

### Tasks
| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/productivity/api/tasks` | `?user_id=<uid>` · auto-flags urgent |
| POST | `/productivity/api/tasks` | Create task |
| PATCH | `/productivity/api/tasks/<id>` | Update status/fields |
| DELETE | `/productivity/api/tasks/<id>` | Delete |
| POST | `/productivity/api/unicover` | `{user_id, course_code}` |

### Campus & Admin
| Method | Endpoint | Notes |
|--------|----------|-------|
| GET/POST | `/campus/api/resources` | List / Upload resource |
| POST | `/admin/api/seed-database` | Seeds 51 routines + 35 mappings |
| POST | `/admin/api/upload-routine` | Multipart `.xlsx` upload |
| GET | `/admin/api/stats` | DB row counts |

---

## 🗄️ Database Schema (5 tables)

| Table | Purpose |
|-------|---------|
| `profiles` | User info + role (admin/teacher/student) |
| `mappings` | Course & teacher code → full name |
| `routines` | 51 class schedule entries (day · room · time · codes) |
| `tasks` | Personal task tracker per user |
| `resources` | Study materials with file URLs |

All tables use **Row Level Security (RLS)** via Supabase.

---

## ✨ Features

| Feature | How it works |
|---------|-------------|
| **Live Class Tracker** | Polls `/academic/api/live-class` every 60s with local day+time. Shows progress ring countdown. |
| **Time Search** | Input any HH:MM → instantly find classes running at that time across any day |
| **Smart Routine** | Full week table per day with room, teacher name, course name from `mappings` |
| **Task Manager** | Create/update/delete tasks. Deadline within 2h → auto URGENT flag |
| **UniCover Generator** | Auto-fills cover page from your profile. Print to PDF from browser. |
| **Study Resources** | Upload & share notes/files with Google Drive links |
| **Admin Seeder** | One-click to load full Rabindra University 2025-26 schedule |
| **Excel Upload** | Admin uploads `.xlsx` → Pandas processes → DB updated atomically |
| **RBAC** | Admin sees Admin nav. Students see read-only data. |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ · Flask 3 · Blueprints architecture |
| Database | Supabase (PostgreSQL) + Row Level Security |
| Auth | Supabase Auth · JWT tokens stored in `localStorage` |
| Frontend | Vanilla JS (no framework) · Jinja2 templates |
| Styling | Custom CSS · CSS Variables · Dark theme |
| Fonts | Syne (display) · Space Grotesk (body) · JetBrains Mono |
| Excel | Pandas + openpyxl |

---

## 👨‍💻 Developer

```
╔══════════════════════════════════════════════════╗
║          UniSync — Academic Portal v1.0          ║
║      Rabindra University, Bangladesh             ║
║      Department of Management                   ║
║                                                  ║
║  Developer : Sourav                              ║
║  Stack     : Flask · Supabase · Vanilla JS       ║
║  Session   : 2025-26                             ║
║  Built     : March 2026                          ║
║                                                  ║
║  "Sync every student's academic life"            ║
╚══════════════════════════════════════════════════╝
```
