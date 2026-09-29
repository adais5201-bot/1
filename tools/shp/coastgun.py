"""WWII coastal gun (GAGUN, 海岸炮) artwork: python3 coastgun.py OUTDIR

The old art was a flat grey disc with red lights and a thin sci-fi turret.
The mod's other defences (警戒哨塔, 热卫激光塔, 黑寡妇机炮) are tall, crisp,
pre-rendered pieces: sandbag rings, silver-blue steel, red house-colour
panels. This builds the same kind of piece: a concrete armoured gun drum (silver-blue steel on a
concrete footing) on a sandbag ring with a steel door and a red house-colour band, carrying a heavy steel
gun turret (red side panels, rangefinder, long barrel with muzzle brake).
The voxel models are rendered like pre-rendered art (ambient occlusion,
metal highlights, dark outline) into SHPs with the old canvas, frame layout
and anchor, so rules/art stay as they are.

NewTheater=yes: the game loads GG* on temperate/urban/desert maps and GA* on
snow maps, so both sets are written (the snow set has snow on the ground and
on the sandbags):
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
GROUND = np.array([76.5, 99.0])     # screen position of the cell centre on the ground
VOX = 56.0                          # voxels per cell
PX_X = np.array([30.0, 15.0]) / VOX           # screen step of +1 voxel along world x
PX_Y = np.array([-30.0, 15.0]) / VOX          # ... along world y
PX_Z = 36.9 / VOX                             # screen pixels per voxel of height
SS = 3                                        # supersampling
LIGHT = np.array([-0.45, -0.35, 0.82])
LIGHT /= np.linalg.norm(LIGHT)
VIEW = np.array([0.62, 0.62, 0.48])
VIEW /= np.linalg.norm(VIEW)
HALF = (LIGHT + VIEW) / np.linalg.norm(LIGHT + VIEW)
SHADOW_INDEX = 1

# materials
CONCRETE = (170, 166, 154)
CONCRETE_D = (128, 124, 114)
EARTH = (104, 92, 70)
SNOW = (226, 230, 234)
BAG = (138, 132, 90)
BAG_D = (78, 74, 50)
STEEL = (150, 156, 184)       # silver-blue like the laser tower dome
STEEL_D = (82, 86, 110)
STEEL_L = (196, 200, 224)
BARREL = (104, 110, 120)
DARK = (46, 48, 54)
HOUSE = (180, 180, 180)       # remap (house colour) base shade


class Model:
    def __init__(self, n, nz=None):
        nz = nz or n
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

    def paint(self, mask, rgb, remap=None, metal=None):
        m = mask & self.occ
        self.rgb[m] = rgb
        if remap is not None:
            self.remap[m] = remap
        if metal is not None:
            self.metal[m] = metal

    def cut(self, mask):
        self.occ &= ~mask


def octagon(X, Y, R):
    return np.maximum(np.maximum(np.abs(X), np.abs(Y)), (np.abs(X) + np.abs(Y)) / np.sqrt(2)) <= R


# ------------------------------------------------------------------ models
def base_model(damage=0, snow=False):
    m = Model(80, 34)
    X, Y, Z = m.X, m.Y, m.Z
    rr = np.hypot(X, Y)
    ang = np.arctan2(Y, X)
    rng = np.random.default_rng(3)
    # ground apron
    edge = 32 + 1.0 * np.sin(5 * ang) + 0.7 * np.sin(13 * ang + 1)
    m.put((rr <= edge) & (Z < 1.5), SNOW if snow else EARTH)
    # sandbag ring: two courses of big rounded bags, staggered; each bag bulges
    # out and up in the middle, the seams are sunk and dark
    ring = (rr >= 22.5) & (rr <= 29.5)
    course = np.where(Z < 3.6, 0, 1)
    phase = (ang * 18 / (2 * np.pi) + 0.5 * course) % 1.0
    bulge = 1.0 - 4 * (phase - 0.5) ** 2                 # 1 at the bag middle, 0 at seams
    ctop = np.where(course == 0, 3.6, 7.4)
    top = ctop - 1.8 * (1 - bulge) ** 2 - 0.5 * np.clip(rr - 27.5, 0, 9)
    outer = 29.5 - 2.6 * (1 - bulge) ** 2 - 1.2 * course
    bags = ring & (Z < top) & (rr <= outer)
    m.put(bags, BAG)
    m.paint(bags & ((phase < 0.09) | (phase > 0.91) | (np.abs(Z - 3.6) < 0.45)), BAG_D)
    if snow:
        m.paint(bags & (Z > top - 1.2), SNOW)
    # armoured drum: octagonal steel plating on a concrete footing, chamfered top
    drum = octagon(X, Y, 20.5 - np.clip(Z - 18.5, 0, 9)) & (Z < 21.5)
    m.put(drum, STEEL, metal=True)
    m.paint(drum & (Z < 2.5), CONCRETE_D, metal=False)
    m.paint(drum & (Z >= 18.5), STEEL_L)
    oct_ang = (ang + np.pi / 8) % (np.pi / 4)
    m.paint(drum & ((oct_ang < 0.04) | (oct_ang > np.pi / 4 - 0.04)) & (Z >= 2.5), STEEL_D)
    rivets = drum & (np.abs(Z - 17.6) < 0.45) & (((ang * 40 / (2 * np.pi)) % 1.0) < 0.3)
    m.paint(rivets, STEEL_D)
    # house-colour band round the drum, framed
    m.paint(drum & (Z >= 10.5) & (Z < 15) & (rr > 16), HOUSE, remap=True, metal=False)
    m.paint(drum & (np.abs(Z - 10.1) < 0.45) & (rr > 16), STEEL_D)
    m.paint(drum & (np.abs(Z - 15.4) < 0.45) & (rr > 16), STEEL_D)
    # steel door facing the viewer (south-east)
    u = (X - Y) / np.sqrt(2)
    v = (X + Y) / np.sqrt(2)
    door = (np.abs(u) < 3.6) & (v > 17.8) & (v < 21.8) & (Z < 10)
    m.put(door & (v < 20.9), STEEL_D, metal=True)
    m.paint(door & (np.abs(u) < 2.7) & (Z < 9), STEEL_L, metal=True)
    m.paint(door & (np.abs(Z - 5.0) < 0.5) & (np.abs(u) < 2.7), STEEL_D)
    # turret race on the top
    m.put((rr <= 14) & (Z >= 21.5) & (Z < 23), STEEL_D, metal=True)
    # ammunition lockers on the drum top edge
    for a in (2.2, 4.1):
        cx, cy = 16.0 * np.cos(a), 16.0 * np.sin(a)
        box = (np.abs(X - cx) < 2.2) & (np.abs(Y - cy) < 1.6) & (Z >= 19.5) & (Z < 24)
        m.put(box, (92, 98, 70))
    if damage:
        holes = gaussian_filter((rng.random(m.occ.shape) < 0.05 * damage).astype(float), 1.2) > 0.08
        m.cut(bags & holes & (Z > 2))
        chips = gaussian_filter((rng.random(m.occ.shape) < 0.03 * damage).astype(float), 1.0) > 0.07
        m.cut(drum & chips & (Z > 6) & (rr > 17))
        scorch = gaussian_filter(rng.random(m.occ.shape), 3) > 0.5 - 0.02 * damage
        m.rgb[scorch & m.occ] *= 0.62 - 0.1 * damage
    return m


def turret_model():
    m = Model(120, 44)
    X, Y, Z = m.X, m.Y, m.Z
    z0 = 23.0
    # gun house: round rear, tapering front, sloped front plate
    hw = np.where(X < 0, np.sqrt(np.clip(13.5 ** 2 - X ** 2, 0, None)), 13.5 - 0.35 * X)
    top = z0 + 12.5 - 0.6 * np.clip(X - 5, 0, None)
    house = (X >= -13.5) & (X <= 15) & (np.abs(Y) <= hw) & (Z >= z0) & (Z < top)
    m.put(house, STEEL, metal=True)
    m.paint(house & (Z >= top - 1.2), STEEL_L)                 # lit roof edge
    m.paint(house & (Z < z0 + 1.2), STEEL_D)                   # skirt
    # red house-colour side panels, framed
    side = house & (np.abs(Y) > hw - 1.3)
    m.paint(side & (X > -9) & (X < 7) & (Z > z0 + 4) & (Z < z0 + 8.5), HOUSE, remap=True, metal=False)
    m.paint(side & (X > -9.8) & (X < 7.8) & ((np.abs(Z - (z0 + 3.5)) < 0.5) | (np.abs(Z - (z0 + 9)) < 0.5)),
            STEEL_D)
    # vision slits and rivet line on the front plate
    front = house & (X > 12)
    m.paint(front & (np.abs(Z - (z0 + 8)) < 0.6) & (np.abs(Y) > 4) & (np.abs(Y) < 9), DARK)
    # rangefinder ears
    for s in (1, -1):
        ear = (np.hypot(X + 5, Z - (z0 + 10)) <= 1.8) & (np.abs(Y - s * 14.5) <= 2.5)
        m.put(ear, STEEL_D, metal=True)
        m.put((np.hypot(X + 5, Z - (z0 + 10)) <= 1.3) & (np.abs(Y - s * 17) <= 0.7), DARK)
    # commander's cupola
    m.put((np.hypot(X + 6, Y - 5) <= 3.0) & (Z >= top) & (Z < top + 2.2), STEEL_D, metal=True)
    # mantlet, barrel, muzzle brake
    zb = z0 + 6.0
    m.put((X >= 12) & (X <= 18) & (np.abs(Y) <= 4.2) & (np.abs(Z - zb) <= 3.6), STEEL_D, metal=True)
    br = np.hypot(Y, Z - zb)
    m.put((X > 18) & (X <= 56) & (br <= 2.3 - 0.012 * (X - 18)), BARREL, metal=True)
    m.put((X > 18) & (X <= 26) & (br <= 2.9), STEEL_D, metal=True)       # recoil sleeve
    m.put((X > 53) & (X <= 58) & (br <= 2.9), DARK, metal=True)            # muzzle brake
    m.cut((X > 55.5) & (X <= 58) & (br <= 1.2))
    return m


# ------------------------------------------------------------------ render
def normals(occ):
    f = gaussian_filter(occ.astype(np.float32), 1.0)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    return np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))


def occlusion(occ):
    k = np.zeros((7, 7, 7), np.float32)
    k[:, :, 3:] = 1                        # neighbours at or above
    c = convolve(occ.astype(np.float32), k, mode='constant') / k.sum()
    return c


def render(model, angle=0.0, seed=0):
    """Returns (image indices H x W, shadow mask H x W)."""
    occ = model.occ
    nrm = normals(occ)[occ]
    ao = occlusion(occ)[occ]
    P = np.stack([model.X[occ], model.Y[occ], model.Z[occ]], -1)
    rgb = model.rgb[occ]
    rem = model.remap[occ]
    metal = model.metal[occ]
    ca, sa = np.cos(angle), np.sin(angle)
    R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])
    P = P @ R.T
    nrm = nrm @ R.T
    lam = np.clip(nrm @ LIGHT, 0, 1)
    spec = np.clip(nrm @ HALF, 0, 1) ** 22 * np.where(metal, 0.55, 0.12)
    rng = np.random.default_rng(seed)
    shade = (0.42 + 0.72 * lam) * (1.0 - 0.55 * np.clip(ao - 0.35, 0, 1)) * (1 + 0.03 * rng.standard_normal(len(P)))
    col = np.clip(rgb * shade[:, None] + 255 * spec[:, None], 0, 255)

    scr = GROUND + P[:, 0:1] * PX_X + P[:, 1:2] * PX_Y
    scr[:, 1] -= P[:, 2] * PX_Z
    depth = P[:, 0] + P[:, 1] + 1.3 * P[:, 2]
    Hs, Ws = H * SS, W * SS
    zbuf = np.full((Hs, Ws), -1e9)
    cbuf = np.zeros((Hs, Ws, 3))
    rbuf = np.zeros((Hs, Ws), bool)
    order = np.argsort(depth)
    r = 1
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
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
    cov = filled.reshape(H, SS, W, SS).mean((1, 3))
    avg = cbuf.reshape(H, SS, W, SS, 3).sum((1, 3)) / np.maximum(filled.reshape(H, SS, W, SS).sum((1, 3)), 1)[..., None]
    # depth edges inside the image (outline between parts) and the silhouette
    zb = np.where(filled, zbuf, np.nan).reshape(H, SS, W, SS)
    zmin = np.nanmin(np.where(np.isnan(zb), np.inf, zb), axis=(1, 3))
    zmax = np.nanmax(np.where(np.isnan(zb), -np.inf, zb), axis=(1, 3))
    crease = (zmax - zmin) > 6
    m = cov >= 0.45
    sil = m & binary_dilation(~m, iterations=1)
    avg[sil & m] *= 0.72
    avg[crease & m] *= 0.8
    remap = rbuf.reshape(H, SS, W, SS).mean((1, 3)) > 0.5
    img = np.zeros((H, W), np.uint8)
    img[m] = to_index(avg[m], remap[m])

    # shadow: voxels projected to the ground away from the light
    G = P.copy()
    G[:, 0] += P[:, 2] * 0.85
    G[:, 1] += P[:, 2] * 0.35
    s = GROUND + G[:, 0:1] * PX_X + G[:, 1:2] * PX_Y
    sh = np.zeros((H, W), bool)
    xs = np.clip(np.round(s[:, 0]).astype(int), 0, W - 1)
    ys = np.clip(np.round(s[:, 1]).astype(int), 0, H - 1)
    sh[ys, xs] = True
    sh = binary_dilation(sh, iterations=1)
    return img, sh


def build(out, prefix, snow):
    imgs, shadows = [], []
    for dmg in (0, 1, 2):
        img, sh = render(base_model(dmg, snow), seed=dmg)
        imgs.append(img)
        shadows.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gun.shp'), W, H, imgs + shadows)

    tm = turret_model()
    timgs, tsh = [], []
    north = np.radians(225.0)                  # world direction drawn straight up on screen
    for k in range(32):
        a = north - np.radians(360.0 / 32 * k)   # counter-clockwise on screen
        img, sh = render(tm, angle=a, seed=k)
        timgs.append(img)
        tsh.append(np.where(sh, SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'guntur.shp'), W, H, timgs + tsh)

    # build-up: the drum rises from the ground, then the gun is assembled on it
    bm = base_model(0, snow)
    full = bm.occ.copy()
    bups, bsh = [], []
    for k in range(13):
        bm.occ = full & (bm.Z < 1.5 + 23.0 * min(k + 1, 7) / 7)
        img, sh = render(bm, seed=0)
        if k >= 7:
            tfull = tm.occ.copy()
            tm.occ = tfull & (tm.Z < 23.0 + 18.0 * (k - 6) / 6) if k < 12 else tfull
            ti, ts = render(tm, angle=north, seed=0)
            tm.occ = tfull
            img = np.where(ti > 0, ti, img)
            sh |= ts
        bups.append(img)
        bsh.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gunmk.shp'), W, H, bups + bsh)
    print('%sgun.shp / %sguntur.shp / %sgunmk.shp written' % (prefix, prefix, prefix))


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    build(out, 'gg', snow=False)      # temperate, urban, desert ... (generic)
    build(out, 'ga', snow=True)       # snow
