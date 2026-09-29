"""Voxel turret for the coastal battery (GAGUN): python3 coastturret.py OUTDIR

The game draws a building's voxel turret itself (TurretAnimIsVoxel=true, as
the sea cannon NASCAN and the grand cannon GTGCAN), so it is lit and shaded
exactly like every tank and ship. Files, named after the building:
  gaguntur.vxl/.hva   armoured twin-gun turret (x = forward)
  gagunbarl.vxl/.hva  the twin barrels with blast bags
The base is the bastion of tools/shp/coastbattery.py, whose steel turret
ring tops out 25.3 world units up (one unit is about 0.66 px of height on
screen, the game's voxel convention as in T-34 gerf/gerftur: placed above
the base through the bounds), so the turret stands on that ring.
"""
import os
import sys

import numpy as np

from builder import PALETTE, quantize_normals, surface_normals, to_index
from vxlio import Section, write_hva, write_vxl

U = 0.6                    # world units per voxel (the T-34 uses 0.8333; smaller to fit the dome)
BASE_TOP = 25.3            # top of the bastion turret ring (tools/shp/coastbattery.py)
FLOOR = 25.3               # turret floor: straight on the ring, no pedestal
PED = int(round((FLOOR - BASE_TOP) / U))      # pedestal height in voxels

STEEL = (136, 140, 148)
STEEL_D = (86, 90, 98)
STEEL_L = (168, 172, 180)
DARK = (40, 42, 46)
BARREL = (98, 100, 106)
CANVAS = (124, 114, 86)
HOUSE = (170, 170, 170)


def grid(nx, ny, nz):
    return np.meshgrid(np.arange(nx) + 0.5, np.arange(ny) + 0.5 - ny / 2, np.arange(nz) + 0.5, indexing='ij')


def section(name, occ, rgb, remap, minb):
    s = Section(name)
    s.size = tuple(int(v) for v in occ.shape)
    s.scale = U
    s.filled = occ
    s.color = np.zeros(occ.shape, np.uint8)
    s.color[occ] = to_index(rgb[occ], remap[occ])
    s.normal = np.zeros(occ.shape, np.uint8)
    s.normal[occ] = quantize_normals(surface_normals(occ)[occ])
    s.minb = np.array(minb, float)
    s.maxb = s.minb + np.array(occ.shape) * U
    return s


