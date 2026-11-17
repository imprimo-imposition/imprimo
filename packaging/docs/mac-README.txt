IMPRIMO {V} for macOS (test version, Apple Silicon, macOS 15 or newer)
=======================================================================

Install
-------
1. Move Imprimo.app to the Applications folder.
2. First start: the app isn't notarized by Apple, so macOS blocks it.
   - Click Imprimo.app → in the message choose "Done".
   - System Settings → Privacy & Security → next to "Imprimo" click
     "Open Anyway" and confirm with your password.
   Or in Terminal (one line):
     xattr -dr com.apple.quarantine /Applications/Imprimo.app
3. From then on it starts normally (Dock, Launchpad).

Open PDFs by dropping them on the Dock icon or via Finder →
right-click → Open With → Imprimo.

If it doesn't start, run this in Terminal and send the output:
  /Applications/Imprimo.app/Contents/MacOS/Imprimo

License
-------
Imprimo is free software under the GNU GPL v3.0 or later (LICENSE.txt).
Bundled libraries and their licenses: THIRD-PARTY-NOTICES.txt.
Source code and new versions: https://github.com/imprimo-imposition/imprimo
