"""Coastal battery (GAGUN, 海岸炮) artwork: python3 coastbattery.py OUTDIR

A WWII coastal battery built as voxel models and rendered like
pre-rendered building art:
  base    board-formed concrete bastion with battered walls, a parapet ring
          round the gun pit, a recessed entrance with a steel door, sandbag
          piles, ammunition crates and a searchlight on the parapet
  turret  heavy twin-gun armoured turret (field-grey steel, panel lines,
          rivets, red house-colour side panels, rangefinder hood, blast bags)
Texture: concrete formwork lines and rain streaks, steel panel lines and
rivets, grime in crevices, wear on convex edges, dark outline.

NewTheater=yes: GG* files are used on temperate/urban/desert maps, GA* on
snow maps (snow on the ground, parapet and turret roof). Canvas, frame
layout and anchor are the ones of the original files, so only the firing
position (artmd PrimaryFireFLH) follows the new barrels:
  g?gun.shp     155x171, 3 images (normal, damaged, heavily damaged) + 3 shadows
  g?guntur.shp  155x171, 32 facings (0 = north, counter-clockwise) + 32 shadows
  g?gunmk.shp   155x171, build-up: 13 frames + 13 shadows
"""
import os
import sys

import numpy as np
from scipy.ndimage import binary_dilation, convolve, gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'voxplane'))
from builder import to_index                      # noqa: E402
from shpio import write_shp                       # noqa: E402

W, H = 155, 171
GROUND = np.array([76.5, 97.0])     # screen position of the cell centre on the ground (original art)
VOX = 64.0                          # voxels per cell (256 leptons)
PX_X = np.array([30.0, 15.0]) / VOX
PX_Y = np.array([-30.0, 15.0]) / VOX
PX_Z = 36.9 / VOX                   # 15 px per 104 leptons of height
SS = 4
LIGHT = np.array([-0.50, -0.40, 0.77])
LIGHT /= np.linalg.norm(LIGHT)
VIEW = np.array([0.62, 0.62, 0.48])
VIEW /= np.linalg.norm(VIEW)
HALF = (LIGHT + VIEW) / np.linalg.norm(LIGHT + VIEW)
SHADOW_INDEX = 1

# turret pivot height and barrel geometry (also used for the firing position)
PIT_Z = 12.0
BARREL_Z = PIT_Z + 9.0
MUZZLE_X = 64.0
BARREL_Y = 4.6

CONCRETE = (182, 176, 160)
CONCRETE_D = (132, 128, 116)
EARTH = (92, 82, 62)
SNOW = (226, 230, 234)
BAG = (132, 124, 86)
BAG_D = (84, 78, 54)
STEEL = (104, 110, 104)        # field grey
STEEL_D = (66, 70, 68)
STEEL_L = (140, 146, 138)
CANVAS = (92, 84, 62)
DARK = (34, 36, 38)
HOUSE = (180, 180, 180)
GLASS = (210, 214, 170)


class Model:
    def __init__(self, n, nz):
        self.occ = np.zeros((n, n, nz), bool)
        self.rgb = np.zeros((n, n, nz, 3), float)
        self.remap = np.zeros((n, n, nz), bool)
        self.metal = np.zeros((n, n, nz), bool)
        c = np.arange(n) - n / 2 + 0.5
        self.X, self.Y, self.Z = np.meshgrid(c, c, np.arange(nz) + 0.5, indexing='ij')

    def put(self, mask, rgb, remap=False, metal=False):
        self.occ |= mask
        self.rgb[mask] = rgb
        self.remap[mask] = remap
        self.metal[mask] = metal

    def paint(self, mask, rgb, remap=None):
        m = mask & self.occ
        self.rgb[m] = rgb
        if remap is not None:
            self.remap[m] = remap

    def shade(self, mask, k):
        m = mask & self.occ
        self.rgb[m] *= k

    def cut(self, mask):
        self.occ &= ~mask


def octagon(X, Y, R):
    return np.maximum(np.maximum(np.abs(X), np.abs(Y)), (np.abs(X) + np.abs(Y)) / np.sqrt(2)) <= R


