# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - NetworkService.

WLAN- und Netzwerkverwaltung ausschliesslich ueber NetworkManager
(nmcli). Es werden keine Dateien wie /etc/wpa_supplicant.conf
bearbeitet. Alle nmcli-Fehler werden in verstaendliche Meldungen
uebersetzt.
"""

import os
import subprocess
from typing import Any

from app.constants import (
    NMCLI_BINARY,
    NMCLI_TIMEOUT_SECONDS,
    WPA_PSK_MAX_LENGTH,
    WPA_PSK_MIN_LENGTH,
)
from app.exceptions import NetworkError, WifiError
from app.logger import KioskLogger

WIFI_CONNECTION_TYPE: str = "802-11-wireless"


def split_terse_line(line: str) -> list[str]:
    """Zerlegt eine nmcli-Terse-Zeile unter Beachtung von Escapes.

    nmcli maskiert Doppelpunkte in Werten mit einem Backslash.

    Args:
        line:
            Eine Ausgabezeile im Terse-Format.

    Returns:
        Liste der Feldwerte ohne Maskierung.
    """
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    fields.append("".join(current))
    return fields


class NetworkService:
    """WLAN-Verwaltung ueber NetworkManager.

    Args:
        logger:
            Logger fuer alle Netzwerkereignisse.
    """

    def __init__(self, logger: KioskLogger) -> None:
        self._logger = logger

    def scan(self) -> list[dict[str, Any]]:
        """Sucht alle verfuegbaren WLAN-Netzwerke.

        Returns:
            Netzwerke mit ssid, signal, security, frequency und
            in_use, sortiert nach bester Signalstaerke.

        Raises:
            NetworkError
        """
        output = self._run(
            [
                "-t",
                "-f",
                "IN-USE,SSID,SIGNAL,SECURITY,FREQ",
                "device",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ]
        )
        networks: dict[str, dict[str, Any]] = {}
        for line in output.splitlines():
            fields = split_terse_line(line)
            if len(fields) < 5 or not fields[1]:
                continue
            ssid = fields[1]
            network: dict[str, Any] = {
                "in_use": fields[0] == "*",
                "ssid": ssid,
                "signal": int(fields[2]) if fields[2].isdigit() else 0,
                "security": fields[3] or "-",
                "frequency": fields[4],
            }
            known = networks.get(ssid)
            if known is None or int(network["signal"]) > int(known["signal"]):
                networks[ssid] = network
        result = sorted(networks.values(), key=lambda n: -int(n["signal"]))
        self._logger.info(f"WLAN-Scan: {len(result)} Netzwerke gefunden.")
        return result

    def connect(self, ssid: str, password: str = "") -> None:
        """Verbindet den Raspberry Pi mit einem WLAN.

        Mit Passwort wird zuerst ein dauerhaftes Verbindungsprofil
        angelegt oder aktualisiert (Passwort systemweit im Profil,
        automatische Verbindung aktiv) und dieses anschliessend
        aktiviert. Damit kennt das Geraet das Passwort auch nach
        einem Neustart. Schlaegt die Aktivierung eines dabei neu
        angelegten Profils fehl, wird es wieder entfernt.

        Args:
            ssid:
                Name des WLANs.

            password:
                WLAN-Passwort, leer fuer offene Netzwerke.

        Raises:
            WifiError
            NetworkError
        """
        if not ssid:
            raise WifiError("Es wurde kein WLAN ausgewaehlt.", reason="not_found")
        if not password:
            try:
                self._run(["device", "wifi", "connect", ssid])
            except NetworkError as error:
                raise self._map_connect_error(ssid, str(error)) from error
            self._require_ip(ssid)
            self._logger.info(f"Mit WLAN verbunden: {ssid}")
            return
        created = self.save_profile(ssid, password)
        try:
            self._run(["connection", "up", "id", ssid])
        except NetworkError as error:
            if created:
                try:
                    self.delete(ssid)
                except NetworkError:
                    self._logger.warning(
                        f"Fehlgeschlagenes Profil '{ssid}' konnte nicht "
                        "entfernt werden."
                    )
            raise self._map_connect_error(ssid, str(error)) from error
        self._require_ip(ssid)
        self._logger.info(f"Mit WLAN verbunden: {ssid}")

    def save_profile(self, ssid: str, password: str, priority: int = 0) -> bool:
        """Speichert ein WLAN-Profil dauerhaft mit Passwort.

        Das Passwort landet systemweit im NetworkManager-Profil
        (psk-flags 0), die automatische Verbindung wird aktiviert
        und die Prioritaet gesetzt. Ein vorhandenes Profil gleichen
        Namens wird aktualisiert statt dupliziert.

        Args:
            ssid:
                Name des WLANs.

            password:
                WLAN-Passwort (WPA-PSK, 8 bis 63 Zeichen).

            priority:
                Prioritaet der automatischen Verbindung.

        Returns:
            True, wenn das Profil neu angelegt wurde.

        Raises:
            WifiError
            NetworkError
        """
        if not ssid:
            raise WifiError("Es wurde kein WLAN ausgewaehlt.", reason="not_found")
        if not WPA_PSK_MIN_LENGTH <= len(password) <= WPA_PSK_MAX_LENGTH:
            raise WifiError(
                "Das WLAN-Passwort muss 8 bis 63 Zeichen lang sein.",
                reason="invalid_password",
            )
        settings = [
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            password,
            "wifi-sec.psk-flags",
            "0",
            "connection.autoconnect",
            "yes",
            "connection.autoconnect-priority",
            str(priority),
        ]
        created = ssid not in self.saved()
        try:
            if created:
                self._run(
                    [
                        "connection",
                        "add",
                        "type",
                        "wifi",
                        "ifname",
                        "*",
                        "con-name",
                        ssid,
                        "ssid",
                        ssid,
                        *settings,
                    ]
                )
            else:
                self._run(["connection", "modify", "id", ssid, *settings])
        except NetworkError as error:
            raise self._map_connect_error(ssid, str(error)) from error
        self._logger.info(
            f"WLAN-Profil dauerhaft gespeichert: {ssid} "
            f"(automatische Verbindung, Prioritaet {priority})."
        )
        return created

    def set_autoconnect(self, ssid: str, priority: int) -> None:
        """Aktiviert die automatische Verbindung eines Profils.

        Args:
            ssid:
                Name des gespeicherten Profils.

            priority:
                Prioritaet der automatischen Verbindung.

        Raises:
            WifiError
            NetworkError
        """
        if ssid not in self.saved():
            raise WifiError(
                f"Fuer '{ssid}' ist kein gespeichertes Profil vorhanden.",
                reason="not_found",
            )
        self._run(
            [
                "connection",
                "modify",
                "id",
                ssid,
                "connection.autoconnect",
                "yes",
                "connection.autoconnect-priority",
                str(priority),
            ]
        )
        self._logger.info(
            f"Automatische Verbindung fuer '{ssid}' aktiviert "
            f"(Prioritaet {priority})."
        )

    def _require_ip(self, ssid: str) -> None:
        """Prueft, ob das WLAN eine IPv4-Adresse vergeben hat.

        Args:
            ssid:
                Name des WLANs (fuer die Fehlermeldung).

        Raises:
            WifiError
        """
        if not self.ip():
            raise WifiError(
                f"Keine IP-Adresse im WLAN '{ssid}' erhalten.", reason="no_ip"
            )

    def connect_saved(self, ssid: str) -> None:
        """Verbindet mit einem bereits gespeicherten WLAN-Profil.

        Das Passwort wird nicht benoetigt: NetworkManager kennt es
        aus dem gespeicherten Profil. PiKiosk Pro speichert selbst
        keine WLAN-Passwoerter.

        Args:
            ssid:
                Name des gespeicherten Profils.

        Raises:
            WifiError
            NetworkError
        """
        if not ssid:
            raise WifiError("Es ist kein Standard-WLAN hinterlegt.", reason="not_found")
        if ssid not in self.saved():
            raise WifiError(
                f"Fuer '{ssid}' ist kein gespeichertes Profil vorhanden.",
                reason="not_found",
            )
        try:
            self._run(["connection", "up", "id", ssid])
        except NetworkError as error:
            raise self._map_connect_error(ssid, str(error)) from error
        self._logger.info(f"Mit gespeichertem WLAN verbunden: {ssid}")

    def disconnect(self) -> None:
        """Trennt die aktive WLAN-Verbindung.

        Raises:
            NetworkError
        """
        device = self._wifi_device()
        self._run(["device", "disconnect", device])
        self._logger.info("WLAN-Verbindung getrennt.")

    def current(self) -> dict[str, Any] | None:
        """Liefert das aktuell verbundene WLAN.

        Returns:
            Netzwerkdaten des aktiven WLANs oder None.

        Raises:
            NetworkError
        """
        output = self._run(
            ["-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi"]
        )
        for line in output.splitlines():
            fields = split_terse_line(line)
            if len(fields) >= 4 and fields[0] == "yes" and fields[1]:
                return {
                    "ssid": fields[1],
                    "signal": int(fields[2]) if fields[2].isdigit() else 0,
                    "security": fields[3] or "-",
                }
        return None

    def saved(self) -> list[str]:
        """Listet alle gespeicherten WLAN-Profile auf.

        Returns:
            Namen der gespeicherten WLAN-Verbindungen.

        Raises:
            NetworkError
        """
        output = self._run(["-t", "-f", "NAME,TYPE", "connection", "show"])
        profiles: list[str] = []
        for line in output.splitlines():
            fields = split_terse_line(line)
            if len(fields) >= 2 and fields[1] == WIFI_CONNECTION_TYPE:
                profiles.append(fields[0])
        return profiles

    def delete(self, profile: str) -> None:
        """Loescht ein gespeichertes WLAN-Profil.

        Args:
            profile:
                Name des Verbindungsprofils.

        Raises:
            NetworkError
        """
        self._run(["connection", "delete", profile])
        self._logger.info(f"WLAN-Profil geloescht: {profile}")

    def ip(self) -> str:
        """Liefert die IPv4-Adresse des WLAN-Geraets.

        Returns:
            IPv4-Adresse ohne Praefixlaenge oder leer.

        Raises:
            NetworkError
        """
        address = self._device_field("IP4.ADDRESS")
        return address.split("/", 1)[0] if address else ""

    def gateway(self) -> str:
        """Liefert das IPv4-Gateway des WLAN-Geraets.

        Returns:
            Gateway-Adresse oder leer.

        Raises:
            NetworkError
        """
        return self._device_field("IP4.GATEWAY")

    def dns(self) -> list[str]:
        """Liefert die konfigurierten DNS-Server.

        Returns:
            Liste der DNS-Adressen.

        Raises:
            NetworkError
        """
        return self._device_fields("IP4.DNS")

    def mac(self) -> str:
        """Liefert die MAC-Adresse des WLAN-Geraets.

        Returns:
            MAC-Adresse oder leer.

        Raises:
            NetworkError
        """
        return self._device_field("GENERAL.HWADDR")

    def signal(self) -> int:
        """Liefert die Signalstaerke des aktiven WLANs.

        Returns:
            Signalstaerke in Prozent, 0 ohne Verbindung.

        Raises:
            NetworkError
        """
        active = self.current()
        return int(active["signal"]) if active else 0

    def _run(self, arguments: list[str]) -> str:
        """Fuehrt einen nmcli-Befehl aus.

        Args:
            arguments:
                nmcli-Argumente.

        Returns:
            Standardausgabe des Befehls.

        Raises:
            NetworkError
        """
        environment = os.environ.copy()
        environment["LC_ALL"] = "C"
        try:
            result = subprocess.run(
                [NMCLI_BINARY, *arguments],
                capture_output=True,
                text=True,
                timeout=NMCLI_TIMEOUT_SECONDS,
                check=False,
                env=environment,
            )
        except FileNotFoundError as error:
            raise NetworkError(
                "NetworkManager (nmcli) ist nicht installiert."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise NetworkError("Zeitueberschreitung bei nmcli.") from error
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            raise NetworkError(details or "nmcli meldete einen Fehler.")
        return result.stdout

    def _wifi_device(self) -> str:
        """Ermittelt das erste WLAN-Geraet des Systems.

        Returns:
            Geraetename des WLAN-Adapters.

        Raises:
            NetworkError
        """
        output = self._run(["-t", "-f", "DEVICE,TYPE", "device"])
        for line in output.splitlines():
            fields = split_terse_line(line)
            if len(fields) >= 2 and fields[1] == "wifi":
                return fields[0]
        raise NetworkError("Kein WLAN-Geraet gefunden.")

    def _device_fields(self, field: str) -> list[str]:
        """Liest alle Werte eines Feldes vom WLAN-Geraet.

        Args:
            field:
                nmcli-Feldname, zum Beispiel IP4.DNS.

        Returns:
            Alle Werte des Feldes.

        Raises:
            NetworkError
        """
        device = self._wifi_device()
        output = self._run(["-t", "-f", field, "device", "show", device])
        values: list[str] = []
        for line in output.splitlines():
            fields = split_terse_line(line)
            if len(fields) < 2 or not fields[0].startswith(field):
                continue
            value = ":".join(fields[1:])
            if value:
                values.append(value)
        return values

    def _device_field(self, field: str) -> str:
        """Liest den ersten Wert eines Feldes vom WLAN-Geraet.

        Args:
            field:
                nmcli-Feldname.

        Returns:
            Erster Wert des Feldes oder leer.

        Raises:
            NetworkError
        """
        values = self._device_fields(field)
        return values[0] if values else ""

    def _map_connect_error(self, ssid: str, details: str) -> WifiError:
        """Uebersetzt nmcli-Fehler in verstaendliche WLAN-Fehler.

        Args:
            ssid:
                Name des WLANs.

            details:
                Fehlertext von nmcli.

        Returns:
            Ein WifiError mit maschinenlesbarem Grund.
        """
        lowered = details.lower()
        if "not authorized" in lowered or "permission denied" in lowered:
            reason = "not_authorized"
        elif (
            "secrets were required" in lowered or "802-11-wireless-security" in lowered
        ):
            reason = "wrong_password"
        elif "no network with ssid" in lowered or "not found" in lowered:
            reason = "not_found"
        elif "timeout" in lowered or "zeitueberschreitung" in lowered:
            reason = "timeout"
        else:
            reason = "generic"
        self._logger.error(f"WLAN-Verbindung zu '{ssid}' fehlgeschlagen: {details}")
        return WifiError(
            f"Verbindung mit '{ssid}' fehlgeschlagen: {details}", reason=reason
        )
