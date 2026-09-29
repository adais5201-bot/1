"""Validate generated models: re-read files, normal accuracy, bounds, HVA frames."""
import sys

import numpy as np
from scipy.ndimage import binary_erosion

from builder import NORMALS, surface_normals
from vxlio import read_hva, read_vxl

for path in sys.argv[1:]:
    v = read_vxl(path + '.vxl')
    h = read_hva(path + '.hva')
    secs = v['sections']
    assert [s.name for s in secs] == h['names'], (path, h['names'])
    body = secs[-1]
    surf = body.filled & ~binary_erosion(body.filled, border_value=0)
    g = surface_normals(body.filled)
    dots = (NORMALS[body.normal[surf]] * g[surf]).sum(1)
    spans = [tuple(np.round((s.maxb - s.minb) / np.array(s.size), 3)) for s in secs]
    ok_span = all(sp == (1.0, 1.0, 1.0) for sp in spans)
    idx = np.argwhere(body.filled) + 0.5 + body.minb
    ctr = (idx.min(0) + idx.max(0)) / 2
    remap = ((body.color[body.filled] >= 16) & (body.color[body.filled] <= 31)).mean()
    angs = []
    for i, s in enumerate(secs[:-1]):
        m = h['mats'][:, i]
        angs.append(round(float(np.degrees(np.arctan2(m[-1, 2, 1], m[-1, 1, 1]))), 1))
        assert np.allclose(m[0, :, 3], m[-1, :, 3]), 'prop pivot moves between frames'
    assert np.allclose(h['mats'][:, -1], np.eye(3, 4)), 'body must not move'
    name = path.split('/')[-1]
    print('%-10s size %-15s normal-dot %.3f  inverted %.1f%%  unit-span %s  centre %s  remap %.1f%%  prop-frame-rot %s' % (
        name, body.size, dots.mean(), 100 * (dots < 0).mean(), ok_span, np.round(ctr[:2], 1), 100 * remap, angs))
