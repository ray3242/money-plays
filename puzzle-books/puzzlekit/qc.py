"""Quality checks against KDP paperback rules. Every check returns (name, ok, detail)."""
import os

import pymupdf

from . import cover as cover_mod
from . import interior, verify

IN = 72.0
MIN_FONT = 7.0          # KDP minimum font size
KDP_GUTTER = {150: 0.375, 300: 0.5, 500: 0.625, 700: 0.75, 828: 0.875}
KDP_OUTSIDE = 0.25      # no-bleed minimum outside margin
MAX_BYTES = 650 * 1024 * 1024


def _gutter_min(pages):
    for limit, g in sorted(KDP_GUTTER.items()):
        if pages <= limit:
            return g
    raise ValueError("too many pages")


def _content_rect(page):
    r = pymupdf.Rect()
    for b in page.get_text("blocks"):
        r |= pymupdf.Rect(b[:4])
    for d in page.get_drawings():
        r |= d["rect"]
    return r


def _fonts_embedded(doc):
    bad = set()
    for i in range(len(doc)):
        for f in doc.get_page_fonts(i):
            if f[1] == "n/a":
                bad.add(f[3])
    return bad


def _min_font(doc):
    m = 1e9
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    if sp["text"].strip():
                        m = min(m, sp["size"])
    return m


def check_puzzles(puzzles, expected_count):
    out = []
    out.append(("puzzle count", len(puzzles) == expected_count, f"{len(puzzles)} of {expected_count}"))
    bad = []
    for p in puzzles:
        ok, why = verify.verify(p)
        if not ok:
            bad.append((p["number"], why))
    out.append(("every puzzle has exactly one solution (independent CP-SAT proof)", not bad,
                f"{len(puzzles) - len(bad)} of {len(puzzles)} proven unique" + (f"; failures {bad[:5]}" if bad else "")))
    sigs = {verify.signature(p) for p in puzzles}
    out.append(("no duplicate puzzles", len(sigs) == len(puzzles), f"{len(sigs)} distinct clue sets"))
    sols = {repr(p["solution"]) for p in puzzles}
    out.append(("no duplicate solutions", len(sols) == len(puzzles), f"{len(sols)} distinct solutions"))
    return out


def check_interior(path, puzzles, info):
    out = []
    doc = pymupdf.open(path)
    n = len(doc)
    out.append(("interior opens, page count matches layout", n == info["pages"], f"{n} pages"))
    out.append(("page count within KDP 24 to 828 and even", 24 <= n <= 828 and n % 2 == 0, str(n)))
    w, h = interior.TRIM
    sizes = {(round(p.rect.width, 2), round(p.rect.height, 2)) for p in doc}
    out.append(("every page is 8.5 x 11 in trim", sizes == {(round(w, 2), round(h, 2))}, str(sizes)))
    bad = _fonts_embedded(doc)
    out.append(("all fonts embedded", not bad, f"not embedded: {sorted(bad)}" if bad else "3 embedded TrueType subsets"))
    mf = _min_font(doc)
    out.append(("smallest text is at least 7 pt", mf >= MIN_FONT - 0.01, f"{mf:.1f} pt"))
    imgs = sum(len(p.get_images()) for p in doc)
    out.append(("no raster images (all vector, so no 300 DPI concern)", imgs == 0, f"{imgs} images"))
    gmin, min_g, min_o, min_tb = _gutter_min(n), 1e9, 1e9, 1e9
    for i, page in enumerate(doc):
        r = _content_rect(page)
        if r.is_empty:
            continue
        odd = (i + 1) % 2 == 1  # odd pages are right-hand: gutter on the left
        g = r.x0 if odd else w - r.x1
        o = w - r.x1 if odd else r.x0
        min_g, min_o = min(min_g, g / IN), min(min_o, o / IN)
        min_tb = min(min_tb, r.y0 / IN, (h - r.y1) / IN)
    out.append((f"gutter margin at least {gmin} in", min_g >= gmin, f"smallest {min_g:.3f} in"))
    out.append((f"outside margin at least {KDP_OUTSIDE} in", min_o >= KDP_OUTSIDE, f"smallest {min_o:.3f} in"))
    out.append((f"top and bottom margin at least {KDP_OUTSIDE} in", min_tb >= KDP_OUTSIDE, f"smallest {min_tb:.3f} in"))
    missing = [p["number"] for p in puzzles
               if f"Puzzle {p['number']}" not in doc[info["puzzle_pages"][p["number"]] - 1].get_text()]
    out.append(("each puzzle page carries its puzzle number", not missing, f"missing {missing}" if missing else "all present"))
    sol_text = "".join(doc[i].get_text() for i in range(max(info["puzzle_pages"].values()), n))
    missing = [p["number"] for p in puzzles if f"Puzzle {p['number']}\n" not in sol_text]
    out.append(("answer key lists every puzzle", not missing, f"missing {missing}" if missing else "all present"))
    size = os.path.getsize(path)
    out.append(("file under 650 MB", size < MAX_BYTES, f"{size / 1e6:.2f} MB"))
    return out


