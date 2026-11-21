"""Calcudoku (arithmetic cage latin square) generator and solver.

A puzzle is {"type":"calcudoku","n","cages":[{"cells":[[r,c]..],"op":"+-x/=" ,"target":int}],
"solution":[[..]]}. "=" marks a single given cell.
"""
import random
from itertools import product


def latin(rng, n):
    base = [[(r + c) % n + 1 for c in range(n)] for r in range(n)]
    rng.shuffle(base)
    cols = list(range(n))
    rng.shuffle(cols)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    sq = [[perm[base[r][c] - 1] for c in cols] for r in range(n)]
    # extra mixing: random intercalate swaps keep it latin
    for _ in range(n * n * 4):
        r1, r2 = rng.sample(range(n), 2)
        c1, c2 = rng.sample(range(n), 2)
        if sq[r1][c1] == sq[r2][c2] and sq[r1][c2] == sq[r2][c1]:
            sq[r1][c1], sq[r1][c2] = sq[r1][c2], sq[r1][c1]
            sq[r2][c1], sq[r2][c2] = sq[r2][c2], sq[r2][c1]
    return sq


def make_cages(rng, n, max_size, singles):
    cage_of = [[-1] * n for _ in range(n)]
    cages = []
    cells = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(cells)
    n_single = 0
    for r, c in cells:
        if cage_of[r][c] != -1:
            continue
        size = rng.choices((2, 3, 4), weights=(5, 4, 2 if max_size >= 4 else 0))[0]
        size = min(size, max_size)
        cage = [(r, c)]
        cage_of[r][c] = len(cages)
        while len(cage) < size:
            nb = [
                (rr, cc)
                for (r0, c0) in cage
                for rr, cc in ((r0 + 1, c0), (r0 - 1, c0), (r0, c0 + 1), (r0, c0 - 1))
                if 0 <= rr < n and 0 <= cc < n and cage_of[rr][cc] == -1
            ]
            if not nb:
                break
            rr, cc = rng.choice(nb)
            cage.append((rr, cc))
            cage_of[rr][cc] = len(cages)
        if len(cage) == 1:
            n_single += 1
        cages.append(sorted(cage))
    if n_single > singles:
        return None
    return cages


def cage_ok(op, target, vals):
    if op == "=":
        return vals[0] == target
    if op == "+":
        return sum(vals) == target
    if op == "x":
        p = 1
        for v in vals:
            p *= v
        return p == target
    a, b = max(vals), min(vals)
    if op == "-":
        return a - b == target
    return b * target == a


def cage_tuples(n, cage):
    cells, op, target = cage["cells"], cage["op"], cage["target"]
    out = []
    for vals in product(range(1, n + 1), repeat=len(cells)):
        if not cage_ok(op, target, vals):
            continue
        good = True
        for i in range(len(cells)):
            for j in range(i):
                if vals[i] == vals[j] and (cells[i][0] == cells[j][0] or cells[i][1] == cells[j][1]):
                    good = False
        if good:
            out.append(vals)
    return out


def solve(n, cages, limit=2):
    cand = [cage_tuples(n, c) for c in cages]
    order = sorted(range(len(cages)), key=lambda i: len(cand[i]))
    rows = [0] * n
    cols = [0] * n
    grid = [[0] * n for _ in range(n)]
    sols = []
    stats = {"nodes": 0}

    def rec(k):
        if len(sols) >= limit:
            return
        if k == len(order):
            sols.append([row[:] for row in grid])
            return
        # dynamic choice: cage with fewest feasible tuples
        best, best_opts = None, None
        for idx in range(k, len(order)):
            ci = order[idx]
            cells = cages[ci]["cells"]
            opts = [
                t for t in cand[ci]
                if all(not (rows[r] >> v & 1) and not (cols[c] >> v & 1) for (r, c), v in zip(cells, t))
            ]
            if best_opts is None or len(opts) < len(best_opts):
                best, best_opts = idx, opts
                if len(opts) <= 1:
                    break
        if not best_opts:
            return
        order[k], order[best] = order[best], order[k]
        ci = order[k]
        cells = cages[ci]["cells"]
        stats["nodes"] += len(best_opts) - 1
        for t in best_opts:
            for (r, c), v in zip(cells, t):
                rows[r] |= 1 << v
                cols[c] |= 1 << v
                grid[r][c] = v
            rec(k + 1)
            for (r, c), v in zip(cells, t):
                rows[r] &= ~(1 << v)
                cols[c] &= ~(1 << v)
            if len(sols) >= limit:
                break
        order[k], order[best] = order[best], order[k]

    rec(0)
    return sols, stats["nodes"]


def generate(seed, n, ops="+-x/", max_size=3, singles=2):
    rng = random.Random(seed)
    while True:
        sol = latin(rng, n)
        layout = make_cages(rng, n, max_size, singles)
        if layout is None:
            continue
        cages = []
        for cells in layout:
            vals = [sol[r][c] for r, c in cells]
            if len(cells) == 1:
                op, target = "=", vals[0]
            else:
                choices = [o for o in ops if o in "+x"]
                if len(cells) == 2:
                    if "-" in ops:
                        choices.append("-")
                        choices.append("-")
                    if "/" in ops and max(vals) % min(vals) == 0:
                        choices += ["/", "/", "/"]
                op = rng.choice(choices)
                if op == "+":
                    target = sum(vals)
                elif op == "x":
                    target = 1
                    for v in vals:
                        target *= v
                elif op == "-":
                    target = max(vals) - min(vals)
                else:
                    target = max(vals) // min(vals)
            cages.append({"cells": [list(rc) for rc in cells], "op": op, "target": target})
        sols, nodes = solve(n, cages, 2)
        if len(sols) == 1:
            assert sols[0] == sol
            return {"type": "calcudoku", "n": n, "cages": cages, "solution": sol, "nodes": nodes}
