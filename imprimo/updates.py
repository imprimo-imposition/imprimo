"""Checking for a newer version: reads docs/latest.json from the website.

Nothing about the user is sent – it's one plain download of a small public file.
The packaged runtimes have no Python SSL module, so when urllib can't do HTTPS the
system curl is used (part of Windows 10/11, macOS and common Linux systems).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from . import __version__

LATEST_URL = "https://imprimo-imposition.github.io/imprimo/latest.json"
WEBSITE = "https://imprimo-imposition.github.io/imprimo/"
TIMEOUT = 8


class UpdateError(Exception):
    pass


def _via_urllib(url, timeout):
    import ssl                       # noqa: F401 – missing in the packaged runtimes
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": f"Imprimo/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _curl() -> str | None:
    if sys.platform == "win32":
        p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
        if os.path.exists(p):
            return p
    return shutil.which("curl")


def _via_curl(url, timeout):
    exe = _curl()
    if not exe:
        raise UpdateError("curl not found")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    r = subprocess.run([exe, "-fsSL", "--max-time", str(timeout), "-A", f"Imprimo/{__version__}", url],
                       capture_output=True, timeout=timeout + 5, creationflags=flags)
    if r.returncode != 0:
        raise UpdateError((r.stderr or b"").decode("utf-8", "replace").strip() or f"curl {r.returncode}")
    return r.stdout


def fetch(url: str = LATEST_URL, timeout: int = TIMEOUT) -> dict:
    """The parsed latest.json; UpdateError when it can't be read."""
    errors = []
    for get in (_via_urllib, _via_curl):
        try:
            data = get(url, timeout)
            return json.loads(data.decode("utf-8"))
        except Exception as e:       # try the next way
            errors.append(f"{get.__name__[5:]}: {e}")
    raise UpdateError("; ".join(errors))


def version_tuple(v: str) -> tuple:
    out = []
    for part in str(v).strip().lstrip("v").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def is_newer(latest: str, current: str = __version__) -> bool:
    return version_tuple(latest) > version_tuple(current)


def platform_key() -> str:
    if sys.platform == "win32":
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def download_url(info: dict) -> str:
    return (info.get("downloads") or {}).get(platform_key()) or info.get("page") or WEBSITE


def notes(info: dict, lang: str) -> list[str]:
    n = info.get("notes") or {}
    return list(n.get(lang) or n.get("en") or [])
