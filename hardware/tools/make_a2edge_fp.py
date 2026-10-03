#!/usr/bin/env python3
"""Write Frob2354.pretty/Apple2_Slot_Edge_50.kicad_mod.

The Apple II peripheral-slot card edge (Apple II Reference Manual, 1979,
p.106; geometry of the reverse-engineered FROB card, retroabandon/apple2-re
frob/kicad/a2board.kicad_pcb, footprint "Apple II Expansion Edge Connector"):

  * 25 fingers per side at 0.100 in (2.54 mm), 60.96 mm span, centred on a
    65.405 mm wide, 7.62 mm deep tab
  * pins 1-25 on the component side (F.Cu), 26-50 on the solder side
    (B.Cu); pin N sits opposite pin 51-N
  * looking at the component side with the fingers DOWN, pin 1 is at the
    LEFT, which is the FRONT of the computer; pins 25/26 (+5V / GND) are at
    the rear, next to the back panel

Fingers are 1.52 mm wide (0.94 mm gaps) and run from 0.3 mm inside the
insertion edge up to the tab base; gen_pcb.py adds locked stubs from there
into the card body.  One solder-mask window per face across the finger field
(hard gold + 45 deg bevel at JLCPCB).

Local frame: y = 0 is the insertion edge, the card extends in -y; the
footprint goes on the bottom edge at rotation 0, pad 1 at -x.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import dump, Q

PITCH, N = 2.54, 25
LAND_W = 1.52
LAND_Y0, LAND_Y1 = 0.3, 7.62          # copper, distance in from the edge
TAB_W, TAB_D = 65.405, 7.62
F = lambda: ['effects', ['font', ['size', 1, 1], ['thickness', 0.15]]]


def pad_x(n):
    """Pad n (1..25) centre x: pin 1 at -x (front of the computer)."""
    return round(-(N - 1) * PITCH / 2 + (n - 1) * PITCH, 3)


fp = ['footprint', Q('Apple2_Slot_Edge_50'), ['version', 20241229], ['generator', Q('frob_gen')],
      ['generator_version', Q('1.0')], ['layer', Q('F.Cu')],
      ['descr', Q('Apple II peripheral slot card edge: 2 x 25 fingers 1.52 x 7.32 mm, 2.54 mm pitch; pins 1-25 '
                  'component side (F.Cu, pin 1 at -x = front), 26-50 solder side, pin N opposite 51-N.  '
                  'Hard gold, bevel.')],
      ['tags', Q('apple ii slot card edge connector')],
      ['property', Q('Reference'), Q('REF**'), ['at', 0, -(TAB_D + 1.5), 0], ['layer', Q('F.SilkS')], F()],
      ['property', Q('Value'), Q('Apple2_Slot_Edge_50'), ['at', 0, -(TAB_D + 3.5), 0], ['layer', Q('F.Fab')], F()],
      ['attr', 'smd', 'exclude_from_pos_files', 'exclude_from_bom'],
      ['fp_rect', ['start', -TAB_W / 2, 0], ['end', TAB_W / 2, -TAB_D],
       ['stroke', ['width', 0.1], ['type', 'solid']], ['fill', 'no'], ['layer', Q('F.Fab')]],
      ['fp_rect', ['start', -TAB_W / 2, 0], ['end', TAB_W / 2, -TAB_D],
       ['stroke', ['width', 0.05], ['type', 'solid']], ['fill', 'no'], ['layer', Q('F.CrtYd')]],
      ['fp_rect', ['start', -TAB_W / 2, 0], ['end', TAB_W / 2, -TAB_D],
       ['stroke', ['width', 0.05], ['type', 'solid']], ['fill', 'no'], ['layer', Q('B.CrtYd')]],
      ['fp_rect', ['start', pad_x(1) - 1.5, 0.2], ['end', pad_x(N) + 1.5, -TAB_D],
       ['stroke', ['width', 0], ['type', 'solid']], ['fill', 'yes'], ['layer', Q('F.Mask')]],
      ['fp_rect', ['start', pad_x(1) - 1.5, 0.2], ['end', pad_x(N) + 1.5, -TAB_D],
       ['stroke', ['width', 0], ['type', 'solid']], ['fill', 'yes'], ['layer', Q('B.Mask')]],
      ['fp_text', 'user', Q('1'), ['at', pad_x(1), -(TAB_D + 1.2), 0], ['layer', Q('F.SilkS')], F()],
      ['fp_text', 'user', Q('25'), ['at', pad_x(N), -(TAB_D + 1.2), 0], ['layer', Q('F.SilkS')], F()],
      ['fp_text', 'user', Q('50'), ['at', pad_x(1), -(TAB_D + 1.2), 0], ['layer', Q('B.SilkS')],
       ['effects', ['font', ['size', 1, 1], ['thickness', 0.15]], ['justify', 'mirror']]],
      ['fp_text', 'user', Q('26'), ['at', pad_x(N), -(TAB_D + 1.2), 0], ['layer', Q('B.SilkS')],
       ['effects', ['font', ['size', 1, 1], ['thickness', 0.15]], ['justify', 'mirror']]]]
yc = -(LAND_Y0 + LAND_Y1) / 2
for n in range(1, N + 1):
    x = pad_x(n)
    for num, layer in ((n, 'F'), (51 - n, 'B')):
        fp.append(['pad', Q(str(num)), 'smd', 'rect', ['at', x, round(yc, 3)], ['size', LAND_W, round(LAND_Y1 - LAND_Y0, 3)],
                   ['layers', Q(layer + '.Cu')]])
fp.append(['embedded_fonts', 'no'])
assert pad_x(1) < 0 < pad_x(N), 'pin 1 must be at -x (front of the computer)'
prj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
open(os.path.join(prj, 'Frob2354.pretty', 'Apple2_Slot_Edge_50.kicad_mod'), 'w').write(dump(fp) + '\n')
print('ok: pad 1 at x=%+.2f (F.Cu), pad 25 at x=%+.2f; fingers %g x %g mm, copper %g..%g mm from the edge'
      % (pad_x(1), pad_x(N), LAND_W, LAND_Y1 - LAND_Y0, LAND_Y0, LAND_Y1))
