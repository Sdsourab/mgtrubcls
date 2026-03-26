"""
app/__init__.py — Flask Application Factory

Absolute-path resolution for templates/ and static/ is required in
Vercel's serverless environment, where the working directory is NOT
the project root.  Using os.path.dirname(__file__) chains guarantees
Flask always finds both folders regardless of where Python is invoked.
"""

import os
from typing import Optional
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from config import config


def create_app(config_name: Optional[str] = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "production")

    # ── Absolute path anchors ─────────────────────────────────────────────────
    # app/__init__.py  →  _app_dir  = …/app/
    # project root     →  _root     = …/             (one level up)
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _root    = os.path.dirname(_app_dir)

    app = Flask(
        __name__,
        template_folder=os.path.join(_root, "templates"),
        static_folder=os.path.join(_root, "static"),
    )

    app.config.from_object(config[config_name])

    # ── Register Blueprints ───────────────────────────────────────────────────
    from app.auth.routes         import auth_bp
    from app.academic.routes     import academic_bp
    from app.productivity.routes import productivity_bp
    from app.campus.routes       import campus_bp
    from app.admin.routes        import admin_bp
    from app.guest.routes        import guest_bp

    app.register_blueprint(auth_bp,          url_prefix="/auth")
    app.register_blueprint(academic_bp,      url_prefix="/academic")
    app.register_blueprint(productivity_bp,  url_prefix="/productivity")
    app.register_blueprint(campus_bp,        url_prefix="/campus")
    app.register_blueprint(admin_bp,         url_prefix="/admin")
    app.register_blueprint(guest_bp,         url_prefix="/guest")

    # ── Core Routes ───────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    # ── Error Handlers ────────────────────────────────────────────────────────
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
        return jsonify({"error": "Forbidden — admin role required", "code": 403}), 403

    return app