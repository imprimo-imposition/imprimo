"""Window with the Imprimo spot color library and the .ase export."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog,
                               QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from . import APP_NAME
from .i18n import t
from .spots import SPOTS, write_ase

ASE_NAME = "Imprimo-spot-colors.ase"


def cmyk_to_qcolor(cmyk) -> QColor:
    c, m, y, k = (v / 100.0 for v in cmyk)
    return QColor.fromRgbF((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))


def _swatch(cmyk, size=18) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(cmyk_to_qcolor(cmyk))
    return QIcon(pm)


class SpotColorsDialog(QDialog):
    def __init__(self, parent=None, last_dir=""):
        super().__init__(parent)
        self.last_dir = last_dir or os.path.expanduser("~")
        self.setWindowTitle(t("spots_title"))
        self.resize(720, 470)
        lay = QVBoxLayout(self)

        intro = QLabel(t("spots_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        cols = [t("spots_col_name"), t("spots_col_use"), t("spots_col_cmyk"), t("spots_col_print")]
        self.table = QTableWidget(len(SPOTS), len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        for r, sp in enumerate(SPOTS):
            name = QTableWidgetItem(_swatch(sp.cmyk), sp.name)
            f = name.font()
            f.setBold(True)
            name.setFont(f)
            name.setToolTip(t("spots_aliases", names=", ".join(sp.aliases)))
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, QTableWidgetItem(t(f"spot_use_{sp.kind}")))
            self.table.setItem(r, 2, QTableWidgetItem(" / ".join(f"{v:g}" for v in sp.cmyk)))
            self.table.setItem(r, 3, QTableWidgetItem(t("spots_no") if sp.technical
                                                      else t("spots_yes")))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.selectRow(0)
        self.table.doubleClicked.connect(lambda _i: self.copy_name())
        lay.addWidget(self.table, 1)

        howto = QLabel(t("spots_howto"))
        howto.setWordWrap(True)
        howto.setTextFormat(Qt.RichText)
        lay.addWidget(howto)

        bb = QDialogButtonBox()
        copy = QPushButton(t("spots_copy"))
        copy.clicked.connect(self.copy_name)
        save = QPushButton(t("spots_save"))
        save.clicked.connect(self.save_ase)
        bb.addButton(copy, QDialogButtonBox.ActionRole)
        bb.addButton(save, QDialogButtonBox.ActionRole)
        close = bb.addButton(QDialogButtonBox.Close)
        close.setText(t("close"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected(self):
        r = self.table.currentRow()
        return SPOTS[r] if 0 <= r < len(SPOTS) else None

    def copy_name(self):
        sp = self.selected()
        if sp is not None:
            QGuiApplication.clipboard().setText(sp.name)
            self.setWindowTitle(f"{t('spots_title')} – {t('spots_copied', name=sp.name)}")

    def save_ase(self):
        path, _ = QFileDialog.getSaveFileName(self, t("spots_save"),
                                              os.path.join(self.last_dir, ASE_NAME),
                                              "Adobe Swatch Exchange (*.ase)")
        if not path:
            return
        if not path.lower().endswith(".ase"):
            path += ".ase"
        try:
            write_ase(path)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, t("save_fail", err=e))
            return
        QMessageBox.information(self, APP_NAME, t("spots_saved", path=path))
