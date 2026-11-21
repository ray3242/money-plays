"""Generate the puzzle set for a book: deterministic, deduplicated, double-verified."""
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor

from . import calcudoku, kakuro, nonogram, verify
from .books import BOOKS

GEN = {"kakuro": kakuro.generate, "nonogram": nonogram.generate, "calcudoku": calcudoku.generate}


def _seed(book_id, label, k):
    h = hashlib.sha256(f"{book_id}/{label}/{k}".encode()).digest()
    return int.from_bytes(h[:6], "big")


def _make(job):
    book_id, ptype, label, k, args = job
    seed = _seed(book_id, label, k)
    kw = dict(args)
    if ptype == "kakuro":
        kw["want_guessfree"] = True
    p = GEN[ptype](seed, **kw)
    ok, why = verify.verify(p)
    p.update(seed=seed, label=label, verified=ok, verify_note=why)
    return p


def example_for(book_id):
    b = BOOKS[book_id]
    return _make((book_id, b["type"], "example", 0, b["example"]))


def generate_book(book_id, workers=None):
    b = BOOKS[book_id]
    out, seen = [], set()
    with ProcessPoolExecutor(workers or os.cpu_count()) as ex:
        for sec in b["sections"]:
            got, k = [], 0
            while len(got) < sec["count"]:
                need = sec["count"] - len(got)
                jobs = [(book_id, b["type"], sec["label"], k + i, sec["args"]) for i in range(need)]
                k += need
                for p in ex.map(_make, jobs):
                    sig = verify.signature(p)
                    if not p["verified"] or sig in seen:
                        continue
                    seen.add(sig)
                    got.append(p)
            out += got
    for i, p in enumerate(out, 1):
        p["number"] = i
    return out


def save(puzzles, path):
    with open(path, "w") as f:
        json.dump(puzzles, f, separators=(",", ":"))


def load(path):
    with open(path) as f:
        return json.load(f)
