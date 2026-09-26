import ipaddress
from functools import wraps
from flask import request, jsonify, current_app, abort
from backend.security import client_ip


# ---------- Admin IP whitelist ----------
def _ip_in_whitelist(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in current_app.config["ADMIN_IP_WHITELIST"]:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def admin_ip_guard(f):
    """Admin routes only accessible from whitelisted IPs.
    Returns 404 (not 403) so attackers can't even confirm the endpoint exists."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = client_ip()
        if not _ip_in_whitelist(ip):
            # Log quietly, return decoy 404
            try:
                from backend.services.audit import log_event
                log_event(
                    action="Admin Route Probe",
                    factor="IP Guard",
                    result="FAIL",
                    details=f"Blocked IP {ip} on {request.path}",
                )
            except Exception:
                pass
            abort(404)
        return f(*args, **kwargs)
    return wrapper


# ---------- Security headers ----------
def register_security_headers(app):
    @app.after_request
    def _headers(resp):
        # Anti-sniff, anti-frame, anti-referrer
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Tell crawlers/scrapers to buzz off (Maltego / search engines)
        resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex"

        # Content Security Policy (tight)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )

        # HSTS only over HTTPS
        if request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Strip server fingerprint
        resp.headers["Server"] = "AuthShield"

        return resp


# ---------- Error handlers (no stack traces leak) ----------
def register_error_handlers(app):
    @app.errorhandler(404)
    def _404(e):
        return jsonify({"ok": False, "message": "Not found"}), 404

    @app.errorhandler(403)
    def _403(e):
        return jsonify({"ok": False, "message": "Forbidden"}), 403

    @app.errorhandler(429)
    def _429(e):
        return jsonify({"ok": False, "message": "Too many requests. Slow down."}), 429

    @app.errorhandler(500)
    def _500(e):
        # Log internally, return generic message
        app.logger.exception("Internal error")
        return jsonify({"ok": False, "message": "Internal server error"}), 500