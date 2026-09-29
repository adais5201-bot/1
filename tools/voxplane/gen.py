"""Build all aircraft: python3 gen.py OUTDIR [codes...]"""
import os
import sys

from aircraft import REG
from builder import PALETTE
from vxlio import write_hva, write_vxl


def build(code, outdir):
    f, desc = REG[code]
    plane, livery = f()
    sections, mats = plane.finish(livery)
    write_vxl(os.path.join(outdir, code + '.vxl'), sections, PALETTE)
    write_hva(os.path.join(outdir, code + '.hva'), desc[:15], [s.name for s in sections], mats)
    return sections, mats


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    codes = sys.argv[2:] or list(REG)
    for c in codes:
        secs, _ = build(c, out)
        b = secs[-1]
        print('%-10s %-28s body %s voxels %d props %d' % (c, REG[c][1], b.size, b.filled.sum(), len(secs) - 1))
