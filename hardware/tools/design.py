"""Frob2354 -- single-MCU FROB card for the Apple II.  The single source of truth.

Every part, value, footprint, MPN, LCSC code and pin->net assignment lives
here.  gen_sch.py, gen_pcb.py, check_nets.py and export.py import it; the
KiCad files are generated output.

What it replaces: the FROB Apple II card (Frobco, 1982; reverse-engineered
schematic in retroabandon/apple2-re frob/kicad/a2board) -- 22 74LS packages
and two M58725P 2K x 8 SRAMs -- with one RP2354B that holds the 4 KB RAM, the
control register and the two mailbox registers in firmware
(../../firmware).  J2 keeps the original DIP-24 socket pin-out, so the
existing ribbon cable and 2600 cartridge adapter plug in unchanged.

Circuit provenance: the RP2354B core (supplies, core SMPS, crystal, USB,
BOOTSEL/RUN) is FujiNet-NES-Rev0's (fujinet-hardware), itself from the
Raspberry Pi RP2350 minimal design.

Signal paths:
  Apple A0-A7, R/W, /IOSEL, /DEVSEL, PHI0, /RES -> RP2354B directly.  The
    RP2350 pads are 5 V tolerant while IOVDD is powered, and the card's
    3.3 V comes from the slot's own +5 V through a fast LDO.
  Apple D0-D7 <-> 74LVC245A (U2), DIR = slot R/W (A side = RP, so a 6502
    read drives the slot), /OE = 74LVC1G0832: (/IOSEL & /DEVSEL) | A2_DOE_N.
    The buffer can only ever drive the Apple bus while this slot is
    selected, whatever the firmware does.
  2600 cable (J2) -> 74LVC245A x2 -> RP (100k pull-downs keep the inputs
    defined with the cable unplugged; bus-hold LVCH parts were rejected: their
    +/-500 uA overdrive is more than the 6507's NMOS outputs promise to
    source down the cable); data through a third 74LVC245A with DIR from
    the RP and /OE = 74LVC1G32: /CE | V_DOE_N.  The 2600 side has its own
    supply (the console's), so everything the cable touches is an Ioff,
    5 V-tolerant LVC input on the card's 3.3 V, never an RP pad.

RP2350 datasheet, pin types: GPIO0-39 are "Digital IO (FT)" (5.5 V
tolerant provided IOVDD is at 3.3 V); GPIO40-47 are ADC-capable pads and NOT
5 V tolerant -- on this board they only ever see 3.3 V buffer outputs and a
3.3 V pull-up.  The slot signals wired to the RP directly are all on GP8-20.
"""

LIB = 'Frob2354'
PROJECT = 'Frob2354'
NC = None  # explicit no-connect

SHEETS = [  # (file stem, title, page) -- the order of the block diagram, left to right
    ('apple', 'Apple II slot interface', 2),
    ('mcu', 'RP2354B: FROB RAM + registers', 3),
    ('vcs', '2600 cable (FROB J2) interface', 4),
    ('power', 'Power entry, 3.3 V, USB-C', 5),
]

# ---- RP2354B (QFN-80) GPIO -> package pin ---------------------------------
# From KiCad's MCU_RaspberryPi:RP2354B symbol (gen_sch.py re-checks every entry).
RP_GPIO_PIN = {0: 77, 1: 78, 2: 79, 3: 80, 4: 1, 5: 2, 6: 3, 7: 4, 8: 6, 9: 7, 10: 8, 11: 9,
               12: 11, 13: 12, 14: 13, 15: 14, 16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21,
               22: 22, 23: 23, 24: 25, 25: 26, 26: 27, 27: 28, 28: 36, 29: 37, 30: 38, 31: 39,
               32: 40, 33: 42, 34: 43, 35: 44, 36: 45, 37: 46, 38: 47, 39: 48, 40: 49, 41: 52,
               42: 53, 43: 54, 44: 55, 45: 56, 46: 57, 47: 58}
RP_IOVDD_PINS = [5, 15, 24, 29, 41, 50, 60, 76]
RP_DVDD_PINS = [10, 32, 51]
RP_RAIL = '+3V3'

# firmware/src/frob_pins.h: all 48 GPIOs (check_nets.py reads the header and
# compares it with the generated netlist).
RP_GPIO_NET = {i: 'A2D_RP%d' % i for i in range(8)}             # A2_DATA_PIN 0: '245 A side
RP_GPIO_NET.update({8 + i: 'A2_A%d' % i for i in range(8)})     # A2_ADDR_PIN 8: slot A0-A7
RP_GPIO_NET.update({16: 'A2_RW', 17: 'A2_IOSEL_N', 18: 'A2_DEVSEL_N', 19: 'A2_PHI0',
                    20: 'A2_RES_N', 21: 'A2_DOE_N', 22: 'LED', 23: 'GP23'})
