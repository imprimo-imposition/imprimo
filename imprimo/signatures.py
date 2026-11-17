"""Signatures for perfect (V2) and sewn binding: folding schemes and how pages split.

A signature is one sheet printed on both sides and folded in half one or more
times (right-angle folds). Instead of a table of schemes, the sheet is folded
virtually: each fold lays one half over the other, and when the packet is turned
so that its last fold (the spine) is on the left and the previous fold at the
head, the leaves are read from the top. This gives the page number and the
orientation (upright or upside down) of every panel.

The results match the usual schemes (F4-1, F8-7, F16-7, F32-…); a quick check
for students: pages next to each other across a spine fold add up to n + 1.
"""
from __future__ import annotations

from dataclasses import dataclass

# pages per signature: (columns, rows, folds in order; v = vertical line, h = horizontal)
FOLDS = {
    4: (2, 1, "v"),
    8: (2, 2, "hv"),
    16: (4, 2, "vhv"),
    32: (4, 4, "hvhv"),
}
SIZES = (32, 16, 8, 4)


@dataclass
class Panel:
    col: int          # 0 = left, as seen on the side with page 1
    row: int          # 0 = bottom
    front: int        # page number (1..n) on the side with page 1
    back: int         # page number behind it
    rot: int          # 0 = upright, 180 = upside down (same for both faces)


@dataclass
class Scheme:
    pages: int
    cols: int
    rows: int
    folds: str
    panels: list            # [Panel]
    spine_cols: list        # column boundaries (1..cols-1) that are spine folds
    fold_order: list        # [(axis "x"/"y", boundary index, fold number 1..)]

    def at(self, col, row) -> Panel:
        return next(p for p in self.panels if p.col == col and p.row == row)


def _mul(A, B):
    return (A[0] * B[0] + A[1] * B[2], A[0] * B[1] + A[1] * B[3],
            A[2] * B[0] + A[3] * B[2], A[2] * B[1] + A[3] * B[3])


def _app(A, v):
    return (A[0] * v[0] + A[1] * v[1], A[2] * v[0] + A[3] * v[1])


def _det(A):
    return A[0] * A[3] - A[1] * A[2]


_I = (1, 0, 0, 1)
_MX = (-1, 0, 0, 1)
_MY = (1, 0, 0, -1)


def scheme(pages: int) -> Scheme:
    cols, rows, folds = FOLDS[pages]
    # every panel: center in packet units, linear map front face → packet, layer (0 = bottom)
    st = {(c, r): [c + .5, r + .5, _I, 0] for c in range(cols) for r in range(rows)}
    w, h, n = cols, rows, 1
    for f in folds:
        if f == "v":                        # right half over the left half
            a = w / 2
            for p in st.values():
                if p[0] > a:
                    p[0], p[2], p[3] = 2 * a - p[0], _mul(_MX, p[2]), 2 * n - 1 - p[3]
            w = a
        else:                               # top half down over the bottom half
            a = h / 2
            for p in st.values():
                if p[1] > a:
                    p[1], p[2], p[3] = 2 * a - p[1], _mul(_MY, p[2]), 2 * n - 1 - p[3]
            h = a
        n *= 2

    # turn the packet: spine (last fold) to the left, the previous fold to the head
    edge = {"v": (1, 0), "h": (0, 1)}
    spine = edge[folds[-1]]
    head = edge[folds[-2]] if len(folds) > 1 else (0, 1)
    best = None
    for G in ((1, 0, 0, 1), (0, -1, 1, 0), (-1, 0, 0, -1), (0, 1, -1, 0)):
        for F in (_I, _MY):                 # _MY = turn the packet over
            T = _mul(F, G)
            if _app(T, spine) == (-1, 0) and _app(T, head) == (0, 1):
                best = T
                break
        if best:
            break
    flip = _det(best) < 0

    raw = {}
    for (c, r), (_, _, L, layer) in st.items():
        if flip:
            layer = n - 1 - layer
        leaf = n - layer                    # 1 = top leaf
        L = _mul(best, L)
        up = _det(L) > 0                    # front face of the sheet faces up
        pf, pb = (2 * leaf - 1, 2 * leaf) if up else (2 * leaf, 2 * leaf - 1)
        Lf = L if up else _mul(_MX, L)      # a face seen from below is mirrored
        u = _app((Lf[0], Lf[2], Lf[1], Lf[3]), (0, 1))     # transpose = inverse
        rot = 0 if round(u[1]) == 1 else 180
        raw[(c, r)] = (pf, pb, rot)

    # the side with page 1 is the front; seen from that side the columns are mirrored
    one_on_front = any(v[0] == 1 for v in raw.values())
    panels = []
    for (c, r), (pf, pb, rot) in raw.items():
        if one_on_front:
            panels.append(Panel(c, r, pf, pb, rot))
        else:
            panels.append(Panel(cols - 1 - c, r, pb, pf, rot))
    panels.sort(key=lambda p: (p.row, p.col))

    sch = Scheme(pages, cols, rows, folds, panels, [], [])
    # spine folds: neighbors across them add up to n + 1
    for b in range(1, cols):
        if sch.at(b - 1, 0).front + sch.at(b, 0).front == pages + 1:
            sch.spine_cols.append(b)
    # fold numbers: the k-th fold in one direction halves the parts made so far
    count = {"v": 0, "h": 0}
    for i, f in enumerate(folds, 1):
        k = count[f]
        count[f] += 1
        N = cols if f == "v" else rows
        step = N // (2 ** (k + 1))
        for j in range(2 ** k):
            sch.fold_order.append(("x" if f == "v" else "y", step * (2 * j + 1), i))
    return sch


def split(total: int, size: int) -> list[int]:
    """Pages of every signature: as many of `size` as possible, the rest in
    smaller ones (104 with 16 → 16 ×6 + 8). `total` is a multiple of 4."""
    out, rest = [], total
    for s in [x for x in SIZES if x <= size]:
        while rest >= s:
            out.append(s)
            rest -= s
    return out