def noise(shape, sigma, seed):
    rng = np.random.default_rng(seed)
    f = gaussian_filter(rng.standard_normal(shape), sigma)
    return f / (f.std() + 1e-9)


# ------------------------------------------------------------------ base
def base_model(damage=0, snow=False):
    m = Model(92, 30)
    X, Y, Z = m.X, m.Y, m.Z
    rr = np.hypot(X, Y)
    ang = np.arctan2(Y, X)
    # ground apron with a few rocks
    edge = 36 + 1.0 * np.sin(5 * ang) + 0.8 * np.sin(11 * ang + 2)
    m.put((rr <= edge) & (Z < 1.0), SNOW if snow else EARTH)
    # sandbag ring round the foot of the bastion: two courses of big bags
    ring = (rr >= 28.5) & (rr <= 35.5)
    course = np.where(Z < 3.4, 0, 1)
    phase = (ang * 22 / (2 * np.pi) + 0.5 * course) % 1.0
    bulge = 1.0 - 4 * (phase - 0.5) ** 2
    ctop = np.where(course == 0, 3.4, 6.8)
    btop = ctop - 1.6 * (1 - bulge) ** 2 - 0.45 * np.clip(rr - 33.5, 0, 9)
    outer = 35.5 - 2.4 * (1 - bulge) ** 2 - 1.1 * course
    bags = ring & (Z < btop) & (rr <= outer)
    u0 = (X - Y) / np.sqrt(2)
    bags &= ~((np.abs(u0) < 6.5) & ((X + Y) > 0))          # gap for the entrance
    m.put(bags, BAG)
    m.paint(bags & ((phase < 0.09) | (phase > 0.91) | (np.abs(Z - 3.4) < 0.4)), BAG_D)
    rng = np.random.default_rng(7)
    for _ in range(9):
        a = rng.uniform(0, 2 * np.pi)
        r = rng.uniform(31, 37)
        cx, cy, s = r * np.cos(a), r * np.sin(a), rng.uniform(1.2, 2.2)
        m.put(((X - cx) ** 2 + (Y - cy) ** 2 + (Z * 1.6) ** 2) <= s ** 2, (120, 114, 104))
    # bastion: battered octagonal walls, parapet ring round the pit
    wall_r = 29.5 - 0.18 * Z
    bastion = octagon(X, Y, wall_r) & (Z < 17)
    pit = octagon(X, Y, 21.5) & (Z >= PIT_Z)
    body = bastion & ~pit
    m.put(body, CONCRETE)
    # formwork boards and rain streaks
    m.shade(body & ((Z % 2.4) < 0.5), 0.8)
    streak = noise(m.occ.shape, (0.8, 0.8, 6), 3)
    m.shade(body & (streak > 1.0), 0.78)
    m.shade(body & (Z < 2.5), 0.8)
    # parapet coping and inner face
    m.paint(bastion & (Z >= 16) & ~pit, (176, 170, 156))
    m.paint(bastion & octagon(X, Y, 23) & ~octagon(X, Y, 21.5) & (Z >= PIT_Z), CONCRETE_D)
    # pit floor with the steel turret race
    m.put(octagon(X, Y, 21.5) & (Z >= PIT_Z - 1) & (Z < PIT_Z), CONCRETE_D)
    m.put((rr <= 15.5) & (Z >= PIT_Z - 0.5) & (Z < PIT_Z + 0.8), STEEL_D, metal=True)
    # house-colour band under the coping
    m.paint(body & (Z >= 13.5) & (Z < 15.2) & ~octagon(X, Y, wall_r - 1.2), HOUSE, remap=True)
    # recessed entrance on the south-east face, steel door, steps
    u = (X - Y) / np.sqrt(2)
    v = (X + Y) / np.sqrt(2)
    m.cut((np.abs(u) < 5.5) & (v > 22.5) & (Z < 11) & (Z >= 1.5))
    m.put((np.abs(u) < 5.5) & (v > 22.5) & (v < 24.2) & (Z < 11), CONCRETE_D)
    door = (np.abs(u) < 3.4) & (v > 23.2) & (v < 24.6) & (Z >= 1.5) & (Z < 9)
    m.put(door, STEEL_D, metal=True)
    m.paint(door & (np.abs(u) < 2.8) & (Z >= 2) & (Z < 8.5), (86, 92, 88))
    m.paint(door & (np.abs(Z - 5.0) < 0.45), STEEL_D)
    m.put((np.abs(u) < 5.0) & (v > 27) & (v < 31) & (Z < 1.5 + np.clip(31 - v, 0, 4) * 0.5), CONCRETE_D)
    # sandbag piles on the parapet (left and back)
    for a0, n in ((2.1, 5), (3.6, 4), (4.9, 3)):
        for k in range(n):
            a = a0 + (k - n / 2) * 0.14
            cx, cy = 26 * np.cos(a), 26 * np.sin(a)
            bag = (((X - cx) / 2.8) ** 2 + ((Y - cy) / 1.8) ** 2 + ((Z - 18) / 1.1) ** 2) <= 1
            m.put(bag, BAG)
            m.paint(bag & (Z < 17.4), BAG_D)
    # ammunition crates by the entrance, searchlight on the north-east corner
    for cu, cv in ((-9.0, 26.0), (-6.5, 27.5)):
        crate = (np.abs(u - cu) < 1.6) & (np.abs(v - cv) < 1.2) & (Z < 4.2)
        m.put(crate, (96, 90, 60))
        m.paint(crate & (Z > 3.6), (120, 112, 76))
    sx, sy = 20.0, -20.0
    m.put((np.hypot(X - sx, Y - sy) <= 1.0) & (Z >= 16) & (Z < 20), STEEL_D, metal=True)
    lamp = (np.hypot(Y - sy, Z - 21.2) <= 2.1) & (np.abs(X - sx) <= 1.6)
    m.put(lamp, STEEL, metal=True)
    m.put((np.hypot(Y - sy, Z - 21.2) <= 1.6) & (X > sx + 1.2) & (X <= sx + 1.8), GLASS, metal=True)
    if snow:
        up = m.occ & ~np.roll(m.occ, -1, axis=2)
        m.paint(up & (Z > 1), SNOW)
    if damage:
        rngd = np.random.default_rng(11 + damage)
        chips = gaussian_filter((rngd.random(m.occ.shape) < 0.04 * damage).astype(float), 1.3) > 0.08
        m.cut(body & chips & (Z > 4) & ~octagon(X, Y, wall_r - 2.5))
        m.cut(chips & (Z > 16.5))
        scorch = gaussian_filter(rngd.random(m.occ.shape), 3.5) > 0.5 - 0.02 * damage
        m.rgb[scorch & m.occ] *= 0.6 - 0.1 * damage
    return m


