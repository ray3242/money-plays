"""Independent verification with OR-tools CP-SAT.

Each check rebuilds the puzzle from its printed clues only, solves it, compares
with the stored solution, then forbids that solution and proves no other exists.
This shares no code with the generators' own solvers.
"""
from ortools.sat.python import cp_model

from . import kakuro, nonogram


def _unique(model, variables, expected):
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = 120
    st = solver.Solve(model)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return False, "no solution found from printed clues"
    got = [solver.Value(v) for v in variables]
    if got != expected:
        return False, "solver found a different solution than the stored one"
    model.AddForbiddenAssignments(variables, [tuple(got)])
    st = solver.Solve(model)
    if st != cp_model.INFEASIBLE:
        return False, "second solution exists (or timeout)"
    return True, "unique"


def verify_kakuro(p):
    white, sol = p["white"], p["solution"]
    m = cp_model.CpModel()
    v = {}
    for r, row in enumerate(white):
        for c, w in enumerate(row):
            if w:
                v[r, c] = m.NewIntVar(1, 9, f"x{r}_{c}")
    n_runs = {rc: 0 for rc in v}
    for _d, cells, total in kakuro.clues(white, sol):
        if not 2 <= len(cells) <= 9:
            return False, "bad run length"
        m.AddAllDifferent([v[rc] for rc in cells])
        m.Add(sum(v[rc] for rc in cells) == total)
        for rc in cells:
            n_runs[tuple(rc)] += 1
    if any(k != 2 for k in n_runs.values()):
        return False, "cell not covered by both an across and a down clue"
    keys = sorted(v)
    return _unique(m, [v[k] for k in keys], [sol[r][c] for r, c in keys])


def _line_automaton(m, cells, clue):
    # states: 0 start; for each block, one state per filled cell, plus a gap state
    if not clue:
        for x in cells:
            m.Add(x == 0)
        return
    trans = []
    state = 0
    for bi, L in enumerate(clue):
        trans.append((state, 0, state))
        for _ in range(L):
            trans.append((state, 1, state + 1))
            state += 1
        if bi < len(clue) - 1:
            trans.append((state, 0, state + 1))
            state += 1
    trans.append((state, 0, state))
    m.AddAutomaton(cells, 0, [state], trans)


def verify_nonogram(p):
    sol = p["solution"]
    R, C = p["rows"], p["cols"]
    rc, cc = nonogram.all_clues(sol)
    m = cp_model.CpModel()
    x = [[m.NewBoolVar(f"x{r}_{c}") for c in range(C)] for r in range(R)]
    for r in range(R):
        _line_automaton(m, x[r], rc[r])
    for c in range(C):
        _line_automaton(m, [x[r][c] for r in range(R)], cc[c])
    flat = [x[r][c] for r in range(R) for c in range(C)]
    return _unique(m, flat, [sol[r][c] for r in range(R) for c in range(C)])


def verify_calcudoku(p):
    n, sol = p["n"], p["solution"]
    m = cp_model.CpModel()
    x = [[m.NewIntVar(1, n, f"x{r}_{c}") for c in range(n)] for r in range(n)]
    for i in range(n):
        m.AddAllDifferent(x[i])
        m.AddAllDifferent([x[r][i] for r in range(n)])
    seen = set()
    for k, cage in enumerate(p["cages"]):
        cells = [tuple(rc) for rc in cage["cells"]]
        if seen & set(cells):
            return False, "overlapping cages"
        seen |= set(cells)
        vs = [x[r][c] for r, c in cells]
        op, t = cage["op"], cage["target"]
        if op == "=":
            if len(vs) != 1:
                return False, "bad given"
            m.Add(vs[0] == t)
        elif op == "+":
            m.Add(sum(vs) == t)
        elif op == "x":
            acc = vs[0]
            for j, w in enumerate(vs[1:]):
                nxt = m.NewIntVar(1, n ** len(vs), f"p{k}_{j}")
                m.AddMultiplicationEquality(nxt, [acc, w])
                acc = nxt
            m.Add(acc == t)
        elif op in "-/":
            if len(vs) != 2:
                return False, "bad two-cell cage"
            b = m.NewBoolVar(f"b{k}")
            if op == "-":
                m.Add(vs[0] - vs[1] == t).OnlyEnforceIf(b)
                m.Add(vs[1] - vs[0] == t).OnlyEnforceIf(b.Not())
            else:
                m.Add(vs[0] == t * vs[1]).OnlyEnforceIf(b)
                m.Add(vs[1] == t * vs[0]).OnlyEnforceIf(b.Not())
        else:
            return False, "unknown op"
    if len(seen) != n * n:
        return False, "cages do not cover the grid"
    flat = [x[r][c] for r in range(n) for c in range(n)]
    return _unique(m, flat, [sol[r][c] for r in range(n) for c in range(n)])


VERIFIERS = {"kakuro": verify_kakuro, "nonogram": verify_nonogram, "calcudoku": verify_calcudoku}


def verify(p):
    return VERIFIERS[p["type"]](p)


def signature(p):
    """Printed-clue signature, used to reject duplicate puzzles inside a book."""
    if p["type"] == "kakuro":
        return repr((p["white"], [(d, t) for d, _c, t in kakuro.clues(p["white"], p["solution"])]))
    if p["type"] == "nonogram":
        return repr(nonogram.all_clues(p["solution"]))
    return repr(p["cages"])
