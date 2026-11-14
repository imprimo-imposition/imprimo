"""Detecting the PDF profile (PDF/X, PDF/A, output intent) and working with ICC profiles."""
from __future__ import annotations

import os
import re
import struct
import sys
from dataclasses import dataclass, field

import pikepdf

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
BUNDLED_ICC = os.path.join(ASSETS, "FOGRA39L_coated.icc")

# Standards offered by InDesign, Illustrator, Affinity, Corel…
#   key: (popis, Info/GTS_PDFXVersion, Info/GTS_PDFXConformance, verzia PDF, rodina)
STANDARDS = {
    "x1a2001": ("PDF/X-1a:2001", "PDF/X-1:2001", "PDF/X-1a:2001", "1.3", "x1a"),
    "x1a2003": ("PDF/X-1a:2003", "PDF/X-1a:2003", None, "1.4", "x1a"),
    "x32002": ("PDF/X-3:2002", "PDF/X-3:2002", None, "1.3", "x3"),
    "x32003": ("PDF/X-3:2003", "PDF/X-3:2003", None, "1.4", "x3"),
    "x4": ("PDF/X-4", "PDF/X-4", None, "1.6", "x4"),
}


# --------------------------------------------------------------------------
# ICC

@dataclass
class IccInfo:
    desc: str
    colorspace: str      # 'CMYK', 'RGB', 'GRAY', …
    device_class: str    # 'prtr', 'mntr', …
    version: str
    path: str | None = None

    @property
    def channels(self):
        return {"CMYK": 4, "RGB": 3, "GRAY": 1}.get(self.colorspace, 4)

    @property
    def condition_id(self):
        """Registered printing condition identifier (ICC registry)."""
        d = self.desc.upper().replace(" ", "")
        for key in ("FOGRA59", "FOGRA58", "FOGRA57", "FOGRA54", "FOGRA53", "FOGRA52", "FOGRA51",
                    "FOGRA47", "FOGRA45", "FOGRA40", "FOGRA39", "FOGRA29", "FOGRA28", "FOGRA27",
                    "CGATS21", "GRACOL2006", "SWOP"):
            if key in d:
                return {"GRACOL2006": "CGATS TR 006", "SWOP": "CGATS TR 001"}.get(key, key)
        if "ISOCOATEDV2" in d:
            return "FOGRA39"
        if "PSOCOATEDV3" in d:
            return "FOGRA51"
        if "PSOUNCOATEDV3" in d:
            return "FOGRA52"
        if "ISOUNCOATED" in d or "PSOUNCOATED" in d:
            return "FOGRA29"
        return "Custom"


def icc_info(data: bytes, path=None) -> IccInfo | None:
    if len(data) < 132 or data[36:40] != b"acsp":
        return None
    space = data[16:20].decode("latin-1").strip()
    dclass = data[12:16].decode("latin-1").strip()
    ver = f"{data[8]}.{data[9] >> 4}"
    desc = ""
    try:
        n = struct.unpack(">I", data[128:132])[0]
        for i in range(min(n, 200)):
            sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
            if sig != b"desc":
                continue
            typ = data[off:off + 4]
            if typ == b"desc":
                ln = struct.unpack(">I", data[off + 8:off + 12])[0]
                desc = data[off + 12:off + 12 + ln].split(b"\0")[0].decode("latin-1")
            elif typ == b"mluc":
                cnt, rsz = struct.unpack(">II", data[off + 8:off + 16])
                if cnt:
                    ln, o2 = struct.unpack(">II", data[off + 20:off + 28])
                    desc = data[off + o2:off + o2 + ln].decode("utf-16-be", "replace")
            break
    except Exception:
        pass
    desc = desc.strip() or (os.path.splitext(os.path.basename(path))[0] if path else "ICC")
    return IccInfo(desc, space, dclass, ver, path)


def icc_from_file(path) -> IccInfo | None:
    try:
        with open(path, "rb") as f:
            return icc_info(f.read(), path)
    except OSError:
        return None


def _icc_dirs():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return [("/Library/ColorSync/Profiles", True),
                (os.path.join(home, "Library/ColorSync/Profiles"), True),
                ("/Library/Application Support/Adobe/Color/Profiles", True),
                ("/System/Library/ColorSync/Profiles", False)]
    if sys.platform.startswith("win"):
        win = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [(os.path.join(win, r"System32\spool\drivers\color"), True)]
        for var in ("CommonProgramFiles", "CommonProgramFiles(x86)"):
            if os.environ.get(var):
                dirs.append((os.path.join(os.environ[var], r"Adobe\Color\Profiles"), True))
        return dirs
    return [("/usr/share/color/icc", True), ("/usr/local/share/color/icc", True),
            (os.path.join(home, ".local/share/color/icc"), True),
            (os.path.join(home, ".color/icc"), True)]


_system_cache = None


