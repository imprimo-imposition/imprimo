"""Command line: python -m imprimo.cli input.pdf output.pdf --set mode=booklet --set bleed=3"""
import argparse
import dataclasses
import sys

from .core import ImposeError, Settings, impose_file, to_mm


def main(argv=None):
    ap = argparse.ArgumentParser(description="Imposition of print PDFs")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="a setting, e.g. mode=booklet, sheet_w=320, duplex=true")
    a = ap.parse_args(argv)

    s = Settings()
    types = {f.name: f.type for f in dataclasses.fields(Settings)}
    for kv in a.set:
        k, _, v = kv.partition("=")
        if k not in types:
            ap.error(f"unknown setting: {k}")
        cur = getattr(s, k)
        if isinstance(cur, bool):
            val = v.lower() in ("1", "true", "yes", "ano", "áno")
        elif isinstance(cur, int):
            val = int(v)
        elif isinstance(cur, float):
            val = float(v)
        else:
            val = v
        setattr(s, k, val)
    try:
        plan = impose_file(a.input, a.output, s)
    except ImposeError as e:
        print("Error:", e, file=sys.stderr)
        return 1
    for w in plan.warnings:
        print("Warning:", w)
    print(f"{plan.summary(s)} | sheets: {plan.n_sheets} | PDF pages: {len(plan.sides)} "
          f"| usage {plan.utilization:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
