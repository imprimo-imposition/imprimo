"""Fast start: QApplication, icon and splash screen before the heavy
libraries (pikepdf, pdfium, fontTools) are loaded."""
import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from . import APP_NAME, __version__

ICON_DIR = os.path.join(os.path.dirname(__file__), "assets", "icon")


def _mac_set_app_name(name: str):
    """When started from Terminal, macOS takes the app name (menu, Dock) from Python.app.
    We overwrite it in the main bundle's infoDictionary before QApplication exists."""
    import ctypes
    import ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    addr = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    vp = ctypes.c_void_p
    send0 = ctypes.CFUNCTYPE(vp, vp, vp)(addr)
    send_str = ctypes.CFUNCTYPE(vp, vp, vp, ctypes.c_char_p)(addr)
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, vp, vp, vp)(addr)
    send_set = ctypes.CFUNCTYPE(None, vp, vp, vp, vp)(addr)
    C, S = objc.objc_getClass, objc.sel_registerName

    bundle = send0(C(b"NSBundle"), S(b"mainBundle"))
    if not bundle:
        return
    value = send_str(C(b"NSString"), S(b"stringWithUTF8String:"), name.encode("utf-8"))
    for getter in (b"infoDictionary", b"localizedInfoDictionary"):
        info = send0(bundle, S(getter))
        # only a mutable dictionary can be changed – otherwise it would raise
        if info and send_bool(info, S(b"respondsToSelector:"), S(b"setObject:forKey:")):
            for key in (b"CFBundleName", b"CFBundleDisplayName"):
                k = send_str(C(b"NSString"), S(b"stringWithUTF8String:"), key)
                send_set(info, S(b"setObject:forKey:"), value, k)


def app_icon() -> QIcon:
    if sys.platform == "darwin":
        # macOS: icon on the Apple grid (with margin), otherwise it looks larger in the Dock
        mac = os.path.join(ICON_DIR, "imprimo-1024-mac.png")
        if os.path.exists(mac):
            return QIcon(mac)
    icon = QIcon()
    png = os.path.join(ICON_DIR, "png")
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        p = os.path.join(png, f"imprimo-{s}.png")
        if os.path.exists(p):
            icon.addFile(p)
    big = os.path.join(ICON_DIR, "imprimo-1024.png")
    if os.path.exists(big):
        icon.addFile(big)
    return icon


def _loading_text():
    from PySide6.QtCore import QLocale, QSettings
    lang = QSettings("Imprimo", "Imprimo").value("language", "")
    if lang not in ("sk", "en"):
        lang = "sk" if QLocale.system().name()[:2] in ("sk", "cs") else "en"
    return "Načítavam…" if lang == "sk" else "Loading…"


def _splash_pixmap(dpr: float) -> QPixmap:
    w, h = 440, 250
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 18, 18)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#3a3b3e"))
    g.setColorAt(1, QColor("#0c0c0d"))
    p.fillPath(path, g)
    p.setPen(QColor(255, 255, 255, 40))
    p.drawPath(path)
    ic = QPixmap(os.path.join(ICON_DIR, "png", "imprimo-256.png"))
    if not ic.isNull():
        p.drawPixmap(QRectF(34, 61, 128, 128), ic, QRectF(ic.rect()))
    f = QFont()
    f.setPointSizeF(30)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#f2f2f2"))
    p.drawText(QRectF(186, 70, 240, 50), Qt.AlignLeft | Qt.AlignVCenter, APP_NAME)
    f.setPointSizeF(11)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor("#a8abb0"))
    p.drawText(QRectF(188, 120, 240, 24), Qt.AlignLeft | Qt.AlignVCenter,
               f"{__version__} · imposition")
    p.drawText(QRectF(188, 150, 240, 24), Qt.AlignLeft | Qt.AlignVCenter, _loading_text())
    p.end()
    return pm


def start():
    """Creates the application and shows the splash screen right away. Returns (app, splash)."""
    if sys.platform == "win32":
        # own taskbar group → Imprimo's icon instead of Python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Imprimo.Imprimo")
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            _mac_set_app_name(APP_NAME)
        except Exception:
            pass
    if sys.platform.startswith("linux"):
        # harmless Qt Wayland text-input warnings when focus moves between fields
        rules = os.environ.get("QT_LOGGING_RULES", "")
        if "qt.qpa.wayland.textinput" not in rules:
            os.environ["QT_LOGGING_RULES"] = ";".join(
                r for r in (rules, "qt.qpa.wayland.textinput=false") if r)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    if sys.platform.startswith("linux"):
        # Wayland/GNOME match the window to imprimo.desktop for its icon and name
        app.setDesktopFileName("imprimo")
    splash = None
    if not os.environ.get("IMPRIMO_NO_SPLASH"):
        splash = QSplashScreen(_splash_pixmap(app.primaryScreen().devicePixelRatio()
                                              if app.primaryScreen() else 1.0))
        splash.setAttribute(Qt.WA_TranslucentBackground)
        splash.show()
        app.processEvents()
    return app, splash
