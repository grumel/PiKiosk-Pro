# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Anmeldung und Ersteinrichtung.

Beim ersten Start legt der Administrator sein Konto an; danach ist
die Zentrale nur nach Anmeldung erreichbar. Passwoerter werden
ausschliesslich als bcrypt-Hash gespeichert.
"""

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.wrappers import Response

from app.exceptions import PiKioskError
from center.controllers import center_texts, ensure_csrf_token
from center.extensions import center_services

center_auth_blueprint = Blueprint("center_auth", __name__)


@center_auth_blueprint.get("/setup")
def setup() -> str | Response:
    """Zeigt die Ersteinrichtung der Zentrale.

    Returns:
        Die Einrichtungsseite oder eine Weiterleitung.
    """
    if center_services().auth_service.administrator_exists():
        return redirect(url_for("center_auth.login"))
    ensure_csrf_token()
    return render_template("center_setup.html", texts=center_texts(), error=None)


@center_auth_blueprint.post("/setup")
def setup_submit() -> str | Response:
    """Legt das Administratorkonto der Zentrale an.

    Returns:
        Weiterleitung zur Anmeldung oder die Seite mit Fehler.
    """
    texts = center_texts()
    services = center_services()
    if services.auth_service.administrator_exists():
        return redirect(url_for("center_auth.login"))
    username = request.form.get("username", "").strip() or "admin"
    password = request.form.get("password", "")
    repeat = request.form.get("password_repeat", "")
    if password != repeat:
        return render_template(
            "center_setup.html", texts=texts, error=texts["password_mismatch"]
        )
    try:
        password_hash = services.auth_service.hash_password(password)
        services.auth_service.create_administrator(username, password_hash)
    except PiKioskError as error:
        return render_template("center_setup.html", texts=texts, error=str(error))
    return redirect(url_for("center_auth.login"))


@center_auth_blueprint.get("/login")
def login() -> str | Response:
    """Zeigt die Anmeldeseite der Zentrale.

    Returns:
        Die Anmeldeseite oder eine Weiterleitung.
    """
    if not center_services().auth_service.administrator_exists():
        return redirect(url_for("center_auth.setup"))
    if current_user.is_authenticated:
        return redirect(url_for("fleet.index"))
    ensure_csrf_token()
    texts = center_texts()
    notice = texts["session_expired"] if request.args.get("expired") else None
    return render_template("center_login.html", texts=texts, error=None, notice=notice)


@center_auth_blueprint.post("/login")
def login_submit() -> str | Response:
    """Verarbeitet die Anmeldedaten der Zentrale.

    Returns:
        Weiterleitung zur Uebersicht oder die Seite mit Fehler.
    """
    texts = center_texts()
    services = center_services()
    user = services.auth_service.authenticate(
        request.form.get("username", ""), request.form.get("password", "")
    )
    if user is None:
        return render_template(
            "center_login.html", texts=texts, error=texts["login_failed"]
        )
    session.permanent = True
    login_user(user, remember=request.form.get("remember", "") == "on")
    return redirect(url_for("fleet.index"))


@center_auth_blueprint.post("/logout")
@login_required
def logout() -> Response:
    """Meldet den Administrator ab.

    Returns:
        Weiterleitung zur Anmeldeseite.
    """
    center_services().logger.info("Administrator abgemeldet.")
    logout_user()
    return redirect(url_for("center_auth.login"))
