"""Interior PDF layout (KDP paperback, no bleed)."""
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from . import draw
from .draw import BOLD, REG, SERIF

TRIM = (8.5 * inch, 11 * inch)
INSIDE, OUTSIDE, TOP, BOTTOM = 0.875 * inch, 0.625 * inch, 0.7 * inch, 0.7 * inch
SOL_PER_PAGE = 12


class Layout:
    def __init__(self, path, meta, mirror=True):
        draw.register_fonts()
        self.c = canvas.Canvas(path, pagesize=TRIM, pageCompression=1, initialFontName=REG)
        self.c.setTitle(meta["title"] + ": " + meta["subtitle"])
        self.c.setAuthor(meta.get("author", ""))
        self.c.setCreator("puzzlebooks")
        self.mirror = mirror
        self.page = 1
        self.W, self.H = TRIM

    @property
    def left(self):
        if not self.mirror:
            return (INSIDE + OUTSIDE) / 2
        return INSIDE if self.page % 2 == 1 else OUTSIDE

    @property
    def width(self):
        return self.W - INSIDE - OUTSIDE

    def footer(self):
        c = self.c
        c.setFillGray(0.25)
        c.setFont(REG, 10)
        c.drawCentredString(self.left + self.width / 2, BOTTOM - 0.22 * inch, str(self.page))

    def next(self, number=True):
        if number:
            self.footer()
        self.c.showPage()
        self.page += 1

    def para(self, text, y, size=12.5, font=REG, leading=None, align=0, indent=0, bullet=None, color=0):
        st = ParagraphStyle("p", fontName=font, fontSize=size, leading=leading or size * 1.45,
                            alignment=align, leftIndent=indent, bulletIndent=0, bulletFontName=REG, bulletFontSize=size, textColor=(color,) * 3)
        p = Paragraph(text, st, bulletText=bullet)
        _w, h = p.wrap(self.width, 1000)
        p.drawOn(self.c, self.left, y - h)
        return y - h


def _header(L, left_text, right_text):
    c = L.c
    y = L.H - TOP
    c.setFillGray(0)
    c.setFont(BOLD, 20)
    c.drawString(L.left, y - 16, left_text)
    c.setFont(REG, 12)
    c.setFillGray(0.2)
    c.drawRightString(L.left + L.width, y - 14, right_text)
    c.setStrokeGray(0)
    c.setLineWidth(1.2)
    c.line(L.left, y - 26, L.left + L.width, y - 26)
    return y - 26


