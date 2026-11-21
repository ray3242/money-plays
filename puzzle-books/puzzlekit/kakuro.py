"""Kakuro (cross sums) generator and solver.

Grid: R x C cells. cell value 0 = black, 1 = white. Row 0 and column 0 are black.
A puzzle is {"rows","cols","white":[[0/1]],"solution":[[digit or 0]]}; clues are
derived from the solution by `runs()`.
"""
import random
from functools import lru_cache
from itertools import combinations

FULL = 0b1111111110


@lru_cache(maxsize=None)
def combo_masks(length, total):
    return tuple(
        sum(1 << d for d in c)
        for c in combinations(range(1, 10), length)
        if sum(c) == total
    )


def find_runs(white):
    R, C = len(white), len(white[0])
    runs = []
    for r in range(R):
        c = 0
        while c < C:
            if white[r][c]:
                s = c
                while c < C and white[r][c]:
                    c += 1
                runs.append(("h", [(r, k) for k in range(s, c)]))
            else:
                c += 1
    for c in range(C):
        r = 0
        while r < R:
            if white[r][c]:
                s = r
                while r < R and white[r][c]:
                    r += 1
                runs.append(("v", [(k, c) for k in range(s, r)]))
            else:
                r += 1
    return runs


def clues(white, solution):
    """Return list of (dir, cells, total)."""
    return [(d, cells, sum(solution[r][c] for r, c in cells)) for d, cells in find_runs(white)]


def make_layout(rng, R, C, max_run, density):
    while True:
        white = [[0] * C for _ in range(R)]
        for r in range(1, R):
            for c in range(1, C):
                white[r][c] = 1
        # symmetric random blacks (180 degree rotation of the interior)
        for r in range(1, R):
            for c in range(1, C):
                if rng.random() < density:
                    white[r][c] = 0
                    white[R - r][C - c] = 0
        ok = True
        for _it in range(60):
            changed = False
            for d, cells in find_runs(white):
                if len(cells) == 1:
                    r, c = cells[0]
                    white[r][c] = 0
                    white[R - r][C - c] = 0
                    changed = True
                elif len(cells) > max_run:
                    r, c = cells[rng.randrange(1, len(cells) - 1)]
                    white[r][c] = 0
                    white[R - r][C - c] = 0
                    changed = True
            if not changed:
                break
        else:
            ok = False
        if not ok:
            continue
        cells = [(r, c) for r in range(R) for c in range(C) if white[r][c]]
        if len(cells) < 0.5 * (R - 1) * (C - 1):
            continue
        # every white cell must be in both an h-run and a v-run of length >= 2
        runs = find_runs(white)
        if any(len(cs) < 2 or len(cs) > max_run for _, cs in runs):
            continue
        # no empty interior row / column
        if any(not any(white[r][1:]) for r in range(1, R)):
            continue
        if any(not any(white[r][c] for r in range(1, R)) for c in range(1, C)):
            continue
        # connectivity
        seen = {cells[0]}
        stack = [cells[0]]
        while stack:
            r, c = stack.pop()
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < R and 0 <= nc < C and white[nr][nc] and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
        if len(seen) != len(cells):
            continue
        return white


