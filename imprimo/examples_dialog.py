"""Help → Sample files: the lessons in examples/, opened in Imprimo with their preset."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout)

from .about import REPO_URL
from .i18n import get_language, t

# (lesson, main PDF, preset key)
LESSONS = (
    ("01", "01_vizitky_90x50_obojstranne.pdf", "preset_cards"),
    ("02", "02_vizitka_bez_spadavky.pdf", "preset_cards_1s"),
    ("03", "03_pozvanka_A5_na_polovicu.pdf", "preset_invite"),
    ("04", "04_DL_skladacka_zavinovacia.pdf", "preset_dl"),
    ("05", "05_brozura_A5_12_stran.pdf", "preset_booklet"),
    ("06", "06_vstupenky_cut_and_stack.pdf", "preset_tickets"),
    ("07", "07_vizitka_s_lakom.pdf", "preset_cards_1s"),
    ("08", "08_chybne_pdf_na_preflight.pdf", None),
    ("09", "09_plagat_A2.pdf", "preset_poster"),
    ("10", "10_vizitky_jana.pdf", "preset_gang_cards"),
)


def examples_dir() -> str | None:
    """examples/ next to the imprimo package (source tree, app folder of the packages)."""
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.join(os.path.dirname(here), "examples"),
              os.path.join(os.path.dirname(os.path.dirname(here)), "examples")):
        if os.path.isdir(d):
            return d
    return None


def guide_url() -> str:
    name = "CITAJ-MA.md" if get_language() == "sk" else "README.md"
    return f"{REPO_URL}/blob/main/examples/{name}"


class ExamplesDialog(QDialog):
    """Lists the lessons; “Open in Imprimo” loads the PDF and applies its preset."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.dir = examples_dir()
        self.setWindowTitle(t("ex_title"))
        self.resize(620, 470)
        lay = QVBoxLayout(self)
        intro = QLabel(t("ex_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSpacing(3)
        for num, pdf, _preset in LESSONS:
            it = QListWidgetItem(f"{num}  {t(f'ex_{num}')}\n      {t(f'ex_{num}_d')}")
            ok = self.dir is not None and os.path.isfile(os.path.join(self.dir, pdf))
            if not ok:
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _i: self.open_lesson())
        lay.addWidget(self.list, 1)

        if self.dir is None:
            miss = QLabel(t("ex_missing"))
            miss.setWordWrap(True)
            lay.addWidget(miss)

        bb = QDialogButtonBox()
        self.open_btn = QPushButton(t("ex_open"))
        self.open_btn.setDefault(True)
        self.open_btn.setEnabled(self.dir is not None)
        self.open_btn.clicked.connect(self.open_lesson)
        guide = QPushButton(t("ex_guide"))
        guide.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(guide_url())))
        folder = QPushButton(t("ex_folder"))
        folder.setEnabled(self.dir is not None)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.dir)))
        for b in (self.open_btn, guide, folder):
            bb.addButton(b, QDialogButtonBox.ActionRole)
        close = bb.addButton(QDialogButtonBox.Close)
        close.setText(t("close"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def open_lesson(self):
        r = self.list.currentRow()
        if self.dir is None or not 0 <= r < len(LESSONS):
            return
        num, pdf, preset = LESSONS[r]
        self.accept()
        self.win.open_lesson(os.path.join(self.dir, pdf), preset)
