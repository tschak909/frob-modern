"""Schematic layout for gen_sch.py: where every symbol goes on its sheet, which
nets are drawn as buses, where the hierarchical labels sit, and the root
block diagram.  Coordinates in mm on A3 (420 x 297), y down; symbol origins
on the 2.54 mm grid so every pin tip lands on the 1.27 mm routing grid.

Signal flow on every sheet is left to right: Apple slot -> data buffer ->
RP2354B -> 2600 buffers -> FROB cable socket; power entry -> LDO.

  place:  ref -> (x, y, rotation CCW[, 'y' to mirror left-right])
  buses:  members leaving one side of one symbol, drawn as stub + bus entry +
          bus line, and the bus routed to its hierarchical label
  hier:   single signals leaving the sheet: net -> (x, y, side of the sheet)
  wired_power: rails drawn as wires on this sheet (one power symbol names them)
  flags:  PWR_FLAG positions (net -> (x, y)), pin pointing down
"""

R1 = lambda i: i                    # readability helpers for row arithmetic
ROW = 2.54

# ---------------------------------------------------------------------------
# Apple slot sheet.  J1 is drawn by function: used pins on its right side, in
# the order A0-A7, D7-D0, /IOSEL /DEVSEL R/W PHI0 /RES, daisy chains, +5V GND.
J1X, J1Y = 45.72, 127.0             # right-side pin tips at x 62.23; J1 has 42 rows, centre row 20
J1ROW = lambda i: J1Y - 50.8 + ROW * i
U2X, U2Y = 101.6, J1ROW(9) + 12.7   # mirrored '245: B0 (=D7) row on J1's D7 row (index 9); U2 /OE row = U2Y + 12.7
APPLE = {
    'paper': 'A4',
    'place': {
        'J1': (J1X, J1Y, 0),
        'U2': (U2X, U2Y, 0, 'y'),
        'C22': (86.36, U2Y - 25.4, 0),
        # select gate, mirrored: output Y on U2's /OE row, inputs facing the sheet edge
        'U3': (147.32, U2Y + 12.7, 0, 'y'),
        'C23': (175.26, U2Y - 5.08, 0),
        'R10': (182.88, U2Y + 22.86, 0),
    },
    'buses': [
        {'name': 'A2_A', 'members': ['A2_A%d' % i for i in range(8)], 'hier': (264.16, J1ROW(0) - 2.54, 'right')},
        {'name': 'A2D_RP', 'members': ['A2D_RP%d' % (7 - i) for i in range(8)], 'vector': 'A2D_RP[0..7]',
         'hier': (264.16, J1ROW(9) - 10.16, 'right')},
    ],
    'hier': {                         # on J1's own rows: straight runs across the sheet
        'A2_IOSEL_N': (264.16, J1ROW(27), 'right'),
        'A2_DEVSEL_N': (264.16, J1ROW(28), 'right'),
        'A2_RW': (264.16, J1ROW(29), 'right'),
        'A2_PHI0': (264.16, J1ROW(30), 'right'),
        'A2_RES_N': (264.16, J1ROW(31), 'right'),
        'A2_DOE_N': (264.16, J1ROW(33), 'right'),
    },
    'trunk': ['J1', 'U2'],
    'route_first': ['A2_D%d' % i for i in range(8)] + ['A2_IOSEL_N', 'A2_DEVSEL_N', 'A2_RW', 'A2_PHI0', 'A2_RES_N',
                                                      'A2_INT_DAISY', 'A2_DMA_DAISY', 'A2_BUF_OE_N'],
    'notes': [(20.32, 20.32,
               'Apple II slot interface\n'
               'A0-A7, R/W, /IOSEL, /DEVSEL, PHI0, /RES go to the RP2354B directly (5 V-tolerant pads, GP8-20).\n'
               'D0-D7 pass through U2 (74LVC245A): DIR = R/W, so a 6502 read drives the slot.\n'
               'U2 /OE = (/IOSEL & /DEVSEL) | A2_DOE_N (U3): it can only drive during this slot\'s own cycles.\n'
               'INT / DMA daisy chains passed through; unused slot pins (A8-A15, IRQ, NMI, ...) left open.')],
}

