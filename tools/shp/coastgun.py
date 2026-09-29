"""WWII coastal gun (GAGUN, 海岸炮) artwork: python3 coastgun.py OUTDIR

The old art was a flat grey disc with red lights and a thin sci-fi turret,
out of place next to the mod's other defences (steel, sandbags, earth). This
builds a concrete gun pit inside a sandbag ring and a naval gun in an
armoured gunhouse as voxel models and renders them into SHPs with the same
canvas, frame layout and anchor as the old files, so rules/art stay as they
are:
  gagun.shp     155x171, 3 images (normal, damaged, heavily damaged) + 3 shadows
  gaguntur.shp  155x171, 32 facings (0 = north, counter-clockwise) + 32 shadows
  gagunmk.shp   155x171, build-up: 13 frames + 13 shadows
"""
import os
import sys

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'voxplane'))
from builder import to_index                      # noqa: E402
from shpio import write_shp                       # noqa: E402

W, H = 155, 171
GROUND = np.array([76.5, 97.0])     # screen position of the cell centre on the ground (old art)
VOX = 32.0                          # voxels per cell
PX_X = np.array([30.0, 15.0]) / VOX           # screen step of +1 voxel along world x
PX_Y = np.array([-30.0, 15.0]) / VOX          # ... along world y
PX_Z = 36.9 / VOX                             # screen pixels per voxel of height
SS = 4                                        # supersampling
LIGHT = np.array([-0.55, -0.25, 0.80])
LIGHT /= np.linalg.norm(LIGHT)
SHADOW_INDEX = 1


class Model:
    def __init__(self, n):
        self.n = n
        self.occ = np.zeros((n, n, n), bool)
        self.rgb = np.zeros((n, n, n, 3), float)
        self.remap = np.zeros((n, n, n), bool)
        c = np.arange(n) - n / 2 + 0.5
        self.X, self.Y, self.Z = np.meshgrid(c, c, np.arange(n) + 0.5, indexing='ij')

    def put(self, mask, rgb, remap=False):
        self.occ |= mask
        self.rgb[mask] = rgb
        self.remap[mask] = remap

    def cut(self, mask):
        self.occ &= ~mask

    def paint(self, mask, rgb):
        m = mask & self.occ
        self.rgb[m] = rgb


def normals(occ):
    f = gaussian_filter(occ.astype(np.float32), 1.0)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    return np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))


def render(model, angle=0.0, seed=0, shade_noise=0.07):
    """Returns (image indices H x W, shadow mask H x W)."""
    occ = model.occ
    nrm = normals(occ)[occ]
    P = np.stack([model.X[occ], model.Y[occ], model.Z[occ]], -1)
    rgb = model.rgb[occ]
    rem = model.remap[occ]
    ca, sa = np.cos(angle), np.sin(angle)
    R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])
    P = P @ R.T
    nrm = nrm @ R.T
    lam = np.clip(nrm @ LIGHT, 0, 1)
    rng = np.random.default_rng(seed)
    shade = (0.50 + 0.62 * lam) * (1 + shade_noise * rng.standard_normal(len(P)))
    col = np.clip(rgb * shade[:, None], 0, 255)

    # screen positions (supersampled)
    scr = GROUND + P[:, 0:1] * PX_X + P[:, 1:2] * PX_Y
    scr[:, 1] -= P[:, 2] * PX_Z
    depth = P[:, 0] + P[:, 1] + 1.3 * P[:, 2]
    Hs, Ws = H * SS, W * SS
    zbuf = np.full((Hs, Ws), -1e9)
    cbuf = np.zeros((Hs, Ws, 3))
    rbuf = np.zeros((Hs, Ws), bool)
    order = np.argsort(depth)
    r = int(np.ceil(SS * 0.75))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            xs = np.round(scr[order, 0] * SS).astype(int) + dx
            ys = np.round(scr[order, 1] * SS).astype(int) + dy
            ok = (xs >= 0) & (xs < Ws) & (ys >= 0) & (ys < Hs)
            xs, ys, oo = xs[ok], ys[ok], order[ok]
            d = depth[oo]
            # later (closer) voxels overwrite: iterate sorted, numpy keeps last write
            better = d >= zbuf[ys, xs]
            xs, ys, oo = xs[better], ys[better], oo[better]
            zbuf[ys, xs] = depth[oo]
            cbuf[ys, xs] = col[oo]
            rbuf[ys, xs] = rem[oo]
    cov = (zbuf > -1e9).reshape(H, SS, W, SS).mean((1, 3))
    avg = cbuf.reshape(H, SS, W, SS, 3).sum((1, 3)) / np.maximum(
        (zbuf > -1e9).reshape(H, SS, W, SS).sum((1, 3)), 1)[..., None]
    remap = rbuf.reshape(H, SS, W, SS).mean((1, 3)) > 0.5
    img = np.zeros((H, W), np.uint8)
    m = cov >= 0.45
    img[m] = to_index(avg[m], remap[m])

    # shadow: voxels projected to the ground away from the light
    G = P.copy()
    G[:, 0] += P[:, 2] * 0.85
    G[:, 1] += P[:, 2] * 0.15
    s = GROUND + G[:, 0:1] * PX_X + G[:, 1:2] * PX_Y
    sh = np.zeros((H, W), bool)
    xs = np.clip(np.round(s[:, 0]).astype(int), 0, W - 1)
    ys = np.clip(np.round(s[:, 1]).astype(int), 0, H - 1)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sh[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)] = True
    sh = gaussian_filter(sh.astype(float), 0.7) > 0.3
    return img, sh


