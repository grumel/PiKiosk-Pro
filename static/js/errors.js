/*
 * Copyright (c) 2026 Holger John
 * Lizenz: MIT License (siehe LICENSE)
 *
 * PiKiosk Pro - Globale Fehleranzeige.
 * Schlaegt eine HTMX-Anfrage fehl (Serverfehler oder keine
 * Verbindung), erscheint eine sichtbare Meldung am unteren
 * Bildschirmrand, damit ein Fehler niemals wie "es passiert
 * nichts" wirkt. Die Texte kommen aus den Sprachdateien und
 * stehen als data-Attribute am body. Der Einrichtungsassistent
 * bringt eine eigene Fehleranzeige mit und ist ausgenommen.
 */

(function () {
    "use strict";

    var DISMISS_AFTER_MS = 10000;

    function message(name, fallback) {
        return document.body.getAttribute("data-" + name) || fallback;
    }

    function container() {
        var region = document.getElementById("global-error-region");
        if (region) {
            return region;
        }
        region = document.createElement("div");
        region.id = "global-error-region";
        region.setAttribute("aria-live", "assertive");
        region.style.position = "fixed";
        region.style.bottom = "1rem";
        region.style.left = "50%";
        region.style.transform = "translateX(-50%)";
        region.style.zIndex = "1080";
        region.style.maxWidth = "36rem";
        region.style.width = "calc(100% - 2rem)";
        document.body.appendChild(region);
        return region;
    }

    function show(text) {
        var region = container();
        var previous = region.firstElementChild;
        if (previous && previous.textContent === text) {
            return;
        }
        var alert = document.createElement("div");
        alert.className = "alert alert-danger shadow-sm mb-2";
        alert.setAttribute("role", "alert");
        alert.textContent = text;
        region.appendChild(alert);
        window.setTimeout(function () {
            alert.remove();
        }, DISMISS_AFTER_MS);
    }

    function bind() {
        if (document.getElementById("setup-wizard")) {
            return;
        }
        document.body.addEventListener("htmx:responseError", function () {
            show(message("error-server", "Der Server hat die Anfrage abgelehnt."));
        });
        document.body.addEventListener("htmx:sendError", function () {
            show(message("error-network", "Keine Verbindung zum Geraet."));
        });
    }

    document.addEventListener("DOMContentLoaded", bind);
})();
