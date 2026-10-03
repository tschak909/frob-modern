#!/usr/bin/env python3
"""Generate the schematic from design.py + sch_layout.py: a wired, readable drawing.

* Root: a block diagram -- one sheet symbol per block (Apple slot, RP2354B,
  2600 cable, power/USB) with the buses and control lines between them drawn
  as buses / wires between sheet pins.
* Each sheet: symbols placed by hand (sch_layout.py), every connection drawn:
    - power rails as power symbols (GND, +3V3, +5V, VBUS, SLOT_5V, DVDD); on
      a sheet that lists a rail in `wired_power` it is drawn as wires instead,
      with one power symbol naming it
    - the parallel buses (A2_A, A2_D, A2D_RP, VA_RP, VD_RP, VCS_A, VCS_D) as
      KiCad buses with bus entries and member labels
    - signals that leave the sheet as hierarchical labels on the sheet edge
    - everything else as orthogonal wires (sch_route.Router), with a local
      net label on each named net; a net the router cannot draw falls back
      to labels and is reported
* design.py stays the netlist's single source of truth; compare_netlists.py
  checks that the drawing produces exactly the same connectivity.

Usage: python3 tools/gen_sch.py
"""
import os, sys, uuid, copy, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, dump, find, findall, Q
import design as D
import sch_layout as LAY
from sch_route import Router, OPP

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
DATE = '2026-10-02'
NS = uuid.UUID('3b0f6e2a-9c41-4b7a-8d2e-f40b2a2600a2')
G = 1.27                          # routing grid (mm)
PAPER = {'A3': (420.0, 297.0), 'A2': (594.0, 420.0), 'A4': (297.0, 210.0)}
POWER_SYMS = {'GND': 'power:GND', '+3V3': 'power:+3V3', '+5V': 'power:+5V', 'VBUS': 'power:VBUS',
              'SLOT_5V': 'Frob2354:SLOT_5V', 'DVDD': 'Frob2354:DVDD'}
POWER_DIR = {'GND': 'S'}          # direction the symbol's graphic points (default: up, 'N')


def uid(*k):
    return Q(str(uuid.uuid5(NS, '/'.join(map(str, k)))))


def font(size=1.27):
    return ['effects', ['font', ['size', size, size]]]


def hidden():
    return ['effects', ['font', ['size', 1.27, 1.27]], ['hide', 'yes']]


# ---------------------------------------------------------------------------
# project symbols
def box_symbol(name, ref, value, footprint, desc, left, right=(), bottom=(), top=(), w=15.24):
    """left/right/bottom/top: lists of entries, 2.54 pitch.  An entry is
    (number, name, etype), None (a gap), or a list of such tuples (stacked
    pins at one position: the first visible, the rest hidden)."""
    n = max(len(left), len(right), 1)
    h = (n + 1) * 2.54
    y0 = round(((n - 1) * 2.54 / 2) / 2.54) * 2.54
    top_y = y0 + 2.54
    bot_y = top_y - h
    half = w / 2
    body = ['symbol', Q(name + '_0_1'),
            ['rectangle', ['start', -half, top_y], ['end', half, bot_y],
             ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'background']]]]
    pins = ['symbol', Q(name + '_1_1')]

    def pin(entry, x, y, ang):
        if entry is None:
            return
        group = entry if isinstance(entry, list) else [entry]
        for i, (num, nm, et) in enumerate(group):
            # hidden stacked pins are passive: KiCad still treats a hidden power_in pin as a global net
            p = ['pin', et if not i else 'passive', 'line', ['at', x, y, ang], ['length', 2.54]]
            if i:
                p.append(['hide', 'yes'])
            p += [['name', Q(nm), font()], ['number', Q(str(num)), font()]]
            pins.append(p)
    for i, e in enumerate(left):
        pin(e, -half - 2.54, y0 - i * 2.54, 0)
    for i, e in enumerate(right):
        pin(e, half + 2.54, y0 - i * 2.54, 180)
    for i, e in enumerate(bottom):
        x = -((len(bottom) - 1) * 2.54) / 2 + i * 2.54
        pin(e, round(x / 1.27) * 1.27, bot_y - 2.54, 90)
    for i, e in enumerate(top):
        x = -((len(top) - 1) * 2.54) / 2 + i * 2.54
        pin(e, round(x / 1.27) * 1.27, top_y + 2.54, 270)
    return ['symbol', Q(name), ['pin_names', ['offset', 1.016]], ['exclude_from_sim', 'no'],
            ['in_bom', 'yes'], ['on_board', 'yes'],
            ['property', Q('Reference'), Q(ref), ['at', 0, top_y + 1.27, 0], font()],
            ['property', Q('Value'), Q(value), ['at', 0, bot_y - 5.08, 0], font()],
            ['property', Q('Footprint'), Q(footprint), ['at', 0, 0, 0], hidden()],
            ['property', Q('Datasheet'), Q(''), ['at', 0, 0, 0], hidden()],
            ['property', Q('Description'), Q(desc), ['at', 0, 0, 0], hidden()],
            body, pins]


def power_symbol(stock, name):
    """A project power symbol (global net `name`) drawn like a stock one."""
    s = copy.deepcopy(stock)
    old = str(s[1]).split(':')[-1]
    s[1] = Q(name)
    for e in s:
        if isinstance(e, list) and e and e[0] == 'property':
            if e[1] == 'Value':
                e[2] = Q(name)
            elif e[1] == 'Description':
                e[2] = Q('Power symbol creates a global label with name "%s"' % name)
        if isinstance(e, list) and e and e[0] == 'symbol':
            e[1] = Q(name + str(e[1])[len(old):])
    return s


def stock_pins(sym):
    """number -> (name, etype) for every pin of a symbol."""
    out = {}

    def walk(e):
        for x in e:
            if isinstance(x, list) and x:
                if x[0] == 'pin':
                    out[str(find(x, 'number')[1])] = (str(find(x, 'name')[1]), str(x[1]))
                elif x[0] == 'symbol':
                    walk(x)
    walk(sym)
    return out


