"""Light and dark appearance (Fusion style, the same on every system)."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

THEMES = ("system", "light", "dark")
_mode = "system"
_hooked = False


def _dark_palette() -> QPalette:
    p = QPalette()
    c = QColor
    roles = {
        QPalette.Window: c("#2b2d31"),
        QPalette.WindowText: c("#e6e7ea"),
        QPalette.Base: c("#1f2124"),
        QPalette.AlternateBase: c("#27292d"),
        QPalette.ToolTipBase: c("#3a3d42"),
        QPalette.ToolTipText: c("#f0f0f0"),
        QPalette.Text: c("#e6e7ea"),
        QPalette.Button: c("#35383d"),
        QPalette.ButtonText: c("#e6e7ea"),
        QPalette.BrightText: c("#ff6b6b"),
        QPalette.Light: c("#4a4d53"),
        QPalette.Midlight: c("#3e4146"),
        QPalette.Mid: c("#2f3236"),
        QPalette.Dark: c("#18191b"),
        QPalette.Shadow: c("#0c0c0d"),
        QPalette.Highlight: c("#2f7de1"),
        QPalette.HighlightedText: c("#ffffff"),
        QPalette.Link: c("#6aa8ff"),
        QPalette.LinkVisited: c("#b28cff"),
        QPalette.PlaceholderText: c("#8a8d93"),
    }
    for role, color in roles.items():
        p.setColor(role, color)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("#6f7278"))
    p.setColor(QPalette.Disabled, QPalette.Base, c("#26282b"))
    p.setColor(QPalette.Disabled, QPalette.Button, c("#2e3034"))
    return p


def _linux_desktop_dark():
    """Asks the desktop directly (GNOME, KDE… via xdg-desktop-portal, then gsettings).
    Returns True / False, or None if it can't be determined."""
    import re
    import shutil
    import subprocess

    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        except Exception:
            return ""

    if shutil.which("gdbus"):
        for method in ("ReadOne", "Read"):
            out = run(["gdbus", "call", "--session", "--timeout", "1",
                       "--dest", "org.freedesktop.portal.Desktop",
                       "--object-path", "/org/freedesktop/portal/desktop",
                       "--method", f"org.freedesktop.portal.Settings.{method}",
                       "org.freedesktop.appearance", "color-scheme"])
            m = re.search(r"uint32 (\d+)", out)
            if m:
                v = int(m.group(1))       # 0 = no preference, 1 = dark, 2 = light
                if v in (1, 2):
                    return v == 1
                break
    if shutil.which("gsettings"):
        out = run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
        if "prefer-dark" in out:
            return True
        if "prefer-light" in out or "default" in out:
            return False
    return None


def _system_is_dark(app) -> bool:
    if sys.platform.startswith("linux"):
        v = _linux_desktop_dark()
        if v is not None:
            return v
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return app.palette().color(QPalette.Window).lightness() < 128


def is_dark() -> bool:
    return QApplication.instance().palette().color(QPalette.Window).lightness() < 128


_busy = False
_poll = None


def apply_theme(mode: str):
    """mode: system | light | dark"""
    global _mode, _hooked, _busy, _poll
    if _busy:
        return
    _busy = True
    try:
        app = QApplication.instance()
        _mode = mode if mode in THEMES else "system"
        hints = app.styleHints()
        dark = _system_is_dark(app) if _mode == "system" else _mode == "dark"

        # Qt 6.8+: colour scheme of the title bar / window decorations
        if hasattr(hints, "setColorScheme"):
            if _mode == "system" and not sys.platform.startswith("linux"):
                scheme = Qt.ColorScheme.Unknown          # macOS, Windows follow the system natively
            else:
                scheme = Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light
            try:
                hints.setColorScheme(scheme)
            except Exception:
                pass

        # palette first, then style: setStyle() re-polishes every widget with the new
        # palette, including those with a style sheet (section headers)
        app.setPalette(_dark_palette() if dark else QStyleFactory.create("Fusion").standardPalette())
        app.setStyle("Fusion")
        for w in app.allWidgets():
            if w.styleSheet():
                w.setStyleSheet(w.styleSheet())

        if not _hooked and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: _mode == "system" and apply_theme("system"))
            _hooked = True
        # Linux: the desktop doesn't always notify Qt – check every few seconds
        if sys.platform.startswith("linux") and _poll is None:
            from PySide6.QtCore import QTimer
            _poll = QTimer(app)
            _poll.setInterval(3000)
            _poll.timeout.connect(_check_system_change)
            _poll.start()
        for w in app.topLevelWidgets():
            w.update()
    finally:
        _busy = False


def _check_system_change():
    if _mode != "system":
        return
    app = QApplication.instance()
    if app is not None and _system_is_dark(app) != is_dark():
        apply_theme("system")
