#!/usr/bin/env python3
"""Cross-check the Frob2354 schematic netlist against the firmware and the
original hardware -- independently of tools/design.py.

Exports a fresh netlist with kicad-cli and checks, by pin *function* (GPIOn
on the RP2354B, An/Bn/DIR/OE on the '245s, the slot pin names):
  * every #define in firmware/src/frob_pins.h reaches the signal it names:
    Apple slot pins through to the RP (data via the '245), 2600 cable socket
    pins through the 74LVC(H)245s to the RP, the buffer controls
  * the Apple II slot pin-out (Apple II Reference Manual 1979, p.106)
  * J2 against the original FROB card's J2 (reverse-engineered a2board
    netlist, retroabandon/apple2-re frob/kicad)
  * the two hardware guards: Apple '245 /OE = (/IOSEL & /DEVSEL) | DOE,
    2600 data '245 /OE = /CE | DOE; Apple '245 DIR = slot R/W
  * the edge footprint: pin 1 on F.Cu at -x (front of the computer)

Usage: python3 tools/check_nets.py         exit 1 on any failure
"""
import os, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
FW = os.path.join(os.path.dirname(PRJ), 'firmware', 'src', 'frob_pins.h')
SCH = os.path.join(PRJ, 'Frob2354.kicad_sch')

# Apple II Reference Manual (1979) p.106, slots 1-7
SLOT = {1: '/IOSEL', 2: 'A0', 3: 'A1', 4: 'A2', 5: 'A3', 6: 'A4', 7: 'A5', 8: 'A6', 9: 'A7',
        10: 'A8', 11: 'A9', 12: 'A10', 13: 'A11', 14: 'A12', 15: 'A13', 16: 'A14', 17: 'A15',
        18: 'R/W', 19: 'NC', 20: '/IOSTROBE', 21: 'RDY', 22: '/DMA', 23: 'INT OUT', 24: 'DMA OUT',
        25: '+5V', 26: 'GND', 27: 'DMA IN', 28: 'INT IN', 29: '/NMI', 30: '/IRQ', 31: '/RES',
        32: '/INH', 33: '-12V', 34: '-5V', 35: 'NC', 36: '7M', 37: 'Q3', 38: 'PHI1', 39: 'USER1',
        40: 'PHI0', 41: '/DEVSEL', 42: 'D7', 43: 'D6', 44: 'D5', 45: 'D4', 46: 'D3', 47: 'D2',
        48: 'D1', 49: 'D0', 50: '+12V'}
# what the card must leave alone (unconnected)
SLOT_OPEN = ('A8', 'A9', 'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'NC', '/IOSTROBE', 'RDY', '/DMA',
             '/NMI', '/IRQ', '/INH', '-12V', '-5V', '7M', 'Q3', 'PHI1', 'USER1', '+12V')
# original FROB a2board J2 (kicad-cli netlist of retroabandon/apple2-re frob/kicad/a2board.kicad_sch)
J2_ORIG = {8: 'VCSA0', 7: 'VCSA1', 6: 'VCSA2', 5: 'VCSA3', 4: 'VCSA4', 3: 'VCSA5', 2: 'VCSA6', 1: 'VCSA7',
           23: 'VCSA8', 22: 'VCSA9', 19: 'VCSA10', 21: 'VCSA11', 9: 'VCSD0', 10: 'VCSD1', 11: 'VCSD2',
           13: 'VCSD3', 14: 'VCSD4', 15: 'VCSD5', 16: 'VCSD6', 17: 'VCSD7', 18: '/VCSCE', 20: '/VCSOE',
           12: 'GND', 24: 'open'}

fails = 0
count = 0


def chk(desc, ok):
    global fails, count
    count += 1
    if not ok:
        fails += 1
        print('FAIL:', desc)


def define(name):
    txt = open(FW).read()
    m = re.search(r'#define\s+%s\s+(\d+)' % re.escape(name), txt)
    if not m:
        raise SystemExit('%s: no #define %s' % (FW, name))
    return int(m.group(1))


