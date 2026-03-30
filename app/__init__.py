"""
app/__init__.py
"""
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_mail import Mail
from config import config
import os

mail = Mail()


def _fmt12h(t: str) -> str:
    try:
        h, m = map(int, t.split(":"))
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return t


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(_root, "templates"),
        static_folder=os.path.join(_root, "static"),
    )
    app.config.from_object(config[config_name])
    mail.init_app(app)

    # ── Blueprints ────────────────────────────────────────────
    from app.auth.routes         import auth_bp
    from app.academic.routes     import academic_bp
    from app.productivity.routes import productivity_bp
    from app.campus.routes       import campus_bp
    from app.admin.routes        import admin_bp
    from app.guest.routes        import guest_bp
    from app.planner.routes      import planner_bp

    app.register_blueprint(auth_bp,          url_prefix="/auth")
    app.register_blueprint(academic_bp,      url_prefix="/academic")
    app.register_blueprint(productivity_bp,  url_prefix="/productivity")
    app.register_blueprint(campus_bp,        url_prefix="/campus")
    app.register_blueprint(admin_bp,         url_prefix="/admin")
    app.register_blueprint(guest_bp,         url_prefix="/guest")
    app.register_blueprint(planner_bp,       url_prefix="/planner")

    # ── Core Routes ───────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    # ── Vercel Cron: প্রতিদিন রাত ৭টায় email পাঠাবে ─────────
    @app.route("/api/cron/daily", methods=["GET", "POST"])
    def cron_daily():
        from datetime import date, timedelta
        results = {"sent": 0, "skipped": 0, "errors": []}
        try:
            from core.supabase_client import get_supabase_admin
            from core.holidays       import is_holiday
            from core.mailer         import send_daily_summary

            tomorrow = date.today() + timedelta(days=1)
            day_name = tomorrow.strftime("%A")
            date_str = tomorrow.strftime("%d %b %Y")

            if day_name not in ["Sunday","Monday","Tuesday","Wednesday","Thursday"]:
                return jsonify({"ok": True, "reason": "weekend"}), 200

            is_hol, _ = is_holiday(tomorrow)
            sb = get_supabase_admin()
            users = (sb.table("profiles").select("*").execute().data or [])

            for user in users:
                email = (user.get("email") or "").strip()
                if not email:
                    results["skipped"] += 1
                    continue

                classes = []
                if not is_hol:
                    try:
                        rows = sb.table("routines").select("*")\
                            .eq("day",             day_name)\
                            .eq("program",         user.get("program","BBA"))\
                            .eq("course_year",     user.get("year",1))\
                            .eq("course_semester", user.get("semester",1))\
                            .order("time_start").execute()
                        classes = rows.data or []
                    except Exception:
                        classes = []

                    for cls in classes:
                        try:
                            c = sb.table("mappings").select("full_name")\
                                .eq("code", cls.get("course_code","")).execute()
                            cls["course_name"] = c.data[0]["full_name"] if c.data else cls.get("course_code","")
                        except Exception:
                            cls["course_name"] = cls.get("course_code","")
                        try:
                            t = sb.table("mappings").select("full_name")\
                                .eq("code", cls.get("teacher_code","")).execute()
                            cls["teacher_name"] = t.data[0]["full_name"] if t.data else cls.get("teacher_code","")
                        except Exception:
                            cls["teacher_name"] = cls.get("teacher_code","")
                        cls["time_start_12h"] = _fmt12h(cls.get("time_start",""))
                        cls["time_end_12h"]   = _fmt12h(cls.get("time_end",""))

                try:
                    tasks = sb.table("tasks").select("*")\
                        .eq("user_id", user["id"])\
                        .neq("status","done")\
                        .order("deadline").execute().data or []
                except Exception:
                    tasks = []

                ok = send_daily_summary(
                    to_email  = email,
                    user_name = user.get("full_name","Student"),
                    classes   = classes,
                    tasks     = tasks,
                    date_str  = f"{day_name}, {date_str}",
                    app       = app,
                )
                if ok:
                    results["sent"] += 1
                else:
                    results["errors"].append(email)

        except Exception as e:
            results["errors"].append(str(e))

        return jsonify({"ok": True, **results}), 200

    # ── Error Handlers ────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api") or request.accept_mimetypes.accept_json:
            return jsonify({"error": "Not found", "code": 404}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api") or request.accept_mimetypes.accept_json:
            return jsonify({"error": "Internal server error", "code": 500}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "code": 403}), 403

    return app