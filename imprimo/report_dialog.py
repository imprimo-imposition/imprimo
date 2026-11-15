"""Help → Report a problem: the user's description plus version, system and settings,
copied to the clipboard or opened as a prefilled GitHub issue. Nothing is sent by itself."""
from __future__ import annotations

import dataclasses
import datetime
import os
import platform
import sys
from urllib.parse import urlencode

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from . import APP_NAME, __version__
from .about import REPO_URL, component_versions
from .core import Settings, to_mm
from .i18n import get_language, t

ISSUE_TEMPLATE = "bug_report.yml"
URL_LIMIT = 6000          # GitHub refuses very long URLs; the rest stays in the clipboard
LOG_TAIL = 3000           # characters of the error log that are attached
LOG_MAX_AGE = 14          # days – an older error log is not attached


def log_path() -> str:
    """Where main.py / the excepthook write unhandled errors."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Imprimo", "imprimo-chyba.log")


def recent_log() -> tuple[str, str] | None:
    """(modified time, last part of the error log) when there is a recent one."""
    p = log_path()
    try:
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p))
        if (datetime.datetime.now() - mtime).days > LOG_MAX_AGE:
            return None
        with open(p, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    text = text.strip()
    return (mtime.strftime("%Y-%m-%d %H:%M"), text[-LOG_TAIL:]) if text else None


def system_name() -> str:
    machine = platform.machine()
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]} ({machine})"
    if sys.platform == "win32":
        rel, ver, *_ = platform.win32_ver()
        return f"Windows {rel} ({ver}, {machine})"
    try:
        name = platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
    except OSError:
        name = "Linux"
    return f"{name} ({machine}, {os.environ.get('XDG_SESSION_TYPE', '?')})"


def changed_settings(s: Settings) -> str:
    """Settings that differ from the defaults, “name=value, …”."""
    base = Settings()
    out = []
    for f in dataclasses.fields(Settings):
        v = getattr(s, f.name)
        if v != getattr(base, f.name):
            out.append(f"{f.name}={v:g}" if isinstance(v, float) else f"{f.name}={v}")
    return ", ".join(out) or "–"


def info_text(win, with_settings=True, with_name=False, with_log=True) -> str:
    lines = [f"{APP_NAME} {__version__}",
             f"System: {system_name()}",
             component_versions()]
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        g = screen.geometry()
        lines.append(f"Screen: {g.width()}×{g.height()} @{screen.devicePixelRatio():g}x · "
                     f"language {get_language()}")
    if win is not None and getattr(win, "src", None) is not None:
        infos = getattr(win, "infos", None) or []
        name = os.path.basename(win.path) if with_name else "(name hidden)"
        size = (f"{to_mm(infos[0].vis_w):.1f} × {to_mm(infos[0].vis_h):.1f} mm"
                if infos else "?")
        prof = getattr(win, "profile", None)
        std = (prof.pdfx or prof.pdfa or "no PDF/X") if prof is not None else "?"
        creator = prof.app() if prof is not None else ""
        lines.append(f"File: {name} · {len(win.src.pages)} PDF pages · {size} · {std}"
                     + (f" · {creator}" if creator else ""))
    if with_settings and win is not None:
        try:
            s = win.read_settings()
            lines.append(f"Mode: {s.mode}")
            lines.append(f"Settings: {changed_settings(s)}")
            plan = getattr(win, "plan", None)
            if plan is not None:
                lines.append(f"Result: {plan.summary(s)}")
                if plan.warnings:
                    lines.append("Warnings: " + " | ".join(plan.warnings))
        except Exception as e:                       # the report must never fail
            lines.append(f"Settings: ({e})")
    if with_log:
        log = recent_log()
        if log:
            lines.append(f"\nLast error ({log[0]}):\n{log[1]}")
    return "\n".join(lines)


class ReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.win = parent
        self.setWindowTitle(t("report_title"))
        self.resize(620, 620)
        lay = QVBoxLayout(self)
        intro = QLabel(t("report_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        lay.addWidget(QLabel(f"<b>{t('report_what')}</b>"))
        self.what = QPlainTextEdit()
        self.what.setPlaceholderText(t("report_what_ph"))
        self.what.setMinimumHeight(110)
        lay.addWidget(self.what)

        self.with_settings = QCheckBox(t("report_settings"))
        self.with_settings.setChecked(True)
        self.with_name = QCheckBox(t("report_name"))
        self.with_name.setToolTip(t("report_name_tip"))
        self.with_log = QCheckBox(t("report_log"))
        has_log = recent_log() is not None
        self.with_log.setChecked(has_log)
        self.with_log.setVisible(has_log)
        for c in (self.with_settings, self.with_name, self.with_log):
            c.toggled.connect(self._update)
            lay.addWidget(c)

        lay.addWidget(QLabel(f"<b>{t('report_info')}</b>"))
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setStyleSheet("font-family: monospace; font-size: 11px")
        lay.addWidget(self.info, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        hint = QLabel(t("report_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        lay.addWidget(hint)

        btns = QDialogButtonBox()
        copy = QPushButton(t("report_copy"))
        copy.clicked.connect(self.copy)
        gh = QPushButton(t("report_github"))
        gh.clicked.connect(self.github)
        btns.addButton(copy, QDialogButtonBox.ActionRole)
        btns.addButton(gh, QDialogButtonBox.ActionRole)
        btns.addButton(t("close"), QDialogButtonBox.RejectRole)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._update()

    def _info(self) -> str:
        return info_text(self.win, self.with_settings.isChecked(), self.with_name.isChecked(),
                         self.with_log.isChecked())

    def _update(self, *_):
        self.info.setPlainText(self._info())

    def full_text(self) -> str:
        what = self.what.toPlainText().strip() or "–"
        return f"{what}\n\n---\n{self._info()}"

    def copy(self):
        QGuiApplication.clipboard().setText(self.full_text())
        self.status.setText(t("report_copied"))

    def github(self):
        what = self.what.toPlainText().strip()
        info = self._info()
        title = (what.splitlines()[0][:80] if what else t("report_default_title"))
        params = {"template": ISSUE_TEMPLATE, "title": title, "description": what, "system": info}
        url = f"{REPO_URL}/issues/new?{urlencode(params)}"
        cut = False
        while len(url) > URL_LIMIT and len(params["system"]) > 200:
            cut = True                              # keep the description, shorten the info
            params["system"] = params["system"][:int(len(params["system"]) * 0.8)].rstrip("\n…") + "\n…"
            url = f"{REPO_URL}/issues/new?{urlencode(params)}"
        QGuiApplication.clipboard().setText(self.full_text())
        QDesktopServices.openUrl(QUrl(url))
        self.status.setText(t("report_opened_cut" if cut else "report_opened"))