def check_cover(path, pages, dims):
    out = []
    doc = pymupdf.open(path)
    page = doc[0]
    exp = cover_mod.dimensions(pages)
    out.append(("cover is a single page", len(doc) == 1, str(len(doc))))
    ok = abs(page.rect.width - exp["width"]) < 0.05 and abs(page.rect.height - exp["height"]) < 0.05
    out.append(("cover size = 2 x trim + spine + bleed", ok,
                f"{page.rect.width / IN:.3f} x {page.rect.height / IN:.3f} in, spine {exp['spine'] / IN:.3f} in for {pages} pages"))
    bad = _fonts_embedded(doc)
    out.append(("all cover fonts embedded", not bad, str(sorted(bad)) if bad else "embedded"))
    B, tw, sp = cover_mod.BLEED, exp["trim_w"], exp["spine"]
    spine0, spine1 = B + tw, B + tw + sp
    safe = cover_mod.SAFE
    H = page.rect.height
    bx, by, bw, bh = dims["barcode_box"]
    barcode = pymupdf.Rect(bx, H - by - bh, bx + bw, H - by)
    problems, spine_text = [], 0
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if not s["text"].strip():
                    continue
                r = pymupdf.Rect(s["bbox"])
                if r.intersects(barcode):
                    problems.append(("barcode", s["text"]))
                if r.x0 >= spine0 - 1 and r.x1 <= spine1 + 1:
                    spine_text += 1
                    if r.x0 < spine0 + cover_mod.SPINE_TEXT_MARGIN - 0.5 or r.x1 > spine1 - cover_mod.SPINE_TEXT_MARGIN + 0.5:
                        problems.append(("spine margin", s["text"]))
                    continue
                if r.y0 < B + safe or r.y1 > H - B - safe:
                    problems.append(("top/bottom safe zone", s["text"]))
                if r.x1 <= spine0:
                    if r.x0 < B + safe or r.x1 > spine0 - safe:
                        problems.append(("back safe zone", s["text"]))
                elif r.x0 >= spine1:
                    if r.x0 < spine1 + safe or r.x1 > page.rect.width - B - safe:
                        problems.append(("front safe zone", s["text"]))
                else:
                    problems.append(("text crosses the spine fold", s["text"]))
    out.append(("cover text inside safe zones, clear of barcode area and folds", not problems, str(problems[:5]) if problems else "ok"))
    want = pages >= cover_mod.MIN_SPINE_TEXT_PAGES
    out.append(("spine text only when the book has more than 79 pages", (spine_text > 0) == want,
                f"{spine_text} spine text spans, {pages} pages"))
    # background must reach all four bleed edges
    pix = page.get_pixmap(dpi=30)
    corners = [pix.pixel(0, 0), pix.pixel(pix.width - 1, 0), pix.pixel(0, pix.height - 1), pix.pixel(pix.width - 1, pix.height - 1)]
    out.append(("background artwork fills the bleed", all(sum(c[:3]) < 740 for c in corners), "corners are inked"))
    return out
