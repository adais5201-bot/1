"""Repaint an existing voxel model (used for NAFAF's skins, whose base model is
the hand-made original and is not regenerated).

    python3 recolor.py SRC_NOEXT DST_NOEXT R G B

Every body voxel keeps its brightness relative to the model's main paint and
takes the new colour; house colours (remap 16-31), glass (192-199) and very
dark details stay as they are. Other sections (propellers) and the HVA are
copied unchanged.
"""
import shutil
import sys

import numpy as np

from builder import PALETTE, to_index
from vxlio import read_vxl, write_vxl

LUM = np.array([0.30, 0.59, 0.11])


def recolor(src, dst, rgb):
    v = read_vxl(src + '.vxl')
    body = max(v['sections'], key=lambda s: s.filled.sum())
    idx = body.color[body.filled].astype(int)
    lum = PALETTE[idx].astype(float) @ LUM
    keep = ((idx >= 16) & (idx <= 31)) | ((idx >= 192) & (idx <= 199)) | (lum < 40)
    ref = np.median(lum[~keep])
    target = np.array(rgb, float)
    new_rgb = np.clip(target[None, :] * (lum / ref)[:, None], 0, 255)
    new_idx = to_index(new_rgb)
    new_idx[keep] = idx[keep]
    body.color[body.filled] = new_idx
    write_vxl(dst + '.vxl', v['sections'], v['pal'], v['remap'])
    shutil.copyfile(src + '.hva', dst + '.hva')


if __name__ == '__main__':
    recolor(sys.argv[1], sys.argv[2], tuple(int(c) for c in sys.argv[3:6]))
