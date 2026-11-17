IMPRIMO {V} for Linux (x86_64) – portable test version
=====================================================

Start
-----
1. Extract the ZIP (e.g. into ~/Applications or ~/Programs).
2. Run "Imprimo" (double-click or ./Imprimo in a terminal).
3. On first start Imprimo offers to add itself to the applications menu –
   that gives it an icon in the dock / app grid and "Open With" for PDFs.
   If the folder is moved later, the menu entry is updated automatically.

Remove the menu entry: ./uninstall-menu.sh, then delete the folder.
(./install-menu.sh adds it again manually.)

If files can't be executed (permissions lost while extracting):
    chmod +x Imprimo install-menu.sh uninstall-menu.sh runtime/bin/python3.12

If it doesn't start
-------------------
Run ./Imprimo in a terminal – it prints the error. The log is also in
~/Imprimo/imprimo-chyba.log. On plain X11 installations the xcb-cursor
library is sometimes missing:  sudo dnf install xcb-util-cursor

License
-------
Imprimo is free software under the GNU GPL v3.0 or later (LICENSE.txt).
Bundled libraries and their licenses: THIRD-PARTY-NOTICES.txt.
Source code and new versions: https://github.com/imprimo-imposition/imprimo