def project_symbols(stock):
    E = D.EDGE
    ep = lambda p: (p, E[p][1], 'passive')
    used = [p for p in E if E[p][0]]
    # rows: A0-A7 0-7, D7-D0 9-16, controls 27-31 (below U2 on the apple sheet), daisy chains 33-36, +5V GND 40-41
    right = ([ep(2 + i) for i in range(8)] + [None] + [ep(42 + i) for i in range(8)] + [None] * 10 +
             [ep(1), ep(41), ep(18), ep(40), ep(31)] + [None] + [ep(28), ep(23), ep(27), ep(24)] +
             [None] * 3 + [ep(25), ep(26)])
    assert sorted(e[0] for e in right if e) == sorted(used)
    left = [ep(p) for p in sorted(E) if not E[p][0]]
    edge = box_symbol('Apple2_Slot_Edge_50', 'J', 'Apple2_Slot_Edge_50', D.FP('Apple2_Slot_Edge_50'),
                      'Apple II peripheral slot card edge, 50 pins, 0.1 in (pins 1-25 component side, '
                      '26-50 solder side); drawn by function: used pins right, unused (NC) left',
                      left=left, right=right, w=27.94)
    jn = {**{D.VCS_A_PIN[i]: 'A%d' % i for i in D.VCS_A_PIN}, **{D.VCS_D_PIN[i]: 'D%d' % i for i in D.VCS_D_PIN},
          18: '~{CE}', 20: '~{OE}', 12: 'GND', 24: 'VCC'}
    sp = lambda p: (p, jn[p], 'passive')
    # J2 sits right of the three '245s; its pins face them, in their channel order
    # groups 24 rows apart: the three '245s sit 60.96 mm apart on the vcs sheet, B0 rows aligned
    jl = ([sp(D.VCS_A_PIN[7 - i]) for i in range(8)] + [None] * 16 +
          [sp(18), sp(D.VCS_A_PIN[10]), sp(20), sp(D.VCS_A_PIN[11]), sp(D.VCS_A_PIN[9]), sp(D.VCS_A_PIN[8])] +
          [None] * 18 + [sp(D.VCS_D_PIN[7 - i]) for i in range(8)] + [None, sp(12), sp(24)])
    sock = box_symbol('FROB_VCS_Socket_24', 'J', 'FROB cable', D.FP('DIP-24_W15.24mm_Socket'),
                      'FROB 2600 cable socket, DIP-24 0.6 in, 2732 EPROM pin-out (original FROB card J2); '
                      'drawn by function', left=jl, w=15.24)
    # RP2354B by function: Apple pins left, 2600 pins right, supplies top, core/clock/USB bottom
    rp = stock_pins(stock['MCU_RaspberryPi:RP2354B'])
    P = lambda n: (n, rp[str(n)][0], rp[str(n)][1])
    g = lambda i: P(D.RP_GPIO_PIN[i])
    left = ([g(i) for i in range(8)] + [None] + [g(i) for i in range(8, 16)] + [None] +
            [g(i) for i in range(16, 22)] + [None] + [g(22), g(23)] + [None] * 3 + [P(30), P(31)] +
            [None] * 3 + [P(35)])
    right = ([g(i) for i in range(24, 32)] + [None] + [g(i) for i in range(32, 44)] + [None] +
             [g(i) for i in range(44, 48)] + [None] * 3 + [P(33), P(34)] + [None] * 2 + [P(75)] +
             [None] * 2 + [P(70), P(71), P(72), P(73), P(74)])
    top = [[P(p) for p in D.RP_IOVDD_PINS], P(69), P(68), P(59), P(64), None, P(61)]
    bottom = [[P(81), P(62)], None, [P(p) for p in D.RP_DVDD_PINS], P(65), None, P(63), None, None,
              None, None, None, P(67), P(66)]
    rpsym = box_symbol('RP2354B_FROB', 'U', 'RP2354B', D.FP('QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm'),
                       'RP2354B (RP2350B + 2 MB flash), pins drawn by function; numbers and names as '
                       'MCU_RaspberryPi:RP2354B', left=left, right=right, top=top, bottom=bottom, w=60.96)
    for pr in findall(rpsym, 'property'):        # keep the stock symbol's datasheet link
        if pr[1] == 'Datasheet':
            pr[2] = Q(next(str(q[2]) for q in findall(stock['MCU_RaspberryPi:RP2354B'], 'property') if q[1] == 'Datasheet'))
    drawn = stock_pins(rpsym)
    assert {k: v[0] for k, v in drawn.items()} == {k: v[0] for k, v in rp.items()}, \
        'RP2354B_FROB pin numbers / names differ from the stock symbol'
    pw = [power_symbol(stock['power:+5V'], 'SLOT_5V'), power_symbol(stock['power:+1V1'], 'DVDD')]
    lib = ['kicad_symbol_lib', ['version', 20241209], ['generator', Q('frob_gen')],
           ['generator_version', Q('1.0')], edge, sock, rpsym] + pw
    open(os.path.join(PRJ, D.LIB + '.kicad_sym'), 'w').write(dump(lib) + '\n')
    cache = {}
    for s_ in (edge, sock, rpsym, *pw):
        c = copy.deepcopy(s_)
        c[1] = Q(D.LIB + ':' + str(s_[1]))
        cache[c[1]] = c
    return cache


def load_symbols():
    t = parse(open(os.path.join(HERE, 'symcache.sexpr')).read())
    syms = {s[1]: s for s in t[1:]}
    syms.update(project_symbols(syms))
    return syms


# ---------------------------------------------------------------------------
# symbol geometry
def sym_pins(sym):
    """[(unit, number, x, y, angle)] in library coordinates (y up); body style 1 only."""
    out = []
    for sub in findall(sym, 'symbol'):
        unit, style = (int(v) for v in sub[1].rsplit('_', 2)[-2:])
        if style > 1:
            continue
        for p in findall(sub, 'pin'):
            at = find(p, 'at')
            out.append((unit, str(find(p, 'number')[1]), float(at[1]), float(at[2]), int(float(at[3]))))
    return out


def pin_names(sym):
    return {k: v[0] for k, v in stock_pins(sym).items()}