# ---------------------------------------------------------------------------
# RP2354B sheet.  U1 drawn by function: left = Apple side (GP0-23) then crystal and
# RUN, right = 2600 side (GP24-47) then SWD and QSPI_SS, top = supplies, bottom =
# core regulator and USB.  Rows 2.54 mm; left/right tips at x U1X -/+ 33.02.
U1X, U1Y = 203.2, 147.32
U1L = lambda i: U1Y - 50.8 + ROW * i     # left / right pin row i
U1BOT = U1Y + 55.88                       # bottom pin tips (y)
U1B = lambda dx: U1X + dx                 # bottom pin x by offset
CAPY = 55.88
MCU = {
    'paper': 'A3',
    'place': {
        'U1': (U1X, U1Y, 0),
        # decoupling bank above the RP: IOVDD x8, QSPI, USB_OTP, ADC, bulk 10 uF, VREG_VIN
        **{'C%d' % (i + 1): (152.4 + 7.62 * i, CAPY, 0) for i in range(13)},
        # VREG_AVDD filter, next to its pin (top, x +7.62)
        'R1': (U1X + 7.62, 83.82, 0), 'C18': (U1X + 40.64, 83.82, 0),
        # LED and probe pad on GP22 / GP23
        'R9': (154.94, U1L(25), 270), 'D4': (132.08, U1L(25) + 5.08, 90),
        'TP4': (147.32, U1L(26) + 2.54, 180),
        # crystal (XIN row 30, XOUT row 31)
        'R2': (160.02, U1L(31), 270),
        'Y1': (147.32, U1L(31) + 10.16, 0),
        'C19': (132.08, U1L(31) + 17.78, 0), 'C20': (160.02, U1L(31) + 17.78, 0),
        # RUN (row 35): pull-up, power-on delay, RESET button
        'R3': (127.0, U1L(35) - 6.35, 0), 'C21': (119.38, U1L(35) + 6.35, 0),
        'SW1': (104.14, U1L(35), 0, 'y'),
        # SWD pads (right rows 33/34 of the right side = SWCLK/SWDIO), BOOTSEL (QSPI_SS)
        'TP1': (254.0, U1L(28) - 2.54, 0), 'TP2': (261.62, U1L(29) - 2.54, 0),
        'R4': (251.46, U1L(32), 90), 'SW2': (269.24, U1L(32), 0),
        # core regulator (bottom): VREG_LX -> L1 -> DVDD; DVDD caps
        'L1': (U1B(-2.54), U1BOT + 12.7, 180),
        'C14': (154.94, U1BOT + 22.86, 0), 'C15': (162.56, U1BOT + 22.86, 0),
        'C16': (170.18, U1BOT + 22.86, 0), 'C17': (177.8, U1BOT + 22.86, 0),
        # USB series resistors, then to the power sheet
        'R7': (U1B(12.7), U1BOT + 12.7, 180), 'R8': (U1B(20.32), U1BOT + 12.7, 180),
        # probe pads: PHI0 (Apple control row), /CE (2600 control row), GND
        'TP5': (116.84, U1L(17) - 2.54, 0), 'TP6': (279.4, U1L(22) - 2.54, 0),
        'TP3': (137.16, U1BOT + 22.86, 0),
    },
    'buses': [
        {'name': 'A2D_RP', 'members': ['A2D_RP%d' % i for i in range(8)], 'hier': (25.4, U1L(0) - 2.54, 'left')},
        {'name': 'A2_A', 'members': ['A2_A%d' % i for i in range(8)], 'hier': (25.4, U1L(9) - 2.54, 'left')},
        {'name': 'VD_RP', 'members': ['VD_RP%d' % i for i in range(8)], 'hier': (393.7, U1L(0) - 2.54, 'right')},
        {'name': 'VA_RP', 'members': ['VA_RP%d' % i for i in range(12)], 'hier': (393.7, U1L(9) - 2.54, 'right')},
    ],
    'hier': {
        'A2_RW': (25.4, U1L(18), 'left'), 'A2_IOSEL_N': (25.4, U1L(19), 'left'),
        'A2_DEVSEL_N': (25.4, U1L(20), 'left'), 'A2_PHI0': (25.4, U1L(21), 'left'),
        'A2_RES_N': (25.4, U1L(22), 'left'), 'A2_DOE_N': (25.4, U1L(23), 'left'),
        'VCE_RP_N': (393.7, U1L(22), 'right'), 'VOE_RP_N': (393.7, U1L(23), 'right'),
        'V_DOE_N': (393.7, U1L(24), 'right'), 'V_DIR': (393.7, U1L(25), 'right'),
        'USB_DP': (U1B(12.7), 256.54, 'bottom'), 'USB_DM': (U1B(20.32), 256.54, 'bottom'),
    },
    'flags': {'VREG_AVDD': (U1X + 22.86, 76.2), 'DVDD': (149.86, U1BOT + 12.7)},
    'trunk': ['U1'],
    'route_first': ['RP_LX', 'XIN', 'XOUT', 'XOUT_Y', 'VREG_AVDD', 'RUN', 'QSPI_SS', 'RP_USB_DP', 'RP_USB_DM'],
    'notes': [(25.4, 30.48,
               'RP2354B (RP2350B + 2 MB flash in package): the FROB RAM, control register and both mailboxes in firmware.\n'
               'Core 0 serves the Apple bus (left), core 1 the 2600 bus (right).  Pin map = firmware/src/frob_pins.h.\n'
               'GP40-47 (ADC pads) are NOT 5 V tolerant: they only see 3.3 V buffer outputs.\n'
               'BOOTSEL: hold SW2, press SW1 (RESET), copy the UF2.  SWD on TP1/TP2.')],
}