RP_GPIO_NET.update({24 + i: 'VD_RP%d' % i for i in range(8)})   # VCS_DATA_PIN 24: '245 A side
RP_GPIO_NET.update({32 + i: 'VA_RP%d' % i for i in range(12)})  # VCS_ADDR_PIN 32: buffered A0-A11
RP_GPIO_NET.update({44: 'VCE_RP_N', 45: 'V_DOE_N', 46: 'V_DIR', 47: 'VOE_RP_N'})
assert len(RP_GPIO_NET) == 48 and set(RP_GPIO_NET) == set(RP_GPIO_PIN)

# ---- Apple II peripheral slot (Apple II Reference Manual 1979, p.106) ------
# Pins 1-25 on the component side (F.Cu), 26-50 on the solder side, pin N
# opposite pin 51-N; pin 1 toward the FRONT of the computer.  (net, name)
EDGE = {1: ('A2_IOSEL_N', '~{I/O SELECT}'), 18: ('A2_RW', 'R/~{W}'), 19: (NC, 'NC'),
        20: (NC, '~{I/O STROBE}'), 21: (NC, 'RDY'), 22: (NC, '~{DMA}'), 23: ('A2_INT_DAISY', 'INT OUT'),
        24: ('A2_DMA_DAISY', 'DMA OUT'), 25: ('SLOT_5V', '+5V'), 26: ('GND', 'GND'),
        27: ('A2_DMA_DAISY', 'DMA IN'), 28: ('A2_INT_DAISY', 'INT IN'), 29: (NC, '~{NMI}'),
        30: (NC, '~{IRQ}'), 31: ('A2_RES_N', '~{RES}'), 32: (NC, '~{INH}'), 33: (NC, '-12V'),
        34: (NC, '-5V'), 35: (NC, 'NC'), 36: (NC, '7M'), 37: (NC, 'Q3'), 38: (NC, 'PHI1'),
        39: (NC, 'USER 1'), 40: ('A2_PHI0', 'PHI0'), 41: ('A2_DEVSEL_N', '~{DEVICE SELECT}'),
        50: (NC, '+12V')}
EDGE.update({2 + i: ('A2_A%d' % i, 'A%d' % i) for i in range(8)})
EDGE.update({10 + i: (NC, 'A%d' % (8 + i)) for i in range(8)})
EDGE.update({49 - i: ('A2_D%d' % i, 'D%d' % i) for i in range(8)})
assert sorted(EDGE) == list(range(1, 51))

# ---- J2: the original FROB card's 24-pin cable socket (2732 EPROM pin-out),
# from the reverse-engineered a2board netlist.  /CE is the 2600's A12 through
# the cable adapter's inverter; /OE is tied to GND on the adapter; pin 24 (VCC)
# is left open as on the original: the two machines keep separate supplies.
VCS_A_PIN = {0: 8, 1: 7, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2, 7: 1, 8: 23, 9: 22, 10: 19, 11: 21}
VCS_D_PIN = {0: 9, 1: 10, 2: 11, 3: 13, 4: 14, 5: 15, 6: 16, 7: 17}
J2_PINS = {VCS_A_PIN[i]: 'VCS_A%d' % i for i in VCS_A_PIN}
J2_PINS.update({VCS_D_PIN[i]: 'VCS_D%d' % i for i in VCS_D_PIN})
J2_PINS.update({18: 'VCS_CE_N', 20: 'VCS_OE_N', 12: 'GND', 24: NC})
assert sorted(J2_PINS) == list(range(1, 25))

# ---- common parts -----------------------------------------------------------
FP = lambda n: '%s:%s' % (LIB, n)
R0603 = FP('R_0603_1608Metric')
C0603 = FP('C_0603_1608Metric')
C0805 = FP('C_0805_2012Metric')
TSSOP20 = FP('TSSOP-20_4.4x6.5mm_P0.65mm')
RPACK = {'4x100k': ('4D03WGJ0104T5E', 'C1996')}
RES = {'27R': ('0603WAF270JT5E', 'C25190'), '33R': ('0603WAF330JT5E', 'C23140'),
       '1k': ('0603WAF1001T5E', 'C21190'), '5.1k': ('0603WAF5101T5E', 'C23186'),
       '10k': ('0603WAF1002T5E', 'C25804'), '100k': ('0603WAF1003T5E', 'C25803')}