def sym_bbox(sym, unit, pins=True):
    xs, ys = [], []

    def walk(e):
        for x in e:
            if isinstance(x, list) and x:
                if x[0] in ('xy', 'start', 'end', 'center', 'mid') and len(x) >= 3:
                    xs.append(float(x[1])); ys.append(float(x[2]))
                elif x[0] == 'circle':
                    c, r = find(x, 'center'), find(x, 'radius')
                    xs.extend([float(c[1]) - float(r[1]), float(c[1]) + float(r[1])])
                    ys.extend([float(c[2]) - float(r[1]), float(c[2]) + float(r[1])])
                elif x[0] == 'pin':
                    if pins:
                        at = find(x, 'at')
                        xs.append(float(at[1])); ys.append(float(at[2]))
                elif x[0] not in ('property', 'text'):
                    walk(x)
    for sub in findall(sym, 'symbol'):
        u, style = (int(v) for v in sub[1].rsplit('_', 2)[-2:])
        if u in (0, unit) and style <= 1:
            walk(sub)
    if not xs:
        return (-1.27, -1.27, 1.27, 1.27)
    return (min(xs), min(ys), max(xs), max(ys))


def units_of(sym):
    us = sorted({u for u, *_ in sym_pins(sym) if u})
    return us or [1]


ESC = {0: 'W', 180: 'E', 90: 'S', 270: 'N'}      # library pin angle -> direction a wire leaves the tip
CCW = {'E': 'N', 'N': 'W', 'W': 'S', 'S': 'E'}


