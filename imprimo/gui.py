"""User interface (PySide6)."""
from __future__ import annotations

import dataclasses
import math
import io
import json
import os
import sys
from collections import OrderedDict

import pikepdf
import pypdfium2 as pdfium
from PySide6.QtCore import QEvent, QLocale, QPointF, QRectF, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QImage,
                           QCursor, QKeySequence, QPainter, QPen, QShortcut)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QStackedWidget,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSpinBox,
                               QSplitter, QToolButton, QVBoxLayout, QWidget, QDialog,
                               QDialogButtonBox, QInputDialog, QListWidget)

from . import APP_NAME, __version__
from .core import (LAYER_KINDS, MODES, SHEET_PRESETS, ImposeError, Layer, spread_pages,
                   Settings, Source, analyze, build_plan, export_outputs, finalize,
                   layer_display_name, layer_source, output_paths, parse_range, render_sources,
                   resolve_export, mm, tile_name, GangJob, gang_letter,
                   render, to_mm)
from . import presets as presets_mod
from .about import REPO_URL, SUPPORT_URL
from .crease import PRESETS as CREASE_PRESETS, crease_spec, detect_any, format_positions, parse_positions
from .i18n import LANGUAGES, get_language, set_language, t
from .theme import THEMES, apply_theme, is_dark
from .pdfinfo import STANDARDS, detect_profile, icc_from_file, system_cmyk_profiles
from .preflight import evaluate, evaluate_layer, scan
from .preview import (PageRasters, PreviewSource, paint_numbers, paint_side, render_overlay,
                      sheet_to_widget)


def is_pdf(path: str) -> bool:
    """True for a PDF file, judged by its header, not its name.

    Exports without the .pdf extension (e.g. Affinity “test_v1”) must open too.
    The spec allows junk before “%PDF-” within the first 1024 bytes.
    """
    try:
        if not os.path.isfile(path):
            return False
        with open(path, "rb") as f:
            return b"%PDF-" in f.read(1024)
    except OSError:
        return False


def store() -> QSettings:
    return QSettings("Imprimo", "Imprimo")


def migrate_settings():
    """Migrates settings from the working name Vyraďovač (versions 0.1–0.2)."""
    new, old = store(), QSettings("Vyradovac", "Vyradovac")
    if new.allKeys() or not old.allKeys():
        return
    for k in old.allKeys():
        new.setValue(k, old.value(k))
    if old.contains("sheet_key"):
        new.setValue("sheet_key", old.value("sheet_key"))


PF_STYLE = {"ok": ("✓", "#2e9d4f"), "warn": ("⚠", "#c26a00"),
            "error": ("✗", "#d0342c"), "info": ("•", "#808080")}
CHOOSE = "__choose__"

CUSTOM = "custom"
# poster target sizes in mm (portrait); "custom" = scale in %
TILE_TARGETS = {"custom": None, "A3": (297, 420), "A2": (420, 594), "A1": (594, 841),
                "A0": (841, 1189), "B2": (500, 707), "B1": (707, 1000)}
FIT = "fit"
BASE_PX = 1800
ACCENT = QColor("#2f7de1")


# ============================================================================
# Zoom and pan – shared by the sheet view and the overview

class ZoomView(QWidget):
    """Zoom and pan controls shared by SheetView and OverviewView, so both views
    are used the same way (learnt once, works in both):

    * Ctrl/Cmd + wheel or pinch = zoom at the cursor; buttons −/+, Fit, 100 %
    * two-finger double tap = toggle zoom
    * drag with the left button, Space + drag or the middle button = pan

    Subclasses provide the geometry: has_content, scale, zoom_by, zoom_fit,
    _toggle_zoom, can_pan, pan_state, pan_apply; optionally click, wheel_scroll,
    drag_hint and idle_cursor."""

    zoomChanged = Signal()
    CLICK_SLOP = 4                       # px of movement that turns a click into a pan

    def __init__(self):
        super().__init__()
        self.space = False               # Space held = hand tool
        self.pan = None                  # (global start pos, pan_state()) while panning
        self.press = None                # (pos, global pos) of a left press, until it pans
        self.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

    # -- to implement in subclasses
    def has_content(self):
        return False

    def scale(self):
        """Current px per point."""
        return 1.0

    def zoom_by(self, factor, anchor: QPointF | None = None):
        pass

    def zoom_fit(self):
        pass

    def _toggle_zoom(self, pos):
        pass

    def can_pan(self):
        return False

    def pan_state(self):
        return None

    def pan_apply(self, state, d: QPointF):
        """Pans to `state` moved by the mouse movement d (px)."""

    def click(self, pos, release_pos):
        """Left click without movement."""

    def wheel_scroll(self, e):
        """Wheel without Ctrl/Cmd."""
        e.ignore()

    def drag_hint(self):
        """True when a plain left drag pans (shows the open hand)."""
        return False

    def idle_cursor(self):
        return None                      # None = default arrow

    # -- shared
    def actual_scale(self):
        """100 % scale – actual size on screen."""
        return self.logicalDpiX() / 72.0

    def percent(self):
        return round(self.scale() / self.actual_scale() * 100) if self.has_content() else 0

    def zoom_actual(self, anchor: QPointF | None = None):
        if self.has_content():
            self.zoom_by(self.actual_scale() / self.scale(), anchor)

    def _update_cursor(self):
        if self.pan is not None:
            self.setCursor(Qt.ClosedHandCursor)
        elif self.space or self.drag_hint():
            self.setCursor(Qt.OpenHandCursor)
        elif self.idle_cursor() is not None:
            self.setCursor(self.idle_cursor())
        else:
            self.unsetCursor()

    # Space = hand tool while the cursor is over the view (not while typing)
    def _typing(self):
        from PySide6.QtWidgets import QAbstractSpinBox, QLineEdit, QPlainTextEdit, QTextEdit
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit))

    def eventFilter(self, obj, e):
        et = e.type()
        if et in (QEvent.KeyPress, QEvent.KeyRelease) and e.key() == Qt.Key_Space:
            if not self.isVisible() or self._typing():
                return False
            if et == QEvent.KeyPress:
                if not self.space and self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                    self.space = True
                    self._update_cursor()
                return self.space                # also swallows auto-repeat
            if not e.isAutoRepeat() and self.space:
                self.space = False
                self._update_cursor()
                return True
        elif et == QEvent.ApplicationDeactivate and (self.space or self.pan is not None):
            self.space = False
            self.pan = self.press = None
            self._update_cursor()
        return False

    def wheelEvent(self, e):
        if not self.has_content():
            return
        if e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            dy = e.angleDelta().y()
            if dy:
                self.zoom_by(1.0015 ** dy, e.position())
            e.accept()
            return
        self.wheel_scroll(e)

    def event(self, e):
        if e.type() == QEvent.NativeGesture and self.has_content():
            if e.gestureType() == Qt.ZoomNativeGesture:
                self.zoom_by(1 + e.value(), e.position())
                return True
            if e.gestureType() == Qt.SmartZoomNativeGesture:
                self._toggle_zoom(e.position())
                return True
        return super().event(e)

    def mousePressEvent(self, e):
        if not self.has_content():
            return
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self.space):
            if self.can_pan():
                self.pan = (e.globalPosition(), self.pan_state())
                self._update_cursor()
            return
        if e.button() == Qt.LeftButton:
            self.press = (e.position(), e.globalPosition())

    def mouseMoveEvent(self, e):
        if self.press is not None and self.pan is None:
            d = e.globalPosition() - self.press[1]
            if abs(d.x()) + abs(d.y()) > self.CLICK_SLOP and self.can_pan():
                self.pan = (self.press[1], self.pan_state())
                self._update_cursor()
        if self.pan is not None:
            start, state = self.pan
            # global coordinates: the overview widget itself moves while its area scrolls
            self.pan_apply(state, e.globalPosition() - start)

    def mouseReleaseEvent(self, e):
        press, self.press = self.press, None
        if self.pan is not None:
            self.pan = None
            self._update_cursor()
            return
        if press is not None and e.button() == Qt.LeftButton:
            self.click(press[0], e.position())


# ============================================================================
# Sheet preview with zoom

class SheetView(ZoomView):
    """One sheet side; zoom and pan see ZoomView, double-click = zoom in / whole sheet.
    Pages come from cached bitmaps (see preview.py); when zoomed in, sharper
    bitmaps are rendered in the background and the marks are re-rendered sharply."""

    MAX_ZOOM = 16.0                      # 1600 % – for checking marks and bleed

    def __init__(self):
        super().__init__()
        self.pw = self.ph = 0.0
        self.painter_fn = None               # draws the pages: fn(painter, s2w, dpr, wanted, sync)
        self.rasters = None
        self.overlay_bytes = None            # marks / guides PDF (one page)
        self.base: QImage | None = None      # marks at base resolution
        self.base_ppt = 1.0                  # pixels per point in the base image
        self.hires: QImage | None = None
        self.hires_rect = QRectF()
        self.hires_key = None
        self.wanted = set()
        self.zoom: float | None = None       # px per point; None = whole sheet
        self.cx = self.cy = 0.0              # view centre in points (y from the top)
        self.message = t("drop_here")
        self.hires_timer = QTimer(self, singleShot=True, interval=120)
        self.hires_timer.timeout.connect(self._render_hires)
        self.sharpen_timer = QTimer(self, singleShot=True, interval=60)
        self.sharpen_timer.timeout.connect(self._sharpen)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # -- data
    def set_content(self, pw, ph, painter_fn, overlay_bytes):
        if abs(self.pw - pw) > 0.5 or abs(self.ph - ph) > 0.5:
            self.zoom = None
            self.cx, self.cy = pw / 2, ph / 2
        self.pw, self.ph = pw, ph
        self.painter_fn = painter_fn
        self.overlay_bytes = overlay_bytes
        self.base_ppt = BASE_PX / max(pw, ph)
        self.base = render_overlay(overlay_bytes, 0, self.base_ppt)
        self.hires = None
        self.hires_key = None
        self._update_cursor()
        self.update()
        self.zoomChanged.emit()

    def show_message(self, text):
        self.painter_fn = None
        self.base = None
        self.message = text
        self.update()
        self.zoomChanged.emit()

    # -- geometria
    def fit_scale(self):
        if not self.pw:
            return 1.0
        pad = 28
        return max(0.01, min((self.width() - 2 * pad) / self.pw,
                             (self.height() - 2 * pad) / self.ph))

    def has_content(self):
        return bool(self.pw) and self.painter_fn is not None

    def scale(self):
        return self.fit_scale() if self.zoom is None else self.zoom

    def origin(self, s=None):
        s = s or self.scale()
        if self.zoom is None:
            return (self.width() - self.pw * s) / 2, (self.height() - self.ph * s) / 2
        return self.width() / 2 - self.cx * s, self.height() / 2 - self.cy * s

    # -- zoom
    def zoom_by(self, factor, anchor: QPointF | None = None):
        if not self.pw:
            return
        s = self.scale()
        ox, oy = self.origin(s)
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        px = (anchor.x() - ox) / s
        py = (anchor.y() - oy) / s
        lo = min(self.fit_scale(), self.actual_scale()) * 0.5
        hi = self.actual_scale() * self.MAX_ZOOM
        ns = max(lo, min(hi, s * factor))
        if self.zoom is None and ns <= self.fit_scale() * 1.001 and factor <= 1:
            return
        self.zoom = ns
        self.cx = px - (anchor.x() - self.width() / 2) / ns
        self.cy = py - (anchor.y() - self.height() / 2) / ns
        self._clamp()
        self._changed()

    def zoom_fit(self):
        self.zoom = None
        self.cx, self.cy = self.pw / 2, self.ph / 2
        self._changed()

    def _clamp(self):
        self.cx = max(0.0, min(self.pw, self.cx))
        self.cy = max(0.0, min(self.ph, self.cy))

    def _changed(self):
        self.hires = None
        self._update_cursor()
        self.update()
        self.hires_timer.start()
        self.zoomChanged.emit()

    def drag_hint(self):
        return self.zoom is not None

    # -- sharp detail
    def _render_hires(self):
        if self.overlay_bytes is None or self.painter_fn is None:
            return
        s = self.scale()
        dpr = self.devicePixelRatioF()
        if s * dpr <= self.base_ppt * 1.05:
            return
        ox, oy = self.origin(s)
        vx0 = max(0.0, -ox / s)
        vy0 = max(0.0, -oy / s)
        vx1 = min(self.pw, (self.width() - ox) / s)
        vy1 = min(self.ph, (self.height() - oy) / s)
        if vx1 - vx0 < 1 or vy1 - vy0 < 1:
            return
        crop = (vx0, self.ph - vy1, self.pw - vx1, vy0)
        try:
            img = render_overlay(self.overlay_bytes, 0, s * dpr, crop)
        except Exception:
            return
        img.setDevicePixelRatio(dpr)
        self.hires = img
        self.hires_rect = QRectF(ox + vx0 * s, oy + vy0 * s, (vx1 - vx0) * s, (vy1 - vy0) * s)
        self.hires_key = (s, self.cx, self.cy, self.width(), self.height(), self.zoom is None)
        self.update()

    # -- kreslenie
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c1d20" if is_dark() else "#4a4d52"))
        if self.base is None or self.painter_fn is None:
            p.setPen(QColor("#d8d8d8"))
            p.drawText(self.rect().adjusted(30, 30, -30, -30),
                       Qt.AlignCenter | Qt.TextWordWrap, self.message)
            return
        s = self.scale()
        ox, oy = self.origin(s)
        r = QRectF(ox, oy, self.pw * s, self.ph * s)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.fillRect(r.translated(4, 5), QColor(0, 0, 0, 90))
        p.fillRect(r, QColor("#ffffff"))
        wanted = set()
        p.save()
        p.setClipRect(r)
        try:
            self.painter_fn(p, sheet_to_widget(ox, oy, s, self.ph), self.devicePixelRatioF(),
                            wanted, True)
        except Exception:
            pass
        p.restore()
        p.drawImage(r, self.base)
        key = (s, self.cx, self.cy, self.width(), self.height(), self.zoom is None)
        if self.hires is not None and self.hires_key == key:
            p.drawImage(self.hires_rect, self.hires)
        elif s * self.devicePixelRatioF() > self.base_ppt * 1.05:
            self.hires_timer.start()
        p.setPen(QPen(QColor("#2b2d30"), 1))
        p.drawRect(r)
        if wanted:
            self.wanted = wanted
            self.sharpen_timer.start()

    def _sharpen(self):
        """Renders the sharper page bitmaps the last paint asked for."""
        if not self.rasters or not self.wanted:
            return
        todo, self.wanted = self.wanted, set()
        for path, idx, level in sorted(todo, key=lambda w: w[2]):
            try:
                self.rasters.render(path, idx, level)
            except Exception:
                pass
        self.update()

    def resizeEvent(self, e):
        self.hires = None
        self.hires_timer.start()
        super().resizeEvent(e)

    # -- pan (mouse handling in ZoomView)
    def can_pan(self):
        return self.zoom is not None

    def pan_state(self):
        return self.cx, self.cy

    def pan_apply(self, state, d):
        s = self.scale()
        self.cx = state[0] - d.x() / s
        self.cy = state[1] - d.y() / s
        self._clamp()
        self._changed()

    def wheel_scroll(self, e):
        if self.zoom is None:
            e.ignore()
            return
        d = e.pixelDelta()
        if d.isNull():
            d = e.angleDelta() / 2
        s = self.scale()
        self.cx -= d.x() / s
        self.cy -= d.y() / s
        self._clamp()
        self._changed()
        e.accept()

    def mouseDoubleClickEvent(self, e):
        if self.has_content() and e.button() == Qt.LeftButton:
            self._toggle_zoom(e.position())

    def _toggle_zoom(self, pos):
        if self.zoom is None:
            self.zoom_by(3.0, pos)
        else:
            self.zoom_fit()