def build(path, book, puzzles, example, author="", mirror=True, edition_note="", front_matter=True):
    """puzzles: list of dicts with extra keys "label" (difficulty) and "number"."""
    meta = dict(book, author=author)
    L = Layout(path, meta, mirror)
    c = L.c
    cx = lambda: L.left + L.width / 2

    if front_matter:
        # --- title page
        y = L.H - 2.3 * inch
        st_y = L.para(book["title"].upper(), y, size=40, font=SERIF, leading=48, align=TA_CENTER)
        c.setLineWidth(2)
        c.line(cx() - 1.2 * inch, st_y - 22, cx() + 1.2 * inch, st_y - 22)
        st_y = L.para(book["subtitle"], st_y - 44, size=19, font=REG, leading=26, align=TA_CENTER)
        draw.draw_centered(c, example, L.left, st_y - 0.6 * inch, L.width, 3.0 * inch, max_cell=0.55 * inch)
        L.para(book["tagline"], 2.0 * inch, size=13, align=TA_CENTER, color=0.2)
        if author:
            L.para(author, 1.45 * inch, size=14, font=BOLD, align=TA_CENTER)
        L.next(number=False)
        # --- copyright page
        y = L.H - 6.2 * inch
        owner = author or "the publisher"
        for t in (
            f"<b>{book['title']}: {book['subtitle']}</b>",
            f"Copyright \u00a9 2026 {owner}. All rights reserved.",
            "No part of this book may be reproduced, stored or shared in any form without written permission from the publisher, except for personal use by the buyer.",
            "The puzzles in this book were generated and checked by computer software. Each puzzle was solved by two separate programs to confirm that it has exactly one solution.",
            edition_note or "First edition, 2026.",
        ):
            y = L.para(t, y, size=10.5, color=0.15) - 12
        L.next(number=False)
        # --- how to solve
        y = _header(L, "How to Solve", "")
        y -= 14
        for t in book["rules"]:
            y = L.para(t, y, size=13, indent=18, bullet="\u2022") - 9
        y -= 8
        c.setFillGray(0)
        c.setFont(BOLD, 14)
        c.drawString(L.left, y - 12, "Example")
        y -= 26
        half = L.width / 2
        box_h = min(2.9 * inch, y - BOTTOM - 0.5 * inch)
        s = min(draw.size_for(example, half - 20, box_h), 0.62 * inch)
        ew, eh = draw.extent(example, s)
        draw.draw(c, example, L.left + (half - ew) / 2, y, s)
        sw, _sh = draw.extent(example, s, True)
        # solved copy: keep clues for kakuro/calcudoku, plain shaded grid for nonograms
        if example["type"] == "nonogram":
            draw.draw(c, example, L.left + half + (half - ew) / 2, y, s)
            _rc, _cc, lw, th = draw._nono_clue_cells(example)
            ox = L.left + half + (half - ew) / 2 + (lw * draw.CLUE_W + 0.2) * s
            oy = y - (th * draw.CLUE_H + 0.2) * s
            draw.draw(c, example, ox, oy, s, solution=True)
        else:
            draw.draw(c, example, L.left + half + (half - ew) / 2, y, s, solution=True)
        c.setFont(REG, 11)
        c.setFillGray(0.2)
        c.drawCentredString(L.left + half / 2, y - eh - 16, "Puzzle")
        c.drawCentredString(L.left + half * 1.5, y - eh - 16, "Solution")
        L.next()
        y = _header(L, "Solving Tips", "")
        y -= 14
        for t in book["tips"]:
            y = L.para(t, y, size=13, indent=18, bullet="\u2022") - 9
        y -= 14
        c.setFillGray(0)
        c.setFont(BOLD, 14)
        c.drawString(L.left, y - 12, "In This Book")
        y -= 30
        start = 1
        for sec in book["sections"]:
            y = L.para(f"<b>{sec['label']}</b>: puzzles {start} to {start + sec['count'] - 1}", y, size=13, indent=18, bullet="\u2022") - 7
            start += sec["count"]
        y = L.para("Solutions for every puzzle start after the last puzzle. Use a pencil, take your time and enjoy.", y - 10, size=13)
        L.next()

    # --- puzzle pages
    puzzle_pages = {}
    for p in puzzles:
        y = _header(L, f"Puzzle {p['number']}", f"{p['label']}  \u2022  {book['size_label'](p)}")
        top = y - 0.3 * inch
        box_h = top - BOTTOM - 0.25 * inch
        draw.draw_centered(c, p, L.left, top, L.width, box_h, max_cell=1.2 * inch)
        puzzle_pages[p["number"]] = L.page
        L.next()

    # --- solutions
    cols, rows = 3, 4
    for i in range(0, len(puzzles), SOL_PER_PAGE):
        y = _header(L, "Solutions", f"{puzzles[i]['number']} to {puzzles[min(i + SOL_PER_PAGE, len(puzzles)) - 1]['number']}")
        top = y - 0.2 * inch
        cw = L.width / cols
        ch = (top - BOTTOM - 0.1 * inch) / rows
        for k, p in enumerate(puzzles[i:i + SOL_PER_PAGE]):
            bx = L.left + (k % cols) * cw
            by = top - (k // cols) * ch
            c.setFillGray(0)
            c.setFont(BOLD, 11)
            c.drawString(bx + 6, by - 13, f"Puzzle {p['number']}")
            draw.draw_centered(c, p, bx + 6, by - 20, cw - 12, ch - 28, solution=True, labels=False)
        L.next()

    if front_matter:
        if L.page % 2 == 0:
            # closing page keeps the page count even without a blank sheet
            y = L.H - 3.2 * inch
            y = L.para("Well done!", y, size=30, font=SERIF, align=TA_CENTER)
            y = L.para("You reached the end of the book. We hope these puzzles gave you many quiet, satisfying hours.", y - 30, size=14, align=TA_CENTER)
            L.para("Look for more large, clear logic puzzle collections in this series.", y - 16, size=14, align=TA_CENTER)
            L.next(number=False)
    c.save()
    return {"pages": L.page - 1, "puzzle_pages": puzzle_pages}
