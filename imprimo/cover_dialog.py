"""Window “Cover with spine”: spine calculator, cover template, assembling the cover."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QSpinBox, QVBoxLayout)

from . import APP_NAME
from .core import ImposeError
from .cover import PAPERS, _num, caliper, crease_positions, prepare, spine_width, write_template
from .i18n import get_language, t


def _spin(val, lo, hi, step, dec, suffix):
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setSingleStep(step)
    sp.setValue(val)
    sp.setSuffix(suffix)
    sp.setKeyboardTracking(False)
    return sp


class CoverDialog(QDialog):
    def __init__(self, parent=None, w=148.0, h=210.0, pages=64, bleed=3.0, last_dir=""):
        super().__init__(parent)
        self.main = parent
        self.last_dir = last_dir or os.path.expanduser("~")
        self.setWindowTitle(t("cover_title"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        intro = QLabel(t("cover_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        f = QFormLayout()
        self.w = _spin(w, 20, 2000, 1, 1, " mm")
        self.h = _spin(h, 20, 2000, 1, 1, " mm")
        row = QHBoxLayout()
        row.addWidget(self.w)
        row.addWidget(QLabel("×"))
        row.addWidget(self.h)
        f.addRow(t("cover_size"), row)
        self.pages = QSpinBox()
        self.pages.setRange(4, 5000)
        self.pages.setSingleStep(2)
        self.pages.setValue(max(4, pages + pages % 2))
        self.pages.setKeyboardTracking(False)
        f.addRow(t("cover_pages"), self.pages)
        self.paper = QComboBox()
        for key, g, v in PAPERS:
            bulk = f"{v:g}".replace(".", ",") if get_language() == "sk" else f"{v:g}"
            self.paper.addItem(t(f"cover_paper_{key}", g=g, v=bulk), caliper(g, v))
        self.paper.addItem(t("cover_paper_custom"), None)
        f.addRow(t("cover_paper"), self.paper)
        self.cal = _spin(caliper(*PAPERS[0][1:]), 0.03, 1.0, 0.005, 3, " mm")
        self.cal.setToolTip(t("cover_caliper_tip"))
        f.addRow(t("cover_caliper"), self.cal)
        self.hinge = _spin(0, 0, 20, 0.5, 1, " mm")
        self.hinge.setToolTip(t("cover_hinge_tip"))
        f.addRow(t("cover_hinge"), self.hinge)
        self.bleed = _spin(bleed, 0, 10, 0.5, 1, " mm")
        f.addRow(t("cover_bleed"), self.bleed)
        lay.addLayout(f)

        self.result = QLabel()
        self.result.setWordWrap(True)
        lay.addWidget(self.result)
        check = QLabel(t("cover_caliper_tip") + " " + t("cover_check"))
        check.setWordWrap(True)
        check.setStyleSheet("color: gray")
        lay.addWidget(check)

        for title, text, label, slot in (
                (t("cover_step1"), t("cover_step1_hint"), t("cover_save_tpl"), self.save_template),
                (t("cover_step2"), t("cover_make_hint"), t("cover_make"), self.make_cover)):
            head = QLabel(f"<b>{title}</b>")
            lay.addWidget(head)
            hint = QLabel(text)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: gray")
            lay.addWidget(hint)
            b = QPushButton(label)
            b.clicked.connect(slot)
            lay.addWidget(b)
        close = QDialogButtonBox()
        close.addButton(t("close"), QDialogButtonBox.RejectRole)
        close.rejected.connect(self.reject)
        lay.addWidget(close)

        self.paper.currentIndexChanged.connect(self._paper_chosen)
        self.cal.valueChanged.connect(self._caliper_edited)
        for sp in (self.w, self.h, self.hinge, self.bleed):
            sp.valueChanged.connect(self._update)
        self.pages.valueChanged.connect(self._update)
        self._update()

    # ------------------------------------------------------------------
    def _paper_chosen(self, i):
        v = self.paper.itemData(i)
        if v is not None:
            self.cal.blockSignals(True)
            self.cal.setValue(v)
            self.cal.blockSignals(False)
        self._update()

    def _caliper_edited(self, v):
        if self.paper.itemData(self.paper.currentIndex()) is not None and \
                abs(self.paper.currentData() - v) > 1e-6:
            self.paper.blockSignals(True)
            self.paper.setCurrentIndex(self.paper.count() - 1)      # custom
            self.paper.blockSignals(False)
        self._update()

    def spine(self) -> float:
        return round(spine_width(self.pages.value(), self.cal.value()), 1)

    def _update(self, *_):
        s, w, h, b = self.spine(), self.w.value(), self.h.value(), self.bleed.value()
        cw = 2 * w + s
        self.result.setText(t("cover_result", s=_num(s), w=_num(cw), h=_num(h),
                              wb=_num(cw + 2 * b), hb=_num(h + 2 * b)))

    def _info(self):
        return t("cover_tpl_info", w=_num(self.w.value()), h=_num(self.h.value()),
                 s=_num(self.spine()), p=self.pages.value(), c=f"{self.cal.value():.3f}")

    # ------------------------------------------------------------------
    def save_template(self):
        name = t("cover_tpl_file", w=_num(self.w.value()), h=_num(self.h.value()),
                 s=_num(self.spine()))
        path, _ = QFileDialog.getSaveFileName(self, t("cover_save_tpl").rstrip("…"),
                                              os.path.join(self.last_dir, name), t("pdf_filter"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            write_template(path, self.w.value(), self.h.value(), self.spine(), self.bleed.value(),
                           self.hinge.value(), self._info())
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, t("save_fail", err=e))
            return
        self.last_dir = os.path.dirname(path)
        QMessageBox.information(self, APP_NAME, t("cover_saved_tpl", path=path))

    def make_cover(self):
        """Step 2: the designed cover → opened in Imprimo for imposing, creases set."""
        src, _ = QFileDialog.getOpenFileName(self, t("cover_open_title"), self.last_dir,
                                             t("pdf_open_filter"))
        if not src:
            return
        try:
            res = prepare(src, self.w.value(), self.h.value(), self.spine())
        except ImposeError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, t("save_fail", err=e))
            return
        self.last_dir = os.path.dirname(src)
        notes = list(res.warnings)
        if res.blank_spine:
            notes.append(t("cover_joined", name=os.path.basename(res.path)))
            notes.append(t("cover_blank_spine"))
        if notes:
            QMessageBox.information(self, APP_NAME, "\n\n".join(notes))
        pos = crease_positions(self.w.value(), res.spine_mm, self.hinge.value())
        self.accept()
        if self.main is not None:
            self.main.open_cover(res.path, pos, res.two_sided)
