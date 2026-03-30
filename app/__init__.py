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

    # ══════════════════════════════════════════════════════════
    # EMAIL TEST ENDPOINT
    # Browser এ যান: https://আপনার-সাইট.vercel.app/api/test-email?to=আপনার@gmail.com
    # এটা একটা test welcome email পাঠাবে।
    # কাজ করলে browser এ দেখাবে: {"ok": true, "sent_to": "..."}
    # না করলে দেখাবে error message — কী সমস্যা সেটা বুঝতে পারবেন।
    # ══════════════════════════════════════════════════════════
    @app.route("/api/test-email", methods=["GET"])
    def test_email():
        to = request.args.get("to", "").strip()
        if not to:
            return jsonify({
                "ok": False,
                "error": "?to= parameter required",
                "example": "/api/test-email?to=your@gmail.com"
            }), 400

        # Check mail config
        mail_user = app.config.get("MAIL_USERNAME", "")
        mail_pass = app.config.get("MAIL_PASSWORD", "")
        if not mail_user or not mail_pass:
            return jsonify({
                "ok": False,
                "error": "MAIL_USERNAME বা MAIL_PASSWORD Vercel এ set করা নেই।",
                "fix": "Vercel Dashboard → Settings → Environment Variables এ MAIL_USERNAME এবং MAIL_PASSWORD দিন।"
            }), 500

        try:
            from core.mailer import send_welcome
            ok = send_welcome(to_email=to, user_name="Test User")
            if ok:
                return jsonify({
                    "ok": True,
                    "sent_to": to,
                    "from": mail_user,
                    "message": f"✅ Email sent! '{to}' এর inbox চেক করুন (spam ও দেখুন)।"
                })
            else:
                return jsonify({
                    "ok": False,
                    "error": "Email send failed। Vercel Logs দেখুন।"
                }), 500
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": str(e),
                "tip": "Gmail App Password ঠিক আছে কিনা চেক করুন।"
            }), 500

    # ══════════════════════════════════════════════════════════
    # VERCEL CRON — প্রতিদিন রাত ৭ PM (Bangladesh time)
    # Schedule: "0 13 * * 0-4"  (UTC 13:00 = BST 19:00)
    # ══════════════════════════════════════════════════════════
    @app.route("/api/cron/daily", methods=["GET", "POST"])
    def cron_daily():
        from datetime import datetime, timedelta, timezone

        # FIX: Bangladesh Standard Time = UTC+6
        BST      = timezone(timedelta(hours=6))
        now_bst  = datetime.now(BST)
        tomorrow = (now_bst + timedelta(days=1)).date()
        day_name = tomorrow.strftime("%A")
        date_str = tomorrow.strftime("%d %b %Y")

        results = {"sent": 0, "skipped": 0, "errors": [], "day_checked": day_name}

        # শুধু academic days
        if day_name not in ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]:
            return jsonify({"ok": True, "reason": f"tomorrow is {day_name} — weekend", **results}), 200

        try:
            from core.supabase_client import get_supabase_admin
            from core.holidays       import is_holiday
            from core.mailer         import send_daily_summary

            is_hol, _ = is_holiday(tomorrow)
            sb = get_supabase_admin()
            users = sb.table("profiles").select("*").execute().data or []

            for user in users:
                email = (user.get("email") or "").strip()
                if not email:
                    results["skipped"] += 1
                    continue

                program  = user.get("program",  "BBA")
                year     = user.get("year",     1)
                semester = user.get("semester", 1)

                classes = []
                if not is_hol:
                    try:
                        rows = sb.table("routines").select("*") \
                            .eq("day",             day_name) \
                            .eq("program",         program) \
                            .eq("course_year",     year) \
                            .eq("course_semester", semester) \
                            .order("time_start").execute()
                        classes = rows.data or []
                    except Exception:
                        classes = []

                    for cls in classes:
                        try:
                            c = sb.table("mappings").select("full_name") \
                                .eq("code", cls.get("course_code", "")).execute()
                            cls["course_name"] = c.data[0]["full_name"] if c.data else cls.get("course_code", "")
                        except Exception:
                            cls["course_name"] = cls.get("course_code", "")
                        try:
                            t = sb.table("mappings").select("full_name") \
                                .eq("code", cls.get("teacher_code", "")).execute()
                            cls["teacher_name"] = t.data[0]["full_name"] if t.data else cls.get("teacher_code", "")
                        except Exception:
                            cls["teacher_name"] = cls.get("teacher_code", "")
                        cls["time_start_12h"] = _fmt12h(cls.get("time_start", ""))
                        cls["time_end_12h"]   = _fmt12h(cls.get("time_end",   ""))

                try:
                    tasks = sb.table("tasks").select("*") \
                        .eq("user_id", user["id"]) \
                        .neq("status", "done") \
                        .order("deadline").execute().data or []
                except Exception:
                    tasks = []

                ok = send_daily_summary(
                    to_email  = email,
                    user_name = user.get("full_name", "Student"),
                    classes   = classes,
                    tasks     = tasks,
                    date_str  = f"{day_name}, {date_str}",
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