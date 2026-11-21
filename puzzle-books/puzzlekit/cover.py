"""Full-wrap KDP paperback cover: back + spine + front in one PDF, with bleed."""
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from . import draw
from .draw import BOLD, REG, SERIF

BLEED = 0.125 * inch
SAFE = 0.25 * inch          # KDP: keep text this far inside the trim edge
SPINE_PER_PAGE = 0.002252 * inch  # white paper, black ink
BARCODE = (2.0 * inch, 1.2 * inch)
MIN_SPINE_TEXT_PAGES = 80   # KDP: spine text only for books with more than 79 pages
SPINE_TEXT_MARGIN = 0.0625 * inch


def dimensions(pages, trim=(8.5 * inch, 11 * inch)):
    spine = pages * SPINE_PER_PAGE
    return {"spine": spine, "width": 2 * trim[0] + spine + 2 * BLEED, "height": trim[1] + 2 * BLEED,
            "trim_w": trim[0], "trim_h": trim[1]}


def _para(c, text, x, y, w, size, font=REG, color=(1, 1, 1), align=0, leading=None, bullet=None, indent=0):
    st = ParagraphStyle("c", fontName=font, fontSize=size, leading=leading or size * 1.4,
                        textColor=color, alignment=align, leftIndent=indent,
                        bulletFontName=REG, bulletFontSize=size, bulletColor=color)
    p = Paragraph(text, st, bulletText=bullet)
    _w, h = p.wrap(w, 2000)
    p.drawOn(c, x, y - h)
    return y - h


def _fit(c, text, font, max_w, size):
    while c.stringWidth(text, font, size) > max_w and size > 8:
        size -= 0.5
    return size


def build(path, book, pages, sample, author=""):
    draw.register_fonts()
    d = dimensions(pages)
    W, H, spine, tw, th = d["width"], d["height"], d["spine"], d["trim_w"], d["trim_h"]
    pal = book["palette"]
    bg, accent, ink = pal["bg"], pal["accent"], pal["ink"]
    c = canvas.Canvas(path, pagesize=(W, H), initialFontName=REG)
    c.setTitle(book["title"] + " cover")
    c.setFillColorRGB(*bg)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    back_x = BLEED
    spine_x = BLEED + tw
    front_x = spine_x + spine
    m = 0.6 * inch  # design margin inside trim, well beyond the 0.25in safe zone

    # ---------- front
    fx, fw = front_x + m, tw - 2 * m
    cx = front_x + tw / 2
    c.setFillColorRGB(*accent)
    c.rect(0, BLEED + th - 0.42 * inch, W, 0.42 * inch + BLEED, stroke=0, fill=1)
    c.rect(0, 0, W, BLEED + 0.42 * inch, stroke=0, fill=1)
    y = BLEED + th - 1.15 * inch
    words = book["title"].upper().split()
    lines = [" ".join(words[:-1]), words[-1]] if len(words) > 2 else words
    c.setFillColorRGB(*ink)
    for i, ln in enumerate(lines):
        size = _fit(c, ln, SERIF, fw, 78 if i == len(lines) - 1 else 50)
        y -= size * 0.82
        c.setFont(SERIF, size)
        c.drawCentredString(cx, y, ln)
        y -= size * 0.34
    y -= 6
    c.setFillColorRGB(*accent)
    size = _fit(c, book["subtitle"], BOLD, fw, 21)
    c.setFont(BOLD, size)
    c.drawCentredString(cx, y - size, book["subtitle"])
    y -= size + 0.4 * inch
    # white card with a real puzzle from the generator
    card_bottom = BLEED + 1.75 * inch
    card_h = y - card_bottom
    card_w = min(fw, card_h * 1.02)
    c.setFillColorRGB(1, 1, 1)
    c.roundRect(cx - card_w / 2, card_bottom, card_w, card_h, 14, stroke=0, fill=1)
    pad = 0.3 * inch
    draw.draw_centered(c, sample, cx - card_w / 2 + pad, card_bottom + card_h - pad, card_w - 2 * pad, card_h - 2 * pad)
    # badge
    r = 0.78 * inch
    bx, by = front_x + tw - m - r * 0.75, card_bottom + 0.1 * inch
    c.setFillColorRGB(*accent)
    c.circle(bx, by, r, stroke=0, fill=1)
    c.setStrokeColorRGB(*bg)
    c.setLineWidth(2)
    c.circle(bx, by, r - 6, stroke=1, fill=0)
    c.setFillColorRGB(*bg)
    c.setFont(SERIF, 38)
    c.drawCentredString(bx, by - 2, book["badge"][0])
    c.setFont(BOLD, 12)
    c.drawCentredString(bx, by - 20, book["badge"][1])
    c.setFillColorRGB(*ink)
    c.setFont(REG, 15)
    c.drawString(fx, BLEED + 1.12 * inch, book["tagline"].split(". ")[0] + ".")
    c.setFont(BOLD, 15)
    c.drawString(fx, BLEED + 0.8 * inch, "Solutions included.")
    if author:
        c.setFont(BOLD, 15)
        c.drawRightString(front_x + tw - m, BLEED + 0.8 * inch, author)

    # ---------- back
    bxl, bw = back_x + m, tw - 2 * m
    y = BLEED + th - 1.2 * inch
    y = _para(c, book["subtitle"], bxl, y, bw, 24, font=SERIF, color=accent, leading=31)
    y -= 18
    for t in book["back"]:
        y = _para(c, t, bxl, y, bw, 14.5, color=ink, leading=21.5) - 12
    y -= 8
    for t in book["bullets"]:
        y = _para(c, t, bxl, y, bw, 14.5, font=BOLD, color=ink, leading=21, bullet="\u2713", indent=22) - 7
    # barcode area: KDP prints the barcode bottom-right of the back cover; leave it blank
    bcx = back_x + tw - 0.25 * inch - BARCODE[0]
    bcy = BLEED + 0.25 * inch
    c.setFillColorRGB(1, 1, 1)
    c.rect(bcx - 0.12 * inch, bcy, BARCODE[0] + 0.12 * inch, BARCODE[1] + 0.12 * inch, stroke=0, fill=1)
    # small sample strip
    strip_top = y - 0.25 * inch
    strip_bottom = bcy + BARCODE[1] + 0.5 * inch
    if strip_top - strip_bottom > 1.6 * inch:
        hgt = min(strip_top - strip_bottom, 3.0 * inch)
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(bxl, strip_top - hgt, hgt, hgt, 10, stroke=0, fill=1)
        draw.draw_centered(c, sample, bxl + 10, strip_top - 10, hgt - 20, hgt - 20, solution=True,
                           labels=sample["type"] != "nonogram")
        _para(c, "Every puzzle is checked by two separate solver programs, so each one has a single correct answer.",
              bxl + hgt + 0.3 * inch, strip_top - 0.15 * inch, bw - hgt - 0.3 * inch, 13, color=ink, leading=19)

    # ---------- spine
    if pages >= MIN_SPINE_TEXT_PAGES:
        max_h = spine - 2 * SPINE_TEXT_MARGIN
        size = min(max_h / 1.25, 11)
        c.saveState()
        c.translate(spine_x + spine / 2, BLEED + th / 2)
        c.rotate(-90)
        c.setFillColorRGB(*ink)
        c.setFont(BOLD, size)
        c.drawCentredString(0, -size * 0.36, f"{book['title'].upper()}   \u2022   {book['badge'][0]} PUZZLES")
        c.restoreState()
    c.save()
    d["barcode_box"] = (bcx, bcy, BARCODE[0], BARCODE[1])
    return d
