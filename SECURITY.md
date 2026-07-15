# Sicherheitsrichtlinie

## Unterstützte Versionen

| Version | Unterstützt |
| ------- | ----------- |
| 0.1.x   | Ja          |

## Sicherheitslücken melden

Bitte melde Sicherheitslücken vertraulich per E-Mail an den
Projektverantwortlichen und veröffentliche keine Details, bevor eine
korrigierte Version verfügbar ist. Du erhältst innerhalb von 7 Tagen
eine Rückmeldung.

## Grundsätze

- Passwörter werden ausschließlich als bcrypt-Hash gespeichert,
  niemals im Klartext.
- CSRF-Schutz, Session-Timeout und HttpOnly/SameSite-Cookies sind für
  die Weboberfläche vorgesehen.
- Die OWASP Top 10 werden bei der Entwicklung berücksichtigt.
- PiKiosk Pro sendet keine Telemetrie; alle Daten bleiben lokal auf
  dem Gerät.
