# Frob2354 firmware

Runs on the RP2354B of the Frob2354 card and *is* the FROB: the 4 KB RAM,
the control register and the two mailbox registers of the Frobco card, at
the original addresses, with the original semantics.  The existing FROB
software (PMOVE, FLOAD/FSAVE, AMON/FMON, VCS Explorer) runs unchanged.

| file | what |
|---|---|
| `src/frob_pins.h` | GPIO map: the contract with the board (`hardware/tools/check_nets.py` checks the netlist against it) |
| `src/frob_logic.h` | register semantics, pure C, shared with the host tests (`../test`) |
| `src/apple_bus.c` | core 0: the Apple II slot |
| `src/vcs_bus.c` | core 1: the 2600 cartridge port through the FROB cable |
| `src/main.c` | clocks, pins, start both cores |
| `boards/frob2354.h` | Pico SDK board definition (RP2354B: RP2350B die, 2 MB flash in package) |

## Build

Pico SDK 2.x (tested with 2.3.0) and `arm-none-eabi-gcc`:

```sh
cmake -S . -B build -DPICO_SDK_PATH=/usr/share/pico-sdk
cmake --build build -j
```

`build/frob2354.uf2` is the image.  The binary is `copy_to_ram`: both bus
loops run from SRAM with interrupts off and never touch flash (check with
`arm-none-eabi-objdump -d build/frob2354.elf`: `apple_bus_loop` and
`vcs_bus_loop` sit at 0x2000xxxx and call nothing but `frob_ctrl_changed`,
also in SRAM).

`-DFROB_SYS_KHZ=200000` builds for 200 MHz (core voltage raised to 1.15 V);
the default is the RP2350's nominal 150 MHz.

## Flashing

* **USB-C (J3):** hold **BOOTSEL** (SW2), press **RESET** (SW1), release
  BOOTSEL: the card appears as the `RP2350` drive; copy `frob2354.uf2` to it.
  Or `picotool load -x build/frob2354.uf2` from BOOTSEL mode.  The card can
  sit in the Apple (powered or not) while it is plugged into USB: USB VBUS
  never reaches the Apple's +5 V (P-FET + Schottky OR on the card).
* **SWD:** test pads TP1 (SWCLK), TP2 (SWDIO), TP3 (GND).

## Register map (unchanged from the FROB)

n = slot + 8.  Only A0 is decoded, so $C0n0-$C0nF mirror the pair.

| Apple | read | write |
|---|---|---|
| $C0n0 | D7 = may write (2600 mailbox empty), D6 = may read (Apple mailbox full); D5-D0 = 0 | D3-D0 page, D4 = RAM to the 2600, D5 = bidirectional port on; D7-D6 ignored |
| $C0n1 | Apple mailbox (clears "Apple full") | 2600 mailbox (sets "2600 full") |
| $Cn00-$CnFF | RAM page (Apple owns the RAM), else not driven | RAM page (Apple owns the RAM) |

| 2600 (A12 high) | |
|---|---|
| $F000-$FFFF | the FROB RAM as cartridge ROM while the 2600 owns it; not driven otherwise |
| $FFF0 | write: Apple mailbox (sets "Apple full") -- port on only |
| $FFF1 | read: D7 = may write (Apple mailbox empty), D6 = may read (2600 mailbox full) -- port on only |
| $FFF2 | read: 2600 mailbox (clears "2600 full") -- port on only |

"Port on" needs both D4 and D5, as on the original (U10A).  MAME's
`a2frob.cpp` maps $FFF0-$FFF2 regardless; the hardware does not, and this
firmware follows the hardware.

Power-on state: control register 0 (Apple owns the RAM, page 0, port off),
both mailboxes empty, RAM zeroed.  The original powered up with random
'174/'74 and SRAM contents; zero is what MAME does and can never look like
a slot boot ROM.  Apple /RES does not reset anything, as on the original.

## How the buses are served

**Apple (core 0).**  /IOSEL and /DEVSEL are PHI0-qualified by the Apple, so
the loop spins until one of them falls, takes A7-A0 and R/W in one read of
`gpio_in`, and:

* *read*: puts the byte on GP0-7, makes them outputs, pulls A2_DOE low;
  waits for the select to rise; releases A2_DOE; applies the read's side
  effect (clear "Apple full" for $C0n1).
* *write*: makes GP0-7 inputs, pulls A2_DOE low (the '245's DIR is R/W, so it
  now drives Apple -> RP), keeps sampling until the select rises and uses
  the last sample taken with the select still low -- the original latched on
  the strobe's trailing edge.

The data '245's /OE is `(/IOSEL & /DEVSEL) | A2_DOE` in hardware
(74LVC1G0832): nothing this code does can drive the Apple bus outside this
slot's own cycles.

**2600 (core 1).**  The cart port has no clock and no R/W.  The loop waits
for two equal consecutive address samples, then drives RAM[A11..A0] (or the
port register) on GP24-31.  V_DOE stays low while the 2600 owns the RAM;
the data '245's /OE is `/CE | V_DOE` in hardware, so it opens and closes
with A12.  $FFF0 turns the buffer round (DIR low) and samples the 2600's data
until the address moves, keeping the next-to-last sample (PlusCart's rule:
the last one may belong to the next cycle).  Port side effects (mailbox
flags) only happen if the address was stable for `STABLE_LOOPS` samples
(~100 ns), which filters address-transition glitches; the 6507 holds a real
address for ~800 ns.

## Timing budget

| path | budget | spent (estimate, 150 MHz) |
|---|---|---|
| Apple read: select low -> data on the slot | ~350 ns (PHI0 high ~490 ns, 6502 setup ~100 ns) | spin 2-3 loads + lookup + 3 SIO writes ~ 60-100 ns, + 1G0832 and '245 ~10 ns |
| Apple write: data sampled | strobe trailing edge | last sample <= ~15 ns before the select rises |
| 2600 read: stable A12-A0 -> data at the cart pins | ~450 ns (838 ns cycle, address valid ~225 ns in, ~100 ns setup), less cable | 2 samples + decode + lookup + 1 SIO write ~ 100-150 ns, + '245 and cable ~15 ns |

These are estimates from the instruction count; measure them at bring-up
(below) and build with `-DFROB_SYS_KHZ=200000` if a margin is under 100 ns.

## Bring-up checklist

1. Power from USB only, no Apple: the LED stays off; `picotool info` sees the
   RP2354B.  Flash the UF2.
2. In the Apple (slot 1-7, not slot 3 on a IIe), no cable: boot; from the
   monitor `C0n0` reads `80`; `C0n0:5` then `Cn00`..`CnFF` read/write as RAM;
   page through 16 pages and check each holds its own data (`PMOVE`).
3. Probe PHI0 (TP5) against slot D0-D7 on a `Cn00` read: data valid >= 100 ns
   before PHI0 falls.  `SPARE_PIN` (TP4) is free for toggling from the loops.
4. With the cable and a 2600: `FLOAD` a 4K image, `C0n0:10`, reset the 2600:
   it runs.  Probe /CE (TP6) against the cart D0-D7 at the adapter: data valid
   >= 100 ns before the 6507's PHI2 falls.
5. `C0n0:30`, run `frobecho` (`../programs`) / AMON+FMON: bytes go both ways.
6. Stress: 4 KB write/read-back loop from the Apple, page by page, for an hour.
