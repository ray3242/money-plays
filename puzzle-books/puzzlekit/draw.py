"""Vector drawing of puzzles on a reportlab canvas. (x, y) is the top-left corner."""
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from . import kakuro, nonogram

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
REG, BOLD, SERIF = "DejaVuSans", "DejaVuSans-Bold", "DejaVuSerif-Bold"
_done = False


def register_fonts():
    global _done
    if not _done:
        for name in (REG, BOLD, SERIF):
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, name + ".ttf")))
        pdfmetrics.registerFontFamily(REG, normal=REG, bold=BOLD, italic=REG, boldItalic=BOLD)
        _done = True


OPS = {"+": "+", "-": "\u2212", "x": "\u00d7", "/": "\u00f7", "=": ""}


def _ctext(c, x, y, text, font, size):
    c.setFont(font, size)
    c.drawCentredString(x, y - size * 0.36, text)


def kakuro_size(p, width, height):
    return min(width / p["cols"], height / p["rows"])


def draw_kakuro(c, p, x, y, s, solution=False, labels=True):
    R, C = p["rows"], p["cols"]
    white, sol = p["white"], p["solution"]
    across, down = {}, {}
    for d, cells, total in kakuro.clues(white, sol):
        r, cc = cells[0]
        if d == "h":
            across[(r, cc - 1)] = total
        else:
            down[(r - 1, cc)] = total
    fs = max(7.0, s * 0.29)
    for r in range(R):
        for cc in range(C):
            x0, y0 = x + cc * s, y - (r + 1) * s
            if white[r][cc]:
                c.setFillGray(1)
                c.rect(x0, y0, s, s, stroke=0, fill=1)
                if solution:
                    c.setFillGray(0)
                    _ctext(c, x0 + s / 2, y0 + s / 2, str(sol[r][cc]), BOLD, max(7.0, s * 0.55))
            else:
                c.setFillGray(0.12)
                c.rect(x0, y0, s, s, stroke=0, fill=1)
                a, dn = across.get((r, cc)), down.get((r, cc))
                if labels and (a is not None or dn is not None):
                    c.setStrokeGray(1)
                    c.setLineWidth(max(0.6, s * 0.018))
                    c.line(x0, y0 + s, x0 + s, y0)
                    c.setFillGray(1)
                    if a is not None:
                        _ctext(c, x0 + s * 0.70, y0 + s * 0.72, str(a), BOLD, fs)
                    if dn is not None:
                        _ctext(c, x0 + s * 0.30, y0 + s * 0.28, str(dn), BOLD, fs)
    c.setStrokeGray(0)
    c.setLineWidth(max(0.5, s * 0.02))
    for r in range(R + 1):
        c.line(x, y - r * s, x + C * s, y - r * s)
    for cc in range(C + 1):
        c.line(x + cc * s, y, x + cc * s, y - R * s)
    c.setLineWidth(max(1.0, s * 0.05))
    c.rect(x, y - R * s, C * s, R * s, stroke=1, fill=0)
    return C * s, R * s


def _nono_clue_cells(p):
    rc, cc = nonogram.all_clues(p["solution"])
    return rc, cc, max(len(k) for k in rc), max(len(k) for k in cc)


CLUE_W, CLUE_H = 0.66, 0.74  # clue slot size as a fraction of the cell size


def nonogram_size(p, width, height, solution=False):
    if solution:
        return min(width / p["cols"], height / p["rows"])
    _rc, _cc, lw, th = _nono_clue_cells(p)
    return min(width / (p["cols"] + lw * CLUE_W + 0.2), height / (p["rows"] + th * CLUE_H + 0.2))


def draw_nonogram(c, p, x, y, s, solution=False, labels=True):
    R, C = p["rows"], p["cols"]
    sol = p["solution"]
    left = top = 0.0
    if labels and not solution:
        rc, cc, lw, th = _nono_clue_cells(p)
        left, top = (lw * CLUE_W + 0.2) * s, (th * CLUE_H + 0.2) * s
        fs = max(7.0, s * 0.5)
        c.setFillGray(0)
        for r in range(R):
            for k, v in enumerate(reversed(rc[r])):
                _ctext(c, x + left - (k + 0.5) * CLUE_W * s - 0.1 * s, y - top - (r + 0.5) * s, str(v), REG, fs)
        for col in range(C):
            for k, v in enumerate(reversed(cc[col])):
                _ctext(c, x + left + (col + 0.5) * s, y - top + (k + 0.5) * CLUE_H * s + 0.1 * s, str(v), REG, fs)
    gx, gy = x + left, y - top
    if solution:
        c.setFillGray(0.1)
        for r in range(R):
            for col in range(C):
                if sol[r][col]:
                    c.rect(gx + col * s, gy - (r + 1) * s, s, s, stroke=0, fill=1)
    c.setStrokeGray(0.35 if not solution else 0.55)
    c.setLineWidth(max(0.35, s * 0.02))
    for r in range(R + 1):
        c.line(gx, gy - r * s, gx + C * s, gy - r * s)
    for col in range(C + 1):
        c.line(gx + col * s, gy, gx + col * s, gy - R * s)
    c.setStrokeGray(0)
    c.setLineWidth(max(0.8, s * 0.07))
    for r in range(0, R + 1, 5):
        c.line(gx, gy - r * s, gx + C * s, gy - r * s)
    for col in range(0, C + 1, 5):
        c.line(gx + col * s, gy, gx + col * s, gy - R * s)
    c.rect(gx, gy - R * s, C * s, R * s, stroke=1, fill=0)
    return left + C * s, top + R * s