# ------------------------------------------------------------------ turret
def turret_model(snow=False):
    m = Model(140, 34)
    X, Y, Z = m.X, m.Y, m.Z
    z0 = PIT_Z
    # armoured gunhouse: sloped front and sides, flat roof, rear overhang
    zr = z0 + 13.0
    hw = 13.0 - 0.12 * np.clip(X, 0, None) - 0.25 * np.clip(Z - z0 - 6, 0, None)
    top = zr - 0.55 * np.clip(X - 7, 0, None)
    house = (X >= -17) & (X <= 16) & (np.abs(Y) <= hw) & (Z >= z0 + 0.5) & (Z < top)
    m.put(house, STEEL, metal=True)
    # plate joints, rivet rows
    m.shade(house & ((np.abs(X + 5) < 0.4) | (np.abs(X - 6.5) < 0.4)), 0.72)
    m.shade(house & (np.abs(Z - (z0 + 3.2)) < 0.35), 0.75)
    riv = house & (np.abs(Z - (zr - 1.6)) < 0.45) & ((X % 2.2) < 0.6)
    m.paint(riv, STEEL_L)
    m.paint(house & (Z >= top - 1.0), STEEL_L)                      # lit roof edge
    # red house-colour panels on both sides
    side = house & (np.abs(Y) > hw - 1.2)
    panel = side & (X > -13) & (X < 5) & (Z > z0 + 5) & (Z < z0 + 9.5)
    m.paint(panel, HOUSE, remap=True)
    m.rgb[panel & m.occ] = HOUSE
    # roof hatches and ventilator
    for hx, hy in ((-9.0, 5.0), (-9.0, -5.0)):
        m.put((np.hypot(X - hx, Y - hy) <= 2.2) & (Z >= top) & (Z < top + 1.0), STEEL_D, metal=True)
    m.put((np.abs(X + 2) <= 1.5) & (np.abs(Y) <= 1.5) & (Z >= top) & (Z < top + 1.6), STEEL_D, metal=True)
    # rangefinder hood across the rear roof
    rf = (np.abs(X + 13.5) <= 1.8) & (np.abs(Y) <= 16) & (Z >= zr - 1) & (Z < zr + 1.8)
    m.put(rf, STEEL_D, metal=True)
    m.put((np.abs(X + 13.5) <= 1.2) & (np.abs(np.abs(Y) - 16.5) <= 0.6) & (np.abs(Z - (zr + 0.4)) <= 1.2), DARK)
    # twin guns: blast bags, long barrels, muzzle rings
    for s in (1, -1):
        yb = s * BARREL_Y
        bag = (X > 14) & (X <= 19) & (np.hypot(Y - yb, Z - BARREL_Z) <= 3.0)
        m.put(bag, CANVAS)
        r = np.hypot(Y - yb, Z - BARREL_Z)
        m.put((X > 19) & (X <= MUZZLE_X) & (r <= 1.85 - 0.01 * (X - 19)), (80, 84, 82), metal=True)
        m.put((X > 19) & (X <= 27) & (r <= 2.3), STEEL_D, metal=True)
        m.put((X > MUZZLE_X - 2.5) & (X <= MUZZLE_X) & (r <= 1.9), DARK, metal=True)
    if snow:
        up = m.occ & ~np.roll(m.occ, -1, axis=2)
        m.paint(up & (X < 16) & (Z > z0 + 8), SNOW)
    grime = noise(m.occ.shape, 1.5, 21)
    m.shade(m.occ & ~m.remap & (grime > 1.2), 0.85)
    return m


