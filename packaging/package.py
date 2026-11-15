#!/usr/bin/env python3
"""Builds the Imprimo release zips from the current source.

The bundled Python runtimes are not rebuilt: each package is made from the
previous release zip of the same platform, with the app folder, the readmes and
the version replaced. Put the previous release zips in one folder and run

    python3 packaging/package.py 0.7.1 --base ~/Imprimo-releases/0.7.0

Output (default: dist/):
    Imprimo-0.6.4-windows.zip, Imprimo-0.6.4-macOS.zip,
    Imprimo-0.6.4-linux-x86_64.zip, imprimo-0.6.4.zip (source)

Needs macOS or Linux with `zip` and `unzip` (they keep symlinks and permissions).
Python files are precompiled for Python 3.12 (the runtime version) when a 3.12
interpreter is available: this one, --python, or the runtime inside the macOS
package on an Apple Silicon Mac. Without it the packages still work, the first
start is just a little slower.

The Windows launcher (Imprimo.exe) is recompiled with the new version number when
`python3 -m ziglang` works (pip install ziglang); otherwise the previous exe is kept.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "packaging")
ICON_DIR = os.path.join("imprimo", "assets", "icon")

PLATFORMS = {
    # name: (zip pattern, app dir inside the package, icon files not needed there, docs prefix)
    "windows": ("Imprimo-*-windows.zip", "app",
                ("imprimo.icns", "imprimo-1024-mac.png"), "win"),
    "linux-x86_64": ("Imprimo-*-linux-x86_64.zip", "app",
                     ("imprimo.ico", "imprimo.icns", "imprimo-1024-mac.png"), "linux"),
    "macOS": ("Imprimo-*-macOS.zip", "Imprimo.app/Contents/Resources/app",
              ("imprimo.ico",), "mac"),
}


def run(*cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def find_python312(arg, work):
    cands = [arg] if arg else []
    if sys.version_info[:2] == (3, 12):
        cands.append(sys.executable)
    cands += glob.glob(os.path.join(work, "macOS", "*", "Imprimo.app", "Contents", "MacOS", "python"))
    cands += [shutil.which("python3.12")]
    for c in cands:
        if not c:
            continue
        try:
            out = subprocess.run([c, "-c", "import sys; print(sys.version_info[:2])"],
                                 capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip() == "(3, 12)":
                return c
        except Exception:
            pass
    return None


def copy_app(dst, drop_icons):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    shutil.copy2(os.path.join(ROOT, "main.py"), dst)
    shutil.copy2(os.path.join(ROOT, "README.md"), dst)
    for name in ("LICENSE", "THIRD-PARTY-NOTICES.txt"):     # read by the About dialog
        shutil.copy2(os.path.join(ROOT, name), dst)
    # sample files for Help → Sample files (the generator script stays in the source zip)
    shutil.copytree(os.path.join(ROOT, "examples"), os.path.join(dst, "examples"),
                    ignore=shutil.ignore_patterns("*.py", "ZADANIE.md", "__pycache__", ".DS_Store"))
    shutil.copytree(os.path.join(ROOT, "imprimo"), os.path.join(dst, "imprimo"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ("imprimo-1024-master.png",) + tuple(drop_icons):
        p = os.path.join(dst, ICON_DIR, f)
        if os.path.exists(p):
            os.remove(p)


def write_docs(prefix, target, version, crlf):
    for name in ("README", "CITAJ-MA"):
        with open(os.path.join(HERE, "docs", f"{prefix}-{name}.txt"), encoding="utf-8") as f:
            text = f.read().replace("{V}", version)
        if crlf:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        with open(os.path.join(target, f"{name}.txt"), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    # licence files next to the readmes
    for name, out in (("LICENSE", "LICENSE.txt"), ("THIRD-PARTY-NOTICES.txt", "THIRD-PARTY-NOTICES.txt")):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            text = f.read()
        if crlf:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        with open(os.path.join(target, out), "w", encoding="utf-8", newline="") as f:
            f.write(text)


def build_launcher(version, out_exe):
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy2(os.path.join(HERE, "windows", "launcher.c"), tmp)
        shutil.copy2(os.path.join(ROOT, ICON_DIR, "imprimo.ico"), tmp)
        with open(os.path.join(HERE, "windows", "launcher.rc"), encoding="utf-8") as f:
            rc = f.read()
        vc = version.replace(".", ",") + ",0"
        rc = re.sub(r"(FILEVERSION|PRODUCTVERSION) [\d,]+", rf"\g<1> {vc}", rc)
        rc = re.sub(r'"(FileVersion|ProductVersion)", "[^"]*"', rf'"\g<1>", "{version}"', rc)
        with open(os.path.join(tmp, "launcher.rc"), "w", encoding="utf-8") as f:
            f.write(rc)
        run(sys.executable, "-m", "ziglang", "cc", "-target", "x86_64-windows-gnu", "-municode",
            "-Wl,--subsystem,windows", "-Os", "-s", "-o", "Imprimo.exe", "launcher.c",
            "launcher.rc", cwd=tmp)
        shutil.copy2(os.path.join(tmp, "Imprimo.exe"), out_exe)
        return True
    except Exception as e:
        print(f"  ! launcher not rebuilt ({e}); keeping the previous Imprimo.exe")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--base", required=True, help="folder with the previous release zips")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--python", help="Python 3.12 interpreter for precompiling")
    ap.add_argument("--only", nargs="*", choices=list(PLATFORMS) + ["source"])
    a = ap.parse_args()
    V = a.version
    os.makedirs(a.out, exist_ok=True)
    out_dir = os.path.abspath(a.out)
    want = set(a.only or list(PLATFORMS) + ["source"])

    with open(os.path.join(ROOT, "imprimo", "__init__.py"), encoding="utf-8") as f:
        m = re.search(r'__version__ = "([^"]+)"', f.read())
    if m and m.group(1) != V:
        print(f"! imprimo/__init__.py says {m.group(1)}, packaging as {V}")

    work = tempfile.mkdtemp(prefix="imprimo-pkg-")
    try:
        # unpack the bases first (the macOS runtime may be the Python used to precompile)
        bases = {}
        for name, (pattern, *_rest) in PLATFORMS.items():
            if name not in want:
                continue
            zips = sorted(glob.glob(os.path.join(os.path.expanduser(a.base), pattern)))
            if not zips:
                print(f"! no {pattern} in {a.base} – skipping {name}")
                continue
            d = os.path.join(work, name)
            os.makedirs(d)
            run("unzip", "-q", zips[-1], "-d", d)
            top = [x for x in os.listdir(d) if not x.startswith("__MACOSX")]
            bases[name] = (d, top[0])
        py312 = find_python312(a.python, work)
        print("precompile with:", py312 or "– (no Python 3.12 found, skipping .pyc)")

        for name, (d, old_top) in bases.items():
            _pattern, app_rel, drop, prefix = PLATFORMS[name]
            new_top = f"Imprimo-{V}-{name}"
            os.rename(os.path.join(d, old_top), os.path.join(d, new_top))
            pkg = os.path.join(d, new_top)
            print(f"{name}: {old_top} → {new_top}")
            copy_app(os.path.join(pkg, app_rel), drop)
            write_docs(prefix, pkg, V, crlf=(name == "windows"))
            if name == "windows":
                build_launcher(V, os.path.join(pkg, "Imprimo.exe"))
            if name == "macOS":
                plist = os.path.join(pkg, "Imprimo.app", "Contents", "Info.plist")
                with open(plist, "rb") as f:
                    info = plistlib.load(f)
                info["CFBundleShortVersionString"] = info["CFBundleVersion"] = V
                with open(plist, "wb") as f:
                    plistlib.dump(info, f)
                shutil.copy2(os.path.join(ROOT, ICON_DIR, "imprimo.icns"),
                             os.path.join(pkg, "Imprimo.app", "Contents", "Resources", "imprimo.icns"))
            if py312:
                run(py312, "-m", "compileall", "-q", "--invalidation-mode", "checked-hash",
                    os.path.join(pkg, app_rel))
            z = os.path.join(out_dir, f"{new_top}.zip")
            if os.path.exists(z):
                os.remove(z)
            run("zip", "-q", "-r", "-y", "-9", z, new_top, cwd=d)
            print("  →", z)

        # the website's download buttons read docs/latest.json
        base_url = f"https://github.com/imprimo-imposition/imprimo/releases/download/v{V}/"
        latest = {"version": V, "downloads": {
            "win": base_url + f"Imprimo-{V}-windows.zip",
            "mac": base_url + f"Imprimo-{V}-macOS.zip",
            "linux": base_url + f"Imprimo-{V}-linux-x86_64.zip"}}
        with open(os.path.join(ROOT, "docs", "latest.json"), "w", encoding="utf-8") as f:
            json.dump(latest, f, indent=2)
            f.write("\n")
        print("website downloads → docs/latest.json")

        if "source" in want:
            z = os.path.join(out_dir, f"imprimo-{V}.zip")
            if os.path.exists(z):
                os.remove(z)
            parent, base = os.path.split(ROOT)
            if os.path.isdir(os.path.join(ROOT, ".git")):
                # only what is committed – no private or local files (CLAUDE.local.md, .claude/…)
                run("git", "archive", "--format=zip", f"--prefix={base}/", "-o", z, "HEAD", cwd=ROOT)
            else:
                run("zip", "-q", "-r", z, base, "-x", "*/__pycache__/*", "-x", "*.pyc",
                    "-x", f"{base}/dist/*", "-x", f"{base}/tests/samples/*", "-x", f"{base}/.venv/*",
                    "-x", "*/.DS_Store", "-x", f"{base}/CLAUDE.local.md", "-x", f"{base}/.claude/*",
                    cwd=parent)
            print("source →", z)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
