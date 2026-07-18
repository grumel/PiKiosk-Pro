# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Produktions-Webserver.

Startet die Flask-Anwendung auf dem Cheroot-WSGI-Server (reines
Python, produktionsreif, laeuft ohne Kompilieren auf ARM). Liegen
Zertifikat und Schluessel unter config/tls, wird der Hauptlistener
mit TLS betrieben; zusaetzlich lauscht dann ein reiner
HTTP-Listener auf der Loopback-Schnittstelle, damit Kioskbrowser
und Watchdog lokal ohne Zertifikatswarnung arbeiten.
"""

import threading
from pathlib import Path

from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server
from flask import Flask

from app.constants import LOOPBACK_HOST, SERVER_THREADS


def build_server(
    app: Flask,
    host: str,
    port: int,
    tls: tuple[Path, Path] | None = None,
    threads: int = SERVER_THREADS,
) -> Server:
    """Erzeugt einen konfigurierten Cheroot-Server.

    Args:
        app:
            Die WSGI-Anwendung.

        host:
            Netzwerkschnittstelle des Listeners.

        port:
            Port des Listeners.

        tls:
            Optionales Pfadpaar (Zertifikat, Schluessel) fuer TLS.

        threads:
            Anzahl der Arbeitsthreads.

    Returns:
        Der startbereite Server.
    """
    server = Server((host, port), app, numthreads=threads)
    if tls is not None:
        certificate, key = tls
        server.ssl_adapter = BuiltinSSLAdapter(str(certificate), str(key))
    return server


def serve(
    app: Flask,
    host: str,
    port: int,
    tls: tuple[Path, Path] | None = None,
    loopback_port: int | None = None,
) -> None:
    """Betreibt die Anwendung, bis der Prozess beendet wird.

    Args:
        app:
            Die WSGI-Anwendung.

        host:
            Netzwerkschnittstelle des Hauptlisteners.

        port:
            Port des Hauptlisteners.

        tls:
            Optionales Pfadpaar (Zertifikat, Schluessel); der
            Hauptlistener laeuft dann ueber HTTPS.

        loopback_port:
            Optionaler Port eines zusaetzlichen HTTP-Listeners auf
            der Loopback-Schnittstelle (nur sinnvoll mit TLS).
    """
    main_server = build_server(app, host, port, tls=tls)
    extra_servers: list[Server] = []
    if tls is not None and loopback_port is not None:
        extra_servers.append(build_server(app, LOOPBACK_HOST, loopback_port))
    threads = [
        threading.Thread(target=extra.safe_start, daemon=True)
        for extra in extra_servers
    ]
    for thread in threads:
        thread.start()
    try:
        main_server.safe_start()
    finally:
        for extra in extra_servers:
            extra.stop()
        main_server.stop()
