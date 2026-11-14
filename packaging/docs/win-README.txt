IMPRIMO {V} for Windows (portable test version)
===============================================

Start
-----
1. Extract the whole ZIP into a folder (e.g. Desktop or Documents).
   Don't run the program from inside the ZIP.
2. Double-click Imprimo.exe.

Windows may show "Windows protected your PC" (SmartScreen) because the
program isn't digitally signed: click "More info" → "Run anyway".

If it doesn't start
-------------------
- Run Imprimo-diagnostics.bat – a console window shows the error.
- The error is also written to %LOCALAPPDATA%\Imprimo\imprimo-chyba.log

Contents
--------
Imprimo.exe                 launcher
Imprimo-diagnostics.bat     start with error output
app\                        Imprimo (source code, README.md)
runtime\                    Python 3.12 and libraries (PySide6/Qt, pikepdf, pdfium…)

Nothing is installed. Settings are stored in the user registry
(HKCU\Software\Imprimo). To uninstall, delete the folder.

Requirements: Windows 10 or 11, 64-bit.
