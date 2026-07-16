# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - REST API.

Basis der REST API unter /api: Token-Ausgabe (JWT, HS256),
Authentifizierungs-Dekorator und einheitliche JSON-Fehler. Alle
Endpunkte sind authentifiziert und liefern ausschliesslich JSON.
Die API ist die Grundlage fuer die Remote-Verwaltung mehrerer
Geraete; die lokale Weboberflaeche bleibt davon unberuehrt.
"""

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, g, jsonify, request

from app.constants import API_TOKEN_TTL_SECONDS
from app.controllers import current_services
from app.exceptions import AuthenticationError, PiKioskError, ValidationError
from app.utils.crypto import create_jwt, verify_jwt

api_blueprint = Blueprint("api", __name__, url_prefix="/api")

ApiView = Callable[..., Response | tuple[Response, int]]


def api_error(status_code: int, message: str) -> tuple[Response, int]:
    """Baut eine einheitliche JSON-Fehlerantwort.

    Args:
        status_code:
            HTTP-Statuscode.

        message:
            Fehlermeldung.

    Returns:
        JSON-Antwort mit Statuscode.
    """
    return jsonify(error=message), status_code


def json_body() -> dict[str, Any]:
    """Liest den JSON-Koerper der aktuellen Anfrage.

    Returns:
        Der JSON-Koerper oder ein leeres Woerterbuch.
    """
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def api_auth_required(view: ApiView) -> ApiView:
    """Erzwingt ein gueltiges Bearer-Token fuer einen API-Endpunkt.

    Args:
        view:
            Zu schuetzende View-Funktion.

    Returns:
        Die geschuetzte View-Funktion.
    """

    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Response | tuple[Response, int]:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return api_error(401, "unauthorized")
        try:
            claims = verify_jwt(
                header[len("Bearer ") :], str(current_app.config["SECRET_KEY"])
            )
        except AuthenticationError:
            return api_error(401, "unauthorized")
        user = current_services().auth_service.load_user(str(claims.get("sub", "")))
        if user is None:
            return api_error(401, "unauthorized")
        g.api_user = user
        return view(*args, **kwargs)

    return wrapper


def api_call(view: ApiView) -> ApiView:
    """Uebersetzt Anwendungsfehler in JSON-Fehlerantworten.

    Args:
        view:
            Auszufuehrende View-Funktion.

    Returns:
        Die abgesicherte View-Funktion.
    """

    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Response | tuple[Response, int]:
        try:
            return view(*args, **kwargs)
        except ValidationError as error:
            return api_error(400, str(error))
        except PiKioskError as error:
            return api_error(400, str(error))

    return wrapper


@api_blueprint.post("/token")
def issue_token() -> Response | tuple[Response, int]:
    """Stellt ein JWT fuer gueltige Anmeldedaten aus.

    Returns:
        Token, Tokentyp und Gueltigkeitsdauer oder Fehler 401.
    """
    body = json_body()
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))
    user = current_services().auth_service.authenticate(username, password)
    if user is None:
        return api_error(401, "invalid_credentials")
    token = create_jwt(
        {"sub": user.get_id(), "username": user.username},
        str(current_app.config["SECRET_KEY"]),
        API_TOKEN_TTL_SECONDS,
    )
    return jsonify(token=token, token_type="Bearer", expires_in=API_TOKEN_TTL_SECONDS)


from app.api import (  # noqa: E402,F401
    backup,
    browser,
    logs,
    network,
    settings,
    status,
    system,
    update,
)