# ------------------------------------------------------------------ models
CONCRETE = (156, 150, 136)
CONCRETE_D = (118, 114, 104)
EARTH = (112, 94, 66)
BAG = (142, 126, 90)
BAG_SEAM = (96, 84, 60)
OLIVE = (92, 98, 70)
GUN = (98, 106, 92)          # grey-green gunhouse
GUN_D = (70, 74, 70)
BARREL = (78, 80, 78)


def base_model(damage=0):
    m = Model(64)
    X, Y, Z = m.X, m.Y, m.Z
    rr = np.hypot(X, Y)
    ang = np.arctan2(Y, X)
    rng = np.random.default_rng(3)
    # earth apron, slightly uneven edge
    edge = 27 + 1.5 * np.sin(5 * ang) + 1.0 * np.sin(11 * ang + 1)
    m.put((rr <= edge) & (Z < 1.0), EARTH)
    # concrete pit floor and gun plinth
    m.put((rr <= 17) & (Z < 2.0), CONCRETE_D)
    m.put((rr <= 10.5) & (Z < 4.0), CONCRETE)
    m.paint((rr > 9.5) & (rr <= 10.5) & (Z >= 3), CONCRETE_D)
    # sandbag ring: courses of bags, staggered
    ring = (rr >= 17) & (rr <= 22.5) & (Z < 7.0 - 0.25 * np.clip(rr - 20, 0, 9))
    m.put(ring, BAG)
    course = np.floor(Z / 1.75)
    along = (ang * 21 / np.pi + course * 0.5) % 1.0
    seam = (along < 0.12) | ((Z % 1.75) < 0.35)
    m.paint(ring & seam, BAG_SEAM)
    # concrete ready-use lockers and ammo boxes inside the ring
    for a in (0.9, 2.2, 4.0, 5.3):
        cx, cy = 14.2 * np.cos(a), 14.2 * np.sin(a)
        box = (np.abs(X - cx) < 1.8) & (np.abs(Y - cy) < 1.3) & (Z < 4.0)
        m.put(box, OLIVE)
    # remap marker: painted band on the plinth rim
    m.put((rr > 10.5) & (rr <= 11.5) & (Z < 2.6), (170, 170, 170), remap=True)
    if damage:
        holes = rng.random(m.occ.shape) < 0.05 * damage
        holes = gaussian_filter(holes.astype(float), 1.2) > 0.08
        m.cut(ring & holes & (Z > 2))
        scorch = gaussian_filter(rng.random(m.occ.shape), 3) > 0.5 - 0.02 * damage
        m.rgb[scorch & m.occ] *= 0.55 - 0.08 * damage
    return m


