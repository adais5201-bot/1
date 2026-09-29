"""Coastal battery (GAGUN, 海岸炮) artwork: python3 coastbattery.py OUTDIR MOD_DIR

Base: the laser tower's base art (gghail / gahail: sandbag ring and steel
dome, with its build-up), copied so the battery belongs to the same family
as the mod's other defences. Turret: a heavy twin-gun armoured turret
(glossy lavender-grey steel like the laser/sentry towers, red house-colour
side panels, rangefinder hood, blast bags, long barrels) built as a voxel
model and rendered onto the same 250x250 canvas and anchor, sitting on the
dome: 32 facings (0 = north, counter-clockwise) + 32 shadows.

NewTheater=yes: GG* files are used on temperate/urban/desert maps, GA* on
snow maps. The firing position (artmd PrimaryFireFLH) follows the barrels.
"""
import os
import sys

import numpy as np
from scipy.ndimage import binary_dilation, convolve, gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'voxplane'))
from builder import to_index                      # noqa: E402
from shpio import write_shp                       # noqa: E402

W, H = 250, 250                     # canvas of the laser tower base the gun now stands on
GROUND = np.array([124.0, 136.5])   # cell centre on the ground (canvas centre + (-1, +11.5), as the 155x171 original)
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
PIT_Z = 30.0                        # top of the laser tower's dome (17.5 px above the ground)
BARREL_Z = PIT_Z + 9.0
MUZZLE_X = 64.0
BARREL_Y = 4.6

SNOW = (226, 230, 234)
# colours of the mod's other defences: khaki-olive sandbags and the
# lavender-grey steel of the laser tower / sentry tower
STEEL = (134, 138, 154)
STEEL_D = (84, 88, 106)
STEEL_L = (178, 182, 198)
CANVAS = (92, 84, 62)
DARK = (34, 36, 38)
HOUSE = (180, 180, 180)


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


def noise(shape, sigma, seed):
    rng = np.random.default_rng(seed)
    f = gaussian_filter(rng.standard_normal(shape), sigma)
    return f / (f.std() + 1e-9)


# ------------------------------------------------------------------ turret
def turret_model(snow=False):
    m = Model(140, int(PIT_Z) + 24)
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
    m.shade(m.occ & ~m.remap & (grime > 1.8), 0.92)
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
    # broad glossy highlight on metal, like the pre-rendered defences
    spec = np.clip(nrm @ HALF, 0, 1) ** 8 * np.where(metal, 0.5, 0.08)
    wear = np.clip((0.55 - local) * 1.2, 0, 0.25)             # convex edges catch light
    rng = np.random.default_rng(seed)
    grain = 1 + 0.01 * rng.standard_normal(len(P))           # smooth shading, no grain
    shade = (0.5 + 0.85 * lam) * (1.0 - 0.45 * np.clip(ao - 0.3, 0, 1)) * (1 + wear) * grain
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
    avg[sil] *= 0.8
    avg[crease & m & ~sil] *= 0.92
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


def build(out, src, prefix, snow):
    """Base: the laser tower's base art (sandbag ring and steel dome, both
    theaters, with its build-up), so the battery matches the mod's other
    defences; the twin-gun turret is rendered onto the same canvas."""
    import shutil
    base = 'gahail' if snow else 'gghail'
    shutil.copyfile(os.path.join(src, base + '.shp'), os.path.join(out, prefix + 'gun.shp'))
    shutil.copyfile(os.path.join(src, base + 'mk.shp'), os.path.join(out, prefix + 'gunmk.shp'))
    tm = turret_model(snow)
    timgs, tsh = [], []
    north = np.radians(225.0)
    for k in range(32):
        a = north - np.radians(360.0 / 32 * k)
        img, sh = render(tm, angle=a, seed=k)
        timgs.append(img)
        tsh.append(np.where(sh, SHADOW_INDEX, 0).astype(np.uint8))
    write_shp(os.path.join(out, prefix + 'guntur.shp'), W, H, timgs + tsh)
    print('%sgun / %sgunmk from %s, %sguntur rendered; PrimaryFireFLH=%d,%d,%d'
          % ((prefix, prefix, base, prefix) + firing_flh()))


if __name__ == '__main__':
    out, src = sys.argv[1], sys.argv[2]      # OUTDIR, folder with gghail*.shp / gahail*.shp
    os.makedirs(out, exist_ok=True)
    build(out, src, 'gg', snow=False)
    build(out, src, 'ga', snow=True)
