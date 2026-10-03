# 3D models

Referenced as `${KIPRJMOD}/3d/...` by `tools/set_models.py`, so renders need no
KiCad 3D package.  Sources: KiCad kicad-packages3D (CC-BY-SA 4.0 with the
KiCad library exception) for the stock packages, copied from
FujiNet-NES-Rev0/3d or fetched from gitlab.com/kicad/libraries/kicad-packages3D;
LCSC/EasyEDA models for the Abracon AOTA inductor and the HRO USB-C.  KiCad has
no QFN-80 10x10 model, so the RP2354B's is generated: `tools/make_qfn80_model.py`
writes QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.wrl (10 x 10 x 0.85 mm body, 80
terminals at 0.4 mm, 3.4 mm exposed pad, pin-1 dimple).
