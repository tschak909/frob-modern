"""Component placement for gen_pcb.py: ref -> (x, y, rot).  Card body
x 117..202.88, y 25.4 (top edge) .. 95.25 (tab base); the fingers are on the
tab below, insertion edge y = 102.87.  Top view (component side), y down,
rotation CCW.  The rear of the Apple (back panel) is at +x.

Slot fingers (0.1 in, pin 1 at x 130.175):
  F.Cu  /IOSEL 130.2, A0-A7 132.7-150.5, R/W 173.4, INT/DMA OUT 186.1/188.6, +5V 191.1
  B.Cu  D0-D7 132.7-150.5, /DEVSEL 153.0, PHI0 155.6, /RES 178.4, INT/DMA IN 186.1/188.6, GND 191.1

Regions:
  centre        RP2354B at (150, 64) rot 90: Apple pins (GP4-20) face the fingers
                (south), GP0-3 + VREG/USB/QSPI west, 2600 address/controls
                (GP32-47) north, 2600 data + crystal + SWD/RUN east.  The core block
                (decoupling ring, VREG corner, crystal) is FujiNet-NES-Rev0's,
                which has the same package at the same rotation.
  south-west    Apple data '245 + select gate, by the D0-D7 fingers
  south-east    power entry by the +5V/GND fingers: P-FET, Schottky, LDO
  north-east    the FROB cable socket J2 (original card: top, toward the rear) and
                the three 2600 buffers between it and the RP
  north-west    USB-C on the top edge, ESD, CC; RESET/BOOTSEL buttons below it
"""


