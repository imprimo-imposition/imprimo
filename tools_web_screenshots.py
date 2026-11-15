"""Screenshots of the real macOS Imprimo window for the website (docs/mac/*.webp).

Drives its own Imprimo window (own settings, the user's are untouched) through the sample
lessons and captures it with macOS screencapture – the window with its shadow, like
Cmd+Shift+4, Space. Needs: macOS, Screen Recording permission for the app running this,
and a Python with pyobjc-framework-Quartz (to find the window id).

    python3 -m venv /tmp/qv && /tmp/qv/bin/pip install pyobjc-framework-Quartz
    for L in sk en; do for T in light dark; do
      .venv/bin/python tools_web_screenshots.py /tmp/shots $L $T /tmp/qv/bin/python; done; done
    then convert to WebP (1600 px hero, 1300 px others) into docs/mac/

Run it with the Python of the packaged Imprimo.app, not the .venv one: macOS draws the
window frame and title bar per app bundle, so a window of the development Python looks
different from the released app. Unzip dist/Imprimo-X.Y.Z-macOS.zip and use
    Imprimo.app/Contents/MacOS/python tools_web_screenshots.py /tmp/shots sk light /tmp/qv/bin/python
(the script imports imprimo from this repository, the runtime comes from the app).
"""
import sys, os, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs(sys.argv[1], exist_ok=True)
OUT, LANG, THEME, QPY = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
from PySide6.QtCore import QSettings
from imprimo.splash import start
app, splash = start()
splash.close()
from imprimo import gui, i18n, theme
gui.store = lambda: QSettings(OUT + "/../mac_settings.ini", QSettings.IniFormat)
theme.apply_theme(THEME)
w = gui.MainWindow(); i18n.set_language(LANG); w._build_ui(); w._build_menu(); w._load_settings()
w.resize(1440, 900); w.move(80, 60); w.show(); w.raise_(); w.activateWindow()
ex = os.path.abspath("examples")

def pump(sec=0.6):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)

def settle():
    w.refresh(); pump(2.5)

def wid():
    code = ("import Quartz,sys\n"
            "for x in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0):\n"
            f"  if x.get('kCGWindowOwnerPID')=={os.getpid()} and x.get('kCGWindowLayer')==0 and x['kCGWindowBounds']['Width']>1000: print(x['kCGWindowNumber']); break\n")
    return subprocess.run([QPY, "-c", code], capture_output=True, text=True).stdout.strip()

def shot(name):
    w.raise_(); pump(0.4)
    n = wid()
    subprocess.run(["screencapture", "-x", f"-l{n}", f"{OUT}/{name}_{LANG}_{THEME}.png"], check=True)

def show(section):
    """Scroll the left panel so the section is at the top (None = back to the top)."""
    sa = w.mode.parentWidget()
    while sa is not None and not hasattr(sa, "ensureWidgetVisible"):
        sa = sa.parentWidget()
    if sa is None:
        return
    bar = sa.verticalScrollBar()
    if section is None:
        bar.setValue(0)
    else:
        section.btn.setChecked(True); pump(0.3)
        y = section.mapTo(sa.widget(), section.rect().topLeft()).y()
        bar.setValue(max(0, y - 8))
    pump(0.4)

def lesson(f, preset):
    w.open_lesson(os.path.join(ex, f), preset); settle()

w.setWindowTitle(f"Imprimo {__import__('imprimo').__version__}")
lesson("01_vizitky_90x50_obojstranne.pdf", "preset_cards2")
w.set_view_mode("sheet"); w.guides.setChecked(False); w.numbers.setChecked(False); settle(); show(None); shot("hero")
lesson("05_brozura_A5_12_stran.pdf", "preset_booklet")
w.numbers.setChecked(True); w.set_view_mode("all"); settle(); show(w.booklet_box); shot("booklet")
lesson("04_DL_skladacka_zavinovacia.pdf", "preset_dl")
w.numbers.setChecked(False); w.guides.setChecked(True); w.set_view_mode("sheet")
settle(); show(w.crease_box); shot("crease")
lesson("09_plagat_A2.pdf", "preset_poster")
w.guides.setChecked(False); w.set_view_mode("all"); settle(); show(w.tile_box); shot("poster")
lesson("10_vizitky_jana.pdf", "preset_gang_cards")
w.add_jobs([ex + "/10_vizitky_peter.pdf", ex + "/10_vizitky_eva.pdf"])
w.jobs[1]["qty"] = 250; w.jobs[2]["qty"] = 50; w._rebuild_job_rows()
w.numbers.setChecked(True); w.set_view_mode("sheet"); settle(); show(w.gang_box); shot("gang")
w.numbers.setChecked(False)
lesson("11_zbornik_A6_48_stran.pdf", "preset_signatures")
w.numbers.setChecked(True); w.guides.setChecked(False); w.set_view_mode("all"); settle()
show(w.sig_box); shot("signatures")
w.numbers.setChecked(False)
w.close(); pump(0.3)
print("done", LANG, THEME)