CAP = {'15pF': (C0603, 'CL10C150JB8NNNC', 'C1644'),
       '100nF': (C0603, 'CC0603KRX7R9BB104', 'C14663'),
       '1uF': (C0603, 'CL10A105KB8NNNC', 'C15849'),
       '4.7uF': (C0603, 'CL10A475KO8NNNC', 'C19666'),
       '10uF': (C0603, 'CL10A106KP8NNNC', 'C19702'),
       '22uF': (C0805, 'CL21A226MAQNNNE', 'C45783')}


class Part:
    def __init__(self, prefix, lib_id, value, footprint, pins, sheet,
                 mpn='', lcsc='', desc='', bom=True, dnp=False, jlc=True, ref=None):
        self.prefix, self.lib_id, self.value, self.footprint = prefix, lib_id, value, footprint
        self.pins = {str(k): v for k, v in pins.items()}  # pad number -> net (None = NC)
        self.sheet, self.mpn, self.lcsc, self.desc, self.bom, self.dnp = sheet, mpn, lcsc, desc, bom, dnp
        self.jlc = jlc     # False: in the BOM, but hand-soldered (not in the JLCPCB BOM/CPL)
        self.ref = ref     # explicit reference (J1 = edge, U1 = RP2354B); others numbered in order


PARTS = []
_sheet = None


def sheet(name):
    global _sheet
    _sheet = name


def add(*a, **k):
    p = Part(*a, sheet=_sheet, **k)
    PARTS.append(p)
    return p


def R(value, a, b, desc='', **k):
    mpn, lcsc = RES[value]
    return add('R', 'Device:R', value, R0603, {1: a, 2: b}, mpn=mpn, lcsc=lcsc, desc=desc, **k)


def C(value, a, b='GND', desc='', **k):
    fp, mpn, lcsc = CAP[value]
    return add('C', 'Device:C', value, fp, {1: a, 2: b}, mpn=mpn, lcsc=lcsc, desc=desc, **k)


def SW(value, net, desc):
    return add('SW', 'Switch:SW_Push', value, FP('SW_SPST_TL3342'), {1: net, 2: 'GND'},
               mpn='TL3342F160QG', lcsc='C2886898', desc=desc)


def TP(net, label):
    return add('TP', 'Connector:TestPoint', label, FP('TestPoint_Pad_D1.5mm'), {1: net},
               desc='test pad', bom=False)


def RN(value, nets, common, desc=''):
    """4-resistor array: nets[0..3] on pins 1-4, common on 5-8 (R_Pack04: Rn.1 = pin n, Rn.2 = pin 9-n)."""
    mpn, lcsc = RPACK[value]
    pins = {i + 1: n for i, n in enumerate(nets)}
    pins.update({8 - i: common for i in range(4)})
    return add('RN', 'Device:R_Pack04', value, FP('R_Array_Convex_4x0603'), pins, mpn=mpn, lcsc=lcsc, desc=desc)


def BUF245(dir_net, oe_net, a_nets, b_nets, desc, hold=False):
    """74LVC(H)245A, TSSOP-20.  a_nets/b_nets: 8 nets each for A0-A7 / B0-B7
    (pins 2-9 / 18-11).  DIR high = A -> B."""
    pins = {1: dir_net, 19: oe_net, 10: 'GND', 20: '+3V3'}
    pins.update({2 + i: n for i, n in enumerate(a_nets)})
    pins.update({18 - i: n for i, n in enumerate(b_nets)})
    if hold:
        return add('U', '74xx:74HC245', '74LVCH245A', TSSOP20, pins, mpn='SN74LVCH245APWR',
                   lcsc='C352976', desc=desc)
    return add('U', '74xx:74HC245', '74LVC245A', TSSOP20, pins, mpn='SN74LVC245APWR',
               lcsc='C7848', desc=desc)


