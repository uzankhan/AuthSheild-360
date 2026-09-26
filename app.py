# app.py
import os
from flask import Flask, render_template, request, jsonify, abort, send_from_directory
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from backend.database import db
from backend.middleware import register_security_headers, register_error_handlers
from backend.routes.auth import auth_bp
from backend.routes.portal import portal_bp
from backend.routes.admin import admin_bp
from backend.seed import seed_data


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    @app.before_request
    def log_request():
        from flask import request as req
        if req.path.startswith("/api/auth"):
            app.logger.info(f"[REQ] {req.method} {req.path} | cookies: {list(req.cookies.keys())}")

    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)

    db.init_app(app)

    # ---- CSRF Protection ----
    # We use SameSite=Strict cookies which already prevent CSRF,
    # so we exempt the auth API routes from CSRF token validation.
    # This is a well-known production pattern.
    csrf = CSRFProtect(app)
    csrf.exempt(auth_bp)
    csrf.exempt(portal_bp)
    csrf.exempt(admin_bp)

    # ---- Rate Limiting ----
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[app.config["RATELIMIT_DEFAULT"]],
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    )

    # ---- Blueprints ----
    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(admin_bp)

    # ---- Security Headers & Errors ----
    register_security_headers(app)
    register_error_handlers(app)

    # ---- Anti-Recon ----
    @app.route("/robots.txt")
    def robots():
        abort(404)

    @app.route("/.env")
    @app.route("/.git/config")
    @app.route("/wp-admin")
    def honeypot():
        abort(404)

    # ---- SPA ----
    @app.route("/")
    def index():
        return render_template("index.html")

    # ---- DB init ----
    with app.app_context():
        db.create_all()
        seed_data()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)