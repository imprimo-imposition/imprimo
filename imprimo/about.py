"""About dialog: version, licence (GPL-3.0-or-later), third-party notices."""
from __future__ import annotations

import os
import platform

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from . import APP_NAME, __version__
from .i18n import t
from .splash import app_icon

REPO_URL = "https://github.com/imprimo-imposition/imprimo"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

_HERE = os.path.dirname(os.path.abspath(__file__))


def find_doc(*names) -> str | None:
    """LICENSE / THIRD-PARTY-NOTICES.txt: next to main.py (source tree, app folder of
    the release packages) or one level up (top of the release zip)."""
    app_dir = os.path.dirname(_HERE)
    for d in (app_dir, os.path.dirname(app_dir)):
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


def component_versions() -> str:
    """One line with the versions that matter for bug reports."""
    parts = [f"Python {platform.python_version()}"]
    try:
        from PySide6 import __version__ as pyside
        from PySide6.QtCore import qVersion
        parts.append(f"Qt {qVersion()} (PySide6 {pyside})")
    except Exception:
        pass
    try:
        import pikepdf
        parts.append(f"pikepdf {pikepdf.__version__} (QPDF {pikepdf.__libqpdf_version__})")
    except Exception:
        pass
    try:
        from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO
        pdfium = str(getattr(PDFIUM_INFO, "version", PDFIUM_INFO)).split("@")[0]
        parts.append(f"pypdfium2 {PYPDFIUM_INFO.version} (PDFium {pdfium})")
    except Exception:
        pass
    parts.append(f"{platform.system()} {platform.machine()}")
    return " · ".join(parts)


class TextDialog(QDialog):
    """Read-only text (the licence or the third-party notices)."""

    def __init__(self, parent, title, path, missing_url):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 640)
        lay = QVBoxLayout(self)
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                path = None
        if path:
            view = QPlainTextEdit(text)
            view.setReadOnly(True)
            view.setLineWrapMode(QPlainTextEdit.NoWrap)
            view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
            lay.addWidget(view)
        else:
            msg = QLabel(t("about_missing", url=f"<a href='{missing_url}'>{missing_url}</a>"))
            msg.setWordWrap(True)
            msg.setOpenExternalLinks(True)
            lay.addWidget(msg)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(t("close"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about_title"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(18)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(96, 96))
        icon.setAlignment(Qt.AlignTop)
        top.addWidget(icon)
        head = QLabel(
            f"<div style='font-size:20pt; font-weight:600'>{APP_NAME}</div>"
            f"<div>{t('about_version', v=__version__)}</div>"
            f"<p>{t('about_desc')}</p>"
            f"<p>© Maxim Darák</p>"
            f"<p>{t('about_credits')}</p>")
        head.setWordWrap(True)
        head.setTextFormat(Qt.RichText)
        top.addWidget(head, 1)
        lay.addLayout(top)

        link = lambda url, text: f"<a href='{url}'>{text}</a>"
        body = QLabel(
            f"<p>{t('about_license', gpl=link(LICENSE_URL, 'GNU GPL v3.0'))}</p>"
            f"<p>{t('about_commercial')}</p>"
            f"<p>{t('about_repo', link=link(REPO_URL, 'github.com/imprimo-imposition/imprimo'))}</p>")
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setOpenExternalLinks(True)
        lay.addWidget(body)

        ver = QLabel(component_versions())
        ver.setWordWrap(True)
        grey = self.palette().color(QPalette.PlaceholderText).name()
        ver.setStyleSheet(f"color: {grey}; font-size: 9pt")
        ver.setTextInteractionFlags(Qt.TextSelectableByMouse)  # copy for bug reports
        lay.addWidget(ver)

        bb = QDialogButtonBox()
        lic = QPushButton(t("about_show_license"))
        lic.clicked.connect(self.show_license)
        notices = QPushButton(t("about_show_notices"))
        notices.clicked.connect(self.show_notices)
        bb.addButton(lic, QDialogButtonBox.ActionRole)
        bb.addButton(notices, QDialogButtonBox.ActionRole)
        close = bb.addButton(QDialogButtonBox.Close)
        close.setText(t("close"))
        close.setDefault(True)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def show_license(self):
        TextDialog(self, t("about_show_license"), find_doc("LICENSE", "LICENSE.txt"),
                   LICENSE_URL).exec()

    def show_notices(self):
        TextDialog(self, t("about_show_notices"), find_doc("THIRD-PARTY-NOTICES.txt"),
                   f"{REPO_URL}/blob/main/THIRD-PARTY-NOTICES.txt").exec()
