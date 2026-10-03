#!/usr/bin/env python3
"""Via-in-pad escapes for RP2354B signal pins that cannot leave on F.Cu.

The QFN-80's 0.4 mm-pitch pins escape straight out on F.Cu; a supply pin's
plane via (fanout.py) sits 2 mm in front of it, and once both neighbours'
lanes are taken a signal pin next to it has no way out.  Those pins get a
0.25 / 0.15 mm via in the middle of their own pad (JLCPCB: epoxy-filled and
capped, the standard via-in-pad process for 6-layer boards) and leave on
In2 / In3; the finisher routes them from there.

The via is 0.05 mm wider than the 0.2 mm pad: 0.175 mm to the neighbouring
pads.  The vias are locked, on the pad's own net.

Usage: python3 tools/via_in_pad.py U1:14,U1:23,...    (ref:pad list)
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, dump, find, findall, Q
import gen_pcb as G

VIA_D, VIA_DRILL = 0.25, 0.15


def main():
    want = [tuple(s.split(':')) for s in sys.argv[1].split(',')]
    board = parse(open(G.PCB).read())
    fps = {}
    for e in board:
        if isinstance(e, list) and e and e[0] == 'footprint':
            ref = [str(p[2]) for p in findall(e, 'property') if p[1] == 'Reference'][0]
            fps[ref] = e
    have = {(round(float(find(e, 'at')[1]), 3), round(float(find(e, 'at')[2]), 3))
            for e in board if isinstance(e, list) and e and e[0] == 'via'}
    k = max(i for i, e in enumerate(board) if isinstance(e, list) and e and e[0] in ('segment', 'via'))
    added = []
    for ref, num in want:
        fp = fps[ref]
        at = find(fp, 'at')
        fx, fy, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        pad = [p for p in findall(fp, 'pad') if str(p[1]) == num][0]
        pa = find(pad, 'at')
        dx, dy = G.rot_pt(float(pa[1]), float(pa[2]), rot)
        x, y = round(fx + dx, 4), round(fy + dy, 4)
        if (round(x, 3), round(y, 3)) in have:
            continue
        net = str(find(pad, 'net')[1])
        added.append(['via', ['at', x, y], ['size', VIA_D], ['drill', VIA_DRILL],
                      ['layers', Q('F.Cu'), Q('B.Cu')], ['locked', 'yes'], ['net', Q(net)],
                      ['uuid', Q(str(G.uid('viainpad', ref, num)))]])
    board[k + 1:k + 1] = added
    open(G.PCB, 'w').write(dump(board) + '\n')
    print('via_in_pad: %d vias (%s)' % (len(added), sys.argv[1]))


if __name__ == '__main__':
    main()