# ------------------------------------------------------------------ render
def normals(occ):
    f = gaussian_filter(occ.astype(np.float32), 1.0)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    return np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))


def render(model, angle=0.0, seed=0):
    occ = model.occ
    nrm = normals(occ)[occ]
    k = np.zeros((7, 7, 7), np.float32)
    k[:, :, 3:] = 1
    ao = (convolve(occ.astype(np.float32), k, mode='constant') / k.sum())[occ]
    local = (convolve(occ.astype(np.float32), np.ones((3, 3, 3), np.float32), mode='constant') / 27.0)[occ]
    P = np.stack([model.X[occ], model.Y[occ], model.Z[occ]], -1)
    rgb = model.rgb[occ]
    rem = model.remap[occ]
    metal = model.metal[occ]
    ca, sa = np.cos(angle), np.sin(angle)
    R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])
    P = P @ R.T
    nrm = nrm @ R.T
    lam = np.clip(nrm @ LIGHT, 0, 1)
    spec = np.clip(nrm @ HALF, 0, 1) ** 16 * np.where(metal, 0.28, 0.06)
    wear = np.clip((0.55 - local) * 1.6, 0, 0.35)             # convex edges catch light
    rng = np.random.default_rng(seed)
    grain = 1 + 0.05 * rng.standard_normal(len(P))
    shade = (0.46 + 0.86 * lam) * (1.0 - 0.6 * np.clip(ao - 0.3, 0, 1)) * (1 + wear) * grain
    col = np.clip(rgb * shade[:, None] + 255 * spec[:, None], 0, 255)

    scr = GROUND + P[:, 0:1] * PX_X + P[:, 1:2] * PX_Y
    scr[:, 1] -= P[:, 2] * PX_Z
    depth = P[:, 0] + P[:, 1] + 1.3 * P[:, 2]
    Hs, Ws = H * SS, W * SS
    zbuf = np.full((Hs, Ws), -1e9)
    cbuf = np.zeros((Hs, Ws, 3))
    rbuf = np.zeros((Hs, Ws), bool)
    order = np.argsort(depth)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            xs = np.round(scr[order, 0] * SS).astype(int) + dx
            ys = np.round(scr[order, 1] * SS).astype(int) + dy
            ok = (xs >= 0) & (xs < Ws) & (ys >= 0) & (ys < Hs)
            xs, ys, oo = xs[ok], ys[ok], order[ok]
            better = depth[oo] >= zbuf[ys, xs]
            xs, ys, oo = xs[better], ys[better], oo[better]
            zbuf[ys, xs] = depth[oo]
            cbuf[ys, xs] = col[oo]
            rbuf[ys, xs] = rem[oo]
    filled = zbuf > -1e9
    fs = filled.reshape(H, SS, W, SS)
    cov = fs.mean((1, 3))
    avg = cbuf.reshape(H, SS, W, SS, 3).sum((1, 3)) / np.maximum(fs.sum((1, 3)), 1)[..., None]
    zb = np.where(filled, zbuf, np.nan).reshape(H, SS, W, SS)
    zmin = np.nanmin(np.where(np.isnan(zb), np.inf, zb), axis=(1, 3))
    zmax = np.nanmax(np.where(np.isnan(zb), -np.inf, zb), axis=(1, 3))
    crease = (zmax - zmin) > 8
    m = cov >= 0.45
    sil = m & binary_dilation(~m, iterations=1)
    avg[sil] *= 0.62
    avg[crease & m & ~sil] *= 0.82
    remap = rbuf.reshape(H, SS, W, SS).mean((1, 3)) > 0.5
    img = np.zeros((H, W), np.uint8)
    img[m] = to_index(avg[m], remap[m])

    G = P.copy()
    G[:, 0] += P[:, 2] * 0.9
    G[:, 1] += P[:, 2] * 0.35
    s = GROUND + G[:, 0:1] * PX_X + G[:, 1:2] * PX_Y
    sh = np.zeros((H, W), bool)
    xs = np.clip(np.round(s[:, 0]).astype(int), 0, W - 1)
    ys = np.clip(np.round(s[:, 1]).astype(int), 0, H - 1)
    sh[ys, xs] = True
    sh = binary_dilation(sh, iterations=1)
    return img, sh


