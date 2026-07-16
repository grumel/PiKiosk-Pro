# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Anmeldung.

Stellt Login und Logout ueber Flask-Login bereit. Passwoerter
werden ausschliesslich ueber bcrypt geprueft, die Sitzung laeuft
nach 30 Minuten ab.
"""

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.wrappers import Response

from app.controllers import current_services, current_texts, ensure_csrf_token

auth_blueprint = Blueprint("auth", __name__)


def _render_login(error: str | None = None) -> str:
    """Rendert die Anmeldeseite.

    Args:
        error:
            Optionale Fehlermeldung.

    Returns:
        Die gerenderte Anmeldeseite.
    """
    config = current_services().config_service.load()
    ensure_csrf_token()
    return render_template(
        "login.html", texts=current_texts(), theme=config["theme"], error=error
    )


@auth_blueprint.get("/login")
def login() -> str | Response:
    """Zeigt die Anmeldeseite.

    Returns:
        Anmeldeseite oder Weiterleitung zum Dashboard.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return _render_login()


@auth_blueprint.post("/login")
def login_submit() -> str | Response:
    """Verarbeitet die Anmeldedaten.

    Returns:
        Weiterleitung zum Dashboard oder Anmeldeseite mit Fehler.
    """
    texts = current_texts()
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    remember = request.form.get("remember", "") == "on"
    user = current_services().auth_service.authenticate(username, password)
    if user is None:
        return _render_login(error=texts["login_failed"])
    session.permanent = True
    login_user(user, remember=remember)
    target = request.args.get("next", "")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("dashboard.index")
    return redirect(target)


@auth_blueprint.post("/logout")
@login_required
def logout() -> Response:
    """Meldet den Benutzer ab.

    Returns:
        Weiterleitung zur Anmeldeseite.
    """
    current_services().logger.info("Benutzer abgemeldet.")
    logout_user()
    return redirect(url_for("auth.login"))