def system_cmyk_profiles() -> list[IccInfo]:
    """CMYK output profiles installed in the system (including Adobe profiles)."""
    global _system_cache
    if _system_cache is not None:
        return _system_cache
    found, seen = [], set()
    for root, recursive in _icc_dirs():
        if not os.path.isdir(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            if not recursive:
                dirs[:] = []
            if dirpath.count(os.sep) - root.count(os.sep) > 4:
                dirs[:] = []
            for fn in files:
                if not fn.lower().endswith((".icc", ".icm")):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, "rb") as f:
                        head = f.read(132)
                        if head[16:20] != b"CMYK" or head[12:16] != b"prtr":
                            continue
                        f.seek(0)
                        info = icc_info(f.read(), p)
                except OSError:
                    continue
                if info and info.desc not in seen:
                    seen.add(info.desc)
                    found.append(info)
    found.sort(key=lambda i: (i.condition_id != "FOGRA39", i.desc.lower()))
    _system_cache = found
    return found


# --------------------------------------------------------------------------
# Rozpoznanie profilu PDF

@dataclass
class OutputIntent:
    subtype: str
    identifier: str
    condition: str
    info: str
    registry: str
    icc: IccInfo | None

    def label(self):
        name = self.icc.desc if self.icc else (self.info or self.condition or "")
        ident = self.identifier
        if ident and name and ident.lower() not in name.lower():
            return f"{ident} ({name})"
        return name or ident or "?"


@dataclass
class SourceProfile:
    pdf_version: str
    pdfx: str | None = None             # napr. "PDF/X-4", "PDF/X-1a:2001"
    pdfx_version_key: str | None = None  # hodnota GTS_PDFXVersion
    pdfx_conformance: str | None = None
    pdfa: str | None = None              # napr. "PDF/A-2b"
    intents: list = field(default_factory=list)
    creator: str = ""
    producer: str = ""
    encrypted: bool = False

    @property
    def standard_key(self):
        """Key in STANDARDS, if known."""
        if not self.pdfx:
            return None
        for k, (label, *_rest) in STANDARDS.items():
            if self.pdfx.upper() == label.upper():
                return k
        if "X-4" in self.pdfx.upper():
            return "x4"
        return None

    @property
    def pdfx_intent(self):
        for oi in self.intents:
            if oi.subtype == "GTS_PDFX":
                return oi
        return self.intents[0] if self.intents else None

    def app(self):
        """Short name of the application that created the PDF."""
        for s in (self.creator, self.producer):
            for name in ("InDesign", "Illustrator", "Photoshop", "Affinity Publisher",
                         "Affinity Designer", "Affinity Photo", "Affinity", "CorelDRAW",
                         "Corel", "QuarkXPress", "Scribus", "Inkscape", "Canva", "Word",
                         "PowerPoint", "LibreOffice", "Acrobat", "Quartz", "Imprimo"):
                if name.lower() in s.lower():
                    m = re.search(re.escape(name) + r"[^\d(]{0,12}([\d.]+)", s, re.I)
                    return f"{name} {m.group(1)}" if m else name
        return self.creator or self.producer


def _s(v):
    try:
        return str(v).strip()
    except Exception:
        return ""


def detect_profile(pdf: pikepdf.Pdf) -> SourceProfile:
    prof = SourceProfile(pdf_version=str(pdf.pdf_version), encrypted=pdf.is_encrypted)
    info = pdf.trailer.get("/Info")
    xmp = ""
    try:
        if "/Metadata" in pdf.Root:
            xmp = pdf.Root.Metadata.read_bytes().decode("utf-8", "replace")
    except Exception:
        xmp = ""

    def from_xmp(tag):
        if not xmp:
            return None
        prefix, local = tag.split(":")
        m = (re.search(rf"{prefix}:{local}\s*=\s*[\"']([^\"']*)[\"']", xmp)
             or re.search(rf"<{prefix}:{local}>\s*([^<]*?)\s*</{prefix}:{local}>", xmp))
        return m.group(1).strip() if m and m.group(1).strip() else None

    ver = conf = None
    if info is not None:
        if "/GTS_PDFXVersion" in info:
            ver = _s(info.GTS_PDFXVersion)
        if "/GTS_PDFXConformance" in info:
            conf = _s(info.GTS_PDFXConformance)
        prof.creator = _s(info.get("/Creator", ""))
        prof.producer = _s(info.get("/Producer", ""))
    ver = ver or from_xmp("pdfxid:GTS_PDFXVersion") or from_xmp("pdfx:GTS_PDFXVersion")
    conf = conf or from_xmp("pdfx:GTS_PDFXConformance")
    if not prof.creator:
        prof.creator = from_xmp("xmp:CreatorTool") or ""
    if not prof.producer:
        prof.producer = from_xmp("pdf:Producer") or ""
    if ver:
        prof.pdfx_version_key = ver
        prof.pdfx_conformance = conf
        prof.pdfx = conf if (conf and ver.startswith("PDF/X-1:")) else ver

    part = from_xmp("pdfaid:part")
    if part:
        prof.pdfa = f"PDF/A-{part}{(from_xmp('pdfaid:conformance') or '').lower()}"

    for oi in pdf.Root.get("/OutputIntents", []) or []:
        try:
            icc = None
            if "/DestOutputProfile" in oi:
                icc = icc_info(oi.DestOutputProfile.read_bytes())
            prof.intents.append(OutputIntent(
                subtype=_s(oi.get("/S", "")).lstrip("/"),
                identifier=_s(oi.get("/OutputConditionIdentifier", "")),
                condition=_s(oi.get("/OutputCondition", "")),
                info=_s(oi.get("/Info", "")),
                registry=_s(oi.get("/RegistryName", "")),
                icc=icc))
        except Exception:
            continue
    return prof