def firing_flh():
    """PrimaryFireFLH for the barrel tips: forward, lateral, height in leptons."""
    lep = 256.0 / VOX
    h = BARREL_Z * PX_Z * 104.0 / 15.0
    return int(round(MUZZLE_X * lep)), 0, int(round(h))


def build(out, prefix, snow):
    imgs, shadows = [], []
    for dmg in (0, 1, 2):
        img, sh = render(base_model(dmg, snow), seed=dmg)
        imgs.append(img)
        shadows.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gun.shp'), W, H, imgs + shadows)

    tm = turret_model(snow)
    timgs, tsh = [], []
    north = np.radians(225.0)
    for k in range(32):
        a = north - np.radians(360.0 / 32 * k)
        img, sh = render(tm, angle=a, seed=k)
        timgs.append(img)
        tsh.append(np.where(sh, SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'guntur.shp'), W, H, timgs + tsh)

    bm = base_model(0, snow)
    full = bm.occ.copy()
    bups, bsh = [], []
    for k in range(13):
        bm.occ = full & (bm.Z < 1.5 + 21.0 * min(k + 1, 7) / 7)
        img, sh = render(bm, seed=0)
        if k >= 7:
            tfull = tm.occ.copy()
            if k < 12:
                tm.occ = tfull & (tm.Z < PIT_Z + 16.0 * (k - 6) / 6)
            ti, ts = render(tm, angle=north, seed=0)
            tm.occ = tfull
            img = np.where(ti > 0, ti, img)
            sh |= ts
        bups.append(img)
        bsh.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gunmk.shp'), W, H, bups + bsh)
    print('%sgun / %sguntur / %sgunmk written; PrimaryFireFLH=%d,%d,%d' % ((prefix,) * 3 + firing_flh()))


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    build(out, 'gg', snow=False)
    build(out, 'ga', snow=True)