def main():
    fn = os.path.join(tempfile.gettempdir(), 'frob2354-check.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', fn, SCH],
                   check=True, capture_output=True)
    t = ET.parse(fn)
    pin_net, comp_val = {}, {}
    for c in t.iter('comp'):
        comp_val[c.get('ref')] = c.findtext('value')
    for n in t.iter('net'):
        name = n.get('name')
        for nd in n.iter('node'):
            pin_net[(nd.get('ref'), nd.get('pin'))] = name
    net_nodes = {}
    for (r, p), nm in pin_net.items():
        net_nodes.setdefault(nm, set()).add((r, p))

    def net(ref, pin):
        return pin_net.get((ref, str(pin)))

    def connected(a, b):
        na, nb = net(*a), net(*b)
        return na is not None and na == nb and not na.startswith('unconnected')

    def open_(ref, pin):
        n = net(ref, pin)
        return n is None or n.startswith('unconnected') or len(net_nodes.get(n, ())) == 1

    # --- find the parts by function, not by design.py's reference ---
    rp = [r for r, v in comp_val.items() if v == 'RP2354B']
    chk('exactly one RP2354B', len(rp) == 1)
    rp = rp[0]
    gpio_pin = {}
    for nd in t.iter('node'):
        if nd.get('ref') == rp:
            m = re.match(r'GPIO(\d+)', nd.get('pinfunction') or '')
            if m:
                gpio_pin[int(m.group(1))] = nd.get('pin')
    chk('48 GPIOs on the RP2354B', len(gpio_pin) == 48)
    edge = [r for r, v in comp_val.items() if v == 'Apple2_Slot_Edge_50'][0]
    sock = [r for r, v in comp_val.items() if v == 'FROB cable'][0]
    bufs = [r for r, v in comp_val.items() if v in ('74LVC245A', '74LVCH245A')]
    chk("four '245s", len(bufs) == 4)

    def gp(n):
        return (rp, gpio_pin[n])

    # '245 helpers: A(i) = pin 2+i, B(i) = pin 18-i, DIR = 1, /OE = 19
    def buf_path(b_node):
        """the '245 + channel whose B pin is on b_node's net -> (ref, i)"""
        for b in bufs:
            for i in range(8):
                if connected((b, 18 - i), b_node):
                    return b, i
        return None, None

    # --- Apple slot ---
    for p, f in SLOT.items():
        if f in SLOT_OPEN:
            chk('slot pin %d (%s) left open' % (p, f), open_(edge, p))
    chk('slot +5V (25) is not GND and feeds the P-FET', net(edge, 25) not in (None, 'GND'))
    chk('slot GND (26)', net(edge, 26) == 'GND')
    chk('INT IN -> INT OUT daisy chain passed through', connected((edge, 28), (edge, 23)))
    chk('DMA IN -> DMA OUT daisy chain passed through', connected((edge, 27), (edge, 24)))
    a2a = define('A2_ADDR_PIN')
    for i in range(8):
        chk('slot A%d (pin %d) -> GPIO%d' % (i, 2 + i, a2a + i), connected((edge, 2 + i), gp(a2a + i)))
    for name, pin in (('A2_RW_PIN', 18), ('A2_IOSEL_PIN', 1), ('A2_DEVSEL_PIN', 41), ('A2_PHI0_PIN', 40),
                      ('A2_RES_PIN', 31)):
        chk('slot %s (pin %d) -> GPIO%d' % (SLOT[pin], pin, define(name)), connected((edge, pin), gp(define(name))))
    a2d = define('A2_DATA_PIN')
    dbuf = None
    for i in range(8):
        b, ch = buf_path((edge, 49 - i))
        chk('slot D%d reaches a \'245 B pin' % i, b is not None)
        if b is None:
            continue
        dbuf = dbuf or b
        chk('slot D%d on the Apple data buffer' % i, b == dbuf)
        chk('Apple D%d buffer A side -> GPIO%d' % (i, a2d + i), connected((b, 2 + ch), gp(a2d + i)))
    chk("Apple '245 DIR = slot R/W (A side = RP: a 6502 read drives the slot)", connected((dbuf, 1), (edge, 18)))
    # select gate: the '245 /OE comes from a 74LVC1G0832 Y = (A & B) | C, A/B = the selects, C = DOE
    oe = net(dbuf, 19)
    g = [r for r, v in comp_val.items() if v == '74LVC1G0832']
    chk('one 74LVC1G0832', len(g) == 1)
    if g:
        g = g[0]
        chk("Apple '245 /OE = gate Y", net(g, 4) == oe)
        chk('gate A&B = /IOSEL, /DEVSEL', {net(g, 1), net(g, 3)} == {net(edge, 1), net(edge, 41)})
        chk('gate C = GPIO%d (A2_DOE)' % define('A2_DOE_PIN'), connected((g, 6), gp(define('A2_DOE_PIN'))))
    # --- 2600 cable socket: the original J2 pin-out ---
    for p, f in J2_ORIG.items():
        if f == 'open':
            chk('J2 pin %d (VCC) open' % p, open_(sock, p))
        elif f == 'GND':
            chk('J2 pin %d GND' % p, net(sock, p) == 'GND')
    vaddr = define('VCS_ADDR_PIN')
    for i in range(12):
        p = [k for k, v in J2_ORIG.items() if v == 'VCSA%d' % i][0]
        b, ch = buf_path((sock, p))
        chk('J2 pin %d (A%d) reaches a \'245' % (p, i), b is not None)
        if b:
            chk('2600 A%d -> GPIO%d' % (i, vaddr + i), connected((b, 2 + ch), gp(vaddr + i)))
            chk("2600 A%d buffer: DIR low (B -> A) and always enabled" % i,
                net(b, 1) == 'GND' and net(b, 19) == 'GND')
    for name, p in (('VCS_CE_PIN', 18), ('VCS_PRESENT_PIN', 20)):
        b, ch = buf_path((sock, p))
        chk('J2 pin %d reaches a \'245' % p, b is not None)
        if b:
            chk('J2 pin %d -> GPIO%d (%s)' % (p, define(name), name), connected((b, 2 + ch), gp(define(name))))
            chk('J2 pin %d buffer is input-only, always on' % p, net(b, 1) == 'GND' and net(b, 19) == 'GND')
    vdata = define('VCS_DATA_PIN')
    vbuf = None
    for i in range(8):
        p = [k for k, v in J2_ORIG.items() if v == 'VCSD%d' % i][0]
        b, ch = buf_path((sock, p))
        chk('J2 pin %d (D%d) reaches a \'245' % (p, i), b is not None)
        if b:
            vbuf = vbuf or b
            chk('2600 D%d on the 2600 data buffer' % i, b == vbuf)
            chk('2600 D%d -> GPIO%d' % (i, vdata + i), connected((b, 2 + ch), gp(vdata + i)))
    chk("2600 data '245 DIR = GPIO%d" % define('VCS_DIR_PIN'), connected((vbuf, 1), gp(define('VCS_DIR_PIN'))))
    g = [r for r, v in comp_val.items() if v == '74LVC1G32']
    chk('one 74LVC1G32', len(g) == 1)
    if g:
        g = g[0]
        chk("2600 data '245 /OE = OR gate Y", net(g, 4) == net(vbuf, 19))
        chk('OR inputs = J2 /CE (raw) and GPIO%d (VCS_DOE)' % define('VCS_DOE_PIN'),
            {net(g, 1), net(g, 2)} == {net(sock, 18), net(*gp(define('VCS_DOE_PIN')))})
    # pull-ups that make power-up and an unplugged cable safe
    for what, n in (('A2_DOE', net(*gp(define('A2_DOE_PIN')))), ('VCS_DOE', net(*gp(define('VCS_DOE_PIN')))),
                    ('J2 /CE', net(sock, 18)), ('J2 /OE', net(sock, 20))):
        pulled = any(comp_val[r] == '10k' and any(net(r, q) == '+3V3' for q in ('1', '2'))
                     for r, _ in net_nodes.get(n, ()))
        chk('%s has a 10k pull-up to +3V3' % what, pulled)
    # RP2350 datasheet, pin types: GPIO40-47 are ADC pads, not 5 V tolerant -- no slot or cable pin on them
    for g_ in range(40, 48):
        n = net(*gp(g_))
        chk('GPIO%d (not 5 V tolerant) touches no slot / cable pin' % g_,
            not any(r in (edge, sock) for r, _ in net_nodes.get(n, ())))
    for nm in ('LED_PIN', 'SPARE_PIN'):
        chk('%s GPIO%d is connected' % (nm, define(nm)), not open_(*gp(define(nm))))
    # --- edge footprint orientation ---
    fp = open(os.path.join(PRJ, 'Frob2354.pretty', 'Apple2_Slot_Edge_50.kicad_mod')).read()
    m1 = re.search(r'\(pad "1" smd rect\s*\(at ([-\d.]+) [-\d.]+\)\s*\(size [\d.]+ [\d.]+\)\s*\(layers "F\.Cu"\)', fp)
    m25 = re.search(r'\(pad "25" smd rect\s*\(at ([-\d.]+) [-\d.]+\)\s*\(size [\d.]+ [\d.]+\)\s*\(layers "F\.Cu"\)', fp)
    m50 = re.search(r'\(pad "50" smd rect\s*\(at ([-\d.]+) [-\d.]+\)\s*\(size [\d.]+ [\d.]+\)\s*\(layers "B\.Cu"\)', fp)
    chk('edge footprint: pad 1 on F.Cu at -x, pad 25 at +x, pad 50 behind pad 1 on B.Cu',
        bool(m1 and m25 and m50) and float(m1.group(1)) < 0 < float(m25.group(1))
        and m50 and abs(float(m50.group(1)) - float(m1.group(1))) < 1e-6)
    print('check_nets: %d checks, %d failed' % (count, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