# ---------------------------------------------------------------------------
# 2600 cable sheet.  Three '245s 55.88 mm apart, A side (RP) left, B side right
# straight across to J2, whose pin groups are drawn 22 rows apart to match.
UX, U5Y = 127.0, 71.12              # B tips x 139.7; B0 row = U5Y - 12.7
UP = 60.96                          # buffer pitch (J2's pin groups are drawn 24 rows apart to match)
J2X = 233.68                        # J2 left tips at x 223.52
J2Y = U5Y - 12.7 + 73.66            # J2 row 0 (A7) on U5's B0 row (J2 has 59 rows: centre row 29)
VCS = {
    'paper': 'A3',
    'place': {
        'U5': (UX, U5Y, 0), 'U6': (UX, U5Y + UP, 0), 'U7': (UX, U5Y + 2 * UP, 0),
        'J2': (J2X, J2Y, 0),
        'RN1': (165.1, U5Y + 15.24, 180), 'RN2': (180.34, U5Y + 15.24, 180),
        'RN3': (172.72, U5Y + UP + 15.24, 180), 'RN4': (157.48, U5Y + UP + 15.24, 180),
        'R12': (195.58, U5Y + UP - 22.86, 0), 'R13': (203.2, U5Y + UP - 22.86, 0),
        'U8': (78.74, U5Y + 2 * UP + 25.4, 0), 'R14': (50.8, U5Y + 2 * UP + 15.24, 0),
        'C29': (152.4, U5Y - 25.4, 0), 'C30': (152.4, U5Y + UP - 25.4, 0),
        'C31': (152.4, U5Y + 2 * UP - 25.4, 0), 'C32': (99.06, U5Y + 2 * UP + 12.7, 0),
    },
    'buses': [
        {'name': 'VA_RP', 'members': ['VA_RP%d' % i for i in (7, 6, 5, 4, 3, 2, 1, 0, 10, 11, 9, 8)],
         'vector': 'VA_RP[0..11]', 'hier': (25.4, U5Y - 15.24, 'left')},
        {'name': 'VD_RP', 'members': ['VD_RP%d' % (7 - i) for i in range(8)], 'vector': 'VD_RP[0..7]',
         'hier': (25.4, U5Y + 2 * UP - 15.24, 'left')},
    ],
    'hier': {
        'VCE_RP_N': (25.4, U5Y + UP - 12.7, 'left'), 'VOE_RP_N': (25.4, U5Y + UP - 7.62, 'left'),
        'V_DIR': (25.4, U5Y + 2 * UP + 10.16, 'left'), 'V_DOE_N': (25.4, U5Y + 2 * UP + 27.94, 'left'),
    },
    'trunk': ['U5', 'U6', 'U7', 'J2'],
    'route_first': ['VCS_A%d' % i for i in range(12)] + ['VCS_D%d' % i for i in range(8)] + ['VCS_CE_N', 'VCS_OE_N'],
    'notes': [(25.4, 22.86,
               '2600 cable interface -- J2 is the original FROB card\'s DIP-24 socket (2732 pin-out; /CE = A12 inverted\n'
               'on the cable adapter, /OE grounded there, pin 24 open).  Every cable signal goes through a 74LVC245A on\n'
               'the card\'s 3.3 V (5 V-tolerant, Ioff: the 2600 has its own supply).  U7 /OE = /CE | V_DOE_N (U8).')],
}

# ---------------------------------------------------------------------------
# Power sheet: USB-C and the slot's +5 V OR-ed onto +5V, LDO to +3V3.
J3X, J3Y = 50.8, 127.0              # J3 right-side tips x 66.04: VBUS 111.76, CC1 116.84, CC2 119.38,
                                    # D- 124.46/127, D+ 129.54/132.08