def xform(px, py, rot, mirror):
    """library (x, y up) -> sheet offset (x, y down) for a symbol at rotation rot (CCW), mirror 'y'."""
    x, y = px, -py
    if mirror == 'y':
        x = -x
    for _ in range((rot // 90) % 4):
        x, y = y, -x
    return x, y


def xdir(d, rot, mirror):
    if mirror == 'y' and d in 'EW':
        d = OPP[d]
    for _ in range((rot // 90) % 4):
        d = CCW[d]
    return d


def verify_pin_tables(syms):
    names = pin_names(syms['MCU_RaspberryPi:RP2354B'])
    for g, pin in D.RP_GPIO_PIN.items():
        nm = names.get(str(pin), '')
        if not re.match(r'GPIO%d(/|$)' % g, nm):
            raise SystemExit('RP_GPIO_PIN: GPIO%d -> pin %d, but the symbol calls that pin %r' % (g, pin, nm))
    for pin in D.RP_IOVDD_PINS:
        if names.get(str(pin)) != 'IOVDD':
            raise SystemExit('RP_IOVDD_PINS: pin %d is %r' % (pin, names.get(str(pin))))
    for pin in D.RP_DVDD_PINS:
        if names.get(str(pin)) != 'DVDD':
            raise SystemExit('RP_DVDD_PINS: pin %d is %r' % (pin, names.get(str(pin))))


# ---------------------------------------------------------------------------
def snap(v):
    return round(v / G)


def mm(c):
    return round(c * G, 4)


def label_w(text):
    """approximate width of a 1.27 mm label in grid cells"""
    t = re.sub(r'[~{}]', '', text)
    return int(len(t) * 1.0 / G) + 2


class Sheet:
    def __init__(self, stem, title, page, syms, root_uuid, flags):
        self.stem, self.title, self.page = stem, title, page
        self.syms = syms
        self.lay = LAY.SHEETS[stem]
        self.paper = self.lay.get('paper', 'A3')
        W, H = PAPER[self.paper]
        self.R = Router(int(W / G), int(H / G))
        self.items = []
        self.used = {}
        self.path = '/%s/%s' % (root_uuid, uid('sheet', stem))
        self.flags = flags
        self.pwr_n = 0
        self.fallbacks = []
        self.labelled = set()

    # ---- symbols ---------------------------------------------------------
    def place_part(self, p):
        x, y, rot, mir = (list(self.lay['place'][p.ref]) + [0, None])[:4]
        sym = self.syms[p.lib_id]
        self.used[p.lib_id] = sym
        u = units_of(sym)[0]
        # body (no pins) -> blocked cells; fields next to it
        bx0, by0, bx1, by1 = sym_bbox(sym, u, pins=False)
        corners = [xform(a, b, rot, mir) for a in (bx0, bx1) for b in (by0, by1)]
        X0, X1 = x + min(c[0] for c in corners), x + max(c[0] for c in corners)
        Y0, Y1 = y + min(c[1] for c in corners), y + max(c[1] for c in corners)
        # never let a part's drawing (e.g. an LED's light arrows) cover the way out of its own pins
        bx0, by0, bx1, by1 = snap(X0), snap(Y0), snap(X1), snap(Y1)
        for (uu, n_, px_, py_, a) in sym_pins(sym):
            if uu not in (0, u):
                continue
            ox_, oy_ = xform(px_, py_, rot, mir)
            tx, ty = snap(x + ox_), snap(y + oy_)
            e_ = xdir(ESC[a], rot, mir)
            if e_ == 'S' and by1 >= ty:
                by1 = ty - 1
            elif e_ == 'N' and by0 <= ty:
                by0 = ty + 1
            elif e_ == 'E' and bx1 >= tx:
                bx1 = tx - 1
            elif e_ == 'W' and bx0 <= tx:
                bx0 = tx + 1
        self.R.block_rect(bx0, by0, bx1, by1)
        small = len(p.pins) <= 3
        dirs = {xdir(ESC[a], rot, mir) for (uu, n_, px_, py_, a) in sym_pins(sym) if uu in (0, u)}
        if small and dirs <= {'N', 'S'}:          # pins top/bottom (R, C, L vertical): fields to the right
            fx, fy = X1 + 1.27, (Y0 + Y1) / 2
            fpos = [['at', round(fx, 2), round(fy - 1.27, 2), 0], ['at', round(fx, 2), round(fy + 1.27, 2), 0]]
            just = ['justify', 'left']
            tw = max(label_w(p.ref), label_w(p.value))
            self.R.block_rect(snap(fx), snap(fy - 2.54), snap(fx) + tw, snap(fy + 2.54))
        elif small:                               # small wide part: fields above, centred
            fx = (X0 + X1) / 2
            fpos = [['at', round(fx, 2), round(Y0 - 3.81, 2), 0], ['at', round(fx, 2), round(Y0 - 1.27, 2), 0]]
            just = None
            tw = max(label_w(p.ref), label_w(p.value))
            self.R.block_rect(snap(fx) - tw // 2, snap(Y0 - 5.08), snap(fx) + tw // 2, snap(Y0) - 1)
        else:
            # big part: fields above its top-left corner, unless pins leave upward there;
            # then to the right of the body, else to its left, else below
            tw = max(label_w(p.ref), label_w(p.value))
            ups = [x + xform(px_, py_, rot, mir)[0] for (uu, n_, px_, py_, a) in sym_pins(sym)
                   if uu in (0, u) and xdir(ESC[a], rot, mir) == 'N']
            downs = [x + xform(px_, py_, rot, mir)[0] for (uu, n_, px_, py_, a) in sym_pins(sym)
                     if uu in (0, u) and xdir(ESC[a], rot, mir) == 'S']
            if not any(X0 - 1.27 < ux < X0 + tw * G for ux in ups):
                fx, fy, just = X0, Y0 - 3.81, ['justify', 'left']
                self.R.block_rect(snap(fx), snap(Y0 - 5.08), snap(fx) + tw, snap(Y0) - 1)
            elif 'E' not in dirs:
                fx, fy, just = X1 + 1.27, (Y0 + Y1) / 2 - 1.27, ['justify', 'left']
                self.R.block_rect(snap(fx), snap(fy - 1.27), snap(fx) + tw, snap(fy + 3.81))
            elif 'W' not in dirs:
                fx, fy, just = X0 - 1.27, (Y0 + Y1) / 2 - 1.27, ['justify', 'right']
                self.R.block_rect(snap(fx) - tw, snap(fy - 1.27), snap(fx), snap(fy + 3.81))
            elif not any(X0 - 1.27 < dx_ < X0 + tw * G for dx_ in downs):
                fx, fy, just = X0, Y1 + 2.54, ['justify', 'left']
                self.R.block_rect(snap(fx), snap(Y1) + 1, snap(fx) + tw, snap(Y1 + 6.35))
            else:                                 # last resort: above the top-right corner
                fx, fy, just = X1, Y0 - 3.81, ['justify', 'right']
                self.R.block_rect(snap(fx) - tw, snap(Y0 - 5.08), snap(fx), snap(Y0) - 1)
            fpos = [['at', round(fx, 2), round(fy, 2), 0], ['at', round(fx, 2), round(fy + 2.54, 2), 0]]
        # field angles are relative to the symbol: counter-rotate so the text reads horizontally
        fang = (360 - rot) % 360 if rot % 180 else 0      # KiCad keeps 180-degree text readable itself
        for fp_ in fpos:
            fp_[3] = fang
        eff = ['effects', ['font', ['size', 1.27, 1.27]]] + ([just] if just else [])
        ds = ''
        for pr in findall(sym, 'property'):
            if pr[1] == 'Datasheet':
                ds = pr[2]
        at = ['at', x, y, rot]
        e = ['symbol', ['lib_id', Q(p.lib_id)], at]
        if mir:
            e.append(['mirror', mir])
        e += [['unit', u], ['exclude_from_sim', 'no'], ['in_bom', 'yes' if p.bom else 'no'],
              ['on_board', 'yes'], ['dnp', 'yes' if p.dnp else 'no'], ['uuid', uid(self.stem, p.ref, u)],
              ['property', Q('Reference'), Q(p.ref), fpos[0], eff],
              ['property', Q('Value'), Q(p.value), fpos[1], eff],
              ['property', Q('Footprint'), Q(p.footprint), ['at', x, y, 0], hidden()],
              ['property', Q('Datasheet'), Q(ds), ['at', x, y, 0], hidden()],
              ['property', Q('Description'), Q(p.desc), ['at', x, y, 0], hidden()]]
        for k, v in (('MPN', p.mpn), ('LCSC', p.lcsc)):
            if v:
                e.append(['property', Q(k), Q(v), ['at', x, y, 0], hidden()])
        terms = []
        seen = {}
        for (uu, num, px, py, ang) in sym_pins(sym):
            if uu not in (0, u):
                continue
            e.append(['pin', Q(num), ['uuid', uid(self.stem, p.ref, u, 'pin', num)]])
            ox, oy = xform(px, py, rot, mir)
            c = (snap(x + ox), snap(y + oy))
            d = xdir(ESC[ang], rot, mir)
            net = p.pins.get(num)
            if num not in p.pins:
                raise SystemExit('%s pin %s not assigned in design.py' % (p.ref, num))
            if c in seen:
                if seen[c] != net:
                    raise SystemExit('%s: stacked pins with different nets' % p.ref)
                continue
            seen[c] = net
            # the pin line from the tip into the body is an obstacle
            ln = 3
            for pr in findall(sym, 'symbol'):
                for pn in findall(pr, 'pin'):
                    if str(find(pn, 'number')[1]) == num:
                        ln = snap(float(find(pn, 'length')[1]))
            dx, dy = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}[OPP[d]]
            for k in range(1, ln + 1):
                self.R.block((c[0] + dx * k, c[1] + dy * k))
            terms.append((net, c, d, p.ref))
        e.append(['instances', ['project', Q(D.PROJECT), ['path', Q(self.path), ['reference', Q(p.ref)], ['unit', u]]]])
        self.items.append(e)
        return terms

    def power(self, net, c, d, length=2, end=None):
        """a power symbol for `net` at pin tip c (wire leaving in direction d): on a short stub, or
        on the tip itself.  Drawn upright (GND down, rails up) unless the pin points the opposite way.
        With `end` given, the symbol goes there (the caller drew the wire)."""
        natural = POWER_DIR.get(net, 'N')
        g = OPP[natural] if d == OPP[natural] else natural   # the way the symbol's drawing points
        rot = 180 if g != natural else 0
        DV = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}
        gx, gy = DV[g]

        tw_ = label_w(net)

        def clear(e):
            cells = [(e[0] + gx * k + s * (gy != 0), e[1] + gy * k + s * (gx != 0)) for k in range(1, 4) for s in (-1, 0, 1)]
            if gy:                                       # and where its value text goes
                cells += [(e[0] + s, e[1] + gy * k) for k in (4, 5) for s in range(-(tw_ // 2), tw_ // 2 + 1)]
            return all(q not in self.R.blocked and q not in self.R.occ for q in cells)
        if end is None:
            for L in (length, 3, 4, 1, 0) if length else (0,):
                if L == 0:
                    if clear(c):
                        end = c
                        break
                    continue
                dx, dy = DV[d]
                cells = [(c[0] + dx * k, c[1] + dy * k) for k in range(1, L + 1)]
                if all(self.R._free(net, q, d, set()) and not self.R.occ.get(q) for q in cells) and clear(cells[-1]):
                    end = self.R.stub(net, c, d, L)
                    break
            if end is None:
                return False
        lib = POWER_SYMS[net]
        self.used[lib] = self.syms[lib]
        self.pwr_n += 1
        ref = '#PWR%02d%02d' % (self.page, self.pwr_n)
        x, y = mm(end[0]), mm(end[1])
        for k in range(1, 4):
            for s_ in (-1, 0, 1):
                self.R.block((end[0] + gx * k + s_ * (gy != 0), end[1] + gy * k + s_ * (gx != 0)))
        tw = label_w(net)
        for k in range(4, 6):
            for s_ in range(-(tw // 2), tw // 2 + 1):
                self.R.block((end[0] + s_, end[1] + gy * k)) if gy else None
        vx, vy = x, y + gy * 4.2
        self.items.append(['symbol', ['lib_id', Q(lib)], ['at', x, y, rot], ['unit', 1],
                           ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                           ['uuid', uid(self.stem, 'pwr', self.pwr_n)],
                           ['property', Q('Reference'), Q(ref), ['at', x, y, 0], hidden()],
                           ['property', Q('Value'), Q(net), ['at', round(vx, 2), round(vy, 2), 0], font()],
                           ['property', Q('Footprint'), Q(''), ['at', x, y, 0], hidden()],
                           ['property', Q('Datasheet'), Q(''), ['at', x, y, 0], hidden()],
                           ['property', Q('Description'), Q(''), ['at', x, y, 0], hidden()],
                           ['pin', Q('1'), ['uuid', uid(self.stem, 'pwr', self.pwr_n, 'pin')]],
                           ['instances', ['project', Q(D.PROJECT), ['path', Q(self.path), ['reference', Q(ref)], ['unit', 1]]]]])
        return True

    def power_group(self, net, ts):
        """Several pins of one rail side by side on one side of a part: stub each, join the stub
        ends with one straight wire, and put a single power symbol on it."""
        DV = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}
        d = ts[0][1]
        dx, dy = DV[d]
        L = 2
        ends = [self.R.stub(net, c, d, L) for c, _ in ts]
        if any(e is None for e in ends):
            return False
        ends.sort()
        self.R.commit(net, [(x, ends[0][1]) for x in range(ends[0][0], ends[-1][0] + 1)] if dy else
                      [(ends[0][0], y) for y in range(ends[0][1], ends[-1][1] + 1)])
        for e in ends[1:-1]:
            self.R.junctions.append(e)
        mid = ends[len(ends) // 2] if len(ends) % 2 else ends[len(ends) // 2 - 1]
        tip = (mid[0] + dx, mid[1] + dy)
        end = self.R.stub(net, mid, d, 1)
        if end is None:
            return False
        self.R.junctions.append(mid)
        return self.power(net, end, d, end=end)

    def label(self, kind, text, c, d, shape='bidirectional'):
        """a label whose text runs in direction d from anchor cell c."""
        x, y = mm(c[0]), mm(c[1])
        ang, just = {'E': (0, 'left'), 'W': (180, 'right'), 'N': (90, 'left'), 'S': (270, 'right')}[d]
        e = [kind, Q(text)]
        if kind != 'label':
            e.append(['shape', shape])
        e += [['at', x, y, ang], ['fields_autoplaced', 'yes'],
              ['effects', ['font', ['size', 1.27, 1.27]], ['justify', just]],
              ['uuid', uid(self.stem, kind, text, c)]]
        self.items.append(e)
        n = label_w(text) + (2 if kind != 'label' else 0)
        ddx, ddy = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}[d]
        for k in range(1, n + 1):
            cc = (c[0] + ddx * k, c[1] + ddy * k)
            if kind != 'label' or cc not in self.R.occ:
                self.R.block(cc)
            if kind == 'label':             # keep the line above a wire label clear
                self.R.block((cc[0], cc[1] - 1) if ddx else (cc[0] - 1, cc[1]))

    # ---- buses -----------------------------------------------------------
    def bus_group(self, spec, terms_by_net):
        """members on one side of a symbol, all leaving the same way: stub + entry + bus line,
        then the bus routed to its hierarchical label (or to `join`, another bus line)."""
        name = spec['name']
        members = spec['members']
        tips = [(n, terms_by_net[n][0]) for n in members if n in terms_by_net]
        if not tips:
            return
        d = tips[0][1][1]
        assert all(t[1][1] == d for t in tips), name + ': members leave in different directions'
        sx = 1 if d == 'E' else -1
        stub = spec.get('stub', max(label_w(n) for n in members) + 2)
        if d == 'E':
            bx = max(t[1][0][0] for t in tips) + stub + 2
        else:
            bx = min(t[1][0][0] for t in tips) - stub - 2
        ys = []
        bnet = 'BUS:' + name
        for n, (c, _) in tips:
            ex = bx - 2 * sx                      # wire end / entry start
            self.R.claim_node(n, c)
            path = [(x, c[1]) for x in range(c[0], ex + sx, sx)]
            self.R.commit(n, path)
            self.label('label', n, (c[0] + sx, c[1]), d)
            # entry from (ex, y) to (bx, y-2): slants up toward the bus
            self.items.append(['bus_entry', ['at', mm(ex), mm(c[1])], ['size', mm(2 * sx), mm(-2)],
                               ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid(self.stem, 'be', n)]])
            self.R.block((ex + sx, c[1] - 1))
            ys.append(c[1])
            terms_by_net.pop(n)
        top, bot = min(ys) - 2, max(ys)
        bus_pts = [(bx, top), (bx, bot)]
        self.R.commit(bnet, [(bx, y) for y in range(top, bot + 1)])
        self.buses.append(bus_pts)
        vec = spec.get('vector') or '%s[%d..%d]' % (name, spec.get('lo', 0), spec.get('hi', len(members) - 1))
        self.label('label', vec, (bx, top + 1), 'N' if False else 'E') if False else None
        # bus to its hierarchical label
        if 'hier' in spec:
            hx, hy, side = spec['hier']
            hc = (snap(hx), snap(hy))
            hd = 'W' if side == 'right' else 'E'
            self.R.claim_node(bnet, hc)
            path = self.R.route_to_tree(bnet, hc, hd)
            if path is None:
                raise SystemExit('%s: no path for bus %s to its sheet edge' % (self.stem, name))
            self.R.commit(bnet, path)
            self.buses.append(None)
            self.label('hierarchical_label', vec, hc, 'E' if side == 'right' else 'W', 'bidirectional')
            self.labelled.add(bnet)
            # the bus label sits on the first straight run out of the bus line
        self.bus_names.append((bnet, vec))

    # ---- build -------------------------------------------------------------
    def build(self):
        parts = [p for p in D.PARTS if p.sheet == self.stem]
        self.buses, self.bus_names = [], []
        terms = []
        for p in parts:
            terms += self.place_part(p)
        # PWR_FLAGs (nets whose drivers are passive pins): a pseudo-part whose pin is a terminal
        for k, (net, (fx, fy)) in enumerate(sorted(self.lay.get('flags', {}).items())):
            lib = 'power:PWR_FLAG'
            self.used[lib] = self.syms[lib]
            ref = '#FLG%02d%02d' % (self.page, k + 1)
            self.items.append(['symbol', ['lib_id', Q(lib)], ['at', fx, fy, 0], ['unit', 1],
                               ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                               ['uuid', uid(self.stem, 'flag', net)],
                               ['property', Q('Reference'), Q(ref), ['at', fx, fy, 0], hidden()],
                               ['property', Q('Value'), Q('PWR_FLAG'), ['at', fx, round(fy - 3.81, 2), 0], font()],
                               ['property', Q('Footprint'), Q(''), ['at', fx, fy, 0], hidden()],
                               ['property', Q('Datasheet'), Q(''), ['at', fx, fy, 0], hidden()],
                               ['property', Q('Description'), Q(''), ['at', fx, fy, 0], hidden()],
                               ['pin', Q('1'), ['uuid', uid(self.stem, 'flag', net, 'pin')]],
                               ['instances', ['project', Q(D.PROJECT), ['path', Q(self.path), ['reference', Q(ref)], ['unit', 1]]]]])
            c = (snap(fx), snap(fy))
            self.R.block_rect(c[0] - 1, c[1] - 3, c[0] + 1, c[1] - 1)
            self.R.block_rect(c[0] - 4, c[1] - 5, c[0] + 4, c[1] - 4)
            terms.append((net, c, 'S', '#FLG'))
        by_net = {}
        self.ref_of = {}
        for net, c, d, ref in terms:
            if net is None:
                self.items.append(['no_connect', ['at', mm(c[0]), mm(c[1])], ['uuid', uid(self.stem, 'nc', c)]])
                continue
            by_net.setdefault(net, []).append((c, d))
            self.ref_of[c] = ref
        for net, ts in by_net.items():
            for c, d in ts:
                self.R.claim_node(net, c)
        wired = set(self.lay.get('wired_power', ()))
        # 1. power rails drawn as symbols; adjacent pins of one rail on one side of a part share one
        for net in list(by_net):
            if net in POWER_SYMS and net not in wired:
                ts = by_net.pop(net)
                runs, rest = self.adjacent_runs(ts)
                for run in runs:
                    if not self.power_group(net, run):
                        rest += run
                for c, d in rest:
                    if not self.power(net, c, d):
                        self.fallbacks.append((net, c))
                        self.label('label', net, c, d)
        # 2. buses
        for spec in self.lay.get('buses', ()):
            self.bus_group(spec, by_net)
        # 3. hierarchical labels of single signals: an extra terminal on the sheet edge
        hier = self.lay.get('hier', {})
        for net, (hx, hy, side) in hier.items():
            hc = (snap(hx), snap(hy))
            hd = 'W' if side == 'right' else ('E' if side == 'left' else ('N' if side == 'bottom' else 'S'))
            self.R.claim_node(net, hc)
            by_net.setdefault(net, []).append((hc, hd))     # after the pins: a pin seeds the route
            tdir = {'W': 'E', 'E': 'W', 'N': 'S', 'S': 'N'}[hd]
            self.label('hierarchical_label', net, hc, tdir, 'bidirectional')
            self.labelled.add(net)
        # 4. everything else: wires.  Phase 1: the trunk -- connections between the layout's trunk
        # parts (and to the sheet edge) -- in the layout's order; phase 2: every remaining tap.
        order = list(self.lay.get('route_first', ()))
        rest = sorted((n for n in by_net if n not in order), key=lambda n: -len(by_net[n]))
        trunk = set(self.lay.get('trunk', ())) | {'#HIER'}
        for c, d in [t for n in hier for t in by_net.get(n, ()) if t[0] == (snap(hier[n][0]), snap(hier[n][1]))]:
            self.ref_of[c] = '#HIER'
        for net in order + rest:
            ts = [t for t in by_net.get(net, ()) if self.ref_of.get(t[0]) in trunk]
            if len(ts) >= 2:
                self.R.route(net, ts)
        for net in order + rest:
            if net not in by_net:
                continue
            ts = by_net[net]
            if len(ts) < 2 and net not in wired:
                continue
            failed = self.R.route(net, ts)
            if failed:
                # fallback: a local label on every terminal left out, and one on the connected part
                done = [t for t in ts if t not in failed]
                for c, d in failed + done[:1]:
                    self.fallbacks.append((net, c))
                    if net in POWER_SYMS and self.power(net, c, d):
                        continue                 # a rail: its power symbol joins it globally
                    end = self.R.stub(net, c, d, 2) or self.R.stub(net, c, d, 1) or c
                    self.label('label', net, end, d)
            if net in wired:
                pass
        # 5. wired power rails get one power symbol each; signal nets one local label each
        for net in wired:
            if net in by_net and not self.name_rail(net, by_net[net]):
                self.fallbacks.append((net, 'unnamed'))
        self.name_nets(by_net, wired)
        return self

    def name_rail(self, net, ts):
        """one power symbol on a wired rail: on a stub from one of its pins, else on its wire"""
        for c, d in ts:
            if not any(c in (a, b) for (n, a, b) in self.R.segments if n == net) and self.power(net, c, d):
                return True
        for c, d in ts:
            if self.power(net, c, d, length=0):
                return True
        natural = POWER_DIR.get(net, 'N')
        for (n, a, b) in list(self.R.segments):
            if n != net or a[1] != b[1] or abs(a[0] - b[0]) < 4:
                continue
            for x in range(min(a[0], b[0]) + 2, max(a[0], b[0]) - 1):
                cell = (x, a[1])
                g = OPP[natural] if natural == 'S' else 'N'
                DV = {'N': (0, -1), 'S': (0, 1)}
                if all((x + s, a[1] + DV[g][1] * k) not in self.R.blocked and (x + s, a[1] + DV[g][1] * k) not in self.R.occ
                       for k in range(1, 5) for s in (-1, 0, 1)):
                    self.R._split(net, cell)
                    self.R.junctions.append(cell)
                    return self.power(net, cell, natural, end=cell)
        return False

    @staticmethod
    def adjacent_runs(ts):
        """split terminals into runs of >= 2 tips side by side (2 cells apart, same direction)"""
        runs, rest = [], []
        by_dir = {}
        for c, d in ts:
            key = (d, c[1] if d in 'NS' else c[0])
            by_dir.setdefault(key, []).append((c, d))
        for (d, line), group in by_dir.items():
            ax = 0 if d in 'NS' else 1
            group.sort(key=lambda t: t[0][ax])
            cur = [group[0]]
            for t in group[1:]:
                if t[0][ax] - cur[-1][0][ax] == 2:
                    cur.append(t)
                else:
                    (runs if len(cur) > 1 else rest).extend([cur] if len(cur) > 1 else cur)
                    cur = [t]
            (runs if len(cur) > 1 else rest).extend([cur] if len(cur) > 1 else cur)
        return runs, rest

    def name_nets(self, by_net, wired):
        segs = {}
        for net, a, b in self.R.segments:
            segs.setdefault(net, []).append((a, b))
        for net in by_net:
            if net in self.labelled or net in wired or net.startswith('BUS:'):
                continue
            best = None
            need = label_w(net) + 1
            for a, b in segs.get(net, []):
                if a[1] == b[1]:
                    L = abs(a[0] - b[0])
                    x0 = min(a[0], b[0])
                    ok = all((x, a[1] - 1) not in self.R.blocked and (x, a[1] - 1) not in self.R.occ
                             for x in range(x0 + 1, x0 + need))
                    if L >= need and ok and (best is None or L > best[0]):
                        best = (L, (x0 + 1, a[1]))
            if not best:                          # no horizontal run long enough: a vertical one, text upward
                for a, b in segs.get(net, []):
                    if a[0] == b[0]:
                        L = abs(a[1] - b[1])
                        y1 = max(a[1], b[1])
                        ok = all((a[0] - 1, y) not in self.R.blocked and (a[0] - 1, y) not in self.R.occ
                                 for y in range(y1 - need + 1, y1))
                        if L >= need and ok and (best is None or L > best[0]):
                            best = (L, (a[0], y1 - 1), 'N')
            if best:
                self.label('label', net, best[1], best[2] if len(best) > 2 else 'E')
            elif segs.get(net):
                a, b = segs[net][0]
                self.label('label', net, a, 'E' if b[0] >= a[0] else 'W')

    def write(self, root_uuid):
        R = self.R
        out = list(self.items)
        for net, a, b in R.segments:
            if net.startswith('BUS:'):
                out.append(['bus', ['pts', ['xy', mm(a[0]), mm(a[1])], ['xy', mm(b[0]), mm(b[1])]],
                            ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid(self.stem, 'bus', a, b)]])
            else:
                out.append(['wire', ['pts', ['xy', mm(a[0]), mm(a[1])], ['xy', mm(b[0]), mm(b[1])]],
                            ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid(self.stem, 'w', net, a, b)]])
        for c in sorted(set(R.junctions)):
            out.append(['junction', ['at', mm(c[0]), mm(c[1])], ['diameter', 0], ['color', 0, 0, 0, 0],
                        ['uuid', uid(self.stem, 'j', c)]])
        # bus vector labels on each bus line (top)
        for bnet, vec in self.bus_names:
            seg = [(a, b) for (n, a, b) in R.segments if n == bnet and a[0] == b[0]]
            if seg:
                a, b = max(seg, key=lambda s: abs(s[0][1] - s[1][1]))
                y = min(a[1], b[1])
                out.append(['label', Q(vec), ['at', mm(a[0]), mm(y), 90], ['fields_autoplaced', 'yes'],
                            ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'left', 'bottom']],
                            ['uuid', uid(self.stem, 'buslabel', vec)]])
        lib_symbols = ['lib_symbols'] + [self.used[k] for k in sorted(self.used)]
        tb = ['title_block', ['title', Q('Frob2354 - ' + self.title)], ['date', Q(DATE)],
              ['rev', Q('0')], ['company', Q('frob-modern')],
              ['comment', 1, Q('Generated by tools/gen_sch.py from tools/design.py + tools/sch_layout.py')],
              ['comment', 2, Q('Register-compatible replacement for the Frobco FROB Apple II card (1982)')]]
        for i, t in enumerate(self.lay.get('notes', ())):
            x, y, s = t
            out.append(['text', Q(s.replace('\n', '\\n')), ['exclude_from_sim', 'no'], ['at', x, y, 0],
                        ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'left', 'top']],
                        ['uuid', uid(self.stem, 'note', i)]])
        return ['kicad_sch', ['version', 20250114], ['generator', Q('eeschema')],
                ['generator_version', Q('9.0')], ['uuid', uid('sheet', self.stem)], ['paper', Q(self.paper)], tb,
                lib_symbols] + out + [['embedded_fonts', 'no']]