# =========================================================================
sheet('mcu')
# -- RP2354B core (FujiNet-NES-Rev0 circuit).  One 3.3 V rail: the AP2112K is
# up within tens of us of the 5 V rail, so the pads are powered before the
# slot's 5 V bus levels can reach them.
rp = {30: 'XIN', 31: 'XOUT', 33: 'SWCLK', 34: 'SWDIO', 35: 'RUN',
      59: RP_RAIL,                                                          # ADC_AVDD
      61: 'VREG_AVDD', 62: 'GND', 63: 'RP_LX', 64: RP_RAIL, 65: 'DVDD',       # VREG: AVDD PGND LX VIN FB
      66: 'RP_USB_DM', 67: 'RP_USB_DP', 68: RP_RAIL, 69: RP_RAIL,             # USB, USB_OTP_VDD, QSPI_IOVDD
      70: NC, 71: NC, 72: NC, 73: NC, 74: NC,                                # QSPI (flash in package)
      75: 'QSPI_SS', 81: 'GND'}
rp.update({p: RP_RAIL for p in RP_IOVDD_PINS})
rp.update({p: 'DVDD' for p in RP_DVDD_PINS})
for g, pin in RP_GPIO_PIN.items():
    rp[pin] = RP_GPIO_NET[g]
add('U', '%s:RP2354B_FROB' % LIB, 'RP2354B', FP('QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm'), rp,
    mpn='RP2354B', lcsc='C39843328', ref='U1',
    desc='RP2350B + 2MB flash: FROB RAM, control/status and mailbox registers, both buses')
for _ in RP_IOVDD_PINS:
    C('100nF', RP_RAIL, desc='IOVDD decoupling')
C('100nF', RP_RAIL, desc='QSPI_IOVDD decoupling')
C('100nF', RP_RAIL, desc='USB_OTP_VDD decoupling')
C('100nF', RP_RAIL, desc='ADC_AVDD decoupling')
C('10uF', RP_RAIL, desc='3.3V bulk at the RP')
C('4.7uF', RP_RAIL, desc='VREG_VIN bulk')
for _ in RP_DVDD_PINS:
    C('100nF', 'DVDD', desc='DVDD decoupling')
C('4.7uF', 'DVDD', desc='core regulator output')
R('33R', RP_RAIL, 'VREG_AVDD', desc='VREG_AVDD filter')
C('4.7uF', 'VREG_AVDD', desc='VREG_AVDD filter')
add('L', 'Device:L', '3.3uH', FP('RPI_L_AOTA-B201610S3R3'), {1: 'DVDD', 2: 'RP_LX'},
    mpn='AOTA-B201610S3R3-101-T', lcsc='C42411119', desc='RP2350 core SMPS inductor')
add('Y', 'Device:Crystal_GND24', '12MHz', FP('Crystal_SMD_3225-4Pin_3.2x2.5mm'),
    {1: 'XIN', 2: 'GND', 3: 'XOUT_Y', 4: 'GND'}, mpn='ABM8-272-T3', lcsc='C20625731')
C('15pF', 'XIN', desc='crystal load')
C('15pF', 'XOUT_Y', desc='crystal load')
R('1k', 'XOUT', 'XOUT_Y', desc='crystal drive limit')
# RUN / BOOTSEL
R('10k', RP_RAIL, 'RUN', desc='RUN pull-up')
C('100nF', 'RUN', desc='RUN power-on delay')
SW('RESET', 'RUN', 'RP2354B reset (RUN)')
R('1k', 'QSPI_SS', 'BOOTSEL_BTN', desc='BOOTSEL button series')
SW('BOOTSEL', 'BOOTSEL_BTN', 'RP2354B BOOTSEL: hold while pressing RESET (or plugging USB) for the UF2 drive')
# USB-C: firmware updates (UF2 / picotool); also powers the card on the bench
add('J', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C', FP('USB_C_Receptacle_HRO_TYPE-C-31-M-12'),
    {'A1': 'GND', 'A4': 'VBUS', 'A5': 'CC1', 'A6': 'USB_DP', 'A7': 'USB_DM', 'A8': NC,
     'A9': 'VBUS', 'A12': 'GND', 'B1': 'GND', 'B4': 'VBUS', 'B5': 'CC2', 'B6': 'USB_DP',
     'B7': 'USB_DM', 'B8': NC, 'B9': 'VBUS', 'B12': 'GND', 'SH': 'GND'},
    mpn='TYPE-C-31-M-12', lcsc='C165948', desc='firmware update / bench power', ref='J3')
R('5.1k', 'CC1', 'GND', desc='UFP Rd')
R('5.1k', 'CC2', 'GND', desc='UFP Rd')
R('27R', 'USB_DP', 'RP_USB_DP', desc='USB series')
R('27R', 'USB_DM', 'RP_USB_DM', desc='USB series')
for n in ('USB_DP', 'USB_DM', 'VBUS'):
    add('D', 'Diode:ESD5Zxx', 'ESD5Z5.0T1G', FP('D_SOD-523'), {1: n, 2: 'GND'},
        mpn='ESD5Z5.0T1G', lcsc='C82044', desc='USB ESD')
