"""Coastal battery (GAGUN, 海岸炮) base art: python3 coastbattery.py OUTDIR

The base is drawn the way Red Alert 2 / Yuri's Revenge buildings are: big
simple shapes, saturated colours, strong light and dark, glossy steel and
large bright house-colour panels (the colour feel of the laser tower and
sentry tower), not the fine "realistic" detail of other mods. It is an
octagonal blue-grey concrete bastion on its own khaki sandbag ring, with a
red house-colour band, a steel door under a red panel and a glossy steel
turret ring on top. The turret itself is a voxel drawn by the game
(tools/voxplane/coastturret.py, TurretAnimIsVoxel=true) on that ring.

NewTheater=yes: GG* files are used on temperate/urban/desert maps, GA* on
snow maps. Canvas, frame layout and anchor are the ones of the original:
  g?gun.shp     155x171, 3 images (normal, damaged, heavily damaged) + 3 shadows
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
GROUND = np.array([76.5, 97.0])     # cell centre on the ground (original art)
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

TOP_Z = 29.0                        # top of the turret ring: the voxel turret stands here

CONCRETE = (178, 182, 194)          # Allied blue-grey concrete
CONCRETE_D = (118, 122, 138)
SNOW = (230, 234, 238)
BAG = (140, 132, 90)                # khaki sandbags, the laser tower's colour
BAG_D = (92, 86, 58)
STEEL = (150, 152, 178)             # glossy lavender steel, the laser tower's colour
STEEL_D = (86, 88, 112)
HOUSE = (190, 190, 190)


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


def base_model(damage=0, snow=False):
    m = Model(88, 34)
    X, Y, Z = m.X, m.Y, m.Z
    rr = np.hypot(X, Y)
    ang = np.arctan2(Y, X)
    u = (X - Y) / np.sqrt(2)
    v = (X + Y) / np.sqrt(2)
    # sandbag ring: two courses of big rounded bags (gap at the entrance)
    ring = (rr >= 27) & (rr <= 34.5)
    course = np.where(Z < 3.8, 0, 1)
    phase = (ang * 18 / (2 * np.pi) + 0.5 * course) % 1.0
    bulge = 1.0 - 4 * (phase - 0.5) ** 2
    ctop = np.where(course == 0, 3.8, 7.6)
    btop = ctop - 1.8 * (1 - bulge) ** 2 - 0.5 * np.clip(rr - 32.5, 0, 9)
    outer = 34.5 - 2.6 * (1 - bulge) ** 2 - 1.2 * course
    bags = ring & (Z < btop) & (rr <= outer) & ~((np.abs(u) < 7) & (v > 0))
    m.put(bags, BAG)
    m.paint(bags & ((phase < 0.09) | (phase > 0.91) | (np.abs(Z - 3.8) < 0.45)), BAG_D)
    if snow:
        m.paint(bags & (Z > btop - 1.3), SNOW)
    # bastion: chunky octagonal drum, dark plinth, bevelled top edge
    wall = octagon(X, Y, 26.0 - 0.08 * Z - np.clip(Z - 23.5, 0, 9) * 1.1) & (Z < 26)
    m.put(wall, CONCRETE)
    m.paint(wall & (Z < 3), CONCRETE_D)
    oct_ang = (ang + np.pi / 8) % (np.pi / 4)
    m.paint(wall & ((oct_ang < 0.035) | (oct_ang > np.pi / 4 - 0.035)) & (Z >= 3), CONCRETE_D)
    # big red house-colour band with dark edges
    outer_face = ~octagon(X, Y, 23.5)
    m.paint(wall & outer_face & (Z >= 15) & (Z < 21), HOUSE, remap=True)
    m.paint(wall & outer_face & ((np.abs(Z - 14.6) < 0.5) | (np.abs(Z - 21.4) < 0.5)), CONCRETE_D)
    # steel door on the south-east face under a red square, like the laser tower's
    m.cut((np.abs(u) < 5.0) & (v > 22.0) & (Z < 12) & (Z >= 3))
    door = (np.abs(u) < 5.0) & (v > 21.0) & (v < 23.0) & (Z >= 3) & (Z < 12)
    m.put(door, STEEL_D, metal=True)
    m.paint(door & (np.abs(u) < 4.0) & (Z >= 3.8) & (Z < 11.2), STEEL, metal=True)
    m.paint(door & (np.abs(Z - 7.5) < 0.5), STEEL_D)
    m.paint(wall & (np.abs(u) < 3.5) & (v > 20) & (Z >= 15) & (Z < 21), HOUSE, remap=True)
    # glossy steel turret ring on the top
    m.put((rr <= 18.5) & (Z >= 25) & (Z < TOP_Z), STEEL, metal=True)
    m.paint((rr > 17.2) & (Z >= 25) & (Z < TOP_Z), STEEL_D)
    m.paint((rr <= 18.5) & (Z >= TOP_Z - 1), (176, 178, 204))
    if snow:
        up = m.occ & ~np.roll(m.occ, -1, axis=2)
        m.paint(up & ~m.metal & (Z > 1), SNOW)
    if damage:
        rng = np.random.default_rng(11 + damage)
        chips = gaussian_filter((rng.random(m.occ.shape) < 0.04 * damage).astype(float), 1.3) > 0.08
        m.cut(wall & chips & (Z > 4) & outer_face)
        m.cut(bags & chips)
        scorch = gaussian_filter(rng.random(m.occ.shape), 3.5) > 0.5 - 0.02 * damage
        m.rgb[scorch & m.occ] *= 0.62 - 0.1 * damage
    return m


def normals(occ):
    f = gaussian_filter(occ.astype(np.float32), 1.0)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    return np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))


def render(model):
    """RA2-like shading: strong light/dark contrast, glossy metal, dark outline."""
    occ = model.occ
    nrm = normals(occ)[occ]
    k = np.zeros((7, 7, 7), np.float32)
    k[:, :, 3:] = 1
    ao = (convolve(occ.astype(np.float32), k, mode='constant') / k.sum())[occ]
    P = np.stack([model.X[occ], model.Y[occ], model.Z[occ]], -1)
    rgb = model.rgb[occ]
    rem = model.remap[occ]
    metal = model.metal[occ]
    lam = np.clip(nrm @ LIGHT, 0, 1)
    spec = np.clip(nrm @ HALF, 0, 1) ** 10 * np.where(metal, 0.6, 0.12)
    shade = (0.34 + 1.0 * lam) * (1.0 - 0.45 * np.clip(ao - 0.3, 0, 1))
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
    m = cov >= 0.45
    sil = m & binary_dilation(~m, iterations=1)
    avg[sil] *= 0.55
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


def top_units():
    """Height of the turret ring in voxel-turret world units (about 0.66 px each)."""
    return TOP_Z * PX_Z / 0.66


def build(out, prefix, snow):
    imgs, shadows = [], []
    for dmg in (0, 1, 2):
        img, sh = render(base_model(dmg, snow))
        imgs.append(img)
        shadows.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gun.shp'), W, H, imgs + shadows)
    bm = base_model(0, snow)
    full = bm.occ.copy()
    bups, bsh = [], []
    for k in range(13):
        bm.occ = full & (bm.Z < 1.5 + (TOP_Z - 1.5) * (k + 1) / 13)
        img, sh = render(bm)
        bups.append(img)
        bsh.append(np.where(sh & (img == 0), SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'gunmk.shp'), W, H, bups + bsh)
    print('%sgun.shp / %sgunmk.shp written; turret ring top at %.1f units' % (prefix, prefix, top_units()))


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    build(out, 'gg', snow=False)
    build(out, 'ga', snow=True)
