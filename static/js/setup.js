/*
 * Copyright (c) 2026 Holger John
 * Lizenz: MIT License (siehe LICENSE)
 *
 * PiKiosk Pro - Fehleranzeige im Einrichtungsassistenten.
 * Schlaegt ein HTMX-Request fehl (Server-Fehler oder keine
 * Verbindung), wird eine sichtbare Meldung eingeblendet, damit ein
 * Fehler niemals wie "es passiert nichts" wirkt. Die Texte kommen
 * aus den Sprachdateien und stehen als data-Attribute am Rahmen.
 */

(function () {
    "use strict";

    function wizard() {
        return document.getElementById("setup-wizard");
    }

    function message(name, fallback) {
        var frame = wizard();
        if (!frame) {
            return fallback;
        }
        return frame.getAttribute("data-" + name) || fallback;
    }

    function show(text) {
        var content = document.getElementById("step-content");
        if (!content) {
            return;
        }
        var alert = content.querySelector(".setup-error");
        if (!alert) {
            alert = document.createElement("div");
            alert.className = "alert alert-danger setup-error";
            alert.setAttribute("role", "alert");
            content.insertBefore(alert, content.firstChild);
        }
        alert.textContent = text;
    }

    function onResponseError() {
        show(message("error-server", "Der Server hat die Anfrage abgelehnt."));
    }

    function onSendError() {
        show(message("error-network", "Keine Verbindung zum Geraet."));
    }

    function onSubmit(event) {
        // Native Formularabsendung unterbinden: Chromium blockiert das
        // Absenden von Passwortfeldern ueber HTTP, wodurch scheinbar
        // nichts passiert. Stattdessen die htmx-Schaltflaeche ausloesen.
        event.preventDefault();
        var button = event.target.querySelector("[data-default-action]");
        if (button) {
            button.click();
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var frame = wizard();
        if (!frame) {
            return;
        }
        frame.addEventListener("htmx:responseError", onResponseError);
        frame.addEventListener("htmx:sendError", onSendError);
        frame.addEventListener("submit", onSubmit);
    });
})();
