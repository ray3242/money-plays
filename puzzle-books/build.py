#!/usr/bin/env python3
"""Build print-ready KDP puzzle books: puzzles, interior PDF, cover PDF, QC report.

    python3 build.py                 # all three books
    python3 build.py kakuro --author "Your Pen Name"
"""
import argparse
import json
import os
import sys

from puzzlekit import cover, generate, interior, qc
from puzzlekit.books import BOOKS

ROOT = os.path.dirname(os.path.abspath(__file__))
COVER_SAMPLE = {"kakuro": 30, "nonogram": 5, "calcudoku": 45}  # index of the puzzle shown on the cover


def build_book(book_id, out_dir, author, regenerate=False):
    book = BOOKS[book_id]
    os.makedirs(out_dir, exist_ok=True)
    data = os.path.join(out_dir, f"{book_id}-puzzles.json")
    if os.path.exists(data) and not regenerate:
        puzzles = generate.load(data)
    else:
        puzzles = generate.generate_book(book_id)
        generate.save(puzzles, data)
    example = generate.example_for(book_id)
    ipath = os.path.join(out_dir, f"{book_id}-interior.pdf")
    cpath = os.path.join(out_dir, f"{book_id}-cover.pdf")
    info = interior.build(ipath, book, puzzles, example, author=author)
    dims = cover.build(cpath, book, info["pages"], puzzles[COVER_SAMPLE[book_id]], author=author)
    expected = sum(s["count"] for s in book["sections"])
    checks = (qc.check_puzzles(puzzles + [dict(example, number=0)], expected + 1)
              + qc.check_interior(ipath, puzzles, info) + qc.check_cover(cpath, info["pages"], dims))
    report = {
        "book": book_id, "title": book["title"], "subtitle": book["subtitle"], "author": author,
        "pages": info["pages"], "trim": "8.5 x 11 in", "bleed": "interior: no bleed; cover: 0.125 in",
        "paper": "white, black ink", "spine_in": round(dims["spine"] / 72, 4),
        "cover_size_in": [round(dims["width"] / 72, 3), round(dims["height"] / 72, 3)],
        "checks": [{"check": n, "ok": bool(ok), "detail": d} for n, ok, d in checks],
        "passed": all(ok for _n, ok, _d in checks),
    }
    with open(os.path.join(out_dir, f"{book_id}-qc.json"), "w") as f:
        json.dump(report, f, indent=1)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("books", nargs="*", default=list(BOOKS))
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--author", default="Northgrid Puzzles")
    ap.add_argument("--regenerate", action="store_true", help="ignore cached puzzle JSON")
    a = ap.parse_args()
    ok = True
    for b in a.books:
        rep = build_book(b, a.out, a.author, a.regenerate)
        print(f"\n{rep['title']}: {rep['pages']} pages, spine {rep['spine_in']} in")
        for c in rep["checks"]:
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
        ok &= rep["passed"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
