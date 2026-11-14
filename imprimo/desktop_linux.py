"""Linux desktop integration: menu entry (.desktop) and icons for the current user.

GNOME/KDE on Wayland take an application's icon and name from its .desktop file,
so a portable app has to install one. Imprimo offers this on first start."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ICON_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)
APP_ID = "imprimo"


def data_home() -> str:
    return os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")


def desktop_path() -> str:
    return os.path.join(data_home(), "applications", f"{APP_ID}.desktop")


def exec_line() -> str:
    """Command for the Exec= key: the portable launcher if present, otherwise python + main.py."""
    launcher = os.environ.get("IMPRIMO_LAUNCHER")
    if launcher and os.path.exists(launcher):
        return f'"{launcher}" %f'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}" %f'


def installed_exec() -> str | None:
    try:
        with open(desktop_path(), encoding="utf-8") as f:
            for line in f:
                if line.startswith("Exec="):
                    return line[5:].strip()
    except OSError:
        return None
    return None


def needs_install() -> bool:
    return installed_exec() != exec_line()


def install() -> str:
    icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icon", "png")
    hicolor = os.path.join(data_home(), "icons", "hicolor")
    for s in ICON_SIZES:
        src = os.path.join(icon_dir, f"imprimo-{s}.png")
        if os.path.exists(src):
            dst = os.path.join(hicolor, f"{s}x{s}", "apps")
            os.makedirs(dst, exist_ok=True)
            shutil.copyfile(src, os.path.join(dst, f"{APP_ID}.png"))
    path = desktop_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join([
            "[Desktop Entry]",
            "Type=Application",
            "Name=Imprimo",
            "GenericName=PDF Imposition",
            "GenericName[sk]=Vyraďovanie PDF",
            "Comment=Imposition of print PDFs",
            "Comment[sk]=Vyraďovanie tlačových PDF",
            f"Exec={exec_line()}",
            f"Icon={APP_ID}",
            "Terminal=false",
            "Categories=Graphics;Publishing;",
            "MimeType=application/pdf;",
            f"StartupWMClass={APP_ID}",
            "Keywords=pdf;imposition;print;vyraďovanie;tlač;",
            ""]))
    for cmd in (["update-desktop-database", os.path.dirname(path)],
                ["gtk-update-icon-cache", "-q", "-t", hicolor]):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            pass
    return path


def uninstall():
    try:
        os.remove(desktop_path())
    except OSError:
        pass
    hicolor = os.path.join(data_home(), "icons", "hicolor")
    for s in ICON_SIZES:
        try:
            os.remove(os.path.join(hicolor, f"{s}x{s}", "apps", f"{APP_ID}.png"))
        except OSError:
            pass