def calcudoku_size(p, width, height):
    return min(width, height) / p["n"]


def draw_calcudoku(c, p, x, y, s, solution=False, labels=True):
    n = p["n"]
    cage_of = {}
    for k, cage in enumerate(p["cages"]):
        for r, col in cage["cells"]:
            cage_of[(r, col)] = k
    c.setFillGray(1)
    c.rect(x, y - n * s, n * s, n * s, stroke=0, fill=1)
    c.setStrokeGray(0.45)
    c.setLineWidth(max(0.4, s * 0.012))
    for i in range(1, n):
        c.line(x, y - i * s, x + n * s, y - i * s)
        c.line(x + i * s, y, x + i * s, y - n * s)
    c.setStrokeGray(0)
    c.setLineCap(2)
    c.setLineWidth(max(1.2, s * 0.05))
    for r in range(n):
        for col in range(n):
            k = cage_of[(r, col)]
            if col + 1 < n and cage_of[(r, col + 1)] != k:
                c.line(x + (col + 1) * s, y - r * s, x + (col + 1) * s, y - (r + 1) * s)
            if r + 1 < n and cage_of[(r + 1, col)] != k:
                c.line(x + col * s, y - (r + 1) * s, x + (col + 1) * s, y - (r + 1) * s)
    c.rect(x, y - n * s, n * s, n * s, stroke=1, fill=0)
    c.setLineCap(0)
    c.setFillGray(0)
    if labels:
        fs = max(7.0, s * 0.23)
        for cage in p["cages"]:
            if cage["op"] == "=" and solution:
                continue
            r, col = min(tuple(rc) for rc in cage["cells"])
            if cage["op"] == "=":
                _ctext(c, x + (col + 0.5) * s, y - (r + 0.5) * s, str(cage["target"]), BOLD, max(7.0, s * 0.5))
            else:
                c.setFont(BOLD, fs)
                c.drawString(x + col * s + s * 0.07, y - r * s - s * 0.07 - fs * 0.78,
                             f"{cage['target']}{OPS[cage['op']]}")
    if solution:
        for r in range(n):
            for col in range(n):
                _ctext(c, x + (col + 0.5) * s, y - (r + 0.56) * s, str(p["solution"][r][col]), REG, max(7.0, s * 0.46))
    return n * s, n * s


def size_for(p, w, h, solution=False):
    if p["type"] == "kakuro":
        return kakuro_size(p, w, h)
    if p["type"] == "nonogram":
        return nonogram_size(p, w, h, solution)
    return calcudoku_size(p, w, h)


def extent(p, s, solution=False):
    if p["type"] == "kakuro":
        return p["cols"] * s, p["rows"] * s
    if p["type"] == "nonogram":
        if solution:
            return p["cols"] * s, p["rows"] * s
        _rc, _cc, lw, th = _nono_clue_cells(p)
        return (p["cols"] + lw * CLUE_W + 0.2) * s, (p["rows"] + th * CLUE_H + 0.2) * s
    return p["n"] * s, p["n"] * s


def draw(c, p, x, y, s, solution=False, labels=True):
    fn = {"kakuro": draw_kakuro, "nonogram": draw_nonogram, "calcudoku": draw_calcudoku}[p["type"]]
    return fn(c, p, x, y, s, solution=solution, labels=labels)


def draw_centered(c, p, x, y, w, h, solution=False, labels=True, max_cell=None):
    """Draw p centred in the box whose top-left is (x, y)."""
    s = size_for(p, w, h, solution)
    if max_cell:
        s = min(s, max_cell)
    ew, eh = extent(p, s, solution)
    draw(c, p, x + (w - ew) / 2, y - (h - eh) / 2, s, solution=solution, labels=labels)
    return s
