import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from puzzlekit import calcudoku, cover, generate, interior, kakuro, nonogram, qc, verify  # noqa: E402
from puzzlekit.books import BOOKS  # noqa: E402

SMALL = {
    "kakuro": lambda s: kakuro.generate(s, rows=6, cols=6, max_run=4, density=0.22, want_guessfree=True),
    "nonogram": lambda s: nonogram.generate(s, rows=8, cols=8, density=0.55, max_full_lines=2),
    "calcudoku": lambda s: calcudoku.generate(s, n=5, ops="+-x/", max_size=3, singles=1),
}


@pytest.mark.parametrize("kind", sorted(SMALL))
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_generated_puzzles_are_proven_unique(kind, seed):
    p = SMALL[kind](seed)
    ok, why = verify.verify(p)
    assert ok, why


@pytest.mark.parametrize("kind", sorted(SMALL))
def test_generation_is_deterministic(kind):
    assert SMALL[kind](7) == SMALL[kind](7)


def test_nonogram_line_clues():
    assert nonogram.line_clue([1, 1, 0, 1, 0, 0, 1, 1, 1]) == [2, 1, 3]
    assert nonogram.line_clue([0, 0, 0]) == []


def test_verifier_rejects_ambiguous_nonogram():
    # a 2x2 checkerboard has the same clues as its mirror image
    p = {"type": "nonogram", "rows": 2, "cols": 2, "solution": [[1, 0], [0, 1]]}
    ok, why = verify.verify(p)
    assert not ok, why


def test_verifier_rejects_wrong_stored_solution():
    p = SMALL["calcudoku"](4)
    bad = copy.deepcopy(p)
    bad["solution"][0][0], bad["solution"][0][1] = bad["solution"][0][1], bad["solution"][0][0]
    ok, _ = verify.verify(bad)
    assert not ok


def test_verifier_rejects_ambiguous_calcudoku():
    # 2x2 with only sum cages over the whole grid: two latin squares fit
    p = {"type": "calcudoku", "n": 2, "solution": [[1, 2], [2, 1]],
         "cages": [{"cells": [[0, 0], [0, 1], [1, 0], [1, 1]], "op": "+", "target": 6}]}
    ok, why = verify.verify(p)
    assert not ok, why


def test_kakuro_clues_match_solution():
    p = SMALL["kakuro"](5)
    for _d, cells, total in kakuro.clues(p["white"], p["solution"]):
        vals = [p["solution"][r][c] for r, c in cells]
        assert sum(vals) == total and len(set(vals)) == len(vals)


def test_calcudoku_cage_ok():
    assert calcudoku.cage_ok("-", 2, [5, 3]) and calcudoku.cage_ok("-", 2, [3, 5])
    assert calcudoku.cage_ok("/", 3, [2, 6]) and not calcudoku.cage_ok("/", 3, [2, 5])
    assert calcudoku.cage_ok("x", 24, [2, 3, 4]) and calcudoku.cage_ok("+", 9, [2, 3, 4])


def test_cover_dimensions_follow_kdp_formula():
    d = cover.dimensions(114)
    assert d["spine"] / 72 == pytest.approx(114 * 0.002252)
    assert d["width"] / 72 == pytest.approx(2 * 8.5 + 114 * 0.002252 + 0.25)
    assert d["height"] / 72 == pytest.approx(11.25)


def test_signature_distinguishes_puzzles():
    a, b = SMALL["nonogram"](1), SMALL["nonogram"](2)
    assert verify.signature(a) != verify.signature(b)


@pytest.mark.parametrize("book_id", sorted(BOOKS))
def test_small_book_passes_qc(tmp_path, book_id):
    """Build a cut-down book (one puzzle per section) and run every KDP check on it."""
    book = copy.deepcopy(BOOKS[book_id])
    kind = book["type"]
    puzzles = []
    for i, sec in enumerate(book["sections"]):
        p = SMALL[kind](100 + i)
        p.update(label=sec["label"], number=i + 1)
        puzzles.append(p)
        sec["count"] = 1
    example = dict(SMALL[kind](99), label="example")
    ipath, cpath = str(tmp_path / "interior.pdf"), str(tmp_path / "cover.pdf")
    info = interior.build(ipath, book, puzzles, example, author="Test Author")
    dims = cover.build(cpath, book, info["pages"], puzzles[0], author="Test Author")
    checks = (qc.check_puzzles(puzzles + [dict(example, number=0)], len(puzzles) + 1)
              + qc.check_interior(ipath, puzzles, info) + qc.check_cover(cpath, info["pages"], dims))
    # a cut-down book is shorter than KDP's 24-page minimum; every other check applies
    failed = [(n, d) for n, ok, d in checks if not ok and not n.startswith("page count within")]
    assert not failed, failed


@pytest.mark.parametrize("book_id", sorted(BOOKS))
def test_built_book_qc_report_passed(book_id):
    import json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist", f"{book_id}-qc.json")
    if not os.path.exists(path):
        pytest.skip("book not built")
    with open(path) as f:
        rep = json.load(f)
    assert rep["passed"], [c for c in rep["checks"] if not c["ok"]]
    puzzles = generate.load(path.replace("-qc.json", "-puzzles.json"))
    assert len(puzzles) == sum(s["count"] for s in BOOKS[book_id]["sections"])
