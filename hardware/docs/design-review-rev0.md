# Frob2354 Rev0 -- design review (2026-10-02)

**Verdict: ready to order as a prototype (5 boards).**  No blockers.  ERC 0,
DRC 0 errors / 0 unconnected / 0 schematic-parity issues, `check_nets.py`
159/159, firmware builds, host tests 4144/4144.  Nothing has been built yet.

## What was run

| analysis | result |
|---|---|
| `kicad-cli sch erc --severity-all` | 0 violations |
| `tools/check_nets.py` (netlist vs firmware pin map, Apple slot pin-out, original FROB J2, buffer guards, non-5 V-tolerant GPIO40-47) | 159 checks, 0 failed |
| `kicad-cli pcb drc --refill-zones --schematic-parity` | 0 errors, 0 unconnected, 0 parity; warnings only (finger mask window, silk) |
| kicad-happy `analyze_schematic`, `analyze_pcb --full`, `cross_analysis`, `analyze_emc`, `analyze_thermal`, `analyze_gerbers` | 125 findings, triaged below |
| kicad-happy SPICE (ngspice) | 11/11 pass (RUN RC 159 Hz, crystal C_L 10.5 pF, decoupling, inrush 0.17 A) |
| datasheets | TI SN74LVC245A / SN74LVCH245A / SN74LVC1G0832 / SN74LVC1G32 (ti.com), Diodes AP2112K, AOS AO3401A, RP2350 datasheet (LCSC copy) |
| lifecycle audit | **not run** (`--lifecycle` needs distributor API keys); all parts are in stock at LCSC today |

## Verified against datasheets

* 74LVC1G0832 DBV pin-out 1 A, 2 GND, 3 B, 4 Y, 5 VCC, 6 C and Y = (A·B)+C
  (SN74LVC1G0832 datasheet, p.1-2): the Apple buffer's /OE is low only when
  /IOSEL or /DEVSEL is low *and* A2_DOE is low.
* 74LVC1G32 DBV 1 A, 2 B, 3 GND, 4 Y, 5 VCC; AP2112K SOT-25 1 VIN, 2 GND,
  3 EN, 5 VOUT; AO3401A SOT-23 1 G, 2 S, 3 D.
* 74LVC245A: inputs and I/Os accept 5.5 V at VCC 3.3 V, Ioff (partial power
  down) -- required on the 2600 side, which has its own supply.
* RP2350 pin types: GPIO0-39 "Digital IO (FT)", 5.5 V tolerant *provided
  IOVDD is at 3.3 V*; GPIO40-47 are ADC pads, not 5 V tolerant.  The slot
  signals wired straight to the RP are GP8-20 (FT); GP40-47 only see 3.3 V
  buffer outputs (`check_nets.py` enforces it).
* Changed by the review: the 2600 address buffers were 74LVCH245A (bus
  hold); its +/-500 uA overdrive current is more than the 6507's NMOS outputs
  guarantee to source down the cable, so they are 74LVC245A with 100k
  pull-downs.  ESD diode added on VBUS (UC-002).

## Findings triage

| finding | verdict |
|---|---|
| TS-001 U4 Tj 137 C | **False positive.** The analyzer assumed 264 mA.  The card's 3.3 V load is ~60 mA worst case (RP2354B at 150 MHz, core rail from its own switcher; four LVC245s switching 1 MHz buses; LED; pull-ups): (5.0-3.3) V x 0.06 A = 0.10 W, Tj ~ 25 + 0.10 x 250 = 51 C. |
| DFM-001/002 annular ring 0.05 mm, 0.15 mm drill | **By design**: the ten via-in-pad escapes (0.25/0.15 mm) inside RP2354B pads, JLCPCB's published multilayer minimum.  Order with "epoxy filled and capped" vias. |
| VP-001 untented via in pad (6, decoupling caps) | Plane fan-out vias in passive pads; covered by the same filled-and-capped option. |
| KO-001 J1 inside keep-out | By design: the tab rule areas allow pads and forbid tracks/vias/pour. |
| DP-001/003/004 USB pair skew / layer change / outer layer | USB is Full Speed (12 Mb/s) and only for firmware updates; FS has no impedance or skew requirement at these lengths. |
| CK-001 XIN on outer layer | Raspberry Pi's minimal-design crystal layout (F.Cu, short, over the GND plane). |
| GP-001, RP-001 (reference gaps / layer transitions without a stitching via) | 1 MHz buses with ~10 ns edges; 273 GND stitching vias tie the pours to In1.  Low risk. |
| CC-002 narrow signal 0.15 mm | Signals only. |
| GR-002 layer height differs | Inner layers stop at the tab (fingers only on the outer layers). |
| GR-004 paste 37 % of copper | Fingers, through-hole pads and vias carry no paste. |
| IO-001/002 no EMC filtering, ground pins at J1 | Apple II slot: one GND pin by Apple's design; card-edge signals are the computer's bus. |
| TE-001 test-point coverage | SWD, GND, GP23, PHI0, /CE pads are the bring-up set. |

## Layout notes

* 6 layers (F sig + GND / In1 GND / In2, In3 sig / In4 +3V3 with a DVDD island
  / B sig + GND).  A 4-layer version was routed first: with two signal
  layers ~16 connections stayed open around the RP2354B, and the cause turned
  out to be pin escapes, not layer count -- see the next point.
* Ten RP2354B signal pins (14, 23, 25, 28, 33, 36, 42, 54, 57, 67) sit next to
  a supply pin whose plane via lands 2 mm in front of it; once both
  neighbours' lanes are used they cannot leave on F.Cu.  They leave through a
  0.25/0.15 mm via in their own pad (`tools/via_in_pad.py`).  A future rev
  could instead route the supply pins to their decoupling caps on F.Cu and
  drop those vias.
* Freerouting never connects pads inside the tab keep-out; the finger nets
  are pre-routed by `finish_route.py` (as on FujiNet-NES-Rev0).
* PWR net class clearance is 0.15 mm (was 0.2): pcbnew's mid-flow save drops
  the net-class patterns, so the routers worked to 0.15 mm; 0.15 mm is ample
  for 3.3/5 V and above JLCPCB's 0.09 mm.

## Bring-up risks to watch

1. Apple read timing (select -> data) and 2600 read timing (/CE -> data): the
   firmware margins are instruction-count estimates; measure (firmware/README).
2. `STABLE_LOOPS` (2600 port-register glitch filter) needs a bench check at
   the 6507's real cycle timing.
3. Slot 3 on a IIe maps $C300 to internal firmware unless SLOTC3ROM is set:
   use another slot.
