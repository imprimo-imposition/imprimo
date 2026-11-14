# Packaging

Imprimo ships as portable folders with their own Python 3.12, so users install nothing.

| Package | Content |
|---|---|
| `Imprimo-X.Y.Z-windows.zip` | `Imprimo.exe` (small launcher → `runtime\pythonw.exe app\main.py`), `Imprimo-diagnostics.bat` (same with a console), `runtime\`, `app\`, README.txt, CITAJ-MA.txt |
| `Imprimo-X.Y.Z-macOS.zip` | `Imprimo.app` (Apple Silicon, macOS 15+): `Contents/MacOS/Imprimo` shell launcher + `python`, `Contents/lib`, `Contents/Resources/app`, `en.lproj` / `sk.lproj`, Info.plist with `CFBundleDevelopmentRegion=en` |
| `Imprimo-X.Y.Z-linux-x86_64.zip` | `Imprimo` shell launcher, `install-menu.sh`, `uninstall-menu.sh`, `runtime/`, `app/` |
| `imprimo-X.Y.Z.zip` | source |

## Making a release

1. Set `__version__` in `imprimo/__init__.py` and the heading of `README.md`.
2. Run the tests (`python tests/make_samples.py && python tests/test_core.py`).
3. Put the previous release zips in one folder and run (macOS or Linux):

   ```bash
   python3 packaging/package.py 0.6.4 --base ~/Imprimo-releases/0.6.3
   ```

   The zips land in `dist/`. The runtimes are taken over from the previous release; only
   the app, the readmes (`packaging/docs/`, `{V}` = version) and the version change.
   Windows readmes get CRLF line endings.
4. `pip install ziglang` lets the script rebuild `Imprimo.exe` with the new version
   resource (`packaging/windows/launcher.c`, `launcher.rc`, icon from the assets).

## Runtimes (only needed when dependencies change)

The current runtimes are Python 3.12.16 from conda-forge (`python` package plus its
libraries: bzip2, expat, libffi, liblzma, zlib; ncurses / libcxx on macOS) with these
wheels installed into its `site-packages`:

    PySide6-Essentials 6.12.0, shiboken6 6.12.0, pikepdf 10.18.0, pypdfium2 5.15.2,
    Pillow 13.0.0, fonttools 4.68.0, lxml 6.1.3, packaging 26.3

Trimming that keeps the packages small:

- Only the Qt modules Imprimo uses (QtCore, QtGui, QtWidgets) and the Qt plugins it
  needs; QML, designer tools and unused libraries removed.
- Tests, headers, static libraries and unused standard-library parts removed.
- macOS: universal2 binaries thinned to arm64 (`lipo -thin arm64`). The app is neither
  signed nor notarised; users remove the quarantine as described in `docs/mac-README.txt`.
- Python files are precompiled with `--invalidation-mode checked-hash`.

To update a dependency, unpack the latest release, `pip install --target` the new wheel
for that platform into the runtime's `site-packages` (replacing the old one), zip it again
and use it as the base.