def do_placement(place):
    place('J1', 160.655, 102.87, 0)            # slot edge: tab centre, insertion edge

    # ---------------- RP2354B (FujiNet-NES-Rev0 core block) ----------------
    rx, ry = 150.0, 64.0
    place('U1', rx, ry, 90)
    RING = 10.0
    place('C1', rx - 2.2, ry + RING, 270)     # IOVDD 5   (pad 1 toward the chip)
    place('C2', rx + 1.8, ry + RING, 270)     # IOVDD 15
    place('C3', rx + RING, ry + 3.4, 0)       # IOVDD 24
    place('C4', rx + RING, ry + 1.7, 0)       # IOVDD 29
    place('R3', rx + RING, ry - 1.7, 0)       # RUN pull-up (pin 35)
    place('C21', rx + RING, ry - 3.4, 0)      # RUN power-on delay
    place('Y1', rx + RING + 4.0, ry - 0.0, 0)   # crystal: pad 1 XIN south-west, pad 3 XOUT_Y north-east
    place('C19', rx + RING + 4.0, ry + 3.6, 270)  # XIN load
    place('C20', rx + RING + 7.0, ry - 2.6, 90)   # XOUT_Y load
    place('R2', rx + RING + 4.0, ry - 2.6, 0)   # XOUT -> XOUT_Y
    place('C5', rx + 3.8, ry - RING, 90)      # IOVDD 41
    place('C6', rx + 0.2, ry - RING, 90)      # IOVDD 50
    place('C7', rx - 4.4, ry - RING, 90)      # IOVDD 60
    place('C11', rx - 2.4, ry - RING, 90)     # ADC_AVDD 59
    place('L1', rx - 7.6, ry - 3.0, 0)        # core inductor: pad 2 (LX) east toward pin 63
    place('C17', rx - 11.0, ry - 2.6, 180)    # core 4.7 uF
    place('C16', rx - 14.2, ry - 2.6, 180)    # DVDD 100 nF x3 in the DVDD lobe
    place('C14', rx - 8.6, ry - 4.8, 180)
    place('C15', rx - 11.8, ry - 4.8, 180)
    place('C13', rx - RING - 4.4, ry - 0.6, 180)  # VREG_VIN 4.7 uF
    place('R1', rx - 10.5, ry - 11.0, 0)      # 33R +3V3 -> VREG_AVDD
    place('C18', rx - 7.2, ry - 11.0, 0)      # VREG_AVDD 4.7 uF
    place('R8', rx - RING - 0.6, ry - 0.6, 0)     # USB_DM series (pin 66)
    place('R7', rx - RING - 0.6, ry + 1.1, 0)     # USB_DP series (pin 67)
    place('C10', rx - RING - 0.6, ry + 2.8, 180)  # USB_OTP_VDD (pin 68)
    place('C9', rx - RING - 0.6, ry + 4.5, 180)   # QSPI_IOVDD (pin 69)
    place('R4', rx - RING - 0.6, ry + 6.2, 180)   # QSPI_SS -> BOOTSEL button
    place('C8', rx - RING - 0.6, ry + 7.9, 180)   # IOVDD 76
    place('C12', rx - RING - 4.4, ry + 4.5, 180)  # 3.3V bulk 10 uF

    # ---------------- south-west: Apple data buffer + select gate ----------------
    place('U2', 127.0, 85.0, 270)             # '245: A side (RP) north, B side (slot D0-D7) south
    place('C22', 121.0, 85.0, 90)
    place('U3', 158.0, 77.0, 0)               # select gate: by /DEVSEL (153.0) and GP21; output west to U2
    place('C23', 158.0, 73.8, 0)
    place('R10', 161.5, 77.0, 90)             # A2_DOE_N pull-up

    # ---------------- south-east: power entry ----------------
    place('Q1', 191.5, 88.5, 0)               # P-FET at the +5V finger (x 191.1)
    place('C24', 196.5, 88.5, 90)             # SLOT_5V bypass
    place('R11', 196.5, 84.0, 90)             # P-FET gate pull-down
    place('D5', 191.0, 82.5, 0)               # SS34 VBUS -> +5V
    place('C26', 185.0, 89.5, 90)             # +5V bulk 22 uF
    place('U4', 184.0, 84.0, 0)               # LDO
    place('C27', 180.5, 89.5, 90)             # LDO in
    place('C28', 179.5, 84.0, 90)             # LDO out 10 uF
    place('C25', 196.5, 79.0, 90)             # VBUS 1 uF (at the P-FET end of the VBUS run)

    # ---------------- east: LED, test pads ----------------
    place('D4', 171.0, 72.0, 0)               # status LED (GP22)
    place('R9', 167.5, 72.0, 0)
    for i, tp in enumerate(('TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'TP6')):
        place(tp, 163.0 + 3.0 * i, 81.0, 0)

    # ---------------- north-east: FROB cable socket + 2600 buffers ----------------
    place('J2', 167.0, 47.5, 90)              # pins 1-12 along +x at y 47.5, 13-24 at y 32.26
    place('U5', 177.0, 56.0, 90)              # A0-A7: A side (RP) south, B side (cable) north
    place('U7', 191.0, 56.0, 90)              # D0-D7
    place('U6', 158.0, 40.0, 90)              # A8-A11, /CE, /OE (top row of J2): A side south, B side north
    place('RN1', 175.0, 62.0, 0)              # A0-A3 pull-downs
    place('RN2', 179.5, 62.0, 0)              # A4-A7
    place('RN3', 158.0, 31.0, 0)              # A8-A11
    place('RN4', 153.5, 31.0, 0)              # spares
    place('C29', 182.5, 56.0, 90)             # U5 decoupling
    place('C30', 153.0, 40.0, 90)             # U6 decoupling
    place('C31', 196.5, 56.0, 90)             # U7 decoupling
    place('U8', 192.0, 64.0, 0)               # /OE = /CE | V_DOE_N
    place('C32', 196.0, 64.0, 90)
    place('R12', 162.5, 45.5, 90)             # /CE pull-up
    place('R13', 160.5, 45.5, 90)             # /OE pull-up
    place('R14', 188.0, 64.0, 90)             # V_DOE_N pull-up

    # ---------------- north-west: USB-C, buttons ----------------
    place('J3', 128.0, 30.4, 180)             # receptacle opening at the top edge
    place('R5', 120.8, 32.0, 90)              # CC1 Rd
    place('R6', 135.2, 32.0, 90)              # CC2 Rd
    place('D1', 126.0, 38.0, 0)               # ESD D+
    place('D2', 130.0, 38.0, 0)               # ESD D-
    place('D3', 122.0, 38.0, 0)               # ESD VBUS
    place('SW1', 122.0, 47.0, 0)              # RESET
    place('SW2', 122.0, 55.0, 0)              # BOOTSEL
