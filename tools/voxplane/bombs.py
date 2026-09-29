"""Voxel bombs for the WWII bombers: python3 bombs.py OUTDIR

  wwfab250  FAB-250 (Pe-2 dive bomber)            ~14 voxels, grey-green, 4 fins
  wwnapalm  napalm tank (B-25J)                   ~15 voxels, bare aluminium, no fins
  wwtalboy  Tallboy earthquake bomb (Lancaster)   ~24 voxels, dark green, offset fins

Same layout as the game's own bombs (FEOMB, DROPB): one section, unit voxel
spacing, bounds centred on the model, x = flight direction (nose at +x).
"""
import os
import sys

import numpy as np

from builder import PALETTE, quantize_normals, surface_normals, to_index
from vxlio import Section, write_hva, write_vxl


def grid(L, R):
    n = (int(np.ceil(L)) + 2, int(np.ceil(2 * R)) + 2, int(np.ceil(2 * R)) + 2)
    x = np.arange(n[0])[:, None, None] + 0.5 - 1
    y = np.arange(n[1])[None, :, None] + 0.5 - n[1] / 2
    z = np.arange(n[2])[None, None, :] + 0.5 - n[2] / 2
    return n, x, y, z


def body_of_revolution(L, radius_at):
    """radius_at(u) for u in 0..1 along the bomb (0 = tail, 1 = nose)."""
    R = max(radius_at(u) for u in np.linspace(0, 1, 101))
    n, x, y, z = grid(L, R + 2.5)
    u = np.clip(x / L, 0, 1)
    r = np.vectorize(radius_at)(u)
    occ = (y ** 2 + z ** 2 <= r ** 2) & (x >= 0) & (x <= L)
    return occ, x, y, z


def fins(occ, x, y, z, x0, x1, span, t=0.6, angle=0.0):
    """four cruciform tail fins between x0 and x1 reaching `span` from the axis."""
    for k in range(4):
        a = np.radians(angle + 90 * k)
        along = y * np.cos(a) + z * np.sin(a)
        across = -y * np.sin(a) + z * np.cos(a)
        m = (x >= x0) & (x <= x1) & (along >= 0) & (along <= span) & (np.abs(across) <= t)
        occ |= m
    return occ


def finish(name, occ, colour_fn, out):
    occ = np.broadcast_to(occ, occ.shape).copy()
    idx = np.argwhere(occ)
    lo, hi = idx.min(0), idx.max(0) + 1
    crop = tuple(slice(a, b) for a, b in zip(lo, hi))
    occ = occ[crop]
    size = occ.shape
    P = np.argwhere(occ).astype(float)
    nrm = surface_normals(occ)
    rgb = colour_fn(P, np.array(size, float))
    s = Section('Body')
    s.size = tuple(int(v) for v in size)
    s.filled = occ
    s.color = np.zeros(size, np.uint8)
    s.color[occ] = to_index(rgb)
    s.normal = np.zeros(size, np.uint8)
    s.normal[occ] = quantize_normals(nrm[occ])
    s.minb = -np.array(size, float) / 2
    s.maxb = s.minb + np.array(size)
    write_vxl(os.path.join(out, name + '.vxl'), [s], PALETTE)
    write_hva(os.path.join(out, name + '.hva'), name, ['Body'], np.eye(3, 4)[None, None])
    print('%-9s size %s voxels %d' % (name, s.size, occ.sum()))


def shade(base, P, size, bands=()):
    rgb = np.tile(np.array(base, float), (len(P), 1))
    u = P[:, 0] / max(size[0] - 1, 1)
    for u0, u1, col in bands:
        m = (u >= u0) & (u <= u1)
        rgb[m] = col
    return rgb


def fab250(out):
    L = 13.0

    def r(u):
        if u < 0.28:                      # tail cone
            return 0.9 + 1.2 * u / 0.28
        if u < 0.78:
            return 2.1
        return 2.1 * np.sqrt(max(1 - ((u - 0.78) / 0.22) ** 2, 0.05))    # rounded nose
    occ, x, y, z = body_of_revolution(L, r)
    occ = fins(occ, x, y, z, 0, 3.2, 3.1, t=0.5)
    finish('wwfab250', occ, lambda P, S: shade((104, 112, 92), P, S,
           [(0.0, 0.26, (86, 94, 76)), (0.70, 0.75, (196, 170, 70))]), out)


def napalm(out):
    L = 15.0

    def r(u):                             # teardrop drop tank
        if u < 0.55:
            return 0.5 + 1.9 * np.sin(np.pi / 2 * u / 0.55)
        return 2.4 * np.sqrt(max(1 - ((u - 0.55) / 0.45) ** 2, 0.04))
    occ, x, y, z = body_of_revolution(L, r)
    finish('wwnapalm', occ, lambda P, S: shade((178, 182, 186), P, S,
           [(0.46, 0.50, (120, 124, 128)), (0.95, 1.0, (90, 90, 96))]), out)


def tallboy(out):
    L = 23.0

    def r(u):
        if u < 0.40:                      # long tapering tail
            return 1.0 + 2.2 * (u / 0.40) ** 0.8
        if u < 0.80:
            return 3.2
        return 3.2 * np.sqrt(max(1 - ((u - 0.80) / 0.20) ** 2, 0.02)) ** 0.8    # pointed ogive nose
    occ, x, y, z = body_of_revolution(L, r)
    occ = fins(occ, x, y, z, 0, 5.0, 4.0, t=0.5, angle=8)          # offset fins spin the bomb
    finish('wwtalboy', occ, lambda P, S: shade((70, 82, 62), P, S,
           [(0.0, 0.20, (62, 72, 56)), (0.60, 0.64, (180, 60, 50))]), out)


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    fab250(out)
    napalm(out)
    tallboy(out)
