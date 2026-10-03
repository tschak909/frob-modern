"""Orthogonal wire router for the generated schematic sheets (gen_sch.py).

Works on a 1.27 mm grid (cells are integer grid coordinates, y down, as on
the sheet).  Obstacles are symbol bodies, pin lines, power symbols, labels
and text; wires of other nets may only be crossed at right angles, never
joined, overlapped, bent on, or touched at an end.  A net's terminals are
pin tips with the direction the wire must leave in; the first terminal seeds
the tree and every further terminal is routed (A*) to the nearest cell of the
tree.  Landing on the middle of a tree segment makes a T: the segment is
split there and a junction recorded.

Usage (from gen_sch.py):
    R = Router(width_cells, height_cells)
    R.block_rect(x0, y0, x1, y1)          # inclusive cell rectangle
    R.add_terminal(...); R.route(net, terms) -> True / False
    R.segments, R.junctions               # [(net, (x0, y0), (x1, y1))], [(x, y)]
"""
import heapq

DIRS = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}
OPP = {'E': 'W', 'W': 'E', 'N': 'S', 'S': 'N'}
STEP, BEND, CROSS, NEAR = 1.0, 6.0, 4.0, 0.6


class Router:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.blocked = set()
        self.occ = {}          # cell -> (net, kind): kind 'H', 'V' or 'N' (node: end / bend / tee / pin)
        self.segments = []     # (net, (x0, y0), (x1, y1))
        self.junctions = []
        self.tree = {}         # net -> set of cells on its copper (wires + its pin tips)

    # ---- obstacles -----------------------------------------------------
    def block_rect(self, x0, y0, x1, y1):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                self.blocked.add((x, y))

    def block(self, c):
        self.blocked.add(c)

    def claim_node(self, net, c):
        """A pin tip / label anchor / power-symbol pin: a node of `net` nobody else may touch.
        (Not yet part of the net's connected tree: route() / commit() add it when it is wired.)"""
        self.blocked.discard(c)
        self.occ[c] = (net, 'N')

    # ---- routing -------------------------------------------------------
    def _free(self, net, c, d, goal):
        x, y = c
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        if c in self.blocked:
            return False
        o = self.occ.get(c)
        if o is None:
            return True
        if o[0] == net:
            return c in goal
        # another net's wire: straight across it at a right angle only
        return (o[1] == 'H' and d in 'NS') or (o[1] == 'V' and d in 'EW')

    def _near_cost(self, net, c):
        """Small penalty for running right next to another net's copper (keeps wires apart)."""
        x, y = c
        n = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            o = self.occ.get((x + dx, y + dy))
            if o and o[0] != net:
                n += 1
        return n * NEAR

    def route_to_tree(self, net, start, start_dir, max_cells=400000):
        """A* from a pin tip (leaving in start_dir) to any cell of net's tree."""
        goal = self.tree.get(net, set()) - {start}
        if not goal:
            return None
        gx = [g[0] for g in goal]
        gy = [g[1] for g in goal]

        def h(c):
            # distance to the goal set's bounding box (admissible)
            dx = max(min(gx) - c[0], 0, c[0] - max(gx))
            dy = max(min(gy) - c[1], 0, c[1] - max(gy))
            return dx + dy

        sx, sy = start
        ddx, ddy = DIRS[start_dir]
        first = (sx + ddx, sy + ddy)
        if first in goal:
            return [start, first]
        if not self._free(net, first, start_dir, goal):
            return None
        o = self.occ.get(first)
        crossing0 = bool(o and o[0] != net)
        openq = [(h(first) + STEP, STEP, first, start_dir, crossing0)]
        came = {(first, start_dir): ((start, None), crossing0)}
        best = {(first, start_dir): STEP}
        n = 0
        while openq and n < max_cells:
            n += 1
            f, g, c, d, crossing = heapq.heappop(openq)
            if c in goal:
                path = [c]
                key = (c, d)
                while True:
                    (pc, pd), _ = came[key]
                    path.append(pc)
                    if pd is None:
                        break
                    key = (pc, pd)
                return path[::-1]
            for nd, (dx, dy) in DIRS.items():
                if nd == OPP[d]:
                    continue
                if crossing and nd != d:
                    continue                  # no bends on another net's wire
                nc = (c[0] + dx, c[1] + dy)
                if not self._free(net, nc, nd, goal):
                    continue
                o = self.occ.get(nc)
                ncross = bool(o and o[0] != net)
                cost = g + STEP + (BEND if nd != d else 0) + (CROSS if ncross else 0) + self._near_cost(net, nc)
                key = (nc, nd)
                if cost < best.get(key, 1e18):
                    best[key] = cost
                    came[key] = ((c, d), ncross)
                    heapq.heappush(openq, (cost + h(nc), cost, nc, nd, ncross))
        return None

    def commit(self, net, path):
        """Write a cell path as merged straight segments; mark occupancy; split tees."""
        end = path[-1]
        tee = self.occ.get(end)
        pts = [path[0]]
        for i in range(1, len(path) - 1):
            a, b, c = path[i - 1], path[i], path[i + 1]
            if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                pts.append(b)
        pts.append(end)
        for i in range(len(pts) - 1):
            self.segments.append((net, pts[i], pts[i + 1]))
        # occupancy
        for i, c in enumerate(path):
            if i == 0 or i == len(path) - 1 or c in pts:
                kind = 'N'
            else:
                kind = 'H' if path[i - 1][1] == c[1] else 'V'
            prev = self.occ.get(c)
            if prev and prev[0] != net:      # a crossing: the other net's straight wire stays as it was
                continue
            self.occ[c] = (net, kind)
            self.tree.setdefault(net, set()).add(c)
        # landing on the middle of an existing segment of this net: split it, junction
        if tee and tee[1] in ('H', 'V'):
            self._split(net, end)
            self.junctions.append(end)
            self.occ[end] = (net, 'N')
        elif tee and tee[1] == 'N':
            # three or more wire ends at a node: junction
            ends = sum(1 for (nn, a, b) in self.segments if nn == net and end in (a, b))
            if ends >= 3:
                self.junctions.append(end)

    def _split(self, net, c):
        for i, (nn, a, b) in enumerate(self.segments):
            if nn != net or c in (a, b):
                continue
            if a[0] == b[0] == c[0] and min(a[1], b[1]) < c[1] < max(a[1], b[1]) or \
               a[1] == b[1] == c[1] and min(a[0], b[0]) < c[0] < max(a[0], b[0]):
                self.segments[i] = (nn, a, c)
                self.segments.append((nn, c, b))
                return

    def route(self, net, terms):
        """terms: [(cell, escape_dir)], already claimed.  Routes all to one tree.
        Returns the list of terminals that could not be connected."""
        tree = self.tree.setdefault(net, set())
        if not tree:
            if len(terms) < 2:
                return []
            tree.add(terms[0][0])      # seed: the first terminal; the rest connect to the tree, nearest first
        done = [t for t in terms if t[0] in tree] or [terms[0]]
        todo = [t for t in terms if t[0] not in tree]
        failed = []
        while todo:
            todo.sort(key=lambda t: min(abs(t[0][0] - d[0][0]) + abs(t[0][1] - d[0][1]) for d in done))
            t = todo.pop(0)
            path = self.route_to_tree(net, t[0], t[1])
            if path is None:
                failed.append(t)
                continue
            self.commit(net, path)
            done.append(t)
        return failed

    def stub(self, net, start, d, length):
        """A straight wire of `length` cells from start in direction d (for power symbols / bus taps).
        Returns the end cell, or None if blocked."""
        dx, dy = DIRS[d]
        path = [start]
        for i in range(1, length + 1):
            c = (start[0] + dx * i, start[1] + dy * i)
            if not self._free(net, c, d, set()) or self.occ.get(c):
                return None
            path.append(c)
        self.commit(net, path)
        return path[-1]