# status LED
R('1k', 'LED', 'LED_A', desc='LED series')
add('D', 'Device:LED', 'green', FP('LED_0603_1608Metric'), {1: 'GND', 2: 'LED_A'},
    mpn='KT-0603G', lcsc='C12624', desc='status LED (GP22)')
TP('SWCLK', 'SWCLK')
TP('SWDIO', 'SWDIO')
TP('GND', 'GND')
TP('GP23', 'GP23')
TP('A2_PHI0', 'PHI0')
TP('VCE_RP_N', 'VCE')

# =========================================================================
sheet('apple')
add('J', '%s:Apple2_Slot_Edge_50' % LIB, 'Apple2_Slot_Edge_50', FP('Apple2_Slot_Edge_50'),
    {k: v[0] for k, v in EDGE.items()}, desc='Apple II peripheral slot edge, 50 pins, 0.1 in', bom=False,
    ref='J1')
# Data buffer: A side = RP GP0-7, B side = slot D0-D7.  DIR = R/W: a 6502 read
# (R/W high) drives A -> B onto the slot.  /OE from the select gate below.
# channel k carries bit 7-k: the order of the RP's GP7..GP0 pin row and of the D7..D0 fingers
BUF245('A2_RW', 'A2_BUF_OE_N', ['A2D_RP%d' % (7 - i) for i in range(8)], ['A2_D%d' % (7 - i) for i in range(8)],
       desc='Apple D0-D7 buffer: DIR = R/W, enabled only during this slot\'s /IOSEL or /DEVSEL')
C('100nF', '+3V3', desc='Apple data buffer decoupling')
# /OE = (/IOSEL & /DEVSEL) | A2_DOE_N: low only while a select is active AND the
# firmware asks for it.  Both selects are already PHI0-qualified by the Apple.
add('U', '74xGxx:74LVC1G0832', '74LVC1G0832', FP('SOT-23-6'),
    {1: 'A2_IOSEL_N', 3: 'A2_DEVSEL_N', 6: 'A2_DOE_N', 4: 'A2_BUF_OE_N', 2: 'GND', 5: '+3V3'},
    mpn='SN74LVC1G0832DBVR', lcsc='C206101', desc='Apple buffer /OE = (/IOSEL & /DEVSEL) | A2_DOE_N')
C('100nF', '+3V3', desc='select gate decoupling')
R('10k', '+3V3', 'A2_DOE_N', desc='Apple buffer off until the firmware runs')
# -- power entry: slot +5V through a P-FET (gate = VBUS: on without USB, off
# with it so USB never back-feeds the Apple), USB VBUS through a Schottky.
add('Q', 'Transistor_FET:AO3401A', 'AO3401A', FP('SOT-23'), {1: 'VBUS', 2: '+5V', 3: 'SLOT_5V'},
    mpn='AO3401A', lcsc='C15127', desc='slot 5V switch: G = VBUS, S = +5V, D = SLOT_5V')
R('100k', 'VBUS', 'GND', desc='holds the P-FET gate low without USB')
add('D', 'Diode:SS34', 'SS34', FP('D_SMA'), {1: '+5V', 2: 'VBUS'}, mpn='SS34', lcsc='C8678',
    desc='USB VBUS OR-ing (no back-feed into the Apple)')
C('100nF', 'SLOT_5V', desc='slot 5V HF bypass')
C('1uF', 'VBUS', desc='VBUS decoupling')
C('22uF', '+5V', desc='+5V bulk')
add('U', 'Regulator_Linear:AP2112K-3.3', 'AP2112K-3.3', FP('SOT-23-5'),
    {1: '+5V', 2: 'GND', 3: '+5V', 4: NC, 5: '+3V3'},
    mpn='AP2112K-3.3TRG1', lcsc='C51118', desc='3.3V LDO, 600mA, fast start: every 3.3V load')
C('1uF', '+5V', desc='LDO input')
C('10uF', '+3V3', desc='LDO output')

# =========================================================================
sheet('vcs')
add('J', '%s:FROB_VCS_Socket_24' % LIB, 'FROB cable', FP('DIP-24_W15.24mm_Socket'), J2_PINS,
    mpn='110-43-624-41-001000', desc='2600 cable socket, DIP-24 0.6 in (original FROB J2 pin-out); hand-solder',
    jlc=False)