class Solver:
    def __init__(self, white, clue_list):
        self.cells = [(r, c) for r in range(len(white)) for c in range(len(white[0])) if white[r][c]]
        self.idx = {rc: i for i, rc in enumerate(self.cells)}
        self.runs = [([self.idx[rc] for rc in cells], total) for _, cells, total in clue_list]
        self.cell_runs = [[] for _ in self.cells]
        for ri, (cs, _) in enumerate(self.runs):
            for i in cs:
                self.cell_runs[i].append(ri)
        self.guesses = 0
        self.aborted = False
        self.max_guesses = 400  # give up on search-heavy grids; the generator tries another

    def _prune_run(self, dom, ri):
        """Filter domains of a run to values having support. Returns changed cell list or None on wipeout."""
        cs, total = self.runs[ri]
        n = len(cs)
        doms = [dom[i] for i in cs]
        # quick combo filter
        allowed = 0
        fixed = 0
        for d in doms:
            if d & (d - 1) == 0:
                fixed |= d
        for m in combo_masks(n, total):
            if m & fixed == fixed:
                allowed |= m
        doms = [d & allowed for d in doms]
        if any(d == 0 for d in doms):
            return None
        support = [0] * n
        vals = [[v for v in range(1, 10) if d >> v & 1] for d in doms]
        order = sorted(range(n), key=lambda k: len(vals[k]))

        def rec(k, used, rem, chosen):
            if k == n:
                if rem == 0:
                    for pos, v in chosen:
                        support[pos] |= 1 << v
                    return
                return
            pos = order[k]
            left = n - k - 1
            for v in vals[pos]:
                if used >> v & 1:
                    continue
                r2 = rem - v
                if r2 < left or r2 > 9 * left:
                    continue
                chosen.append((pos, v))
                rec(k + 1, used | 1 << v, r2, chosen)
                chosen.pop()

        rec(0, 0, total, [])
        changed = []
        for k, i in enumerate(cs):
            if support[k] == 0:
                return None
            if support[k] != dom[i]:
                dom[i] = support[k]
                changed.append(i)
        return changed

    def propagate(self, dom, queue):
        queue = set(queue)
        while queue:
            ri = queue.pop()
            ch = self._prune_run(dom, ri)
            if ch is None:
                return False
            for i in ch:
                for r2 in self.cell_runs[i]:
                    if r2 != ri:
                        queue.add(r2)
        return True

    def solve(self, limit=2):
        dom = [FULL] * len(self.cells)
        sols = []
        self.guesses = 0
        self.aborted = False
        if not self.propagate(dom, range(len(self.runs))):
            return sols

        def rec(dom):
            if len(sols) >= limit or self.aborted:
                return
            if self.guesses >= self.max_guesses:
                self.aborted = True
                return
            best, bc = -1, 10
            for i, d in enumerate(dom):
                n = bin(d).count("1")
                if n > 1 and n < bc:
                    best, bc = i, n
            if best < 0:
                sols.append([d.bit_length() - 1 for d in dom])
                return
            self.guesses += 1
            for v in range(1, 10):
                if dom[best] >> v & 1:
                    d2 = dom[:]
                    d2[best] = 1 << v
                    if self.propagate(d2, self.cell_runs[best]):
                        rec(d2)
                    if len(sols) >= limit or self.aborted:
                        return

        rec(dom)
        return sols


def random_fill(rng, white):
    R, C = len(white), len(white[0])
    runs = find_runs(white)
    cells = [(r, c) for r in range(R) for c in range(C) if white[r][c]]
    cell_runs = {rc: [] for rc in cells}
    for ri, (_, cs) in enumerate(runs):
        for rc in cs:
            cell_runs[rc].append(ri)
    used = [0] * len(runs)
    sol = [[0] * C for _ in range(R)]

    def rec(k):
        if k == len(cells):
            return True
        rc = cells[k]
        a, b = cell_runs[rc]
        opts = [v for v in range(1, 10) if not (used[a] | used[b]) >> v & 1]
        rng.shuffle(opts)
        for v in opts:
            used[a] |= 1 << v
            used[b] |= 1 << v
            sol[rc[0]][rc[1]] = v
            if rec(k + 1):
                return True
            used[a] &= ~(1 << v)
            used[b] &= ~(1 << v)
        sol[rc[0]][rc[1]] = 0
        return False

    return sol if rec(0) else None


def generate(seed, rows, cols, max_run=5, density=0.22, want_guessfree=None):
    """Generate a uniquely solvable kakuro. rows/cols include the clue row/col."""
    rng = random.Random(seed)
    while True:
        white = make_layout(rng, rows, cols, max_run, density)
        sol = random_fill(rng, white)
        if sol is None:
            continue
        runs = find_runs(white)
        cell_runs = {}
        for _, cs in runs:
            for rc in cs:
                cell_runs.setdefault(rc, []).append(cs)
        for _ in range(80):
            cl = clues(white, sol)
            s = Solver(white, cl)
            sols = s.solve(2)
            if s.aborted or not sols:
                break
            if len(sols) == 1:
                if want_guessfree is True and s.guesses > 0:
                    break
                return {
                    "type": "kakuro", "rows": rows, "cols": cols,
                    "white": white, "solution": sol, "guesses": s.guesses,
                }
            # repair: change one of the ambiguous cells
            mine = [sol[r][c] for r, c in s.cells]
            other = sols[0] if sols[0] != mine else sols[1]
            diff = [s.cells[i] for i in range(len(mine)) if sols[0][i] != sols[1][i]]
            rng.shuffle(diff)
            done = False
            for rc in diff:
                taken = {sol[r][c] for cs in cell_runs[rc] for r, c in cs if (r, c) != rc}
                opts = [v for v in range(1, 10) if v not in taken and v != sol[rc[0]][rc[1]]]
                if opts:
                    # prefer extreme digits: they make sums more constraining
                    opts.sort(key=lambda v: -abs(v - 5) + rng.random())
                    sol[rc[0]][rc[1]] = opts[0]
                    done = True
                    break
            if not done:
                break
