"""Nonogram generator and line solver.

A puzzle is {"type":"nonogram","rows","cols","solution":[[0/1]]}; clues derive
from the solution via `line_clue`. A puzzle is accepted only when pure line
logic (no guessing) solves it completely, which also proves uniqueness.
"""
import random
from functools import lru_cache


def line_clue(line):
    out, n = [], 0
    for v in line:
        if v:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def all_clues(sol):
    rows = [line_clue(r) for r in sol]
    cols = [line_clue([sol[r][c] for r in range(len(sol))]) for c in range(len(sol[0]))]
    return rows, cols


def solve_line(clue, line):
    """line: list of -1 unknown / 0 empty / 1 filled. Returns refined line or None if contradiction."""
    n, k = len(line), len(clue)
    line = tuple(line)
    clue = tuple(clue)

    @lru_cache(maxsize=None)
    def fits(pos, ci):
        # can clue[ci:] be placed in line[pos:]?
        if ci == k:
            return all(line[i] != 1 for i in range(pos, n))
        if pos >= n:
            return False
        L = clue[ci]
        ok = False
        # option: cell empty
        if line[pos] != 1 and fits(pos + 1, ci):
            ok = True
        # option: block starts here
        if pos + L <= n and all(line[i] != 0 for i in range(pos, pos + L)):
            if pos + L == n:
                if ci == k - 1:
                    ok = True
            elif line[pos + L] != 1 and fits(pos + L + 1, ci + 1):
                ok = True
        return ok

    if not fits(0, 0):
        return None
    can = [[False, False] for _ in range(n)]
    seen = set()

    def walk(pos, ci):
        if (pos, ci) in seen:
            return
        seen.add((pos, ci))
        if ci == k:
            for i in range(pos, n):
                can[i][0] = True
            return
        L = clue[ci]
        if line[pos] != 1 and fits(pos + 1, ci):
            can[pos][0] = True
            walk(pos + 1, ci)
        if pos + L <= n and all(line[i] != 0 for i in range(pos, pos + L)):
            if pos + L == n:
                if ci == k - 1:
                    for i in range(pos, n):
                        can[i][1] = True
            elif line[pos + L] != 1 and fits(pos + L + 1, ci + 1):
                for i in range(pos, pos + L):
                    can[i][1] = True
                can[pos + L][0] = True
                walk(pos + L + 1, ci + 1)

    walk(0, 0)
    out = []
    for i in range(n):
        if can[i][0] and can[i][1]:
            out.append(-1)
        elif can[i][1]:
            out.append(1)
        elif can[i][0]:
            out.append(0)
        else:
            return None
    return out


def line_solve(row_clues, col_clues):
    """Returns (grid, passes). Unknown cells stay -1."""
    R, C = len(row_clues), len(col_clues)
    g = [[-1] * C for _ in range(R)]
    passes = 0
    changed = True
    while changed:
        changed = False
        passes += 1
        for r in range(R):
            new = solve_line(row_clues[r], g[r])
            if new is None:
                return None, passes
            if new != g[r]:
                g[r] = new
                changed = True
        for c in range(C):
            col = [g[r][c] for r in range(R)]
            new = solve_line(col_clues[c], col)
            if new is None:
                return None, passes
            if new != col:
                for r in range(R):
                    g[r][c] = new[r]
                changed = True
    return g, passes


def _pattern(rng, R, C, density, symmetry):
    g = [[1 if rng.random() < density else 0 for _ in range(C)] for _ in range(R)]
    # cellular smoothing gives blobby, picture-like shapes
    for _ in range(rng.choice((1, 1, 2))):
        h = [row[:] for row in g]
        for r in range(R):
            for c in range(C):
                n = sum(
                    g[rr][cc]
                    for rr in range(r - 1, r + 2)
                    for cc in range(c - 1, c + 2)
                    if 0 <= rr < R and 0 <= cc < C and (rr, cc) != (r, c)
                )
                if n >= 5:
                    h[r][c] = 1
                elif n <= 2:
                    h[r][c] = 0
        g = h
    if symmetry == "mirror":
        for r in range(R):
            for c in range(C // 2):
                g[r][C - 1 - c] = g[r][c]
    elif symmetry == "rot":
        for r in range(R):
            for c in range(C):
                if (r, c) < (R - 1 - r, C - 1 - c):
                    g[R - 1 - r][C - 1 - c] = g[r][c]
    elif symmetry == "quad":
        for r in range(R):
            for c in range(C):
                g[r][c] = g[min(r, R - 1 - r)][min(c, C - 1 - c)]
    return g


def generate(seed, rows, cols, density=0.6, min_passes=1, max_full_lines=1):
    rng = random.Random(seed)
    while True:
        sym = rng.choice(("mirror", "mirror", "rot", "quad", "none"))
        sol = _pattern(rng, rows, cols, density, sym)
        fill = sum(map(sum, sol)) / (rows * cols)
        if not 0.40 <= fill <= 0.62:
            continue
        lines = sol + [list(col) for col in zip(*sol)]
        # nearly full lines make a puzzle trivial and dull
        if sum(1 for ln in lines if sum(ln) >= len(ln) - 1) > max_full_lines:
            continue
        if any(not any(r) for r in sol) or any(not any(sol[r][c] for r in range(rows)) for c in range(cols)):
            continue
        rc, cc = all_clues(sol)
        g, passes = line_solve(rc, cc)
        if g is None or any(v == -1 for row in g for v in row):
            continue
        assert g == sol
        if passes < min_passes:
            continue
        return {"type": "nonogram", "rows": rows, "cols": cols, "solution": sol,
                "passes": passes, "symmetry": sym}