# address: B side = cable (inputs), A side = RP; DIR low = B -> A, always enabled
# channels in the order of J2's A7..A0 row and the RP's GP39..GP32 row (layout: no crossings)
BUF245('GND', 'GND', ['VA_RP%d' % (7 - i) for i in range(8)], ['VCS_A%d' % (7 - i) for i in range(8)],
       desc='2600 A0-A7 in')
# channels in the order J2's top row reaches the buffer (CE A10 OE A11 A9 A8)
BUF245('GND', 'GND', ['VCE_RP_N', 'VA_RP10', 'VOE_RP_N', 'VA_RP11', 'VA_RP9', 'VA_RP8', NC, NC],
       ['VCS_CE_N', 'VCS_A10', 'VCS_OE_N', 'VCS_A11', 'VCS_A9', 'VCS_A8', 'VSPARE6', 'VSPARE7'],
       desc='2600 A8-A11, /CE (A12 inverted on the cable adapter), /OE (cable present) in; B6/B7 spare')
for k in range(3):
    RN('4x100k', ['VCS_A%d' % i for i in range(4 * k, 4 * k + 4)], 'GND',
       desc='2600 address pull-downs: defined inputs with the cable unplugged')
RN('4x100k', ['VSPARE6', 'VSPARE7', NC, NC], 'GND', desc="unused '245 inputs held low")
# data: A side = RP GP24-31, B side = cable; DIR high (V_DIR) = drive the 2600.
# channel k carries bit 7-k: VD7 is the top pin of the RP's east column
BUF245('V_DIR', 'VBUF_OE_N', ['VD_RP%d' % (7 - i) for i in range(8)], ['VCS_D%d' % (7 - i) for i in range(8)],
       desc='2600 D0-D7: DIR from the RP (low only for the $FFF0 write), enabled only while /CE is low')
add('U', '74xGxx:74LVC1G32', '74LVC1G32', FP('SOT-23-5'),
    {1: 'VCS_CE_N', 2: 'V_DOE_N', 4: 'VBUF_OE_N', 3: 'GND', 5: '+3V3'},
    mpn='SN74LVC1G32DBVR', lcsc='C10096', desc='2600 data buffer /OE = /CE | V_DOE_N')
for _ in range(3):
    C('100nF', '+3V3', desc='2600 buffer decoupling')
C('100nF', '+3V3', desc='2600 gate decoupling')
R('10k', '+3V3', 'VCS_CE_N', desc='no cable: /CE inactive')
R('10k', '+3V3', 'VCS_OE_N', desc='no cable: /OE reads high (the adapter grounds it)')
R('10k', '+3V3', 'V_DOE_N', desc='2600 buffer off until the firmware runs')

# PWR_FLAGs: nets whose drivers are passive pins (placed by sch_layout.py)
PWR_FLAG_NETS = ['GND', 'SLOT_5V', 'VBUS', '+5V', 'DVDD', 'VREG_AVDD']
FLAG_SHEET = 'power'

# Drawing: the power path (USB-C, P-FET / Schottky OR, LDO) gets its own sheet.
# Applied after the references are numbered, so the references (and the routed
# board) do not change.
SHEET_OF = {r: 'power' for r in ('J3', 'R5', 'R6', 'D1', 'D2', 'D3', 'Q1', 'R11', 'D5',
                                 'C24', 'C25', 'C26', 'C27', 'U4', 'C28')}

# ---- reference assignment (stable: declaration order) ---------------------
_taken = {p.ref for p in PARTS if p.ref}
_count = {}
for p in PARTS:
    if p.ref:
        continue
    while True:
        _count[p.prefix] = _count.get(p.prefix, 0) + 1
        p.ref = '%s%d' % (p.prefix, _count[p.prefix])
        if p.ref not in _taken:
            break

for p in PARTS:
    p.sheet = SHEET_OF.get(p.ref, p.sheet)

BY_REF = {p.ref: p for p in PARTS}


def nets():
    out = {}
    for p in PARTS:
        for pad, n in p.pins.items():
            if n:
                out.setdefault(n, []).append((p.ref, pad))
    return out


if __name__ == '__main__':
    for p in PARTS:
        print(p.sheet, p.ref, p.value, p.footprint.split(':')[1], p.lcsc, 'DNP' if p.dnp else '')
    ns = nets()
    print(len(PARTS), 'parts', len(ns), 'nets')
    for n, pp in sorted(ns.items()):
        if len(pp) < 2:
            print('SINGLE-PIN NET', n, pp)