# ---------------------------------------------------------------------------
def root_sheet(root_uuid, sheets):
    """The block diagram: sheet symbols with pins, joined by buses and wires."""
    R = LAY.ROOT
    items = []
    W, H = PAPER['A3']
    rt = Router(int(W / G), int(H / G))
    pins_at = {}
    for stem, title, page in D.SHEETS:
        x, y, w, h = R['sheets'][stem]
        e = ['sheet', ['at', x, y], ['size', w, h], ['exclude_from_sim', 'no'], ['in_bom', 'yes'],
             ['on_board', 'yes'], ['dnp', 'no'], ['fields_autoplaced', 'yes'],
             ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 255, 255, 225, 1.0]],
             ['uuid', uid('sheet', stem)],
             ['property', Q('Sheetname'), Q(stem), ['at', x, round(y - 0.7, 2), 0],
              ['effects', ['font', ['size', 1.524, 1.524], ['bold', 'yes']], ['justify', 'left', 'bottom']]],
             ['property', Q('Sheetfile'), Q(stem + '.kicad_sch'), ['at', x, round(y + h + 0.6, 2), 0],
              ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'left', 'top']]]]
        items.append(['text', Q(title), ['exclude_from_sim', 'no'], ['at', round(x + 2.54, 2), round(y + h - 2.54, 2), 0],
                      ['effects', ['font', ['size', 1.524, 1.524], ['italic', 'yes']], ['justify', 'left', 'bottom']],
                      ['uuid', uid('sheettitle', stem)]])
        rt.block_rect(snap(x), snap(y), snap(x + w), snap(y + h))
        for side, names in R['pins'][stem].items():
            for i, name in enumerate(names):
                if name is None:
                    continue
                if side in ('left', 'right'):
                    px = x if side == 'left' else x + w
                    py = y + 5.08 + i * 2.54
                    ang = 180 if side == 'left' else 0
                    d = 'W' if side == 'left' else 'E'
                else:
                    px = x + 7.62 + i * 2.54
                    py = y if side == 'top' else y + h
                    ang = 90 if side == 'top' else 270
                    d = 'N' if side == 'top' else 'S'
                e.append(['pin', Q(name), 'bidirectional', ['at', round(px, 2), round(py, 2), ang],
                          ['uuid', uid('sheetpin', stem, name)],
                          ['effects', ['font', ['size', 1.27, 1.27]],
                           ['justify', 'left' if side in ('right', 'top') else 'right']]])
                c = (snap(px), snap(py))
                pins_at.setdefault(name, []).append((c, d))
        e.append(['instances', ['project', Q(D.PROJECT), ['path', Q('/' + root_uuid), ['page', Q(str(page))]]]])
        items.append(e)
    for name, ts in pins_at.items():
        net = ('BUS:' if '[' in name else '') + name
        for c, d in ts:
            rt.claim_node(net, c)
        failed = rt.route(net, ts)
        if failed:
            raise SystemExit('root: cannot connect %s' % name)
    for net, a, b in rt.segments:
        kind = 'bus' if net.startswith('BUS:') else 'wire'
        items.append([kind, ['pts', ['xy', mm(a[0]), mm(a[1])], ['xy', mm(b[0]), mm(b[1])]],
                      ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid('root', kind, net, a, b)]])
    for x, y, s, size in R.get('text', ()):
        items.append(['text', Q(s.replace('\n', '\\n')), ['exclude_from_sim', 'no'], ['at', x, y, 0],
                      ['effects', ['font', ['size', size, size]], ['justify', 'left', 'top']],
                      ['uuid', uid('roottext', s[:20])]])
    return ['kicad_sch', ['version', 20250114], ['generator', Q('eeschema')],
            ['generator_version', Q('9.0')], ['uuid', Q(root_uuid)], ['paper', Q('A3')],
            ['title_block', ['title', Q('Frob2354')], ['date', Q(DATE)], ['rev', Q('0')],
             ['company', Q('frob-modern')], ['comment', 1, Q('Generated by tools/gen_sch.py')]],
            ['lib_symbols']] + items + [['sheet_instances', ['path', Q('/'), ['page', Q('1')]]],
                                        ['embedded_fonts', 'no']]