def turret():
    nx, ny, nz = 78, 62, 26 + PED
    X, Y, Z = grid(nx, ny, nz)
    Z = Z - PED                         # z = 0 is the turret floor, below it the pedestal
    occ = np.zeros((nx, ny, nz), bool)
    rgb = np.zeros((nx, ny, nz, 3))
    remap = np.zeros((nx, ny, nz), bool)

    def put(m, c, r=False):
        occ[m] = True
        rgb[m] = c
        remap[m] = r

    def paint(m, c, r=None):
        m = m & occ
        rgb[m] = c
        if r is not None:
            remap[m] = r

    # pedestal drum with a house-colour band, then the traverse ring
    ped = (np.hypot(X - 36, Y) <= 22) & (Z < 0)          # empty when PED == 0
    put(ped, STEEL)
    paint(ped & (Z < -PED + 1.5), STEEL_D)
    paint(ped & (np.hypot(X - 36, Y) > 20.5) & (np.abs(Z + PED / 2.0) < PED / 4.0), HOUSE, True)
    put((np.hypot(X - 36, Y) <= 24) & (Z >= 0) & (Z < 3), STEEL_D)
    # gun house: rounded rear, sides and front sloped inwards, flat roof
    hw = 27.0 - 0.10 * np.clip(X - 40, 0, None) - 0.35 * np.clip(Z - 8, 0, None)
    rear = np.hypot(np.clip(18 - X, 0, None), Y) <= hw
    top = 20.0 - 0.45 * np.clip(X - 56, 0, None)
    house = (X >= 4) & (X <= 72) & (np.abs(Y) <= hw) & rear & (Z >= 2) & (Z < top)
    put(house, STEEL)
    paint(house & (Z >= top - 1.2), STEEL_L)
    paint(house & (Z < 3.5), STEEL_D)
    for xj in (24, 44):                                       # plate joints
        paint(house & (np.abs(X - xj) < 0.6), STEEL_D)
    paint(house & (np.abs(Z - (top - 2.5)) < 0.5) & ((X % 4) < 1.2), STEEL_L)   # rivet row
    # red house-colour panels on both sides
    side = house & (np.abs(Y) > hw - 3.0)
    paint(side & (X > 10) & (X < 48) & (Z > 8) & (Z < 14.5), HOUSE, True)
    # roof: two hatches, ventilator, sighting hoods
    for hx, hy in ((18, 9), (18, -9)):
        put((np.hypot(X - hx, Y - hy) <= 4.2) & (Z >= top) & (Z < top + 1.6), STEEL_D)
        put((np.hypot(X - hx, Y - hy) <= 2.5) & (Z >= top + 1.6) & (Z < top + 2.4), STEEL)
    put((np.abs(X - 32) <= 3) & (np.abs(Y) <= 3) & (Z >= top) & (Z < top + 2.8), STEEL_D)
    for hy in (14, -14):
        put((np.abs(X - 60) <= 4) & (np.abs(Y - hy) <= 3) & (Z >= top - 0.5) & (Z < top + 2.2), STEEL_D)
    # rangefinder ears at the rear of the roof
    rf = (np.hypot(X - 14, Z - (top - 1)) <= 3.0) & (np.abs(Y) <= 33)
    put(rf, STEEL_D)
    put((np.hypot(X - 14, Z - (top - 1)) <= 2.0) & (np.abs(np.abs(Y) - 32.5) <= 0.8), DARK)
    # gun ports in the front plate
    for gy in (-8, 8):
        put((X > 68) & (X <= 74) & (np.abs(Y - gy) <= 4.2) & (np.abs(Z - 10) <= 4.2), DARK)
    return section('Turret', occ, rgb, remap, (-36 * U, -ny / 2 * U, BASE_TOP))


def barrels():
    nx, ny, nz = 72, 26, 12
    X, Y, Z = grid(nx, ny, nz)
    occ = np.zeros((nx, ny, nz), bool)
    rgb = np.zeros((nx, ny, nz, 3))
    remap = np.zeros((nx, ny, nz), bool)
    for gy in (-8, 8):
        r = np.hypot(Y - gy, Z - 6)
        m = (X < 8) & (r <= 4.6)                              # canvas blast bags
        occ[m], rgb[m] = True, CANVAS
        m = (X >= 6) & (X < 16) & (r <= 3.0)                  # recoil sleeve
        occ[m], rgb[m] = True, STEEL_D
        m = (X >= 16) & (X < 70) & (r <= 2.2 - 0.008 * (X - 16))
        occ[m], rgb[m] = True, BARREL
        m = (X >= 67) & (r <= 2.6) & (r >= 1.0)               # muzzle ring
        occ[m], rgb[m] = True, DARK
    # the bags start in the gun ports (turret front at x = 74 voxels)
    return section('Barrel', occ, rgb, remap, ((68 - 36) * U, -ny / 2 * U, FLOOR + 4 * U))


def firing_flh():
    """PrimaryFireFLH (leptons): one unit is about 4.6 leptons (0.6 px)."""
    lep = 4.6
    muzzle = ((68 - 36) + 70) * U
    return int(round(muzzle * lep)), int(round(8 * U * lep)), int(round((FLOOR + 10 * U) * lep))


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, sec in (('gaguntur', turret()), ('gagunbarl', barrels())):
        write_vxl(os.path.join(out, name + '.vxl'), [sec], PALETTE)
        write_hva(os.path.join(out, name + '.hva'), name, [sec.name], np.eye(3, 4)[None, None])
        print('%-10s size %s voxels %d bounds %s..%s' % (name, sec.size, sec.filled.sum(),
                                                         np.round(sec.minb, 1), np.round(sec.maxb, 1)))
    print('PrimaryFireFLH=%d,%d,%d' % firing_flh())
