// Frob2354 GPIO map: the contract between the firmware and the board.
// hardware/tools/check_nets.py reads these #defines and checks them against
// the generated KiCad netlist; change both together.
#ifndef FROB_PINS_H
#define FROB_PINS_H

// ---- Apple II slot (PIO0 window: GPIO 0-31) ---------------------------------
#define A2_DATA_PIN      0   // GP0-7   D0-D7, through the 74LVC245A (A side)
#define A2_ADDR_PIN      8   // GP8-15  A0-A7, direct (5 V-tolerant pads)
#define A2_RW_PIN       16   // R/W (high = 6502 read); also the '245 DIR
#define A2_IOSEL_PIN    17   // /I/O SELECT  ($Cn00-$CnFF, PHI0-qualified)
#define A2_DEVSEL_PIN   18   // /DEVICE SELECT ($C0n0-$C0nF, PHI0-qualified)
#define A2_PHI0_PIN     19   // PHI0
#define A2_RES_PIN      20   // /RES
#define A2_DOE_PIN      21   // drive low: let the '245 drive during our selects (10k pull-up)
#define LED_PIN         22   // status LED, active high
#define SPARE_PIN       23   // test pad (timing probe)

// ---- Atari 2600 cable (PIO1 window with GPIOBASE 16: GPIO 16-47) ----------
#define VCS_DATA_PIN    24   // GP24-31 D0-D7, through the 74LVC245A (A side)
#define VCS_ADDR_PIN    32   // GP32-43 A0-A11, through 74LVCH245A
#define VCS_CE_PIN      44   // /CE = A12 inverted on the cable adapter (low = cartridge access)
#define VCS_DOE_PIN     45   // drive low: let the data '245 drive while /CE is low (10k pull-up)
#define VCS_DIR_PIN     46   // high: card drives the 2600; low: card reads the 2600 ($FFF0 write)
#define VCS_PRESENT_PIN 47   // the cable adapter's /OE (grounded there): low = cable connected

#define A2_DATA_MASK    (0xffu << A2_DATA_PIN)
#define A2_ADDR_MASK    (0xffu << A2_ADDR_PIN)
#define VCS_DATA_MASK   (0xffu << VCS_DATA_PIN)
// in sio_hw->gpio_hi_in (GPIO 32-47): A0-A11 in bits 0-11, /CE in bit 12
#define VCS_HI_ADDR_MASK 0x0fffu
#define VCS_HI_CE_BIT    (VCS_CE_PIN - 32)

#endif
