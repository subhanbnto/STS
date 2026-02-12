"""
Flask dashboard: login-protected, real-time status and trades.
Single user: credentials from .env (DASHBOARD_USERNAME, DASHBOARD_PASSWORD).
"""
import logging
import os
import traceback

from flask import Flask, Response, jsonify, redirect, request, session, url_for

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)


def _config():
    from config import DASHBOARD_USERNAME, DASHBOARD_PASSWORD, FLASK_SECRET_KEY
    return DASHBOARD_USERNAME, DASHBOARD_PASSWORD, FLASK_SECRET_KEY


def _init_secret():
    _, __, secret = _config()
    app.config["SECRET_KEY"] = secret or "sts-dashboard-secret-change-me"


def _check_login(username: str, password: str) -> bool:
    user, pwd, _ = _config()
    return bool(user and pwd and username == user and password == pwd)


@app.before_request
def require_auth():
    if request.path in ("/login", "/logout", "/ping"):
        return None
    if request.path.startswith("/api/"):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return None
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return None


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if _check_login(username, password):
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("index"))
        return _login_html(error="Invalid username or password.")
    return _login_html()


@app.route("/ping")
def ping():
    """Health check; no auth. Use to verify server is responding."""
    return "ok", 200, {"Content-Type": "text/plain"}


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
def index():
    try:
        html = _html("dashboard.html")
        return Response(html, mimetype="text/html; charset=utf-8")
    except Exception as e:
        logger.exception("Dashboard index error")
        return Response(
            f"Error loading dashboard: {e}\n\n{traceback.format_exc()}",
            status=500,
            mimetype="text/plain; charset=utf-8",
        )


@app.route("/api/status")
def api_status():
    from app_state import state
    return jsonify(state.snapshot())


def _template_path(name: str) -> str:
    """Resolve template path: same dir as this file, or cwd."""
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "templates", name)
    if os.path.isfile(path):
        return path
    path_cwd = os.path.join(os.getcwd(), "templates", name)
    if os.path.isfile(path_cwd):
        return path_cwd
    return os.path.join(base, "templates", name)


def _html(name: str) -> str:
    path = _template_path(name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _login_html(error: str = "") -> str:
    path = _template_path("login.html")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if error:
        content = content.replace("{{ERROR}}", f'<p class="error">{error}</p>')
    else:
        content = content.replace("{{ERROR}}", "")
    return content


def run_dashboard(host: str = "0.0.0.0", port: int = 5050):
    _init_secret()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def run_dashboard_thread(host: str = "0.0.0.0", port: int = 5050):
    import threading
    _init_secret()
    t = threading.Thread(target=lambda: run_dashboard(host=host, port=port), daemon=True)
    t.start()
    return t
