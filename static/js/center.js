/*
 * Copyright (c) 2026 Holger John
 * Lizenz: MIT License (siehe LICENSE)
 *
 * PiKiosk Center - Auswahl in der Flottenuebersicht.
 * Setzt das Kopfkaestchen "Alle auswaehlen" und haelt es mit den
 * einzelnen Geraetekaestchen synchron. Die Uebersicht wird per HTMX
 * ersetzt, daher wird nach jedem Austausch neu verdrahtet.
 */

(function () {
    "use strict";

    function deviceBoxes() {
        return Array.prototype.slice.call(
            document.querySelectorAll(".device-select:not([disabled])")
        );
    }

    function syncHeader(headerBox) {
        var boxes = deviceBoxes();
        var checked = boxes.filter(function (box) {
            return box.checked;
        });
        headerBox.checked = boxes.length > 0 && checked.length === boxes.length;
        headerBox.indeterminate =
            checked.length > 0 && checked.length < boxes.length;
    }

    function bind() {
        var headerBox = document.getElementById("select-all");
        if (!headerBox) {
            return;
        }
        headerBox.addEventListener("change", function () {
            deviceBoxes().forEach(function (box) {
                box.checked = headerBox.checked;
            });
        });
        deviceBoxes().forEach(function (box) {
            box.addEventListener("change", function () {
                syncHeader(headerBox);
            });
        });
        syncHeader(headerBox);
    }

    document.addEventListener("DOMContentLoaded", bind);
    document.body.addEventListener("htmx:afterSwap", bind);
})();
