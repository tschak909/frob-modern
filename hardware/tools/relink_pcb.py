#!/usr/bin/env python3
"""Bring the routed board in step with a redrawn schematic -- without touching copper.

  * renames nets (pads, tracks, vias, zones) by the old -> new map that
    compare_netlists.py writes (a hierarchical schematic names local nets by
    sheet path, e.g. XIN -> /mcu/XIN)
  * re-points every footprint at its symbol: path, sheetname, sheetfile (parts
    that moved sheet, e.g. into `power`)

Only names and footprint metadata change; tools/compare_copper.py-style
checks (segment / via / pad coordinates) are unaffected.

Usage: python3 tools/relink_pcb.py NETMAP.json
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, dump, find, findall, Q
import design as D
import gen_sch

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
PCB = os.path.join(PRJ, D.PROJECT + '.kicad_pcb')


def main():
    rename = json.load(open(sys.argv[1]))
    board = parse(open(PCB).read())
    n = [0]

    def walk(e):
        for i, x in enumerate(e):
            if isinstance(x, list) and x:
                if x[0] == 'net' and len(x) == 2 and str(x[1]) in rename:
                    x[1] = Q(rename[str(x[1])])
                    n[0] += 1
                else:
                    walk(x)
    walk(board)
    syms = gen_sch.load_symbols()
    moved = 0
    for fp in findall(board, 'footprint'):
        ref = [str(p[2]) for p in findall(fp, 'property') if p[1] == 'Reference']
        if not ref or ref[0] not in D.BY_REF:
            continue
        p = D.BY_REF[ref[0]]
        u = gen_sch.units_of(syms[p.lib_id])[0]
        path = '/%s/%s' % (gen_sch.uid('sheet', p.sheet), gen_sch.uid(p.sheet, p.ref, u))
        want = {'path': path, 'sheetname': '/%s/' % p.sheet, 'sheetfile': p.sheet + '.kicad_sch'}
        for k, v in want.items():
            e = find(fp, k)
            if e is not None and str(e[1]) != v:
                e[1] = Q(v)
                moved += 1
    open(PCB, 'w').write(dump(board) + '\n')
    print('relink_pcb: %d net references renamed, %d footprint path fields updated' % (n[0], moved))


if __name__ == '__main__':
    main()
