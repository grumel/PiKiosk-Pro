/*
 * Copyright (c) 2026 Holger John
 * Lizenz: MIT License (siehe LICENSE)
 *
 * PiKiosk Pro - Passwortanzeige.
 * Ergaenzt jedes Passwortfeld um eine Schaltflaeche mit Auge, die
 * das Passwort sicht- und wieder unsichtbar macht. Die Beschriftung
 * kommt aus den Sprachdateien und steht als data-Attribut am body.
 * Nach jedem HTMX-Austausch werden neue Felder ergaenzt.
 */

(function () {
    "use strict";

    var SVG_NS = "http://www.w3.org/2000/svg";

    function createSvg(hidden) {
        var svg = document.createElementNS(SVG_NS, "svg");
        svg.setAttribute("viewBox", "0 0 16 16");
        svg.setAttribute("width", "16");
        svg.setAttribute("height", "16");
        svg.setAttribute("aria-hidden", "true");
        var ellipse = document.createElementNS(SVG_NS, "ellipse");
        ellipse.setAttribute("cx", "8");
        ellipse.setAttribute("cy", "8");
        ellipse.setAttribute("rx", "7");
        ellipse.setAttribute("ry", "4.2");
        ellipse.setAttribute("fill", "none");
        ellipse.setAttribute("stroke", "currentColor");
        ellipse.setAttribute("stroke-width", "1.2");
        svg.appendChild(ellipse);
        var pupil = document.createElementNS(SVG_NS, "circle");
        pupil.setAttribute("cx", "8");
        pupil.setAttribute("cy", "8");
        pupil.setAttribute("r", "2.2");
        pupil.setAttribute("fill", "currentColor");
        svg.appendChild(pupil);
        if (hidden) {
            var line = document.createElementNS(SVG_NS, "line");
            line.setAttribute("x1", "2.5");
            line.setAttribute("y1", "13.5");
            line.setAttribute("x2", "13.5");
            line.setAttribute("y2", "2.5");
            line.setAttribute("stroke", "currentColor");
            line.setAttribute("stroke-width", "1.4");
            svg.appendChild(line);
        }
        return svg;
    }

    function label(name) {
        return document.body.getAttribute("data-" + name) || "";
    }

    function render(button, input) {
        var sichtbar = input.type === "text";
        button.textContent = "";
        button.appendChild(createSvg(sichtbar));
        var text = sichtbar ? label("password-hide") : label("password-show");
        button.setAttribute("aria-label", text);
        button.setAttribute("title", text);
        button.setAttribute("aria-pressed", sichtbar ? "true" : "false");
    }

    function enhance(input) {
        if (input.dataset.passwordToggle === "1") {
            return;
        }
        input.dataset.passwordToggle = "1";
        var group = document.createElement("div");
        group.className = "input-group";
        input.parentNode.insertBefore(group, input);
        group.appendChild(input);
        var button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-outline-secondary";
        button.addEventListener("click", function () {
            input.type = input.type === "password" ? "text" : "password";
            render(button, input);
            input.focus();
        });
        render(button, input);
        group.appendChild(button);
    }

    function bind() {
        var felder = document.querySelectorAll('input[type="password"]');
        Array.prototype.forEach.call(felder, enhance);
    }

    document.addEventListener("DOMContentLoaded", bind);
    document.body.addEventListener("htmx:afterSwap", bind);
})();
