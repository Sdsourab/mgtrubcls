"""
app/__init__.py
═══════════════
Flask application factory.

Email scheduling is handled by Vercel Cron Jobs (api/cron_daily.py and
api/cron_alert.py) — APScheduler is NOT used, making this fully compatible
with Vercel's serverless architecture.
"""

from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_mail import Mail
from config import config
import os

mail = Mail()


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

    # ── Extensions ────────────────────────────────────────────
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

    # ── NOTE: Email scheduling ────────────────────────────────
    # Handled by Vercel Cron Jobs — see vercel.json and api/cron_*.py
    # APScheduler is intentionally NOT used here so the app works on Vercel.

    return app