def turret_model():
    m = Model(96)
    X, Y, Z = m.X, m.Y, m.Z
    z0 = 4.0                               # sits on the plinth
    rr = np.hypot(X, Y)
    # traverse ring
    m.put((rr <= 9.5) & (Z >= z0) & (Z < z0 + 2.5), GUN_D)
    # gunhouse: sloped front, flat roof, open-ish rear overhang
    zt = z0 + 2.5
    hw = 8.5 - 0.10 * np.clip(X - 2, 0, None)
    top = zt + 8.0 - 0.55 * np.clip(X - 3.5, 0, None)          # sloped front plate
    house = (X >= -9) & (X <= 10) & (np.abs(Y) <= hw) & (Z >= zt) & (Z < top)
    m.put(house, GUN)
    m.paint(house & (Z >= top - 1.0), (112, 118, 108))          # lighter roof edge
    # side armour bolts / panel line and remap stripe
    m.paint(house & (np.abs(np.abs(Y) - hw) < 1.0) & (np.abs(X - 1) < 0.5), GUN_D)
    m.put(house & (np.abs(np.abs(Y) - hw) < 1.0) & (Z >= zt + 4.2) & (Z < zt + 5.6) & (X < 6),
          (170, 170, 170), remap=True)
    # vertical armour plate joints
    for xj in (-4.0, 3.5):
        m.paint(house & (np.abs(X - xj) < 0.45), GUN_D)
    m.paint(house & (np.abs(Z - (zt + 0.6)) < 0.6), GUN_D)
    # rangefinder hood on the roof
    m.put((np.abs(X + 3) <= 2.2) & (np.abs(Y) <= 6.5) & (Z >= zt + 8) & (Z < zt + 9.5), GUN_D)
    # gun: mantlet, long barrel, muzzle
    zb = zt + 4.0
    mant = (X >= 8) & (X <= 12) & (np.abs(Y) <= 2.6) & (np.abs(Z - zb) <= 2.4)
    m.put(mant, GUN_D)
    br = np.hypot(Y, Z - zb)
    m.put((X > 12) & (X <= 44) & (br <= 1.35 - 0.012 * (X - 12)), BARREL)
    m.put((X > 42) & (X <= 45.5) & (br <= 1.6), (58, 60, 58))
    # recuperator above the barrel
    rb = np.hypot(Y, Z - zb - 2.0)
    m.put((X > 11) & (X <= 21) & (rb <= 0.9), GUN_D)
    return m


def build(out):
    os.makedirs(out, exist_ok=True)
    imgs, shadows = [], []
    for dmg in (0, 1, 2):
        img, sh = render(base_model(dmg), seed=dmg)
        imgs.append(img)
        shadows.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, 'gagun.shp'), W, H, imgs + shadows)

    tm = turret_model()
    timgs, tsh = [], []
    north = np.radians(225.0)                  # world direction drawn straight up on screen
    for k in range(32):
        a = north - np.radians(360.0 / 32 * k)   # counter-clockwise on screen
        img, sh = render(tm, angle=a, seed=k)
        timgs.append(img)
        tsh.append(np.where(sh, SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, 'gaguntur.shp'), W, H, timgs + tsh)

    # build-up (gagunmk.shp): 13 frames + 13 shadows, the pit rises from the
    # ground, then the gun is assembled on it (turret facing north)
    bm = base_model(0)
    full = bm.occ.copy()
    bups, bsh = [], []
    for k in range(13):
        bm.occ = full & (bm.Z < 1 + 8.0 * min(k + 1, 7) / 7)
        img, sh = render(bm, seed=0)
        if k >= 7:
            tfull = tm.occ.copy()
            tm.occ = tfull & (tm.Z < 4 + 14.0 * (k - 6) / 6)
            if k == 12:
                tm.occ = tfull
            ti, ts = render(tm, angle=north, seed=0)
            tm.occ = tfull
            img = np.where(ti > 0, ti, img)
            sh |= ts
        bups.append(img)
        bsh.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, 'gagunmk.shp'), W, H, bups + bsh)
    print('gagun.shp: 3 images + 3 shadows; gaguntur.shp: 32 facings + 32 shadows; gagunmk.shp: 13 + 13')


if __name__ == '__main__':
    build(sys.argv[1])
