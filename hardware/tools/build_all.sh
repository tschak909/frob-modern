#!/usr/bin/env bash
# Regenerate Frob2354 end to end: schematic, checks, BOM; with LAYOUT=1 also
# the board, routing, DRC and the fab outputs.
# Needs KiCad 10, Python 3 (+ numpy), Java + Freerouting 2.4.1 for the board.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/harvest_symbols.py >/dev/null   # stock symbols -> tools/symcache.sexpr
python3 tools/make_a2edge_fp.py               # Apple II 50-pin card edge
python3 tools/gen_sch.py                      # design.py + sch_layout.py -> wired block diagram + 4 sheets
kicad-cli sch erc --severity-all --exit-code-violations Frob2354.kicad_sch -o /dev/null
python3 tools/compare_netlists.py tools/reference-netlist.xml   # the drawing must not change connectivity
python3 tools/check_nets.py                   # netlist vs ../firmware/src/frob_pins.h, slot + J2 pin-outs
if [ "${LAYOUT:-0}" = 1 ]; then
    python3 tools/gen_pcb.py
    # locked pre-route of the RP2354B core-regulator corner and the crystal on the empty board
    python3 tools/finish_route.py --nets=RP_LX,DVDD,VREG_AVDD,XIN,XOUT,XOUT_Y --lock || true
    # the slot fingers: Freerouting never reaches pads inside the tab keep-out, so the
    # finisher pre-routes those nets (unlocked: Freerouting may still move them)
    FINGERS=A2_A0,A2_A1,A2_A2,A2_A3,A2_A4,A2_A5,A2_A6,A2_A7,A2_D0,A2_D1,A2_D2,A2_D3,A2_D4,A2_D5,A2_D6,A2_D7
    python3 tools/finish_route.py --nets=$FINGERS,A2_IOSEL_N,A2_DEVSEL_N,A2_RW,A2_PHI0,A2_RES_N,SLOT_5V,A2_INT_DAISY,A2_DMA_DAISY || true
    python3 tools/route.py --passes 10 --timeout 7200
    # RP2354B signal pins boxed in by a neighbouring supply pin's plane via: via-in-pad (filled + capped)
    python3 tools/via_in_pad.py U1:14,U1:23,U1:25,U1:28,U1:33,U1:36,U1:42,U1:54,U1:57,U1:67
    python3 tools/drc_fix.py                  # drop router copper that breaks DRC; the finisher redoes it
    python3 tools/finish_route.py || echo 'finish_route: links left open -- the DRC gate below will fail'
    python3 tools/tidy_tracks.py
    python3 tools/stitch_gnd.py               # GND stitching grid + edge guard row, DRC-filtered
    python3 tools/make_qfn80_model.py           # RP2354B package model (none in KiCad's 3D library)
    python3 tools/set_models.py
    kicad-cli pcb drc --refill-zones --schematic-parity --severity-error --exit-code-violations Frob2354.kicad_pcb -o /dev/null
fi
python3 tools/export.py                       # BOM, JLCPCB BOM, schematic PDF (+ CPL/gerbers/renders with a .kicad_pcb)
