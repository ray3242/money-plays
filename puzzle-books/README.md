# Puzzle books for Amazon KDP

Code-generated, print-ready puzzle books (8.5 x 11 in paperback, black ink, white paper).

    pip install -r requirements.txt
    python3 build.py            # builds every book into dist/ and runs QC; exits 1 on any failed check
    python3 build.py kakuro --author "Pen Name" --regenerate

- `puzzlekit/kakuro.py`, `nonogram.py`, `calcudoku.py`: generators, each with its own solver.
- `puzzlekit/verify.py`: independent OR-tools CP-SAT proof that each puzzle has exactly one solution.
- `puzzlekit/interior.py`, `cover.py`, `draw.py`: vector PDF interior and full-wrap cover.
- `puzzlekit/qc.py`: KDP checks (trim, margins, embedded fonts, 7 pt minimum, spine width, safe zones, barcode area).
- `puzzlekit/books.py`: titles, copy, difficulty sections.

## Status

- All three books are built in `dist/` and pass every QC check (114 pages each, see `dist/*-qc.json`).
- Listings: `LISTINGS.md`. Publishing steps, expected payout and odds: `SUBMIT.md`.
- Tests: `python3 -m pytest tests` (generators, the CP-SAT uniqueness proof, a cut-down book through every QC check).
- The author name `Northgrid Puzzles` is a placeholder pen name.

## Rules checked (official pages)

- KDP AI content (https://kdp.amazon.com/en_US/help/topic/G200672390): "We require you to inform us of AI-generated
  content (text, images, or translations) when you publish a new book or make edits to and republish an existing book
  through KDP." Disclose these books as AI-generated at upload.
- KDP low-content (https://kdp.amazon.com/en_US/help/topic/GGE5T76TWKA85DJM): "This does not typically include activity
  books, such as puzzle books or coloring books".
- KDP is free to publish; printing cost is deducted from royalties. Canadian bank accounts are paid by EFT in CAD;
  a tax interview is required (US withholding up to 30 percent before treaty). Limit: 2 new titles per format per week.
- Printing, black ink, large trim (8.5 x 11), 110 to 828 pages (https://kdp.amazon.com/en_US/help/topic/G201834340):
  Amazon.com USD 1.00 + 0.017 per page, Amazon.ca CAD 1.26 + 0.021 per page. Royalty = rate x list price - printing
  (https://kdp.amazon.com/en_US/help/topic/G201834330: 60 percent at USD 9.99 / CAD 13.99 and above, 50 percent below).
- Gumroad: 10 percent + USD 0.50 per direct sale, pays out to Canadian banks; original puzzle PDFs are not prohibited.
- Teachers Pay Teachers: prohibits entirely or substantially AI-generated resources. Not a fit for these books.
- Payhip: its Terms of Use (https://payhip.com/terms) have no rule on AI-made products.
- Gumroad's prohibited list (https://gumroad.com/prohibited, revised 2026-09-16) bans selling "AI services" (access to AI tools), not AI-made PDFs.
- There is no contest, prize or deadline here: income is royalties only, with no guarantee of any sales.
