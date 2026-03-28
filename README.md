# UniSync — Academic Portal
### Department of Management · Rabindra University, Bangladesh
**Class Schedule effective: 25 March 2026**

---

## ⚡ Quickstart (4 steps)

### 1 — Copy the environment file

```bash
cp .env.example .env
```

Open `.env` and fill in your keys (see sections below).

---

### 2 — Add your Supabase API Keys

Open **Supabase Dashboard → Project Settings → API** and paste:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_KEY=your-service-role-key
```

---

### 3 — Add your OpenRouter API Key

The **AI Planner Advisor** feature is powered by [OpenRouter.ai](https://openrouter.ai).  
Your key lives **server-side only** — users never see it or need their own.

1. Sign up free at → **https://openrouter.ai/keys**
2. Create a key and paste it into `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

The app uses these **free-tier models** (tried in order, no cost):
| Priority | Model |
|----------|-------|
| 1st | `meta-llama/llama-3.3-70b-instruct:free` |
| 2nd | `meta-llama/llama-3.1-8b-instruct:free` |
| 3rd | `mistralai/mistral-7b-instruct:free` |
| 4th | `google/gemma-2-9b-it:free` |

> DeepSeek models are **not used**.

---

### 4 — Run the SQL Schema + Launch

Open **Supabase Dashboard → SQL Editor**, paste `supabase_schema.sql` and run it.

Then launch:

**Windows:**
```
Double-click start.bat
```

**Linux / Mac:**
```bash
chmod +x start.sh
bash start.sh
```

**Manual:**
```bash
pip install -r requirements.txt
python run.py
```

Open → **http://localhost:5000**

---

## 🌐 Vercel Deployment

1. Push your code to GitHub (make sure `.env` is in `.gitignore`)
2. Import the repo in Vercel
3. Go to **Vercel → Project → Settings → Environment Variables** and add:

| Variable | Value |
|----------|-------|
| `OPENROUTER_API_KEY` | `sk-or-v1-your-key-here` |
| `SUPABASE_URL` | `https://your-project.supabase.co` |
| `SUPABASE_ANON_KEY` | `your-anon-key` |
| `SUPABASE_SERVICE_KEY` | `your-service-role-key` |
| `FLASK_SECRET_KEY` | `a-long-random-string` |

The `vercel.json` maps `@openrouter-api-key` to the secret automatically.

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
UniSync/
├── app/
│   ├── __init__.py              Flask App Factory + Error Handlers
│   ├── auth/routes.py           Login · Register · Logout (Supabase JWT)
│   ├── academic/routes.py       Routine · Live Tracker · Time Search · Mappings
│   ├── productivity/routes.py   Tasks CRUD · UniCover Generator
│   ├── campus/routes.py         Study Resources
│   ├── planner/routes.py        Plans CRUD · Conflict Checker · AI Advisor
│   └── admin/routes.py          Excel Upload · DB Seeder · Stats
│
├── core/
│   ├── supabase_client.py       Anon + Service Role clients
│   ├── excel_parser.py          Excel parser + full seed data (51 routines)
│   ├── holidays.py              Bangladesh holiday list 2026
│   ├── mailer.py                Flask-Mail helpers
│   └── scheduler.py             APScheduler background jobs
│
├── static/
│   ├── css/style.css            Full design system (dark theme, CSS variables)
│   ├── css/modules/auth.css     Login/register page styles
│   └── js/
│       ├── main.js              Auth state · Toast · Sidebar · Profile modal
│       ├── live_engine.js       Real-time class tracker (polls every 60s)
│       ├── planner.js           AI-powered planner UI
│       └── admin_tools.js       Upload drag-drop UX
│
├── templates/ ...
│
├── .env                         ← Your keys go here (never commit this)
├── .env.example                 Template — copy to .env
├── config.py                    Dev / Production config
├── run.py                       Entry point
├── requirements.txt             All Python dependencies
├── vercel.json                  Vercel deployment config
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

### Planner & AI
| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/planner/api/plans` | `?user_id=<uid>` |
| POST | `/planner/api/plans` | Create plan |
| DELETE | `/planner/api/plans/<id>` | Delete |
| POST | `/planner/api/conflict-check` | `{date, start_time, end_time, program, year, semester}` |
| POST | `/planner/api/ai-advice` | AI advice via OpenRouter — key is server-side only |

### Tasks
| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/productivity/api/tasks` | `?user_id=<uid>` · auto-flags urgent |
| POST | `/productivity/api/tasks` | Create task |
| PATCH | `/productivity/api/tasks/<id>` | Update status/fields |
| DELETE | `/productivity/api/tasks/<id>` | Delete |
| POST | `/productivity/api/unicover` | `{user_id, course_code}` |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ · Flask 3 · Blueprints |
| Database | Supabase (PostgreSQL) + Row Level Security |
| Auth | Supabase Auth · JWT tokens |
| AI | OpenRouter.ai (server-side, free-tier models) |
| Frontend | Vanilla JS · Jinja2 templates |
| Styling | Custom CSS · CSS Variables · Dark theme |
| Fonts | Syne · Space Grotesk · JetBrains Mono |
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
║  AI        : OpenRouter.ai (free-tier)           ║
║  Session   : 2025-26                             ║
║  Built     : March 2026                          ║
║                                                  ║
║  "Sync every student's academic life"            ║
╚══════════════════════════════════════════════════╝
```