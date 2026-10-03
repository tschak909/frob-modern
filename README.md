# frob-modern: Frob2354

A modern, register-compatible replacement for the **FROB** (Frobco, 1982),
the Apple II card for Atari 2600 development.  The original is 22 74LS
packages and two M58725P 2K x 8 SRAMs; parts that are hard to find today, and
whose modern substitutes make reconstructed boards erratic.  Frob2354 is one
**RP2354B** (RP2350B + 2 MB flash), four 74LVC245A bus buffers, two single
gates and a 3.3 V LDO on an Apple II slot card, with the original's **DIP-24
cable socket** so the existing FROB cable and 2600 cartridge adapter plug
straight in, and the original **register map**, so the existing FROB
software runs unchanged.

```
hardware/   KiCad 10 project (generated from tools/design.py) + JLCPCB outputs
firmware/   Pico SDK firmware: the FROB's RAM and registers, both buses
test/       host tests of the register semantics (the firmware's own code)
```

## Why an RP2354B and not an RP2040

The Apple bus and the 2600 bus run at the same time and are asynchronous to
each other (the 2600 executes from the FROB RAM while the Apple polls the
mailbox), so they cannot share pins.  Apple A0-A7, D0-D7, R/W, /IOSEL,
/DEVSEL, PHI0, /RES plus 2600 A0-A11, /CE, D0-D7 and the buffer controls is
46 GPIOs; the RP2040 has 30.  The RP2350B has 48, 5 V-tolerant pads on
GPIO0-39, the same SDK, and the RP2354B variant carries its flash in the
package.

## The card

* **Apple side:** A0-A7, R/W, /IOSEL, /DEVSEL, PHI0, /RES straight into the
  RP's 5 V-tolerant pads (GP8-20).  D0-D7 through a 74LVC245A whose DIR is
  R/W and whose /OE is `(/IOSEL & /DEVSEL) | A2_DOE` in hardware: the card
  cannot drive the Apple bus outside its own slot cycles.  INT and DMA
  daisy chains are passed through.
* **2600 side (J2, original FROB pin-out):** every cable signal goes through
  a 74LVC245A on the card's 3.3 V (Ioff, 5 V-tolerant), because the 2600 is
  powered separately; 100k pull-downs keep the address inputs defined with
  the cable unplugged.  The data buffer's /OE is `/CE | V_DOE` in hardware.
* **Power:** slot +5 V through a P-FET, USB VBUS through a Schottky, AP2112K
  to 3.3 V.  USB-C is for firmware updates (BOOTSEL) and bench power and can
  never back-feed the Apple.
* 6-layer, 1.6 mm, ENIG with hard-gold bevelled fingers.  All SMD on the top
  side; the DIP-24 socket is hand-soldered (JLCPCB stocks no 24-pin 0.6 in
  socket).

## Documentation

* `firmware/README.md`: register map, how each bus is served, timing
  budget, flashing, bring-up checklist.
* `hardware/README.md`: how the board files are generated and checked, the
  fab outputs, JLCPCB order settings.
* Original hardware, software and manuals: retroabandon/apple2-re `frob/`
  (https://gitlab.com/retroabandon/apple2-re/-/tree/main/frob); MAME's
  `a2frob` device emulates the original.

## Status

Rev0: schematic, 6-layer layout, JLCPCB outputs (`hardware/exports/jlcpcb/`)
and firmware generated and checked -- ERC 0, DRC 0 errors / 0 unconnected /
0 schematic-parity, netlist vs firmware pin map 159/159, host tests of the
register semantics 4144/4144, kicad-happy review triaged in
`hardware/docs/design-review-rev0.md`.
**No board has been built yet** -- see the bring-up checklist in
`firmware/README.md`.