# ============================================================================
# Clickable layout picker

class OverviewView(ZoomView):
    """All sheet sides as thumbnails; double-sided work shows front | back per row.
    Thumbnails use the same cached page bitmaps as the sheet view.

    Zoom and pan as in the sheet view (see ZoomView), up to MAX_ZOOM; a click
    opens the sheet. Content smaller than the window is centred and shifted so
    the point under the cursor stays put while zooming. Marks are rendered in
    tiles, only for the visible part, so a deep zoom over many sheets stays
    light on memory."""

    sideClicked = Signal(int)
    GAP = 22
    LABEL_H = 22
    FIT_THUMB = 340.0                    # thumbnail width in px when not zoomed
    MIN_THUMB = 120.0                    # smallest thumbnail width in px
    MAX_ZOOM = 2.0                       # 200 % of actual size
    TILE = 512                           # overlay tile size in device px
    TILE_CACHE = 160                     # tiles kept (≈ 1 MB each)

    def __init__(self):
        super().__init__()
        self.plan = None
        self.painter_for = None          # fn(side_index) -> painter fn
        self.rasters = None
        self.overlay_bytes = None
        self.overlay_doc = None
        self.overlay_cache = OrderedDict()   # (side, width px, tx, ty) -> QImage tile
        self.labels = []
        self.current = 0
        self.zoom: float | None = None   # px per point; None = fit thumbnails to the window
        self.sheet_size = None
        self.cells = []                  # (QRectF, side index)
        self.wanted = set()
        self.scroll_area = None          # the QScrollArea around this widget (for panning)
        self.shift = QPointF()           # offset from centre while the grid is smaller than the window
        self.timer = QTimer(self, singleShot=True, interval=30)
        self.timer.timeout.connect(self._render_some)
        self._update_cursor()

    def idle_cursor(self):
        return Qt.PointingHandCursor

    def _bars(self):
        sa = self.scroll_area
        return (sa.horizontalScrollBar(), sa.verticalScrollBar()) if sa else (None, None)

    def set_content(self, plan, painter_for, overlay_bytes, labels, current):
        self.plan, self.painter_for, self.labels, self.current = plan, painter_for, labels, current
        size = (round(plan.sheet_w), round(plan.sheet_h)) if plan else None
        if size != self.sheet_size:          # another sheet size: back to the fitting view
            self.sheet_size = size
            self.zoom = None
            self.shift = QPointF()
        if self.overlay_doc is not None:
            self.overlay_doc.close()
        self.overlay_bytes = overlay_bytes
        self.overlay_doc = pdfium.PdfDocument(overlay_bytes) if overlay_bytes else None
        self.overlay_cache.clear()
        self.relayout()
        self.update()

    def clear(self):
        self.plan = None
        self.cells = []
        self.setMinimumSize(0, 0)
        self.update()
        self.zoomChanged.emit()

    # -- zoom
    def _viewport(self):
        sa = self.scroll_area
        return sa.viewport() if sa is not None else self

    def has_content(self):
        return bool(self.plan) and bool(self.cells)

    def scale(self):
        """Current px per point (also when the thumbnails just fit the window)."""
        if self.zoom is not None:
            return self.zoom
        if self.cells and self.plan:
            return self.cells[0][0].width() / self.plan.sheet_w
        return 1.0

    def _limits(self):
        lo = self.MIN_THUMB / self.plan.sheet_w
        return lo, max(lo, self.actual_scale() * self.MAX_ZOOM)

    def zoom_by(self, f, anchor: QPointF | None = None):
        """Zooms by factor f, keeping the sheet point under `anchor` (widget coords) in place."""
        if not self.plan or not self.cells:
            return
        lo, hi = self._limits()
        old = self.scale()
        ns = max(lo, min(hi, old * f))
        if abs(ns - old) < 1e-6 and self.zoom is not None:
            return
        vp = self._viewport()
        h, v = self._bars()
        sx = h.value() if h is not None else 0
        sy = v.value() if v is not None else 0
        if anchor is None:
            anchor = QPointF(sx + vp.width() / 2, sy + vp.height() / 2)
        # the cell under (or nearest to) the anchor and the relative position in it
        r, i = min(self.cells, key=lambda c: 0 if c[0].contains(anchor) else
                   (c[0].center().x() - anchor.x()) ** 2 + (c[0].center().y() - anchor.y()) ** 2)
        fx = (anchor.x() - r.x()) / r.width()
        fy = (anchor.y() - r.y()) / r.height()
        on_screen = anchor - QPointF(sx, sy)
        self.zoom = ns
        self.relayout()
        self._apply_size()
        nr = self.rect_of(i)
        if nr is not None:
            want = QPointF(nr.x() + fx * nr.width(), nr.y() + fy * nr.height())
            # scroll where the area can scroll, shift the centred grid where it can't
            dx = dy = 0.0
            if h is not None and h.maximum() > 0:
                h.setValue(round(want.x() - on_screen.x()))
            else:
                dx = on_screen.x() + sx - want.x()
            if v is not None and v.maximum() > 0:
                v.setValue(round(want.y() - on_screen.y()))
            else:
                dy = on_screen.y() + sy - want.y()
            if dx or dy:
                self.shift += QPointF(dx, dy)
                self.relayout()
        self.update()

    def zoom_fit(self):
        self.zoom = None
        self.shift = QPointF()
        self.relayout()
        self.update()

    # -- layout
    def relayout(self):
        self.cells = []
        if not self.plan:
            self.zoomChanged.emit()
            return
        SW, SH = self.plan.sheet_w, self.plan.sheet_h
        g = self.GAP
        vp = self._viewport()
        vw, vh = vp.width(), vp.height()
        avail = max(200, vw - 2 * g)
        two = any(sd.is_back for sd in self.plan.sides)
        tile = self.plan.sides[0].tile if self.plan.sides else None
        if self.zoom is None:
            cols = 2 if two else max(1, int((avail + g) // (self.FIT_THUMB + g)))
            if tile:                     # a poster: pieces laid out as the assembled poster
                cols = tile[3]
            tw = min(self.FIT_THUMB, (avail - (cols - 1) * g) / cols)
        else:
            tw = self.zoom * SW
            cols = 2 if two else max(1, int((avail + g) // (tw + g)))
            if tile:
                cols = tile[3]
        if not two and not tile:         # no empty columns – keeps the grid centred
            cols = max(1, min(cols, len(self.plan.sides)))
        th = tw * SH / SW
        grid_w = cols * tw + (cols - 1) * g
        rows = max(1, math.ceil(len(self.plan.sides) / cols))
        need_w = int(math.ceil(grid_w + 2 * g)) if self.zoom is not None else 0
        need_h = int(g + rows * (th + self.LABEL_H + g))
        width = max(vw, need_w) if self.scroll_area is not None else self.width()
        height = max(vh, need_h) if self.scroll_area is not None else self.height()
        # centred; while it fits the window, shifted by self.shift (kept inside the window)
        free_x = max(0.0, width - grid_w - 2 * g)
        free_y = max(0.0, height - need_h)
        sx = max(-free_x / 2, min(free_x / 2, self.shift.x()))
        sy = max(-free_y / 2, min(free_y / 2, self.shift.y()))
        self.shift = QPointF(sx, sy)
        x0 = (width - grid_w) / 2 + sx
        y = g + free_y / 2 + sy
        for i in range(len(self.plan.sides)):
            c = i % cols
            if c == 0 and i:
                y += th + self.LABEL_H + g
            self.cells.append((QRectF(x0 + c * (tw + g), y, tw, th), i))
        self.setMinimumSize(need_w, need_h)
        self.zoomChanged.emit()

    def _apply_size(self):
        """Lets the scroll area take the new minimum size now, so the scroll bars
        have their new range before zoom_by sets their values."""
        if self.scroll_area is not None:
            QApplication.sendPostedEvents(None, QEvent.LayoutRequest)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def rect_of(self, i):
        for r, k in self.cells:
            if k == i:
                return r
        return None

    # -- marks overlay, in tiles
    def _overlay_tiles(self, p, i, r, dpr, visible):
        if self.overlay_doc is None:
            return
        SW, SH = self.plan.sheet_w, self.plan.sheet_h
        wpx = max(1, round(r.width() * dpr))           # whole cell in device px
        k = wpx / SW                                    # device px per point
        hpx = max(1, round(SH * k))
        part = r.intersected(visible)
        if part.isEmpty():
            return
        T = self.TILE
        tx0 = max(0, int((part.left() - r.x()) * dpr // T))
        tx1 = min((wpx - 1) // T, int((part.right() - r.x()) * dpr // T))
        ty0 = max(0, int((part.top() - r.y()) * dpr // T))
        ty1 = min((hpx - 1) // T, int((part.bottom() - r.y()) * dpr // T))
        page = None
        try:
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    key = (i, wpx, tx, ty)
                    img = self.overlay_cache.get(key)
                    x0, y0 = tx * T, ty * T
                    x1, y1 = min(wpx, x0 + T), min(hpx, y0 + T)
                    if img is None:
                        if page is None:
                            page = self.overlay_doc[i]
                        crop = (x0 / k, SH - y1 / k, SW - x1 / k, y0 / k)
                        bm = page.render(scale=k, crop=crop, fill_color=(255, 255, 255, 0),
                                         rev_byteorder=True)
                        img = QImage(bm.buffer, bm.width, bm.height, bm.stride,
                                     QImage.Format_RGBA8888).copy()
                        self.overlay_cache[key] = img
                        while len(self.overlay_cache) > self.TILE_CACHE:
                            self.overlay_cache.popitem(last=False)
                    else:
                        self.overlay_cache.move_to_end(key)
                    p.drawImage(QRectF(r.x() + x0 / dpr, r.y() + y0 / dpr,
                                       (x1 - x0) / dpr, (y1 - y0) / dpr), img)
        except Exception:
            pass                                        # the preview must never crash
        finally:
            if page is not None:
                page.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c1d20" if is_dark() else "#4a4d52"))
        if not self.plan:
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        dpr = self.devicePixelRatioF()
        visible = QRectF(e.rect())
        wanted = set()
        for r, i in self.cells:
            full = r.adjusted(0, 0, 0, self.LABEL_H)
            if not full.intersects(visible):
                continue
            p.fillRect(r.translated(3, 4), QColor(0, 0, 0, 90))
            p.fillRect(r, QColor("#ffffff"))
            s = r.width() / self.plan.sheet_w
            p.save()
            p.setClipRect(r.intersected(visible))
            try:
                self.painter_for(i)(p, sheet_to_widget(r.x(), r.y(), s, self.plan.sheet_h),
                                    dpr, wanted, False)
            except Exception:
                pass
            p.restore()
            self._overlay_tiles(p, i, r, dpr, visible)
            if i == self.current:
                p.setPen(QPen(ACCENT, 3))
                p.drawRect(r.adjusted(-2, -2, 2, 2))
            else:
                p.setPen(QPen(QColor("#2b2d30"), 1))
                p.drawRect(r)
            p.setPen(QColor("#e6e7ea"))
            p.drawText(QRectF(r.x(), r.bottom() + 3, r.width(), self.LABEL_H - 3),
                       Qt.AlignHCenter | Qt.AlignTop,
                       self.labels[i] if i < len(self.labels) else "")
        if wanted:
            self.wanted |= wanted
            self.timer.start()

    def _render_some(self):
        """Renders a few missing page bitmaps per tick so scrolling stays smooth."""
        if not self.rasters or not self.wanted:
            return
        todo = sorted(self.wanted, key=lambda w: w[2])[:1]
        for w in todo:
            self.wanted.discard(w)
            try:
                self.rasters.render(*w)
            except Exception:
                pass
        self.update()

    def _side_at(self, pos):
        for r, i in self.cells:
            if r.adjusted(0, 0, 0, self.LABEL_H).contains(pos):
                return i
        return None

    # -- pan (mouse handling in ZoomView)
    def can_pan(self):
        h, v = self._bars()
        return h is not None and (h.maximum() > 0 or v.maximum() > 0)

    def pan_state(self):
        h, v = self._bars()
        return h.value(), v.value()

    def pan_apply(self, state, d):
        h, v = self._bars()
        h.setValue(int(state[0] - d.x()))
        v.setValue(int(state[1] - d.y()))

    def click(self, pos, release_pos):
        i = self._side_at(pos)
        if i is not None and i == self._side_at(release_pos):
            self.sideClicked.emit(i)

    def _toggle_zoom(self, pos):
        if self.zoom is None:
            self.zoom_actual(pos)
        else:
            self.zoom_fit()


class GridPicker(QWidget):
    """Miniature sheet: click a cell to choose pieces across × down."""

    picked = Signal(int, int)
    hovered = Signal(int, int)        # (0, 0) = mouse left

    def __init__(self):
        super().__init__()
        self.sheet = None             # (SW, SH) in points, None = sheet sized to content
        self.cell = (1.0, 1.0)
        self.gap = (0.0, 0.0)
        self.cap = (0, 0)
        self.sel = (0, 0)
        self.hover = None
        self.rects = []               # (QRectF, c, r)
        self.setMouseTracking(True)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(190)
        self.setCursor(Qt.PointingHandCursor)

    def set_data(self, sheet, cell, gap, cap, sel):
        self.sheet, self.cell, self.gap, self.cap, self.sel = sheet, cell, gap, cap, sel
        self.update()

    def _layout(self):
        self.rects = []
        cols, rows = self.cap
        if cols < 1 or rows < 1:
            return None
        cw, ch = self.cell
        gx, gy = self.gap
        bw = cols * cw + (cols - 1) * gx
        bh = rows * ch + (rows - 1) * gy
        W, H = self.sheet if self.sheet else (bw * 1.15, bh * 1.15)
        area = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        k = min(area.width() / W, area.height() / H)
        sw, sh = W * k, H * k
        sx = area.x() + (area.width() - sw) / 2
        sy = area.y() + (area.height() - sh) / 2
        bx = sx + (sw - bw * k) / 2
        by = sy + (sh - bh * k) / 2
        for r in range(rows):
            for c in range(cols):
                self.rects.append((QRectF(bx + c * (cw + gx) * k, by + r * (ch + gy) * k,
                                          cw * k, ch * k), c, r))
        return QRectF(sx, sy, sw, sh)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        sheet = self._layout()
        if sheet is None:
            return
        if self.sheet:
            p.fillRect(sheet.translated(2, 2), QColor(0, 0, 0, 40))
            p.fillRect(sheet, QColor("#ffffff"))
            p.setPen(QPen(QColor("#9a9da3"), 1))
            p.drawRect(sheet)
        else:
            p.setPen(QPen(QColor("#9a9da3"), 1, Qt.DashLine))
            p.drawRect(sheet)
        hc, hr = self.hover if self.hover else (-1, -1)
        sc, sr = self.sel
        for rect, c, r in self.rects:
            inside_sel = c < sc and r < sr
            inside_hover = c <= hc and r <= hr
            if inside_hover:
                fill = QColor(ACCENT)
                fill.setAlpha(150)
            elif inside_sel:
                fill = QColor(ACCENT)
                fill.setAlpha(90 if self.hover else 200)
            else:
                fill = QColor("#eceef1")
            p.fillRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), fill)
            p.setPen(QPen(QColor("#7c8088"), 0.6))
            p.drawRect(rect)

    def _hit(self, pos):
        for rect, c, r in self.rects:
            if rect.adjusted(-1, -1, 1, 1).contains(pos):
                return (c, r)
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self.hover:
            self.hover = h
            self.update()
            self.hovered.emit(*(h[0] + 1, h[1] + 1) if h else (0, 0))

    def leaveEvent(self, _):
        self.hover = None
        self.update()
        self.hovered.emit(0, 0)

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h and e.button() == Qt.LeftButton:
            self.picked.emit(h[0] + 1, h[1] + 1)


# ============================================================================
# Helper widgets

class ElidedLabel(QLabel):
    """One-line label that shortens a long text with “…” in the middle (full text as tooltip)."""

    def __init__(self, text=""):
        super().__init__()
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(40)

    def setText(self, text):
        self._full = text
        self._elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, max(10, self.width())))


class Section(QWidget):
    """Collapsible panel section: bold title with an arrow, remembers its state."""

    def __init__(self, title, key):
        super().__init__()
        self.key = key
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(2)
        self.btn = QToolButton()
        self.btn.setText(title)
        self.btn.setCheckable(True)
        self.btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn.setStyleSheet("QToolButton { border: none; font-weight: bold; padding: 3px 0px; "
                               "text-align: left; }")
        self.body = QFrame()
        self.body.setFrameShape(QFrame.StyledPanel)
        lay.addWidget(self.btn)
        lay.addWidget(self.body)
        val = store().value(f"section/{key}", True)
        is_open = val not in (False, "false", "0", 0)
        self.btn.setChecked(is_open)
        self._apply(is_open)
        self.btn.toggled.connect(self._toggled)

    def _apply(self, on):
        self.body.setVisible(on)
        self.btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.updateGeometry()

    def _toggled(self, on):
        self._apply(on)
        store().setValue(f"section/{self.key}", on)


class LayerRow(QFrame):
    """Settings of one layer (varnish, white…) in the Layers section."""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, entry):
        super().__init__()
        self.entry = entry
        ly = entry["layer"]
        self.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.show_cb = QCheckBox(t("layer_show"))
        self.show_cb.setChecked(ly.visible)
        rm = QToolButton(text="✕")
        rm.setToolTip(t("layer_remove"))
        rm.clicked.connect(lambda: self.removed.emit(self.entry))
        head.addWidget(self.title, 1)
        head.addWidget(self.show_cb)
        head.addWidget(rm)
        v.addLayout(head)

        f = QFormLayout()
        self.kind = QComboBox()
        for k in LAYER_KINDS:
            if k != "crease":                       # crease PDFs go to the Creasing section
                self.kind.addItem(t(f"layer_{k}"), k)
        self.kind.setCurrentIndex(self.kind.findData(ly.kind))
        found = sorted(entry["findings"].spots) if entry.get("findings") else []
        self.spot_auto = QCheckBox(t("spot_from_pdf"))
        self.spot_auto.setChecked(not ly.spot)
        self.spot_auto.setToolTip(t("layer_spot_tip"))
        self.spot = QComboBox()                 # expected name, only when not read from the PDF
        self.spot.setEditable(True)
        self.spot.addItems(found)
        self.spot.setCurrentText(ly.spot or (found[0] if found else ""))
        self.spot.lineEdit().setPlaceholderText(t("spot_placeholder"))
        self.spot.setToolTip(t("layer_spot_tip"))
        self.spot.setEnabled(bool(ly.spot))
        self.pos = QComboBox()
        self.pos.addItem(t("pos_above"), "above")
        self.pos.addItem(t("pos_below"), "below")
        self.pos.setCurrentIndex(self.pos.findData(ly.position))
        self.op = QCheckBox(t("layer_op"))
        self.op.setToolTip(t("layer_op_tip"))
        self.op.setChecked(ly.overprint)
        self.pages = QComboBox()
        self.pages.addItem(t("pages_same"), "same")
        self.pages.addItem(t("pages_first"), "first")
        self.pages.setCurrentIndex(self.pages.findData(ly.pages))
        for cb in (self.kind, self.spot, self.pos, self.pages):
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(12)
        f.addRow(t("layer_kind"), self.kind)
        f.addRow(t("layer_spot"), self.spot_auto)
        f.addRow("", self.spot)
        f.addRow(t("layer_pos"), self.pos)
        f.addRow("", self.op)
        f.addRow(t("layer_pages"), self.pages)
        v.addLayout(f)
        self.check = QLabel()
        self.check.setWordWrap(True)
        self.check.setTextFormat(Qt.RichText)
        v.addWidget(self.check)
        self._update_title()

        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.spot.currentTextChanged.connect(self._sync)
        for w in (self.pos, self.pages):
            w.currentIndexChanged.connect(self._sync)
        for w in (self.op, self.show_cb, self.spot_auto):
            w.toggled.connect(self._sync)

    def _update_title(self):
        ly = self.entry["layer"]
        self.title.setText(f"<b>{layer_display_name(ly)}</b> · {os.path.basename(ly.path)}")

    def _kind_changed(self):
        ly = self.entry["layer"]
        old = ly.kind
        new = self.kind.currentData()
        # follow the defaults of the new type unless the user changed them
        if self.pos.currentData() == LAYER_KINDS[old][1]:
            self.pos.setCurrentIndex(self.pos.findData(LAYER_KINDS[new][1]))
        self._sync()

    def _sync(self, *_):
        ly = self.entry["layer"]
        ly.kind = self.kind.currentData()
        auto = self.spot_auto.isChecked()
        self.spot.setEnabled(not auto)
        ly.spot = "" if auto else self.spot.currentText().strip()
        ly.position = self.pos.currentData()
        ly.overprint = self.op.isChecked()
        ly.pages = self.pages.currentData()
        ly.visible = self.show_cb.isChecked()
        self._update_title()
        self.changed.emit()

    def set_check(self, items):
        rows = []
        for lvl, text in items:
            sym, col = PF_STYLE.get(lvl, PF_STYLE["info"])
            rows.append(f"<span style='color:{col}'>{sym}</span> {text}")
        self.check.setText("<br>".join(rows))


def _drop_widget(layout, w):
    """Removes a row from its layout for good. It stays hidden inside the panel until it is
    deleted – setParent(None) would turn a shown widget into a stray top-level window
    (on macOS it appears as a small floating window until the next event loop pass)."""
    layout.removeWidget(w)
    w.hide()
    w.deleteLater()


def guess_kind(path, spots=()):
    """Layer type from the spot colour names in the PDF, then from the file name."""
    from .spots import kind_of
    lib = {"crease": "crease", "cut": "diecut", "perf": "diecut", "white": "white",
           "varnish": "varnish", "foil": "foil"}
    for sp in spots:
        k = lib.get(kind_of(sp) or "")
        if k:
            return k
    words = (("crease", ("crease", "bigov", "ryhov", "score", "_big", "-big", " big")),
             ("white", ("biel", "white", "wit", "weiss", "weiß")),
             ("diecut", ("vysek", "výsek", "cut", "die", "stanz", "kontur")),
             ("foil", ("foil", "folia", "fólia", "razba", "ražba", "gold", "silver")),
             ("varnish", ("lak", "varnish", "uv", "clear", "gloss", "matt")))
    for text in [s.lower() for s in spots] + [os.path.basename(path).lower()]:
        for kind, keys in words:
            if any(w in text for w in keys):
                return kind
    return "varnish"


def _sig_desc(sizes):
    """[16, 16, 16, 8] → “3 × 16 + 8”."""
    out, i = [], 0
    while i < len(sizes):
        j = i
        while j < len(sizes) and sizes[j] == sizes[i]:
            j += 1
        out.append(f"{j - i} × {sizes[i]}" if j - i > 1 else str(sizes[i]))
        i = j
    return " + ".join(out)


def mm_spin(val, lo=0.0, hi=2000.0, step=0.5, dec=1, suffix=" mm"):
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setSingleStep(step)
    sp.setValue(val)
    sp.setSuffix(suffix)
    sp.setKeyboardTracking(False)
    return sp


def int_spin(val, lo=1, hi=99):
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    sp.setKeyboardTracking(False)
    return sp


def hint_label(text=""):
    lb = QLabel(text)
    lb.setWordWrap(True)
    lb.setStyleSheet("color: #808080; font-size: 11px;")
    return lb


# ============================================================================
# Main window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1320, 880)
        self.setAcceptDrops(True)

        self.src: pikepdf.Pdf | None = None
        self.path: str | None = None
        self.profile = None
        self.findings = None
        self.layers = []          # [{"layer": Layer, "pdf": Pdf, "infos": [...], "findings": ...}]
        self.rasters = PageRasters()
        self.view_mode = store().value("view_mode", "sheet")
        if self.view_mode not in ("sheet", "all"):
            self.view_mode = "sheet"
        self.layer_rows = []
        self.infos = None
        self.infos_key = None
        self.jobs = []                # gang run: [{"path", "pdf", "qty", "main"}], jobs[0] = open file
        self.gang_src = None          # gang run: the jobs merged into one PDF (temporary file)
        self.gang_path = None
        self.gang_jobs = None         # [core.GangJob]
        self._gang_key = None
        self._gang_active = False
        self.main_findings = None
        self.crease_detected = None   # crease.Detected from the crease PDF or the print PDF
        self.crease_from_print = False
        self._crease_key = None
        self.plan = None
        self.side_idx = 0
        self._loading = False
        self.last_dir = os.path.expanduser("~")

        self.timer = QTimer(self, singleShot=True, interval=180)
        self.timer.timeout.connect(self.refresh)

        # keyboard shortcuts (created once – survive a language switch)
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self.step(+1))
        QShortcut(QKeySequence.Open, self, activated=self.choose_file)
        QShortcut(QKeySequence.Save, self, activated=self.save)
        QShortcut(QKeySequence.ZoomIn, self, activated=lambda: self._zoom(1.25))
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self._zoom(1.25))
        QShortcut(QKeySequence.ZoomOut, self, activated=lambda: self._zoom(0.8))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self._zoom_fit())
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._zoom_actual())

        qs = store()
        lang = qs.value("language", "")
        if lang not in LANGUAGES:
            lang = "sk" if QLocale.system().name()[:2] in ("sk", "cs") else "en"
        set_language(lang)

        self.job_presets = presets_mod.loads(qs.value("job_presets", "[]"))
        self._build_ui()
        self._load_settings()
        self._sync_job()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        self.layer_rows = []          # old rows die with the old panel
        self._build_menu()

        panel = QWidget()
        col = QVBoxLayout(panel)
        col.setContentsMargins(10, 10, 10, 10)

        # Job preset – one click sets everything for a kind of job
        row = QHBoxLayout()
        lbl = QLabel(f"<b>{t('job_label')}</b>")
        self.job = QComboBox()
        self.job.setToolTip(t("job_tip"))
        self.job.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.job.setMinimumContentsLength(16)
        self.job.activated.connect(self._job_chosen)
        save = QPushButton(t("job_save_btn"))
        save.setToolTip(t("job_save_tip"))
        save.clicked.connect(self.save_job_preset)
        row.addWidget(lbl)
        row.addWidget(self.job, 1)
        row.addWidget(save)
        col.addLayout(row)
        self._fill_job_combo()

        # File
        g = Section(t("file"), "file")
        v = QVBoxLayout(g.body)
        b = QPushButton(t("open_pdf"))
        b.clicked.connect(self.choose_file)
        self.file_label = QLabel(t("no_file"))
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(b)
        v.addWidget(self.file_label)
        col.addWidget(g)

        # Mode
        g = Section(t("mode"), "mode")
        f = QFormLayout(g.body)
        self.mode = QComboBox()
        for k in MODES:
            self.mode.addItem(t(f"mode_{k}"), k)
        self.mode_hint = hint_label()
        f.addRow(self.mode)
        f.addRow(self.mode_hint)
        self.range = QLineEdit()
        self.range.setPlaceholderText(t("pages_ph"))
        f.addRow(t("pages"), self.range)
        self.split = QCheckBox(t("split_spreads"))
        self.split.setToolTip(t("split_spreads_tip"))
        self.split.setChecked(True)
        self.split.setVisible(False)
        f.addRow(self.split)
        col.addWidget(g)

        # Jobs on the sheet (gang run)
        self.gang_box = Section(t("gang_group"), "gang")
        gv = QVBoxLayout(self.gang_box.body)
        self.jobs_col = QVBoxLayout()
        self.jobs_col.setSpacing(2)
        gv.addLayout(self.jobs_col)
        add = QPushButton(t("gang_add"))
        add.clicked.connect(self.add_jobs)
        gv.addWidget(add, 0, Qt.AlignLeft)
        self.gang_info = hint_label()
        self.gang_info.setTextFormat(Qt.RichText)
        gv.addWidget(self.gang_info)
        gv.addWidget(hint_label(t("gang_hint")))
        col.addWidget(self.gang_box)
        self.job_rows = []

        # Sheet
        g = Section(t("sheet_group"), "sheet")
        f = QFormLayout(g.body)
        self.sheet = QComboBox()
        for name in SHEET_PRESETS:
            self.sheet.addItem(name, name)
        self.sheet.addItem(t("sheet_custom"), CUSTOM)
        self.sheet.addItem(t("sheet_fit"), FIT)
        self.sheet_w = mm_spin(320, 20)
        self.sheet_h = mm_spin(450, 20)
        wh = QHBoxLayout()
        wh.addWidget(self.sheet_w)
        wh.addWidget(QLabel("×"))
        wh.addWidget(self.sheet_h)
        self.orientation = QComboBox()
        self.orientation.addItem(t("or_auto"), "auto")
        self.orientation.addItem(t("or_portrait"), "portrait")
        self.orientation.addItem(t("or_landscape"), "landscape")
        self.margin = mm_spin(10, 0, 100)
        self.margin.setToolTip(t("margin_tip"))
        f.addRow(t("sheet_format"), self.sheet)
        f.addRow(t("sheet_size"), wh)
        f.addRow(t("orientation"), self.orientation)
        f.addRow(t("margin"), self.margin)
        col.addWidget(g)

        # Layout (n-up)
        self.grid_box = Section(t("layout_group"), "layout")
        gv = QVBoxLayout(self.grid_box.body)
        self.auto_rb = QRadioButton(t("layout_auto"))
        self.manual_rb = QRadioButton(t("layout_manual"))
        self.layout_grp = QButtonGroup(self)
        self.layout_grp.addButton(self.auto_rb)
        self.layout_grp.addButton(self.manual_rb)
        self.auto_rb.setChecked(True)
        gv.addWidget(self.auto_rb)
        gv.addWidget(self.manual_rb)
        self.picker = GridPicker()
        self.picker.picked.connect(self._picked)
        self.picker.hovered.connect(self._picker_hover)
        gv.addWidget(self.picker)
        self.picker_label = QLabel()
        self.picker_label.setWordWrap(True)
        self.picker_label.setAlignment(Qt.AlignCenter)
        gv.addWidget(self.picker_label)
        row = QHBoxLayout()
        self.cols = int_spin(1)
        self.rows = int_spin(1)
        row.addWidget(QLabel(t("across")))
        row.addWidget(self.cols)
        row.addSpacing(8)
        row.addWidget(QLabel(t("down")))
        row.addWidget(self.rows)
        row.addStretch(1)
        gv.addLayout(row)
        f = QFormLayout()
        self.rotation = QComboBox()
        self.rotation.addItem(t("rot_auto"), "auto")
        self.rotation.addItem(t("rot_0"), "0")
        self.rotation.addItem(t("rot_90"), "90")
        f.addRow(t("rotation"), self.rotation)
        gv.addLayout(f)

        gv.addWidget(QLabel(f"<b>{t('gaps')}</b>"))
        row = QHBoxLayout()
        self.gutter_x = mm_spin(0, 0, 100)
        self.gutter_y = mm_spin(0, 0, 100)
        row.addWidget(QLabel(t("gap_h")))
        row.addWidget(self.gutter_x)
        row.addWidget(QLabel(t("gap_v")))
        row.addWidget(self.gutter_y)
        gv.addLayout(row)
        self.gutter_btn = QPushButton(t("gap_double"))
        self.gutter_btn.clicked.connect(self._gutter_double_bleed)
        gv.addWidget(self.gutter_btn, 0, Qt.AlignLeft)
        gv.addWidget(hint_label(t("gap_hint")))
        col.addWidget(self.grid_box)

        # Booklet
        self.booklet_box = Section(t("booklet_group"), "booklet")
        f = QFormLayout(self.booklet_box.body)
        self.creep = mm_spin(0, 0, 10, 0.05, 2)
        self.creep.setToolTip(t("creep_tip"))
        self.blanks = QComboBox()
        self.blanks.addItem(t("blanks_end"), "end")
        self.blanks.addItem(t("blanks_before"), "before_back")
        f.addRow(t("creep"), self.creep)
        f.addRow(hint_label(t("creep_tip")))
        f.addRow(t("blanks"), self.blanks)
        col.addWidget(self.booklet_box)

        # Signatures (perfect / sewn binding)
        self.sig_box = Section(t("sig_group"), "signatures")
        f = QFormLayout(self.sig_box.body)
        self.sig_pages = QComboBox()
        self.sig_pages.addItem(t("sig_auto"), 0)
        for k in (4, 8, 16, 32):
            self.sig_pages.addItem(str(k), k)
        self.sig_pages.setToolTip(t("sig_pages_tip"))
        self.binding = QComboBox()
        self.binding.addItem(t("binding_perfect"), "perfect")
        self.binding.addItem(t("binding_sewn"), "sewn")
        self.milling = mm_spin(3, 0, 10, 0.5, 1)
        self.milling.setToolTip(t("milling_tip"))
        self.collation = QCheckBox(t("collation"))
        self.collation.setToolTip(t("collation_tip"))
        self.sig_blanks = QComboBox()
        self.sig_blanks.addItem(t("blanks_end"), "end")
        self.sig_blanks.addItem(t("blanks_before"), "before_back")
        f.addRow(t("sig_pages"), self.sig_pages)
        f.addRow(hint_label(t("sig_pages_tip")))
        f.addRow(t("binding"), self.binding)
        f.addRow(t("milling"), self.milling)
        f.addRow(self.collation)
        f.addRow(t("blanks"), self.sig_blanks)
        f.addRow(hint_label(t("sig_hint")))
        cover_btn = QPushButton(t("cover_action"))
        cover_btn.clicked.connect(self.show_cover)
        f.addRow(cover_btn)
        self.sig_form = f
        col.addWidget(self.sig_box)

        # Poster in pieces
        self.tile_box = Section(t("tile_group"), "tile")
        f = QFormLayout(self.tile_box.body)
        self.tile_target = QComboBox()
        for key in TILE_TARGETS:
            self.tile_target.addItem(t(f"tile_target_{key}") if key == "custom" else key, key)
        self.tile_target.setToolTip(t("tile_target_tip"))
        self.tile_target.activated.connect(self._tile_target_chosen)
        self.tile_scale = mm_spin(100, 10, 2000, 5, 1, " %")
        self.tile_overlap = mm_spin(10, 0, 50, 1, 1)
        self.tile_overlap.setToolTip(t("tile_overlap_tip"))
        self.tile_info = hint_label()
        self.tile_info.setTextFormat(Qt.RichText)
        f.addRow(t("tile_target"), self.tile_target)
        f.addRow(t("tile_scale"), self.tile_scale)
        f.addRow(t("tile_overlap"), self.tile_overlap)
        f.addRow(self.tile_info)
        f.addRow(hint_label(t("tile_hint")))
        col.addWidget(self.tile_box)

        # Bleed
        g = Section(t("bleed_group"), "bleed")
        f = QFormLayout(g.body)
        self.bleed = mm_spin(3, 0, 20)
        self.bleed_fill = QComboBox()
        for key in ("off", "mirror", "stretch"):
            self.bleed_fill.addItem(t(f"bleed_fill_{key}"), key)
        self.bleed_fill.setToolTip(t("bleed_fill_tip"))
        self.assume = mm_spin(0, 0, 20)
        self.assume.setToolTip(t("assume_tip"))
        f.addRow(t("bleed"), self.bleed)
        f.addRow(t("bleed_fill"), self.bleed_fill)
        f.addRow(t("assume"), self.assume)
        col.addWidget(g)

        # Double-sided printing
        g = Section(t("duplex_group"), "duplex")
        f = QFormLayout(g.body)
        self.duplex = QCheckBox(t("duplex"))
        self.flip = QComboBox()
        self.flip.addItem(t("flip_long"), "long")
        self.flip.addItem(t("flip_short"), "short")
        self.flip.setToolTip(t("flip_tip"))
        self.back_or = QComboBox()
        self.back_or.addItem(t("back_book"), "book")
        self.back_or.addItem(t("back_cal"), "calendar")
        self.back_or.setToolTip(t("back_tip"))
        f.addRow(self.duplex)
        f.addRow(t("printer"), self.flip)
        self.back_or_label = QLabel(t("back_piece"))
        f.addRow(self.back_or_label, self.back_or)
        f.addRow(hint_label(t("flip_tip")))
        col.addWidget(g)

        # Marks
        g = Section(t("marks_group"), "marks")
        f = QFormLayout(g.body)
        self.crop = QCheckBox(t("crop"))
        self.mark_off = mm_spin(3, 0, 20)
        self.mark_len = mm_spin(5, 1, 30)
        self.mark_w = mm_spin(0.25, 0.05, 2, 0.05, 2, " pt")
        self.reg = QCheckBox(t("reg"))
        self.slug = QCheckBox(t("slug"))
        f.addRow(self.crop)
        f.addRow(t("mark_offset"), self.mark_off)
        f.addRow(t("mark_length"), self.mark_len)
        f.addRow(t("mark_weight"), self.mark_w)
        f.addRow(self.reg)
        f.addRow(self.slug)
        col.addWidget(g)

        # Creasing
        self.crease_box = Section(t("crease_group"), "crease")
        f = QFormLayout(self.crease_box.body)
        self.crease = QComboBox()
        for key in CREASE_PRESETS:
            self.crease.addItem(t(f"crease_{key}"), key)
        self.crease_dir = QComboBox()
        self.crease_dir.addItem(t("crease_dir_v"), "v")
        self.crease_dir.addItem(t("crease_dir_h"), "h")
        self.crease_pos = QLineEdit()
        self.crease_pos.setPlaceholderText(t("crease_pos_ph"))
        self.crease_pos.setToolTip(t("crease_pos_tip"))
        self.crease_marks = QCheckBox(t("crease_marks"))
        self.crease_marks.setChecked(True)
        self.crease_marks.setToolTip(t("crease_marks_tip"))
        self.crease_status = hint_label()
        self.crease_status.setTextFormat(Qt.RichText)
        # “From the PDF”: the PDF with the crease lines lives here, not among the layers
        self.crease_src = QWidget()
        sh = QHBoxLayout(self.crease_src)
        sh.setContentsMargins(0, 0, 0, 0)
        self.crease_src_label = ElidedLabel()
        self.crease_pick = QPushButton(t("crease_pick"))
        self.crease_pick.clicked.connect(self.choose_crease_pdf)
        self.crease_clear = QToolButton(text="✕")
        self.crease_clear.setToolTip(t("crease_clear_tip"))
        self.crease_clear.clicked.connect(self.remove_crease_pdf)
        sh.addWidget(self.crease_src_label, 1)
        sh.addWidget(self.crease_pick)
        sh.addWidget(self.crease_clear)
        self.crease_form = f
        f.addRow(t("crease_preset"), self.crease)
        f.addRow(t("crease_source"), self.crease_src)
        f.addRow(t("crease_dir"), self.crease_dir)
        f.addRow(t("crease_pos"), self.crease_pos)
        f.addRow(self.crease_marks)
        f.addRow(self.crease_status)
        f.addRow(hint_label(t("crease_hint")))
        col.addWidget(self.crease_box)

        # Layers
        g = Section(t("layers_group"), "layers")
        self.layers_box = g
        lv = QVBoxLayout(g.body)
        self.layers_col = QVBoxLayout()
        lv.addLayout(self.layers_col)
        add = QPushButton(t("add_layer"))
        add.clicked.connect(self.add_layer)
        lv.addWidget(add, 0, Qt.AlignLeft)
        lv.addWidget(hint_label(t("layers_hint")))
        col.addWidget(g)

        # Export PDF
        g = Section(t("export_group"), "export")
        f = QFormLayout(g.body)
        self.std = QComboBox()
        self.std.addItem(t("std_keep", std="–"), "keep")
        self.std.addItem(t("std_none"), "none")
        for key, (label, *_r) in STANDARDS.items():
            self.std.addItem(label, key)
        self.icc = QComboBox()
        self.icc.addItem(t("icc_keep", icc="–"), "keep")
        self.icc.addItem(t("icc_bundled"), "bundled")
        for info in system_cmyk_profiles():
            self.icc.addItem(info.desc, info.path)
            self.icc.setItemData(self.icc.count() - 1, info.path, Qt.ToolTipRole)
        self.icc.addItem(t("icc_file"), CHOOSE)
        self.icc.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.icc.setMinimumContentsLength(18)
        self._icc_prev = 0
        f.addRow(t("std_label"), self.std)
        f.addRow(t("icc_label"), self.icc)
        self.out_print = QCheckBox(t("out_print"))
        self.out_layers = QCheckBox(t("out_layers"))
        self.out_combined = QCheckBox(t("out_combined"))
        self.out_dummy = QCheckBox(t("out_dummy"))
        self.out_dummy.setToolTip(t("out_dummy_tip"))
        f.addRow(QLabel(f"<b>{t('out_label')}</b>"))
        for w in (self.out_print, self.out_layers, self.out_combined, self.out_dummy):
            f.addRow(w)
        self.preflight = QLabel()
        self.preflight.setWordWrap(True)
        self.preflight.setTextFormat(Qt.RichText)
        f.addRow(self.preflight)
        f.addRow(hint_label(t("export_hint")))
        col.addWidget(g)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(400)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Right side – preview
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        self.view = SheetView()
        self.view.rasters = self.rasters
        self.view.zoomChanged.connect(self._zoom_label)
        self.overview = OverviewView()
        self.overview.rasters = self.rasters
        self.overview.sideClicked.connect(self._open_side)
        self.overview.zoomChanged.connect(self._zoom_label)
        self.ov_scroll = QScrollArea()
        self.ov_scroll.setWidget(self.overview)
        self.ov_scroll.setWidgetResizable(True)
        self.ov_scroll.setFrameShape(QFrame.NoFrame)
        self.ov_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.overview.scroll_area = self.ov_scroll
        self.stack = QStackedWidget()
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.ov_scroll)
        rv.addWidget(self.stack, 1)

        bar = QWidget()
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(10, 6, 10, 6)
        self.prev_btn = QToolButton(text="◀")
        self.next_btn = QToolButton(text="▶")
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn.clicked.connect(lambda: self.step(+1))
        self.side_label = QLabel("–")
        self.side_label.setMinimumWidth(150)
        self.side_label.setAlignment(Qt.AlignCenter)
        self.mode_sheet = QToolButton(text=t("view_sheet"))
        self.mode_all = QToolButton(text=t("view_overview"))
        self.mode_sheet.setToolTip(t("view_sheet_tip"))
        self.mode_all.setToolTip(t("view_overview_tip"))
        mg = QButtonGroup(self)
        for b in (self.mode_sheet, self.mode_all):
            b.setCheckable(True)
            mg.addButton(b)
        (self.mode_all if self.view_mode == "all" else self.mode_sheet).setChecked(True)
        self.stack.setCurrentIndex(1 if self.view_mode == "all" else 0)
        self.mode_sheet.clicked.connect(lambda: self.set_view_mode("sheet"))
        self.mode_all.clicked.connect(lambda: self.set_view_mode("all"))
        bh.addWidget(self.mode_sheet)
        bh.addWidget(self.mode_all)
        bh.addSpacing(10)
        bh.addWidget(self.prev_btn)
        bh.addWidget(self.side_label)
        bh.addWidget(self.next_btn)
        bh.addSpacing(14)

        zo = QToolButton(text="−")
        zo.setToolTip(t("zoom_out"))
        zo.clicked.connect(lambda: self._zoom(0.8))
        self.zoom_lbl = QLabel("–")
        self.zoom_lbl.setMinimumWidth(48)
        self.zoom_lbl.setAlignment(Qt.AlignCenter)
        zi = QToolButton(text="+")
        zi.setToolTip(t("zoom_in"))
        zi.clicked.connect(lambda: self._zoom(1.25))
        zf = QToolButton(text=t("zoom_fit"))
        zf.clicked.connect(self._zoom_fit)
        z1 = QToolButton(text=t("zoom_100"))
        z1.clicked.connect(self._zoom_actual)
        self.z100 = z1
        self._zoom_tip_widgets = [w for w in (zo, self.zoom_lbl, zi, zf, z1) if not w.toolTip()]
        for w in (zo, self.zoom_lbl, zi, zf, z1):
            bh.addWidget(w)
        self._zoom_tips()
        bh.addSpacing(14)

        self.guides = QCheckBox(t("guides"))
        self.guides.setToolTip(t("guides_tip"))
        self.guides.setChecked(True)
        self.guides.toggled.connect(self.render_current)
        bh.addWidget(self.guides)
        self.numbers = QCheckBox(t("page_numbers"))
        self.numbers.setToolTip(t("page_numbers_tip"))
        self.numbers.setChecked(store().value("page_numbers", "false") in (True, "true"))
        self.numbers.toggled.connect(self._numbers_toggled)
        bh.addWidget(self.numbers)
        bh.addStretch(1)
        self.save_btn = QPushButton(t("save"))
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save)
        bh.addWidget(self.save_btn)
        rv.addWidget(bar)

        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setContentsMargins(12, 6, 12, 2)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setContentsMargins(12, 0, 12, 8)
        self.warn.setStyleSheet("color: #c26a00;")
        rv.addWidget(self.info)
        rv.addWidget(self.warn)

        split = QSplitter()
        split.addWidget(scroll)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([420, 900])
        self.setCentralWidget(split)

        # signals → recalculation
        for w in (self.mode, self.orientation, self.rotation, self.blanks,
                  self.flip, self.back_or, self.crease, self.crease_dir, self.bleed_fill,
                  self.sig_pages, self.binding, self.sig_blanks):
            w.currentIndexChanged.connect(self.changed)
        for w in (self.sheet_w, self.sheet_h, self.margin, self.cols, self.rows,
                  self.gutter_x, self.gutter_y, self.creep, self.bleed, self.assume,
                  self.mark_off, self.mark_len, self.mark_w, self.tile_scale, self.tile_overlap,
                  self.milling):
            w.valueChanged.connect(self.changed)
        for w in (self.duplex, self.crop, self.reg, self.slug, self.manual_rb, self.crease_marks,
                  self.out_print, self.out_layers, self.out_combined, self.collation,
                  self.out_dummy):
            w.toggled.connect(self.changed)
        self._rebuild_layer_rows()
        self._rebuild_job_rows()
        self.manual_rb.toggled.connect(self._manual_toggled)
        self.range.editingFinished.connect(self.changed)
        self.crease_pos.editingFinished.connect(self.changed)
        self.split.toggled.connect(self.changed)
        self.sheet.currentIndexChanged.connect(self._preset_changed)
        self.std.currentIndexChanged.connect(self.changed)
        self.icc.currentIndexChanged.connect(self._icc_changed)

        self.statusBar().showMessage(t("ready"))
        self._update_nav()

    def _build_menu(self):
        mb = self.menuBar()
        mb.clear()
        menu = mb.addMenu(t("language"))
        grp = QActionGroup(self)
        for code, name in LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == get_language())
            a.triggered.connect(lambda _=False, c=code: self.switch_language(c))
            grp.addAction(a)
            menu.addAction(a)

        menu = mb.addMenu(t("appearance"))
        grp = QActionGroup(self)
        current = store().value("theme", "system")
        for code in THEMES:
            a = QAction(t(f"theme_{code}"), self, checkable=True)
            a.setChecked(code == current)
            a.triggered.connect(lambda _=False, c=code: self.switch_theme(c))
            grp.addAction(a)
            menu.addAction(a)

        menu = mb.addMenu(t("jobs_menu"))
        for item in ((t("job_save_action"), self.save_job_preset),
                     (t("job_manage_action"), self.manage_job_presets),
                     None,
                     (t("job_import_action"), self.import_job_presets),
                     (t("job_export_action"), self.export_job_presets)):
            if item is None:
                menu.addSeparator()
                continue
            a = QAction(item[0], self)
            a.setMenuRole(QAction.NoRole)
            a.triggered.connect(item[1])
            menu.addAction(a)

        menu = mb.addMenu(t("tools_menu"))
        a = QAction(t("spots_action"), self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(self.show_spots)
        menu.addAction(a)
        a = QAction(t("cover_action"), self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(self.show_cover)
        menu.addAction(a)

        # Help: on macOS “About Imprimo” moves to the application menu (AboutRole)
        menu = mb.addMenu(t("help_menu"))
        a = QAction(t("ex_action"), self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(self.show_examples)
        menu.addAction(a)
        menu.addSeparator()
        a = QAction(t("about_action"), self)
        a.setMenuRole(QAction.AboutRole)
        a.triggered.connect(self.show_about)
        menu.addAction(a)
        a = QAction(t("about_show_license") + "…", self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(lambda: self._about().show_license())
        menu.addAction(a)
        a = QAction(t("github_action"), self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        menu.addAction(a)
        a = QAction(t("support_action"), self)
        a.setMenuRole(QAction.NoRole)
        a.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(SUPPORT_URL)))
        menu.addAction(a)

    def _about(self):
        from .about import AboutDialog
        return AboutDialog(self)

    def show_about(self):
        self._about().exec()

    def show_examples(self):
        from .examples_dialog import ExamplesDialog
        ExamplesDialog(self).exec()

    def open_lesson(self, path, preset_key):
        """Opens a sample PDF and applies the preset its lesson uses."""
        self.open_file(path)
        if self.src is None or not preset_key:
            return
        for i in range(self.job.count()):
            p = self._job_at(self.job.itemData(i))
            if p is not None and p.builtin == preset_key:
                self.job.setCurrentIndex(i)
                self._job_chosen(i)
                break

    def show_cover(self):
        """Cover with spine – book size and page count from the open file."""
        from .cover_dialog import CoverDialog
        w, h, pages = 148.0, 210.0, 64
        if self.plan is not None and self.mode.currentData() in ("booklet", "signatures"):
            w, h = to_mm(self.plan.page_w), to_mm(self.plan.page_h)
            pages = self.plan.pages or self.plan.n_sheets * 4
        elif self.infos:
            w, h, pages = to_mm(self.infos[0].vis_w), to_mm(self.infos[0].vis_h), len(self.infos)
        CoverDialog(self, round(w, 1), round(h, 1), pages, self.bleed.value(), self.last_dir).exec()

    def open_cover(self, path, creases, two_sided):
        """Opens an assembled cover for imposing: one per sheet position, creases on the spine."""
        self.open_file(path)
        if self.src is None:
            return
        was, self._loading = self._loading, True
        self.mode.setCurrentIndex(self.mode.findData("repeat"))
        self.split.setChecked(False)              # the opened cover is no spread of two pages
        self.duplex.setChecked(two_sided)
        self.crease.setCurrentIndex(self.crease.findData("custom"))
        self.crease_dir.setCurrentIndex(self.crease_dir.findData("v"))
        self.crease_pos.setText(format_positions(creases))
        self.crease_marks.setChecked(True)
        self._loading = was
        self.changed()
        self.statusBar().showMessage(t("cover_status", pos=format_positions(creases)), 15000)

    def show_spots(self):
        from .spots_dialog import SpotColorsDialog
        SpotColorsDialog(self, self.last_dir).exec()

    def switch_theme(self, mode):
        store().setValue("theme", mode)
        apply_theme(mode)
        self.view.update()
        self.overview.update()
        self.picker.update()

    def switch_language(self, lang):
        if lang == get_language():
            return
        s = self.read_settings()
        sheet_key = self.sheet.currentData()
        zoom = (self.view.zoom, self.view.cx, self.view.cy)
        set_language(lang)
        store().setValue("language", lang)
        self._build_ui()
        self.apply_settings(s, sheet_key)
        if self.src is not None:
            self._describe_source()
        self.refresh()
        self.view.zoom, self.view.cx, self.view.cy = zoom
        self.view._changed()

    # ------------------------------------------------------- nastavenia
    def read_settings(self) -> Settings:
        key = self.sheet.currentData()
        manual = self.manual_rb.isChecked()
        return Settings(
            mode=self.mode.currentData(),
            fit_sheet=(key == FIT),
            sheet_w=self.sheet_w.value(),
            sheet_h=self.sheet_h.value(),
            orientation=self.orientation.currentData(),
            margin=self.margin.value(),
            cols=self.cols.value() if manual else 0,
            rows=self.rows.value() if manual else 0,
            gutter_x=self.gutter_x.value(),
            gutter_y=self.gutter_y.value(),
            rotation=self.rotation.currentData(),
            bleed=self.bleed.value(),
            bleed_fill=self.bleed_fill.currentData() or "off",
            tile_scale=self.tile_scale.value(),
            tile_overlap=self.tile_overlap.value(),
            assume_bleed=self.assume.value(),
            duplex=self.duplex.isChecked(),
            duplex_flip=self.flip.currentData(),
            back_orientation=self.back_or.currentData(),
            crop_marks=self.crop.isChecked(),
            mark_offset=self.mark_off.value(),
            mark_length=self.mark_len.value(),
            mark_weight=self.mark_w.value(),
            reg_marks=self.reg.isChecked(),
            slug=self.slug.isChecked(),
            creep=self.creep.value(),
            blanks=(self.sig_blanks if self.mode.currentData() == "signatures"
                    else self.blanks).currentData(),
            sig_pages=self.sig_pages.currentData() or 0,
            binding=self.binding.currentData() or "perfect",
            milling=self.milling.value(),
            collation_marks=self.collation.isChecked(),
            export_dummy=self.out_dummy.isChecked(),
            page_range=self.range.text(),
            split_spreads=self.split.isChecked(),
            export_print=self.out_print.isChecked(),
            export_layers=self.out_layers.isChecked(),
            export_combined=self.out_combined.isChecked(),
            pdf_standard=self.std.currentData() or "keep",
            icc_profile=self.icc.currentData() if self.icc.currentData() != CHOOSE else "keep",
            **self._crease_settings(),
        )

    # ------------------------------------------------------------ gang run
    def _reset_jobs(self):
        for j in self.jobs:
            if not j.get("main"):
                try:
                    j["pdf"].close()
                except Exception:
                    pass
        self.jobs = []
        self._gang_key = None
        self._rebuild_job_rows()

    def _ensure_jobs(self):
        """The open file is always the first job."""
        if self.src is not None and not self.jobs:
            self.jobs = [{"path": self.path, "pdf": self.src, "qty": 100, "main": True}]
            self._rebuild_job_rows()

    def _rebuild_job_rows(self):
        if not hasattr(self, "jobs_col"):
            return
        for w in self.job_rows:
            _drop_widget(self.jobs_col, w)
        self.job_rows = []
        for i, job in enumerate(self.jobs):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            letter = QLabel(f"<b>{gang_letter(i)}</b>")
            letter.setMinimumWidth(18)
            name = ElidedLabel(os.path.basename(job["path"]))
            name.setToolTip(job["path"])
            qty = QSpinBox()
            qty.setRange(1, 1_000_000)
            qty.setValue(job["qty"])
            qty.setSuffix(t("gang_pcs"))
            qty.setKeyboardTracking(False)
            qty.valueChanged.connect(lambda v, j=job: (j.__setitem__("qty", v), self.changed()))
            rm = QToolButton(text="✕")
            rm.setToolTip(t("gang_remove"))
            rm.setEnabled(not job.get("main"))
            rm.clicked.connect(lambda _=False, j=job: self._remove_job(j))
            for w in (letter, name, qty, rm):
                h.addWidget(w, 1 if w is name else 0)
            self.jobs_col.addWidget(row)
            self.job_rows.append(row)

    def add_jobs(self, paths=None):
        if self.src is None:
            QMessageBox.information(self, APP_NAME, t("drop_here"))
            return
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, t("gang_add"), self.last_dir,
                                                    t("pdf_open_filter"))
        self._ensure_jobs()
        for path in paths or []:
            try:
                pdf = pikepdf.open(path)
            except Exception as e:
                QMessageBox.warning(self, APP_NAME, t("cant_open", err=e))
                continue
            self.jobs.append({"path": path, "pdf": pdf, "qty": self.jobs[0]["qty"], "main": False})
        self._rebuild_job_rows()
        self.changed()

    def _remove_job(self, job):
        self.jobs = [j for j in self.jobs if j is not job]
        try:
            job["pdf"].close()
        except Exception:
            pass
        self._rebuild_job_rows()
        self.changed()

    def _gang_build(self, s):
        """Merges the jobs (their first one or two pages) into one temporary PDF, so the
        rest of Imprimo – preview, export, preflight – works with a single source."""
        key = (tuple((j["path"], id(j["pdf"])) for j in self.jobs), s.assume_bleed)
        if key != self._gang_key:
            import tempfile
            merged = pikepdf.new()
            pages = []
            for j in self.jobs:
                start = len(merged.pages)
                for k in range(min(2, len(j["pdf"].pages))):
                    merged.pages.append(j["pdf"].pages[k])
                pages.append(list(range(start, len(merged.pages))))
            fd, path = tempfile.mkstemp(prefix="imprimo-gang-", suffix=".pdf")
            os.close(fd)
            merged.save(path)
            merged.close()
            old = (self.gang_src, self.gang_path)
            self.gang_src = pikepdf.open(path)
            self.gang_path = path
            self.gang_pages = pages
            self.gang_infos = analyze(self.gang_src, s.assume_bleed, False)
            self.gang_findings = scan(self.gang_src)
            self.rasters.clear()
            self._gang_key = key
            if old[0] is not None:
                try:
                    old[0].close()
                    os.remove(old[1])
                except Exception:
                    pass
        self.gang_jobs = [GangJob(os.path.basename(j["path"]), pg, j["qty"])
                          for j, pg in zip(self.jobs, self.gang_pages)]
        return self.gang_jobs

    def _gang_label(self, page):
        for i, job in enumerate(self.gang_jobs or []):
            if page in job.pages:
                return gang_letter(i)
        return str(page + 1)

    def _update_gang_info(self):
        if not self._gang_active or self.plan is None or not self.plan.gang:
            self.gang_info.setText("")
            return
        def slots(k):                                     # 1 miesto, 2 miesta, 5 miest
            form = "1" if k == 1 else "2" if 2 <= k % 100 <= 4 and not 12 <= k % 100 <= 14 else "5"
            return t(f"gang_slots_{form}", k=k)

        rows = []
        for i, (name, qty, k, made) in enumerate(self.plan.gang):
            extra = f" (+{made - qty})" if made > qty else ""
            rows.append(t("gang_row", l=gang_letter(i), slots=slots(k), made=made, extra=extra))
        n = self.plan.n_sheets
        rows.append(t("gang_total", sheets=f"{n} {self._hark(n)}", slots=slots(self.plan.per_sheet)))
        self.gang_info.setText("<br>".join(rows))

    # ------------------------------------------------------------ poster
    def _tile_target_chosen(self, index):
        """A target size (A3 … A0) sets the scale so the page fits it (same orientation)."""
        key = self.tile_target.itemData(index)
        if key not in TILE_TARGETS or key == "custom" or not self.infos:
            return
        tw, th = TILE_TARGETS[key]
        try:
            ref = self.infos[parse_range(self.range.text(), len(self.infos))[0]]
        except Exception:
            ref = self.infos[0]
        w, h = to_mm(ref.vis_w), to_mm(ref.vis_h)
        if (w > h) != (tw > th):
            tw, th = th, tw
        self.tile_scale.setValue(round(min(tw / w, th / h) * 100, 1))

    def _update_tile_info(self, s):
        if s.mode != "tile" or self.plan is None:
            return
        p = self.plan
        k = s.tile_scale / 100
        pw, ph = to_mm(p.page_w) * k, to_mm(p.page_h) * k
        self.tile_info.setText(t("tile_info", c=p.cols, r=p.rows, n=p.cols * p.rows,
                                 w=f"{pw:.0f}", h=f"{ph:.0f}",
                                 sw=f"{to_mm(p.sheet_w):.0f}", sh=f"{to_mm(p.sheet_h):.0f}"))
        # show the target size the poster was fitted to (fits inside it, touching one side)
        big, small = max(pw, ph), min(pw, ph)
        i = 0
        for j in range(1, self.tile_target.count()):
            tw, th = TILE_TARGETS[self.tile_target.itemData(j)]
            TB, TS = max(tw, th), min(tw, th)
            if big <= TB + 1 and small <= TS + 1 and (abs(big - TB) < 1 or abs(small - TS) < 1):
                i = j
                break
        was = self.tile_target.blockSignals(True)
        self.tile_target.setCurrentIndex(i)
        self.tile_target.blockSignals(was)

    # ------------------------------------------------------------ creasing
    def _crease_settings(self):
        preset = self.crease.currentData() or "off"
        d = dict(crease=preset, crease_dir=self.crease_dir.currentData() or "v",
                 crease_pos=self.crease_pos.text().strip(),
                 crease_marks=self.crease_marks.isChecked())
        if preset == "pdf":
            det = self.crease_detected
            if det is not None and det.found:
                d["crease_dir"] = "v" if det.main_vertical else "h"
                d["crease_pos"] = format_positions(det.vertical if det.main_vertical
                                                   else det.horizontal)
            else:
                d["crease_pos"] = ""
        elif preset != "custom":
            d["crease_pos"] = ""
        return d

    def _crease_entry(self):
        """The PDF with crease lines (a layer of type “crease”), or None."""
        return next((e for e in self.layers if e["layer"].kind == "crease"), None)

    def _detect_creases(self):
        """Crease lines from the crease PDF if one is chosen, otherwise from the print PDF –
        only for the preset “from the PDF”, cached until the file or the crease PDF changes."""
        ce = self._crease_entry()
        key = (self.path, ce["layer"].path if ce else None)
        if key == self._crease_key:
            return
        self._crease_key = key
        self.crease_detected, self.crease_from_print = None, False
        try:
            if ce is not None:
                self.crease_detected = detect_any(ce["pdf"], ce["infos"] or analyze(ce["pdf"]))
            elif self.src is not None:
                self.crease_detected = detect_any(self.src, self.infos or analyze(self.src))
                self.crease_from_print = self.crease_detected.found
        except Exception:
            self.crease_detected = None

    def choose_crease_pdf(self):
        if self.src is None:
            QMessageBox.information(self, APP_NAME, t("drop_here"))
            return
        path, _ = QFileDialog.getOpenFileName(self, t("crease_pick_title"), self.last_dir,
                                              t("pdf_open_filter"))
        if not path:
            return
        try:
            pdf = pikepdf.open(path)
            s = self.read_settings()
            infos = analyze(pdf, s.assume_bleed, s.split_spreads)
            findings = scan(pdf)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, t("cant_open", err=e))
            return
        self._set_crease_entry({"layer": Layer(path, kind="crease", position="above"),
                                "pdf": pdf, "infos": infos, "findings": findings})

    def _set_crease_entry(self, entry):
        """Use `entry` as the crease PDF (replaces the previous one) and read creases from it."""
        if len(entry["infos"]) == 1 and self.src is not None and len(self.src.pages) > 1:
            entry["layer"].pages = "first"
        for old in [e for e in self.layers if e["layer"].kind == "crease"]:
            self._drop_entry(old)
        self.layers.append(entry)
        self._crease_key = None
        was, self._loading = self._loading, True
        self.crease.setCurrentIndex(self.crease.findData("pdf"))
        self._loading = was
        self._rebuild_layer_rows()
        self.changed()

    def remove_crease_pdf(self):
        ce = self._crease_entry()
        if ce is not None:
            self._drop_entry(ce)
            self._crease_key = None
            self.changed()

    def _drop_entry(self, entry):
        self.layers = [e for e in self.layers if e is not entry]
        try:
            entry["pdf"].close()
        except Exception:
            pass

    def _update_crease_panel(self):
        preset = self.crease.currentData() or "off"
        booklet = self.mode.currentData() in ("booklet", "signatures")
        on = preset != "off" and not booklet
        from_pdf = on and preset == "pdf"
        det = self.crease_detected if from_pdf else None
        found = det is not None and det.found
        ce = self._crease_entry()
        form = self.crease_form
        self.crease.setEnabled(not booklet)
        form.setRowVisible(self.crease_src, from_pdf)
        # direction and positions mean nothing until there is something to read them from
        form.setRowVisible(self.crease_dir, not from_pdf or found)
        form.setRowVisible(self.crease_pos, not from_pdf or found)
        self.crease_dir.setEnabled(on and preset != "pdf")
        self.crease_pos.setReadOnly(preset != "custom")
        self.crease_pos.setEnabled(on and preset == "custom")    # computed values: greyed
        self.crease_marks.setEnabled(on and (not from_pdf or found))
        if from_pdf:
            if ce is not None:
                name = os.path.basename(ce["layer"].path)
            elif found:
                name = t("crease_src_print")
            else:
                name = "–"
            self.crease_src_label.setText(name)
            self.crease_src_label.setToolTip(ce["layer"].path if ce else (self.path or ""))
            self.crease_pick.setText(t("crease_change") if ce else t("crease_pick"))
            self.crease_clear.setVisible(ce is not None)

        msg = []
        if booklet:
            msg.append(t("crease_booklet"))
        elif from_pdf:
            if found:
                n = len(det.vertical if det.main_vertical else det.horizontal)
                msg.append(t("crease_found_n", n=n, spot=det.spot or "Crease"))
                if det.vertical and det.horizontal:
                    msg.append(t("crease_both_dirs"))
                if self.crease_from_print:
                    msg.append(t("crease_in_print_warn"))
            elif ce is not None:
                msg.append(t("crease_none_file", file=os.path.basename(ce["layer"].path)))
            else:
                msg.append(t("crease_none_print"))
        if on and preset != "custom":
            # show what the preset / the PDF gives, so the student sees the numbers
            vals, vertical = [], True
            if self.plan is not None:
                spec = crease_spec(self.read_settings(), self.plan.page_w, self.plan.page_h)
                if spec is not None:
                    vals, vertical = spec.positions, spec.vertical
            was, self._loading = self._loading, True
            self.crease_pos.setText(format_positions(vals))
            if preset == "pdf":
                self.crease_dir.setCurrentIndex(self.crease_dir.findData("v" if vertical else "h"))
            self._loading = was
        elif not on and preset != "custom":
            self.crease_pos.setText("")
        if on and self.plan is not None:
            spec = crease_spec(self.read_settings(), self.plan.page_w, self.plan.page_h)
            if spec is not None and spec.rejected:
                msg.append(t("crease_outside", pos=format_positions(spec.rejected)))
            if preset == "custom":
                try:
                    parse_positions(self.crease_pos.text())
                except ValueError as e:
                    msg.append(t("crease_bad", tok=str(e)))
        self.crease_status.setText("<br>".join(msg))
        self.crease_status.setVisible(bool(msg))

    def apply_settings(self, s: Settings, sheet_key: str | None = None):
        self._loading = True

        def setc(combo, data):
            i = combo.findData(data)
            if i >= 0:
                combo.setCurrentIndex(i)

        setc(self.mode, s.mode)
        if sheet_key is not None:
            setc(self.sheet, sheet_key)
        self.sheet_w.setValue(s.sheet_w)
        self.sheet_h.setValue(s.sheet_h)
        setc(self.orientation, s.orientation)
        self.margin.setValue(s.margin)
        manual = s.cols > 0 and s.rows > 0
        (self.manual_rb if manual else self.auto_rb).setChecked(True)
        if manual:
            self.cols.setValue(s.cols)
            self.rows.setValue(s.rows)
        self.gutter_x.setValue(s.gutter_x)
        self.gutter_y.setValue(s.gutter_y)
        setc(self.rotation, s.rotation)
        self.bleed.setValue(s.bleed)
        setc(self.bleed_fill, s.bleed_fill)
        self.tile_scale.setValue(s.tile_scale)
        self.tile_overlap.setValue(s.tile_overlap)
        self.assume.setValue(s.assume_bleed)
        self.duplex.setChecked(s.duplex)
        setc(self.flip, s.duplex_flip)
        setc(self.back_or, s.back_orientation)
        self.crop.setChecked(s.crop_marks)
        self.mark_off.setValue(s.mark_offset)
        self.mark_len.setValue(s.mark_length)
        self.mark_w.setValue(s.mark_weight)
        self.reg.setChecked(s.reg_marks)
        self.slug.setChecked(s.slug)
        self.creep.setValue(s.creep)
        setc(self.blanks, s.blanks)
        setc(self.sig_blanks, s.blanks)
        setc(self.sig_pages, s.sig_pages if s.sig_pages in (4, 8, 16, 32) else 0)
        setc(self.binding, s.binding)
        self.milling.setValue(s.milling)
        self.collation.setChecked(s.collation_marks)
        self.out_dummy.setChecked(s.export_dummy)
        setc(self.crease, s.crease if s.crease in CREASE_PRESETS else "off")
        setc(self.crease_dir, s.crease_dir)
        self.crease_pos.setText(s.crease_pos if s.crease == "custom" else "")
        self.crease_marks.setChecked(s.crease_marks)
        self.range.setText(s.page_range)
        self.split.setChecked(s.split_spreads)
        self.out_print.setChecked(s.export_print)
        self.out_layers.setChecked(s.export_layers)
        self.out_combined.setChecked(s.export_combined)
        setc(self.std, s.pdf_standard)
        if s.icc_profile not in ("keep", "bundled") and self.icc.findData(s.icc_profile) < 0:
            if icc_from_file(s.icc_profile):
                self._add_icc(s.icc_profile)
        setc(self.icc, s.icc_profile)
        self._icc_prev = self.icc.currentIndex()
        self._loading = False
        self._preset_changed()

    # ------------------------------------------------------------ job presets
    def _all_jobs(self):
        return list(presets_mod.BUILTIN) + list(self.job_presets)

    def _job_name(self, p):
        return t(p.builtin) if p.builtin else p.name

    def _fill_job_combo(self):
        if not hasattr(self, "job"):
            return
        self.job.blockSignals(True)
        self.job.clear()
        self.job.addItem(t("job_custom"), None)
        for i, p in enumerate(presets_mod.BUILTIN):
            self.job.addItem("★ " + self._job_name(p), ("b", i))
        if self.job_presets:
            self.job.insertSeparator(self.job.count())
        for i, p in enumerate(self.job_presets):
            self.job.addItem(p.name, ("u", i))
        self.job.blockSignals(False)

    def _job_at(self, data):
        if not data:
            return None
        kind, i = data
        lst = presets_mod.BUILTIN if kind == "b" else self.job_presets
        return lst[i] if 0 <= i < len(lst) else None

    def _job_chosen(self, index):
        p = self._job_at(self.job.itemData(index))
        if p is None:
            return
        s = p.to_settings()
        s.page_range = self.range.text()
        self.apply_settings(s, p.sheet_key)
        self._crease_key = None
        self.changed()
        self.statusBar().showMessage(t("job_applied", name=self._job_name(p)), 6000)

    def _sync_job(self):
        """Show the preset that matches the current settings, or “custom settings”."""
        if not hasattr(self, "job"):
            return
        cur, key = self.read_settings(), self.sheet.currentData()
        match = 0
        for i in range(self.job.count()):
            p = self._job_at(self.job.itemData(i))
            if p is not None and p.sheet_key == key and presets_mod.same(p.to_settings(), cur):
                match = i
                break
        if self.job.currentIndex() != match:
            self.job.blockSignals(True)
            self.job.setCurrentIndex(match)
            self.job.blockSignals(False)

    def _store_jobs(self):
        store().setValue("job_presets", presets_mod.dumps(self.job_presets))
        self._fill_job_combo()
        self._sync_job()

    def save_job_preset(self):
        cur = self._job_at(self.job.currentData())
        suggest = cur.name if cur is not None and not cur.builtin else ""
        name, ok = QInputDialog.getText(self, t("job_save_title"), t("job_save_prompt"),
                                        text=suggest)
        name = (name or "").strip()
        if not ok or not name:
            return
        new = presets_mod.from_settings(name, self.read_settings(), self.sheet.currentData())
        existing = [i for i, p in enumerate(self.job_presets) if p.name == name]
        if existing:
            r = QMessageBox.question(self, APP_NAME, t("job_overwrite", name=name))
            if r != QMessageBox.Yes:
                return
            self.job_presets[existing[0]] = new
        else:
            self.job_presets.append(new)
        self._store_jobs()
        self.statusBar().showMessage(t("job_saved", name=name), 6000)

    def manage_job_presets(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("job_manage_title"))
        dlg.resize(420, 360)
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        lay.addWidget(QLabel(t("job_manage_hint")))
        lay.addWidget(lst, 1)

        def fill(sel=0):
            lst.clear()
            for p in self.job_presets:
                lst.addItem(p.name)
            if self.job_presets:
                lst.setCurrentRow(max(0, min(sel, len(self.job_presets) - 1)))

        def rename():
            r = lst.currentRow()
            if r < 0:
                return
            old = self.job_presets[r].name
            name, ok = QInputDialog.getText(dlg, t("job_rename"), t("job_save_prompt"), text=old)
            name = (name or "").strip()
            if ok and name and name != old:
                self.job_presets[r].name = presets_mod.unique_name(
                    name, [p.name for p in self.job_presets])
                self._store_jobs()
                fill(r)

        def delete():
            r = lst.currentRow()
            if r < 0:
                return
            if QMessageBox.question(dlg, APP_NAME, t("job_delete_q", name=self.job_presets[r].name)) \
                    == QMessageBox.Yes:
                del self.job_presets[r]
                self._store_jobs()
                fill(r)

        def move(d):
            r = lst.currentRow()
            if 0 <= r < len(self.job_presets) and 0 <= r + d < len(self.job_presets):
                jp = self.job_presets
                jp[r], jp[r + d] = jp[r + d], jp[r]
                self._store_jobs()
                fill(r + d)

        bb = QDialogButtonBox()
        for text, fn in ((t("job_rename"), rename), (t("job_delete"), delete),
                         ("↑", lambda: move(-1)), ("↓", lambda: move(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bb.addButton(b, QDialogButtonBox.ActionRole)
        close = bb.addButton(QDialogButtonBox.Close)
        close.setText(t("close"))
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        fill()
        dlg.exec()

    def export_job_presets(self):
        if not self.job_presets:
            QMessageBox.information(self, APP_NAME, t("job_none_to_export"))
            return
        path, _ = QFileDialog.getSaveFileName(self, t("job_export_action"),
                                              os.path.join(self.last_dir, "imprimo-predvolby.json"),
                                              "JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(presets_mod.file_text(self.job_presets))
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, t("save_fail", err=e))
            return
        self.statusBar().showMessage(t("job_exported", n=len(self.job_presets), path=path), 8000)

    def import_job_presets(self):
        path, _ = QFileDialog.getOpenFileName(self, t("job_import_action"), self.last_dir,
                                              "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                new = presets_mod.loads(f.read())
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, t("job_import_fail", err=e))
            return
        if not new:
            QMessageBox.warning(self, APP_NAME, t("job_import_fail", err=os.path.basename(path)))
            return
        self.job_presets, n = presets_mod.merge(self.job_presets, new)
        self._store_jobs()
        QMessageBox.information(self, APP_NAME, t("job_imported", n=n))

    def _load_settings(self):
        qs = store()
        s = Settings()
        try:
            data = json.loads(qs.value("settings", "{}"))
            known = {f.name for f in dataclasses.fields(Settings)}
            s = Settings(**{k: v for k, v in data.items() if k in known})
        except Exception:
            pass
        s.page_range = ""
        self.apply_settings(s, qs.value("sheet_key", list(SHEET_PRESETS)[0]))
        self.last_dir = qs.value("last_dir", os.path.expanduser("~"))

    def _store_settings(self):
        qs = store()
        qs.setValue("settings", json.dumps(dataclasses.asdict(self.read_settings())))
        qs.setValue("sheet_key", self.sheet.currentData())
        qs.setValue("last_dir", self.last_dir)

    def closeEvent(self, e):
        self._store_settings()
        if self.gang_path:                                # the merged gang-run PDF is temporary
            try:
                self.gang_src.close()
                os.remove(self.gang_path)
            except Exception:
                pass
        super().closeEvent(e)

    def _preset_changed(self):
        key = self.sheet.currentData()
        if key in SHEET_PRESETS:
            w, h = SHEET_PRESETS[key]
            was, self._loading = self._loading, True
            self.sheet_w.setValue(w)
            self.sheet_h.setValue(h)
            self._loading = was
        self.sheet_w.setEnabled(key == CUSTOM)
        self.sheet_h.setEnabled(key == CUSTOM)
        self.orientation.setEnabled(key != FIT)
        self.changed()

    def _gutter_double_bleed(self):
        self.gutter_x.setValue(2 * self.bleed.value())
        self.gutter_y.setValue(2 * self.bleed.value())

    def _manual_toggled(self, on):
        # switching to manual: start from what the automatic layout produced
        if on and self.plan is not None and self.plan.cols and not self._loading:
            was, self._loading = self._loading, True
            self.cols.setValue(self.plan.cols)
            self.rows.setValue(self.plan.rows)
            self._loading = was

    def _picked(self, c, r):
        was, self._loading = self._loading, True
        self.cols.setValue(c)
        self.rows.setValue(r)
        self.manual_rb.setChecked(True)
        self._loading = was
        self.changed()

    def _picker_hover(self, c, r):
        if c and r:
            self.picker_label.setText(t("picker_hover", c=c, r=r, n=c * r))
        else:
            self._layout_label()

    def _layout_label(self):
        p = self.plan
        if p is None or self.mode.currentData() in ("booklet", "signatures"):
            self.picker_label.setText(t("picker_hint"))
            return
        txt = t("layout_result", c=p.cols, r=p.rows, n=p.per_sheet)
        if p.cap:
            txt += f"<br><span style='color:gray'>{t('layout_cap', c=p.cap[0], r=p.cap[1])}</span>"
        self.picker_label.setText(txt)

    def _update_visibility(self):
        mode = self.mode.currentData()
        sig = mode == "signatures"
        self.sig_box.setVisible(sig)
        self.sig_form.setRowVisible(self.milling, self.binding.currentData() == "perfect")
        self.out_dummy.setEnabled(mode in ("booklet", "signatures"))
        booklet = mode == "booklet"
        tile = mode == "tile"
        self.mode_hint.setText(t(f"mode_hint_{mode}"))
        self.grid_box.setVisible(not booklet and not tile and not sig)
        self.booklet_box.setVisible(booklet)
        booklet = booklet or sig                 # both: always double-sided, no grid
        gang = mode == "gang"
        self.tile_box.setVisible(tile)
        self.crease_box.setVisible(not tile)
        self.gang_box.setVisible(gang)
        self.layers_box.setVisible(not gang)          # layers follow the pages of one PDF
        self.range.setEnabled(not gang)
        if gang:
            self._ensure_jobs()
        self.duplex.setEnabled(not booklet and not tile)
        self.duplex.setText(t("duplex_booklet") if booklet else t("duplex"))
        two_sided = booklet or self.duplex.isChecked()
        self.flip.setEnabled(two_sided)
        self.back_or.setVisible(not booklet)
        self.back_or_label.setVisible(not booklet)
        self.back_or.setEnabled(two_sided)
        manual = self.manual_rb.isChecked()
        self.cols.setEnabled(manual)
        self.rows.setEnabled(manual)
        if self.sheet.currentData() == FIT and not manual:
            # a sheet sized to content needs a piece count
            was, self._loading = self._loading, True
            self.manual_rb.setChecked(True)
            self._loading = was
        has_layers = bool(self.layers)
        self.out_layers.setEnabled(has_layers)
        self.out_combined.setEnabled(has_layers)
        marks = self.crop.isChecked()
        self.mark_off.setEnabled(marks)
        self.mark_len.setEnabled(marks)
        if hasattr(self, "crease_box"):
            self._update_crease_panel()

    def changed(self, *_):
        if self._loading:
            return
        self._update_visibility()
        self._sync_job()
        self.timer.start()

    # ------------------------------------------------------------- file
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, t("open_title"), self.last_dir,
                                              t("pdf_open_filter"))
        if path:
            self.open_file(path)

    def open_file(self, path):
        try:
            pdf = pikepdf.open(path)
        except pikepdf.PasswordError:
            QMessageBox.warning(self, APP_NAME, t("pwd"))
            return
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, t("cant_open", err=e))
            return
        if self.src is not None:
            self.src.close()
        self.src, self.path = pdf, path
        self.last_dir = os.path.dirname(path)
        self.infos = None
        self._crease_key = None
        self._reset_jobs()
        self.rasters.clear()
        self._clear_layers()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.profile = detect_profile(pdf)
            self.findings = scan(pdf)
            self.main_findings = self.findings
        finally:
            QApplication.restoreOverrideCursor()
        self.side_idx = 0
        self.range.setText("")
        self._describe_source()
        self.refresh()

    def _describe_source(self):
        try:
            raw = analyze(self.src, 0, split_spreads=False)
        except ImposeError as e:
            self.file_label.setText(str(e))
            return
        spreads = spread_pages(raw)
        self.split.setVisible(bool(spreads))
        p = min(raw, key=lambda x: x.vis_w) if spreads else raw[0]
        if spreads:
            pages_txt = t("src_spreads", n=len(raw) + len(spreads), pdf=len(raw), s=len(spreads))
        else:
            pages_txt = t("src_pages", n=len(raw))
        trim = t("src_trim_ok") if p.has_trim else t("src_trim_no")
        pr = self.profile
        std = pr.pdfx or pr.pdfa or t("src_no_std")
        oi = pr.pdfx_intent
        intent = oi.label() if oi else t("src_no_intent")
        made = t("src_made", app=pr.app()) if pr.app() else ""
        self.file_label.setText(
            f"<b>{os.path.basename(self.path)}</b><br>"
            f"{pages_txt} · {to_mm(p.vis_w):.1f} × {to_mm(p.vis_h):.1f} mm<br>"
            f"{trim} · {t('src_bleed', mm=f'{to_mm(p.bleed_avail):.1f}')}<br>"
            f"<b>{std}</b> · {intent} · PDF {pr.pdf_version}"
            + (f"<br><span style='color:#808080'>{made}</span>" if made else ""))
        self.file_label.setToolTip("\n".join(x for x in (
            f"Creator: {pr.creator}" if pr.creator else "",
            f"Producer: {pr.producer}" if pr.producer else "",
            *(f"OutputIntent: {o.identifier} | {o.condition} | {o.icc.desc if o.icc else '–'}"
              for o in pr.intents)) if x))
        # labels of the “Keep from source” options
        self.std.setItemText(0, t("std_keep", std=pr.pdfx or t("src_no_std")))
        self.icc.setItemText(0, t("icc_keep", icc=oi.label() if oi else t("icc_none")))

    # -- drag and drop: anywhere in the window, the preview included
    @staticmethod
    def _dropped_pdf(e):
        md = e.mimeData()
        if md is None or not md.hasUrls():
            return None
        for u in md.urls():
            path = u.toLocalFile()
            if path and is_pdf(path):
                return path
        return None

    def dragEnterEvent(self, e):
        if self._dropped_pdf(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._dropped_pdf(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        path = self._dropped_pdf(e)
        if not path:
            return
        e.acceptProposedAction()
        # in a gang run with a file open, dropped PDFs become more jobs
        if self.src is not None and self.mode.currentData() == "gang":
            paths = [u.toLocalFile() for u in e.mimeData().urls()
                     if u.toLocalFile() and is_pdf(u.toLocalFile())]
            QTimer.singleShot(0, lambda: self.add_jobs(paths))
            return
        # open after the drop returns, so the source app (Finder) is not kept waiting
        QTimer.singleShot(0, lambda: self.open_file(path))

    # ---------------------------------------------------------- preview
    def refresh(self):
        self._update_visibility()
        self._sync_job()
        if self.src is None:
            self.plan = None
            self._update_nav()
            self._update_picker()
            return
        s = self.read_settings()
        try:
            gang = None
            if s.mode == "gang":
                self._ensure_jobs()
                gang = self._gang_build(s)
                self.infos, self.infos_key = self.gang_infos, ("gang", self._gang_key)
                self.findings = self.gang_findings
                if not self._gang_active:
                    self.rasters.clear()
                self._gang_active = True
            elif self._gang_active:                       # back from a gang run: the open file again
                self._gang_active = False
                self.infos = None
                self.findings = self.main_findings
                self.rasters.clear()
            key = (s.assume_bleed, s.split_spreads)
            if not self._gang_active and (self.infos is None or self.infos_key != key):
                self.infos = analyze(self.src, *key)
                self.infos_key = key
                for e in self.layers:
                    e["infos"] = analyze(e["pdf"], *key)
            if s.crease == "pdf":
                self._detect_creases()
                s = self.read_settings()
            self.plan = build_plan(self.infos, s, gang)
        except ImposeError as e:
            self.plan = None
            self.view.show_message(str(e))
            self.info.setText("")
            self.warn.setText("")
            self._update_nav()
            self._update_picker()
            return
        self.side_idx = min(self.side_idx, len(self.plan.sides) - 1)
        p = self.plan
        harky = self._hark(p.n_sheets)
        if s.mode == "booklet":
            head = t("info_booklet", pages=p.n_sheets * 4, sheets=p.n_sheets, harky=harky)
        elif s.mode == "signatures":
            head = t("info_signatures", pages=p.pages, desc=_sig_desc(p.signatures),
                     sheets=p.n_sheets, harky=harky)
        else:
            head = t("info_grid", n=p.per_sheet, c=p.cols, r=p.rows,
                     rot=t("info_rot") if p.rot else "", sheets=p.n_sheets, harky=harky,
                     duplex=t("info_duplex") if s.duplex else "")
        tail = t("info_tail", w=f"{to_mm(p.sheet_w):.1f}", h=f"{to_mm(p.sheet_h):.1f}",
                 u=f"{p.utilization:.0%}")
        self.info.setText(f"<b>{head}</b> · {tail}")
        self.warn.setText("\n".join("⚠ " + w for w in p.warnings))
        self._update_crease_panel()
        self._update_tile_info(s)
        self._update_gang_info()
        self._update_nav()
        self._update_picker()
        self._update_preflight(s)
        self.render_current()

    def _update_picker(self):
        p = self.plan
        if p is None or self.mode.currentData() in ("booklet", "signatures") or not p.cols:
            # without a plan show at least an empty grid
            self.picker.set_data(None, (85, 55), (0, 0), (0, 0), (0, 0))
            self._layout_label()
            return
        cw, ch = (p.page_h, p.page_w) if p.rot else (p.page_w, p.page_h)
        if p.cap:
            sheet, cap = (p.sheet_w, p.sheet_h), p.cap
        else:
            sheet = None
            cap = (max(6, p.cols + 1), max(6, p.rows + 1))
        self.picker.set_data(sheet, (cw, ch), p.gutter, cap, (p.cols, p.rows))
        if not self.manual_rb.isChecked():
            # in automatic mode show the result in the (disabled) fields
            was, self._loading = self._loading, True
            self.cols.setValue(p.cols)
            self.rows.setValue(p.rows)
            self._loading = was
        self._layout_label()

    @staticmethod
    def _hark(n):
        return t("sheets_1") if n == 1 else (t("sheets_2") if 2 <= n <= 4 else t("sheets_5"))

    def render_current(self):
        if self.plan is None or self.src is None:
            self.overview.clear()
            return
        s = self.read_settings()
        name = os.path.basename(self.path or "")
        try:                                # the preview must never crash the app
            srcs = self._raster_sources()
            if self.view_mode == "all":
                marks = render_sources([], self.plan, s, guides=self.guides.isChecked(),
                                       filename=name)
                buf = io.BytesIO()
                marks.save(buf)
                plan = self.plan
                self.overview.set_content(
                    plan, lambda i: self._side_painter(plan.sides[i], srcs), buf.getvalue(),
                    self._side_labels(), self.side_idx)
            else:
                marks = render_sources([], self.plan, s, side_indices=[self.side_idx],
                                       guides=self.guides.isChecked(), filename=name)
                buf = io.BytesIO()
                marks.save(buf)
                self.view.set_content(self.plan.sheet_w, self.plan.sheet_h,
                                      self._side_painter(self.plan.sides[self.side_idx], srcs),
                                      buf.getvalue())
        except Exception as e:  # the preview must never crash the app
            self.view.show_message(t("preview_fail", err=e))

    def _side_painter(self, side, srcs):
        rasters = self.rasters
        if not self.numbers.isChecked():
            return lambda p, s2w, dpr, wanted, sync: paint_side(p, side, srcs, s2w, dpr,
                                                                 rasters, wanted, sync)
        infos = self.infos
        blank = t("pn_blank")
        half = lambda i: t("pn_half", page=i.pdf_page + 1,
                           half=t("pn_left") if i.half == "left" else t("pn_right"))

        label = self._gang_label if self._gang_active else None

        def paint(p, s2w, dpr, wanted, sync):
            paint_side(p, side, srcs, s2w, dpr, rasters, wanted, sync)
            paint_numbers(p, side, s2w, infos, blank, half, label)
        return paint

    def _numbers_toggled(self, on):
        store().setValue("page_numbers", bool(on))
        self.render_current()

    def _raster_sources(self):
        """Print and visible layers in drawing order (layers below, print, layers above)."""
        # the crease PDF is drawn as green guides, not as a layer
        visible = [e for e in self.layers if e["layer"].visible and e["layer"].kind != "crease"]
        st = self.read_settings()
        fill = (st.bleed_fill, mm(max(0.0, st.bleed)))
        out = []
        for e in [e for e in visible if e["layer"].position == "below"]:
            ls = layer_source(e["layer"], e["pdf"], e["infos"], key="L")
            out.append(PreviewSource(e["layer"].path, e["infos"], ls.page_for, 0.6, fill))
        out.append(PreviewSource(self.gang_path if self._gang_active else self.path,
                                 self.infos, fill=fill))
        for e in [e for e in visible if e["layer"].position != "below"]:
            ls = layer_source(e["layer"], e["pdf"], e["infos"], key="L")
            out.append(PreviewSource(e["layer"].path, e["infos"], ls.page_for, 0.6, fill))
        return out

    def _side_labels(self):
        out = []
        for sd in self.plan.sides:
            if self.plan.gang:                            # gang run: “Sheet 1 · front · A×6 B×15”
                side = t("side_back") if sd.is_back else t("side_front")
                jobs = " ".join(f"{gang_letter(i)}×{k}" for i, (_n, _q, k, _m) in enumerate(self.plan.gang))
                out.append(f"{t('slug_sheet')} {sd.sheet_no} · {side} · {jobs}")
                continue
            if sd.tile:                                   # poster piece: “A1 · page 1”
                r, c, _rows, _cols = sd.tile
                pg = sd.items[0].page + 1 if sd.items and sd.items[0].page is not None else 0
                out.append(f"{tile_name(r, c)} · " + t("ov_pages", pages=pg))
                continue
            side = t("side_back") if sd.is_back else t("side_front")
            pages = []
            for it in sorted(sd.items, key=lambda it: (-round(it.trim[1]), it.trim[0])):
                if it.page is not None and it.page + 1 not in pages:
                    pages.append(it.page + 1)
            txt = f"{t('slug_sheet')} {sd.sheet_no} · {side}"
            if pages:
                shown = ", ".join(map(str, pages[:6])) + ("…" if len(pages) > 6 else "")
                txt += " · " + t("ov_pages", pages=shown)
            out.append(txt)
        return out

    # ------------------------------------------------------------- view mode
    def set_view_mode(self, mode):
        self.view_mode = mode
        store().setValue("view_mode", mode)
        self.stack.setCurrentIndex(1 if mode == "all" else 0)
        self._zoom_tips()
        self.render_current()
        self._zoom_label()
        if mode == "all":
            QTimer.singleShot(0, self._scroll_to_current)

    def _zoom_tips(self):
        """The zoom tooltip says what the current view does (click vs double-click)."""
        tip = t("zoom_tip_all" if self.view_mode == "all" else "zoom_tip")
        for w in self._zoom_tip_widgets:
            w.setToolTip(tip)

    def _scroll_to_current(self):
        r = self.overview.rect_of(self.side_idx)
        if r is not None:
            self.ov_scroll.ensureVisible(int(r.center().x()), int(r.center().y()),
                                         0, int(r.height() / 2 + 30))

    def _open_side(self, i):
        self.side_idx = i
        self._update_nav()
        self.mode_sheet.setChecked(True)
        self.set_view_mode("sheet")

    def _zoom(self, f):
        if self.view_mode == "all":
            self.overview.zoom_by(f)
        else:
            self.view.zoom_by(f)

    def _zoom_fit(self):
        if self.view_mode == "all":
            self.overview.zoom_fit()
        else:
            self.view.zoom_fit()

    def _zoom_actual(self):
        if self.view_mode == "all":
            self.overview.zoom_actual()
        else:
            self.view.zoom_actual()

    def _zoom_label(self):
        if not hasattr(self, "zoom_lbl"):            # signal during window construction
            return
        if self.view_mode == "all":
            self.zoom_lbl.setText(f"{self.overview.percent()} %" if self.overview.plan else "–")
        else:
            self.zoom_lbl.setText(f"{self.view.percent()} %" if self.view.pw else "–")

    def step(self, d):
        if not self.plan:
            return
        i = self.side_idx + d
        if 0 <= i < len(self.plan.sides):
            self.side_idx = i
            self._update_nav()
            if self.view_mode == "all":
                self.overview.current = i
                self.overview.update()
                self._scroll_to_current()
            else:
                self.render_current()

    def _update_nav(self):
        has = self.plan is not None
        n = len(self.plan.sides) if has else 0
        self.prev_btn.setEnabled(has and self.side_idx > 0)
        self.next_btn.setEnabled(has and self.side_idx < n - 1)
        self.save_btn.setEnabled(has)
        if has:
            side = self.plan.sides[self.side_idx]
            label = t("side_back") if side.is_back else t("side_front")
            self.side_label.setText(t("side_label", n=side.sheet_no,
                                      total=self.plan.n_sheets, side=label))
        else:
            self.side_label.setText("–")


    # ---------------------------------------------------- export / checking
    def _add_icc(self, path):
        info = icc_from_file(path)
        if info is None:
            return -1
        i = self.icc.count() - 1          # before “Choose ICC file…”
        self.icc.insertItem(i, info.desc, path)
        self.icc.setItemData(i, path, Qt.ToolTipRole)
        return i

    def _icc_changed(self, idx):
        if self.icc.itemData(idx) == CHOOSE:
            path, _ = QFileDialog.getOpenFileName(self, t("icc_dialog"), self.last_dir,
                                                  t("icc_filter"))
            self.icc.blockSignals(True)
            if path:
                existing = self.icc.findData(path)
                i = existing if existing >= 0 else self._add_icc(path)
                if i < 0:
                    QMessageBox.warning(self, APP_NAME, t("icc_bad"))
                    i = self._icc_prev
                self.icc.setCurrentIndex(i)
            else:
                self.icc.setCurrentIndex(self._icc_prev)
            self.icc.blockSignals(False)
        self._icc_prev = self.icc.currentIndex()
        self.changed()

    def _selected_pages(self, s, logical=False):
        """Selected pages, 1-based: logical pages, or PDF pages for the preflight."""
        n = len(self.infos) if self.infos else len(self.src.pages)
        try:
            sel = parse_range(s.page_range, n)
        except ImposeError:
            sel = list(range(n))
        if logical or not self.infos:
            return {i + 1 for i in sel}
        return {self.infos[i].pdf_page + 1 for i in sel if i < len(self.infos)}

    def _check(self, s):
        """(export plan, [(level, text)]) for the current settings."""
        ex = resolve_export(s, self.profile)
        src_oi = self.profile.pdfx_intent
        src_id = None
        if src_oi is not None:
            src_id = src_oi.identifier or (src_oi.icc.condition_id if src_oi.icc else None)
        items = [("warn", w) for w in ex.warnings]
        items += evaluate(self.findings, ex.family, self._selected_pages(s), src_id,
                          ex.intent_id if ex.intent == "icc" else None,
                          self.profile.encrypted)
        return ex, items

    def _update_preflight(self, s):
        if self.src is None or self.profile is None:
            self.preflight.setText("")
            return
        ex, items = self._check(s)
        title = t("preflight_title", std=ex.label) if ex.label else t("preflight_title_none")
        rows = [f"<b>{title}</b>"]
        if ex.label or ex.icc_desc:
            rows.append(f"<span style='color:#808080'>→ {ex.label or t('std_none')}"
                        f"{' · ' + ex.icc_desc if ex.icc_desc else ''}</span>")
        if self.layers and s.export_combined and ex.family in ("x1a", "x3"):
            items.append(("warn", t("pf_layers_std", std=ex.label)))
        for lvl, text in items:
            sym, col = PF_STYLE.get(lvl, PF_STYLE["info"])
            rows.append(f"<span style='color:{col}'>{sym}</span> {text}")
        self.preflight.setText("<br>".join(rows))
        sel = self._selected_pages(s, logical=True)
        for row in self.layer_rows:
            e = row.entry
            row.set_check(evaluate_layer(e["findings"], e["layer"], e["infos"], self.infos or [], sel))

    def _confirm_standard(self, s):
        ex, items = self._check(s)
        errors = [txt for lvl, txt in items if lvl == "error"]
        if not ex.label or not errors:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(APP_NAME)
        box.setText(t("save_confirm", std=ex.label, errors="\n".join("• " + e for e in errors)))
        yes = box.addButton(t("save_anyway"), QMessageBox.AcceptRole)
        box.addButton(t("cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is yes

    # ------------------------------------------------------------- saving
    def save(self):
        if not self.plan or not self.src:
            return
        s = self.read_settings()
        layers = [(e["layer"], e["pdf"], e["infos"]) for e in self.layers]
        want_print = s.export_print or not layers
        want_layers = bool(layers) and s.export_layers
        want_combined = bool(layers) and s.export_combined
        want_dummy = s.export_dummy and s.mode in ("booklet", "signatures")
        if not (want_print or want_layers or want_combined):
            QMessageBox.warning(self, APP_NAME, t("out_none"))
            return
        base = os.path.basename(self.path)
        if base.lower().endswith(".pdf"):
            base = base[:-4]
        suggested = os.path.join(os.path.dirname(self.path), f"{base}{t('suffix')}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, t("save_title"), suggested, t("pdf_filter"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        paths = output_paths(path, [ly for ly, _, _ in layers])
        targets = ([paths["print"]] if want_print else []) + \
                  (paths["layers"] if want_layers else []) + \
                  ([paths["combined"]] if want_combined else []) + \
                  ([paths["dummy"]] if want_dummy else [])
        src_abs = {os.path.abspath(self.path)} | {os.path.abspath(e["layer"].path) for e in self.layers}
        if any(os.path.abspath(p) in src_abs for p in targets):
            QMessageBox.warning(self, APP_NAME, t("no_overwrite"))
            return
        exists = [p for p in targets if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(path)]
        if exists:
            r = QMessageBox.question(self, APP_NAME, t("overwrite", files="\n".join(
                os.path.basename(p) for p in exists)))
            if r != QMessageBox.Yes:
                return
        if not self._confirm_standard(s):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            src = self.gang_src if self._gang_active else self.src
            if self._gang_active:
                layers = []                               # layers follow the pages of one PDF
            written = export_outputs(src, self.infos, self.profile, self.plan, s, layers, path,
                                     want_print, want_layers, want_combined,
                                     filename=os.path.basename(self.path), want_dummy=want_dummy)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, t("save_fail", err=e))
            return
        QApplication.restoreOverrideCursor()
        self._store_settings()
        self.statusBar().showMessage(t("saved_status", path=written[0] if written else path), 10000)
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(t("saved_files", n=len(written), files="\n".join(os.path.basename(p) for p in written)))
        openb = box.addButton(t("open_saved"), QMessageBox.AcceptRole)
        folderb = box.addButton(t("open_folder"), QMessageBox.ActionRole)
        box.addButton(t("close"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is openb and written:
            QDesktopServices.openUrl(QUrl.fromLocalFile(written[0]))
        elif box.clickedButton() is folderb:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    # ------------------------------------------------------------- layers
    def add_layer(self):
        if self.src is None:
            QMessageBox.information(self, APP_NAME, t("drop_here"))
            return
        path, _ = QFileDialog.getOpenFileName(self, t("layer_dialog"), self.last_dir,
                                              t("pdf_open_filter"))
        if not path:
            return
        try:
            pdf = pikepdf.open(path)
            s = self.read_settings()
            infos = analyze(pdf, s.assume_bleed, s.split_spreads)
            findings = scan(pdf)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, t("cant_open", err=e))
            return
        kind = guess_kind(path, findings.spots.keys())
        layer = Layer(path, kind=kind, position=LAYER_KINDS[kind][1])
        if kind == "crease":
            # crease lines are not a printed layer – they belong to the Creasing section
            self._set_crease_entry({"layer": layer, "pdf": pdf, "infos": infos, "findings": findings})
            self.crease_box.btn.setChecked(True)          # make sure the section is open
            self.statusBar().showMessage(t("crease_moved"), 8000)
            return
        if len(infos) == 1 and self.src is not None and len(self.src.pages) > 1:
            layer.pages = "first"
        self.layers.append({"layer": layer, "pdf": pdf, "infos": infos, "findings": findings})
        self._rebuild_layer_rows()
        self.changed()

    def _remove_layer(self, entry):
        self.layers = [e for e in self.layers if e is not entry]
        try:
            entry["pdf"].close()
        except Exception:
            pass
        self._rebuild_layer_rows()
        self.changed()

    def _clear_layers(self):
        for e in self.layers:
            try:
                e["pdf"].close()
            except Exception:
                pass
        self.layers = []
        self._rebuild_layer_rows()

    def _rebuild_layer_rows(self):
        if not hasattr(self, "layers_col"):
            return
        for row in self.layer_rows:
            _drop_widget(self.layers_col, row)
        self.layer_rows = []
        for e in self.layers:
            if e["layer"].kind == "crease":         # shown in the Creasing section
                continue
            row = LayerRow(e)
            row.changed.connect(self.changed)
            row.removed.connect(self._remove_layer)
            self.layers_col.addWidget(row)
            self.layer_rows.append(row)


def _offer_linux_menu(win):
    """First start on Linux: offer a menu entry (icon in the dock / app grid)."""
    from . import desktop_linux as dl
    try:
        if not dl.needs_install():
            return
        if dl.installed_exec() is not None:
            dl.install()                      # already accepted once – the app just moved
            return
        if store().value("linux/menu_declined", False) in (True, "true"):
            return
        box = QMessageBox(win)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Question)
        box.setText(t("desktop_offer"))
        yes = box.addButton(t("desktop_add"), QMessageBox.AcceptRole)
        box.addButton(t("desktop_later"), QMessageBox.RejectRole)
        never = box.addButton(t("desktop_never"), QMessageBox.DestructiveRole)
        box.exec()
        if box.clickedButton() is yes:
            dl.install()
            win.statusBar().showMessage(t("desktop_done"), 10000)
        elif box.clickedButton() is never:
            store().setValue("linux/menu_declined", True)
    except Exception:
        pass


def _excepthook(etype, value, tb):
    """Unhandled error: show it and write it to the log (pythonw has no console)."""
    import traceback
    text = "".join(traceback.format_exception(etype, value, tb))
    try:
        folder = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Imprimo")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "imprimo-chyba.log"), "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
    if sys.stderr:
        sys.stderr.write(text)
    try:
        QMessageBox.critical(None, APP_NAME, text[-2000:])
    except Exception:
        pass


def main(app=None, splash=None):
    sys.excepthook = _excepthook
    if app is None:
        from .splash import start
        app, splash = start()
    migrate_settings()
    apply_theme(store().value("theme", "system"))
    w = MainWindow()
    w.show()
    if splash is not None:
        splash.finish(w)

    # macOS delivers files (Finder → Open With, drop on the Dock icon) as an event
    from PySide6.QtCore import QEvent, QObject

    class _FileOpen(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.FileOpen and ev.file():
                w.open_file(ev.file())
                return True
            return False

    w._file_open_filter = _FileOpen(app)
    app.installEventFilter(w._file_open_filter)

    if sys.platform.startswith("linux"):
        QTimer.singleShot(900, lambda: _offer_linux_menu(w))
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        w.open_file(sys.argv[1])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
