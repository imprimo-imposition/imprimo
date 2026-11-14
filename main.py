"""Imprimo entry point. If start-up fails, the error is written to a log and
shown in a message box (important when there is no console, e.g. Imprimo.exe)."""
import os
import sys
import traceback


def report(text):
    log = "?"
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, "Imprimo")
        os.makedirs(folder, exist_ok=True)
        log = os.path.join(folder, "imprimo-chyba.log")
        with open(log, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    msg = (f"Imprimo could not start. / Imprimo sa nepodarilo spustiť.\n\n{text[-1500:]}\n\n"
           f"Log / Záznam chyby: {log}")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Imprimo", 0x10)
    elif sys.stderr:
        print(msg, file=sys.stderr)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from imprimo.splash import start
        app, splash = start()                 # splash screen right after start
        from imprimo.gui import main
    except Exception:
        report(traceback.format_exc())
        sys.exit(1)
    sys.exit(main(app, splash))
