# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Root-Helfer zum Setzen des Hostnamens.

Wird vom HostnameService ueber sudo aufgerufen und aktualisiert
/etc/hostname, /etc/hosts und den laufenden Hostnamen ueber
hostnamectl. Aufruf: hostname_apply.py <neuer-hostname>
"""

import re
import socket
import subprocess
import sys
from pathlib import Path

ETC_HOSTNAME = Path("/etc/hostname")
ETC_HOSTS = Path("/etc/hosts")
HOSTNAME_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,63}$")
HOSTNAMECTL_TIMEOUT_SECONDS = 20.0


def update_etc_hostname(hostname: str) -> None:
    """Schreibt den neuen Hostnamen nach /etc/hostname.

    Args:
        hostname:
            Neuer Hostname.
    """
    ETC_HOSTNAME.write_text(f"{hostname}\n", encoding="utf-8")


def update_etc_hosts(old_hostname: str, new_hostname: str) -> None:
    """Aktualisiert den 127.0.1.1-Eintrag in /etc/hosts.

    Args:
        old_hostname:
            Bisheriger Hostname.

        new_hostname:
            Neuer Hostname.
    """
    lines = ETC_HOSTS.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("127.0.1.1"):
            updated.append(f"127.0.1.1\t{new_hostname}")
            replaced = True
        elif old_hostname and f" {old_hostname}" in f" {line}":
            updated.append(line.replace(old_hostname, new_hostname))
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"127.0.1.1\t{new_hostname}")
    ETC_HOSTS.write_text("\n".join(updated) + "\n", encoding="utf-8")


def apply_hostnamectl(hostname: str) -> None:
    """Setzt den Hostnamen ueber hostnamectl.

    Args:
        hostname:
            Neuer Hostname.

    Raises:
        RuntimeError
    """
    result = subprocess.run(
        ["hostnamectl", "set-hostname", hostname],
        capture_output=True,
        text=True,
        timeout=HOSTNAMECTL_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "hostnamectl fehlgeschlagen")


def main(argv: list[str]) -> int:
    """Setzt den uebergebenen Hostnamen systemweit.

    Args:
        argv:
            Argumente ohne Programmnamen, erwartet den Hostnamen.

    Returns:
        Exit-Code des Programms.
    """
    if len(argv) != 1:
        print("Aufruf: hostname_apply.py <hostname>", file=sys.stderr)
        return 2
    hostname = argv[0]
    if not HOSTNAME_PATTERN.match(hostname):
        print("Ungueltiger Hostname.", file=sys.stderr)
        return 2
    old_hostname = socket.gethostname()
    try:
        update_etc_hostname(hostname)
        update_etc_hosts(old_hostname, hostname)
        apply_hostnamectl(hostname)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Hostname konnte nicht gesetzt werden: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
