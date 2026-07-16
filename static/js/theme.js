/*
 * Copyright (c) 2026 Holger John
 * Lizenz: MIT License (siehe LICENSE)
 *
 * PiKiosk Pro - Theme-Automatik.
 * Ist das Theme "auto" konfiguriert, folgt die Oberflaeche der
 * Systemeinstellung (prefers-color-scheme) und reagiert auf
 * Aenderungen zur Laufzeit.
 */

(function () {
    "use strict";

    var root = document.documentElement;
    if (root.getAttribute("data-theme-mode") !== "auto") {
        return;
    }
    var media = window.matchMedia("(prefers-color-scheme: dark)");

    function apply() {
        root.setAttribute("data-bs-theme", media.matches ? "dark" : "light");
    }

    apply();
    media.addEventListener("change", apply);
})();