def write_project(root_uuid, sheet_uuids):
    fn = os.path.join(PRJ, D.PROJECT + '.kicad_pro')
    pro = json.load(open(fn))
    pro['meta']['filename'] = D.PROJECT + '.kicad_pro'
    pro['sheets'] = [[root_uuid, 'Root']] + [[sheet_uuids[s[0]], s[0]] for s in D.SHEETS]
    json.dump(pro, open(fn, 'w'), indent=2)
    open(fn, 'a').write('\n')


def main():
    syms = load_symbols()
    verify_pin_tables(syms)
    root_uuid = str(uid('root'))
    sheet_uuids = {s[0]: str(uid('sheet', s[0])) for s in D.SHEETS}
    report = []
    for stem, title, page in D.SHEETS:
        sh = Sheet(stem, title, page, syms, root_uuid, D.PWR_FLAG_NETS if stem == D.FLAG_SHEET else ()).build()
        open(os.path.join(PRJ, stem + '.kicad_sch'), 'w').write(dump(sh.write(root_uuid)) + '\n')
        report.append('%s: %d wires, %d junctions, %d label fallbacks %s' % (
            stem, sum(1 for s in sh.R.segments if not s[0].startswith('BUS:')), len(set(sh.R.junctions)),
            len(sh.fallbacks), sorted({n for n, _ in sh.fallbacks})))
    open(os.path.join(PRJ, D.PROJECT + '.kicad_sch'), 'w').write(dump(root_sheet(root_uuid, D.SHEETS)) + '\n')
    write_project(root_uuid, sheet_uuids)
    print('\n'.join(report))
    print('schematic written')


if __name__ == '__main__':
    main()
