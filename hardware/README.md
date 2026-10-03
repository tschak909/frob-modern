# Frob2354 hardware

KiCad 10 project.  **Every KiCad file here is generated** from
`tools/design.py` (parts, values, MPN/LCSC codes, every pin's net) and
`tools/placement.py`; edit those and regenerate, not the schematic or board.
The generator toolchain is FujiNet-NES-Rev0's (fujinet-hardware), adapted to
a 6-layer Apple II card.

## Rebuild

Needs KiCad 10 (`kicad-cli` + the `pcbnew` Python module), Python 3 + numpy,
Java and Freerouting 2.4.1 (`~/.local/share/freerouting/freerouting-2.4.1.jar`).

```sh
tools/build_all.sh            # schematic, ERC, netlist checks, BOM, PDF
LAYOUT=1 tools/build_all.sh   # + placement, routing, DRC, gerbers, CPL, renders
```

| step | tool |
|---|---|
| symbols | `harvest_symbols.py` -> `tools/symcache.sexpr` (stock KiCad symbols, flattened) |
| footprints | `make_a2edge_fp.py` (Apple 50-pin edge); the rest are stock KiCad / FujiNet-NES footprints in `Frob2354.pretty` |
| schematic | `gen_sch.py` + `sch_layout.py` + `sch_route.py`: a block-diagram root (Apple slot -> RP2354B -> 2600 cable, power below, joined by buses) and four wired sheets -- parts placed by hand in `sch_layout.py`, every connection drawn by an orthogonal router, parallel buses as KiCad buses, rails as power symbols, signals that leave a sheet as hierarchical labels |
| connectivity | `compare_netlists.py tools/reference-netlist.xml`: the drawing produces exactly the reference connectivity (the netlist only changes when `design.py` does; refresh the reference then) |
| checks | `kicad-cli sch erc`; `check_nets.py`: the netlist against `../firmware/src/frob_pins.h`, the Apple slot pin-out, the original FROB J2 pin-out and the buffer-enable logic -- independent of `design.py` |
| board | `gen_pcb.py` (outline, placement, finger stubs, plane fan-out, RP core copper, zones), `finish_route.py --lock` (RP core corner), `finish_route.py --nets=...` (slot fingers), `route.py` (Freerouting), `via_in_pad.py` (boxed-in RP pins), `drc_fix.py`, `finish_route.py`, `tidy_tracks.py`, `stitch_gnd.py` |
| outputs | `export.py`: BOM, JLCPCB BOM + CPL, gerbers + drill zip, schematic PDF, renders |

## Board

* Apple II peripheral card in the original FROB card's frame (the
  reverse-engineered `a2board.kicad_pcb`): the same 65.4 x 7.62 mm tab, the
  same rear edge; the front is cut back (85.9 x 69.85 mm body).
* Fingers: 0.1 in pitch, 1.52 x 7.32 mm, pins 1-25 on the component side
  (pin 1 toward the front of the computer), 26-50 behind them on the solder
  side, pin N opposite 51-N.  `check_nets.py` asserts this from the footprint.
* Stack-up (FujiNet-NES-Rev0's): F.Cu signals + GND pour / In1 GND / In2 + In3
  signals / In4 +3V3 (DVDD island under the RP2354B core) / B.Cu signals + GND
  pour.  A 4-layer version (two signal layers) was tried first: Freerouting and
  the finisher left ~16 connections open around the RP2354B's 0.4 mm pin rows.
* J2 (FROB cable): DIP-24 0.6 in socket, original pin-out (2732 EPROM order;
  /CE = A12 inverted on the cable adapter, /OE grounded there, pin 24 open).

## Ordering at JLCPCB

`exports/jlcpcb/`: `Frob2354-gerbers.zip`, `BOM-JLCPCB.csv`, `CPL-JLCPCB.csv`.

* PCB: 6 layers, 1.6 mm, **ENIG**, **gold fingers: yes**, **bevelled edge
  (45 deg): yes**, impedance control not needed.  **Via covering: epoxy
  filled and capped (via-in-pad)** -- ten RP2354B signal pads carry a
  0.25/0.15 mm via (`tools/via_in_pad.py`); JLCPCB's 6-layer process includes it.
* Assembly: top side, Economic or Standard; every assembled part has an
  LCSC code (the extended ones: RP2354B, 74LVC245A, 74LVC1G0832, 74LVC1G32,
  AP2112K, AO3401A, USB-C, inductor, crystal, switches).  Check the
  placement preview for pin 1 of U1-U8, the USB-C and the diodes.
* Hand-solder J2: a 24-pin 0.6 in DIP socket (e.g. Mill-Max
  110-43-624-41-001000, or any turned-pin socket).

## Files

| | |
|---|---|
| `Frob2354.kicad_pro/.kicad_sch/.kicad_pcb` | the project (generated) |
| `apple.kicad_sch`, `mcu.kicad_sch`, `vcs.kicad_sch`, `power.kicad_sch` | the four sheets (Apple slot, RP2354B, 2600 cable, power / USB) |
| `tools/relink_pcb.py` | renames board nets / re-points footprints after a schematic redraw, copper untouched (used once, when the drawing became hierarchical: local nets gained sheet paths such as `/mcu/XIN`) |
| `Frob2354.pretty`, `Frob2354.kicad_sym` | project footprints / symbols |
| `datasheets/` | datasheets used in the review (`manifest.json`; PDFs not committed) |
| `docs/` | schematic PDF, layout SVGs, renders |
