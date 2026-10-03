#!/usr/bin/env python3
"""Check that the generated schematic has exactly the connectivity of a
reference netlist (by default the baseline saved before the redraw), and
write the old -> new net-name map the board needs (relink_pcb.py).

Usage: python3 tools/compare_netlists.py REF.xml [--map out.json]
"""
import json, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)


def nets(fn):
    t = ET.parse(fn)
    out = {}
    for n in t.iter('net'):
        nodes = frozenset((nd.get('ref'), nd.get('pin')) for nd in n.iter('node')
                          if not nd.get('ref').startswith('#'))
        if nodes:
            out[n.get('name')] = nodes
    return out


def main():
    ref = sys.argv[1]
    mp = sys.argv[sys.argv.index('--map') + 1] if '--map' in sys.argv else None
    fn = os.path.join(tempfile.gettempdir(), 'frob2354-new.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', fn,
                    os.path.join(PRJ, 'Frob2354.kicad_sch')], check=True, capture_output=True)
    old, new = nets(ref), nets(fn)
    by_nodes = {v: k for k, v in new.items()}
    bad, rename = [], {}
    for name, nodes in old.items():
        if nodes in by_nodes:
            if by_nodes[nodes] != name:
                rename[name] = by_nodes[nodes]
            continue
        # unconnected pins get per-pin names: only their membership matters
        if name.startswith('unconnected-') and len(nodes) == 1:
            n2 = [k for k, v in new.items() if v == nodes]
            if n2:
                rename[name] = n2[0]
                continue
        bad.append(name)
    extra = [k for k, v in new.items() if v not in set(old.values())]
    for name in bad:
        nodes = old[name]
        hits = sorted({k for k, v in new.items() if v & nodes})
        print('MISMATCH old net %s %s -> new nets %s' % (name, sorted(nodes)[:6], hits))
    for name in extra:
        print('EXTRA new net %s %s' % (name, sorted(new[name])[:6]))
    print('compare_netlists: %d old nets, %d new nets, %d renamed, %d mismatched, %d extra'
          % (len(old), len(new), len(rename), len(bad), len(extra)))
    if mp:
        json.dump(rename, open(mp, 'w'), indent=1, sort_keys=True)
    sys.exit(1 if bad or extra else 0)


if __name__ == '__main__':
    main()