RAIL = 76.2                         # the +5V / +3V3 power path row
POWER = {
    'paper': 'A3',
    'place': {
        'J3': (J3X, J3Y, 0),
        # USB data: ESD diodes hang off the D+/D- lines, CC pull-downs below
        'D1': (109.22, J3Y + 11.43, 270), 'D2': (127.0, J3Y + 11.43, 270),
        'R5': (83.82, J3Y + 20.32, 0), 'R6': (91.44, J3Y + 20.32, 0),
        # VBUS: ESD, bulk, gate pull-down, then up to Q1's gate and D5
        'D3': (101.6, J3Y - 11.43, 270), 'C25': (127.0, J3Y - 11.43, 0), 'R11': (134.62, J3Y - 11.43, 0),
        # power path along RAIL, left to right
        'C24': (119.38, RAIL + 7.62, 0),
        'Q1': (137.16, RAIL + 2.54, 90),
        'D5': (149.86, RAIL + 20.32, 180),
        'C26': (162.56, RAIL + 7.62, 0), 'C27': (172.72, RAIL + 7.62, 0),
        'U4': (195.58, RAIL + 2.54, 0),
        'C28': (215.9, RAIL + 7.62, 0),
    },
    'wired_power': ['VBUS', '+5V', 'SLOT_5V', '+3V3'],
    'hier': {
        'USB_DM': (198.12, J3Y - 2.54, 'right'), 'USB_DP': (198.12, J3Y + 2.54, 'right'),
    },
    'flags': {'SLOT_5V': (109.22, RAIL - 2.54), 'VBUS': (144.78, J3Y - 20.32), '+5V': (182.88, RAIL - 2.54),
              'GND': (60.96, J3Y + 33.02)},
    'route_first': ['SLOT_5V', '+5V', '+3V3', 'VBUS', 'USB_DP', 'USB_DM', 'CC1', 'CC2'],
    'notes': [(25.4, 30.48,
               'Power entry.  Slot +5V reaches +5V through Q1 (P-FET, gate = VBUS): fully on without USB, off with USB\n'
               'plugged in, so USB never back-feeds the Apple.  USB VBUS reaches +5V through D5 (Schottky).\n'
               'U4 (AP2112K, fast start) makes +3V3 for everything: the RP2354B pads are 5 V tolerant only while\n'
               'IOVDD is up, and the LDO tracks the slot rail as it rises.  USB-C is for firmware updates (BOOTSEL).')],
}

SHEETS = {'apple': APPLE, 'mcu': MCU, 'vcs': VCS, 'power': POWER}

# ---------------------------------------------------------------------------
# Root: the block diagram.  Sheet pins are listed top-to-bottom per side
# (None = gap); matching lists on facing sides give straight connections.
APPLE_MCU = ['A2_A[0..7]', 'A2D_RP[0..7]', None, 'A2_RW', 'A2_IOSEL_N', 'A2_DEVSEL_N', 'A2_PHI0',
             'A2_RES_N', 'A2_DOE_N']
MCU_VCS = ['VA_RP[0..11]', 'VD_RP[0..7]', None, 'VCE_RP_N', 'VOE_RP_N', 'V_DOE_N', 'V_DIR']
ROOT = {
    'sheets': {                     # x, y, w, h
        'apple': (45.72, 76.2, 63.5, 50.8),
        'mcu': (165.1, 76.2, 76.2, 76.2),
        'vcs': (297.18, 76.2, 63.5, 50.8),
        'power': (165.1, 190.5, 76.2, 30.48),
    },
    'pins': {
        'apple': {'right': APPLE_MCU},
        'mcu': {'left': APPLE_MCU, 'right': MCU_VCS, 'bottom': ['USB_DP', 'USB_DM']},
        'vcs': {'left': MCU_VCS},
        'power': {'top': ['USB_DP', 'USB_DM']},
    },
    'text': [
        (45.72, 25.4, 'Frob2354 -- the FROB Apple II card (Frobco, 1982) on one RP2354B', 3.0),
        (45.72, 33.02, 'Atari 2600 development: 4 KB of RAM the Apple loads through a paged window ($Cn00-$CnFF) and the 2600\n'
                       'runs as cartridge ROM, plus a one-byte mailbox each way.  Register-compatible with the original\n'
                       '(see firmware/README.md); J2 takes the original FROB cable and cartridge adapter.', 1.524),
        (45.72, 236.22, 'Apple $C0n0 write: D0-D3 page, D4 RAM to the 2600, D5 port on.  Read: D7 may write, D6 may read.\n'
                        'Apple $C0n1: mailbox.   2600 $FFF0 write / $FFF1 status / $FFF2 read (port on).', 1.524),
    ],
}
