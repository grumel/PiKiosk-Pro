# FAQ – Häufige Fragen

**Welche Hardware wird unterstützt?**
Raspberry Pi 4 (empfohlen 4 GB oder 8 GB) mit Raspberry Pi OS
Desktop 64 Bit.

**Wie erreiche ich die Verwaltungsoberfläche?**
Im lokalen Netzwerk unter `http://<ip-des-geraets>:8080/login`.
Die IP-Adresse zeigt die Statusseite bzw. der Setup-Wizard an.

**Ich habe das Administratorpasswort vergessen. Was nun?**
Es gibt keinen Wiederherstellungsweg über die Oberfläche (Passwörter
sind nur als bcrypt-Hash gespeichert). Mit Zugriff auf die SD-Karte:
`config/users.db` löschen und in `config/config.json` den Wert
`"first_start": true` setzen – beim nächsten Start läuft der
Setup-Wizard erneut. Alternativ eine Sicherung mit bekanntem
Passwort wiederherstellen.

**Kann der Kiosk ohne Internet betrieben werden?**
Ja. Alle Assets (Bootstrap, HTMX) liegen lokal. Es ist nur die
konfigurierte Kiosk-URL erreichbar zu halten – auch eine URL im
lokalen Netz ist möglich.

**Wie ändere ich die angezeigte Webseite?**
Im Dashboard über die Kachel „Kiosk-URL" (Testen, dann Speichern)
oder per API (`PUT /api/settings`). Ein laufender Browser startet
automatisch mit der neuen URL.

**Warum wird meine URL beim Prüfen abgelehnt?**
Gültig sind nur http/https-Adressen, die innerhalb von 5 Sekunden
mit HTTP 200, 301 oder 302 antworten. Interne Seiten mit
Anmeldepflicht, die z. B. 401 liefern, werden abgelehnt.

**Startet der Browser nach einem Absturz neu?**
Ja, der Watchdog startet einen abgestürzten Chromium automatisch
neu – maximal 3-mal in 60 Sekunden, danach meldet er einen Fehler
(Dashboard-Badge und Watchdoglog). Ein vom Administrator bewusst
gestoppter Browser wird nicht neu gestartet.

**Wie sichere ich die Konfiguration?**
Dashboard-Kachel „Sicherung" → „Sicherung erstellen". Die ZIP-Datei
enthält Konfiguration und Benutzerkonten und lässt sich
herunterladen, hochladen oder per USB-Stick auf ein anderes Gerät
übertragen (Datei auf dem Stick: `PiKiosk_Backup*.zip`).

**Kann ich den Kiosk ganz ohne Internet betreiben?**
Ja. Kiosk-URL auf eine lokale Adresse setzen, in der Kachel
„Überwachung" die Verbindungsprüfung auf „Kiosk-URL erreichbar"
stellen (sonst meldet das Gerät dauerhaft „Offline") und in der
Kachel „Aktualisierung" die Updatequelle auf „Lokale Quelle" mit der
Adresse eines Webservers im Netz umstellen. Details in
[Administration.md](Administration.md).

**Wie stelle ich eine lokale Updatequelle bereit?**
Ein beliebiger Webserver im Netz genügt. Dort `manifest.json`
(`version`, `archive`, `sha256` – die Prüfsumme des Pakets aus
`sha256sum <paket>` – und optional `notes`) und das Paket ablegen –
mehr braucht es nicht. Alle Geräte holen sich das Update von dort.

**Wie aktualisiere ich PiKiosk Pro?**
Dashboard-Kachel „Aktualisierung" → „Nach Update suchen" (lädt das
neueste GitHub-Release) oder ein Update-Paket hochladen. Vor jedem
Update wird automatisch eine Sicherung erstellt; „Rollback" stellt
den vorherigen Stand wieder her.

**Werden mehrere Sprachen unterstützt?**
Ja, Deutsch und Englisch – umschaltbar im Setup-Wizard und im
Dashboard (Kachel „Darstellung"). Weitere Sprachen lassen sich als
`config/language_<code>.json` ergänzen.

**Sendet PiKiosk Pro Daten nach außen?**
Nein. Keine Telemetrie, keine Cloud-Pflicht; alle Daten bleiben auf
dem Gerät. Nach außen kommuniziert das System nur für die
konfigurierten Zwecke (Kiosk-URL, URL-Prüfung, GitHub-Updates).

**Kann ich mehrere Geräte zentral verwalten?**
Ja – mit PiKiosk Center. Auf einem beliebigen Rechner im Netz
`sudo ./install_center.sh` ausführen, Geräte dort aufnehmen und den
Zustand aller Kioske auf einer Seite sehen; Aktionen lassen sich für
eine Auswahl gleichzeitig ausführen (siehe [Center.md](Center.md)).
Die Geräte selbst bleiben unverändert – die Zentrale nutzt nur die
vorhandene [REST API](API.md).
