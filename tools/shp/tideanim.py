"""Tidal slam warhead animation, 3x3 cells: python3 tideanim.py OUT_DIR

  tidecat.shp  30 frames, 224x176, drawn centred on the impact point
  tidecat.pal  its own sea-water palette (Ares: CustomPalette=tidecat.pal)

What happens on screen: a column of water bursts out of the impact point and
throws spray, a crest of water rolls out to the edge of the 3x3 cells (a cell
is 60x30 px, so 90x45 px radius), the flooded ground behind it turns into a
whirlpool that spins while the targets are slowed, then the water drains away.
"""
import os
import sys

import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shpio import write_shp  # noqa: E402

W, H = 224, 176
CX, CY = W / 2, H / 2            # impact point (the game draws an anim centred on it)
RX, RY = 78.0, 39.0              # 3x3 cells (CellSpread=1.5 reaches ~64 px, corners 90 px)
N = 30
SS = 2                           # supersampling


def make_palette():
    """Index 0 transparent; ramps of deep sea -> teal -> cyan -> foam white."""
    keys_sea = [(0.0, (6, 16, 30)), (0.25, (12, 48, 78)), (0.5, (22, 104, 138)),
                (0.72, (60, 170, 196)), (0.88, (150, 222, 236)), (1.0, (252, 255, 255))]
    keys_foam = [(0.0, (10, 34, 36)), (0.35, (34, 110, 112)), (0.7, (110, 200, 190)), (1.0, (230, 252, 246))]

    def ramp(keys, n):
        t = np.linspace(0, 1, n)
        xs = [k[0] for k in keys]
        return np.stack([np.interp(t, xs, [k[1][c] for k in keys]) for c in range(3)], 1)
    pal = np.zeros((256, 3))
    pal[0] = (0, 0, 255)
    pal[1:161] = ramp(keys_sea, 160)
    pal[161:256] = ramp(keys_foam, 95)
    return np.clip(np.round(pal), 0, 255).astype(np.uint8)


class Canvas:
    def __init__(self):
        self.rgb = np.zeros((H * SS, W * SS, 3))
        self.a = np.zeros((H * SS, W * SS))
        self.Y, self.X = np.mgrid[0:H * SS, 0:W * SS] / SS

    def over(self, mask, col):
        """mask: alpha 0..1 array, col: rgb array broadcastable."""
        mask = np.clip(mask, 0, 1)
        self.rgb = self.rgb * (1 - mask[..., None]) + np.asarray(col, float) * mask[..., None]
        self.a = self.a + mask * (1 - self.a)

    def disc(self, x, y, r, col, soft=0.6):
        d = np.hypot(self.X - x, self.Y - y)
        self.over(np.clip((r - d) / soft + 0.5, 0, 1), col)

    def result(self):
        k = SS
        rgb = self.rgb.reshape(H, k, W, k, 3).mean((1, 3))
        a = self.a.reshape(H, k, W, k).mean((1, 3))
        return rgb, a


def lerp(a, b, t):
    return np.asarray(a, float) + (np.asarray(b, float) - a) * t


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


SEA_D = np.array([10, 44, 72.])
SEA_M = np.array([26, 108, 140.])
SEA_L = np.array([96, 196, 214.])
FOAM = np.array([236, 252, 250.])
LIGHT = np.array([-0.55, -0.65, 0.9])
LIGHT = LIGHT / np.linalg.norm(LIGHT)

_rng = np.random.default_rng(3)
WX = np.arange(-112, 112, 0.5)                 # world x = screen x offset (px)
WY = np.arange(112, -112, -0.5)                # world y (screen y = CY + y/2 - z), front first
GX, GY = np.meshgrid(WX, WY)
NOISE = [gaussian_filter(_rng.normal(size=GX.shape), s) for s in (6, 14)]
NOISE = [n / n.std() for n in NOISE]


def heightfield(tau):
    rho = np.hypot(GX, GY) / RX
    th = np.arctan2(GY, GX)
    grow = smooth(tau / 0.32)
    R = 0.08 + 0.92 * grow
    drain = smooth((tau - 0.6) / 0.42)
    n1, n2 = NOISE
    edge = R + 0.07 + 0.05 * n2 * (0.3 + grow)
    wet = rho < edge
    # drain: the water sinks and breaks up from the rim inwards
    wet &= (n2 * 0.18 + (1 - rho) * 0.7 + 0.3 - drain * 1.05) > 0
    level = 1.6 * (1 - drain)
    ripple = 0.3 * np.cos(30 * rho - 30 * tau + 0.6 * n1) * (1 - drain)
    eye_t = smooth((tau - 0.25) / 0.2) * (1 - drain)
    funnel = -14 * eye_t * np.exp(-(rho / 0.3) ** 2)
    ring_alive = 1 - smooth((tau - 0.42) / 0.25)
    hc = (16 * (1 - grow) + 6) * ring_alive
    d = rho - R
    w = np.where(d > 0, 0.05, 0.13)            # steep outer face, long back slope
    crest = hc * np.exp(-(d / w) ** 2) * (1 + 0.25 * n2)
    col_t = tau / 0.30
    jet = 0
    if col_t < 1:
        hj = 70 * np.sin(np.pi * min(col_t * 1.25, 1)) ** 0.6 * (1 - smooth((col_t - 0.7) / 0.3))
        r = np.hypot(GX, GY)
        jet = hj * np.exp(-(r / (7 + 10 * col_t)) ** 1.5) * (1 + 0.12 * n2)
    z = level + ripple + funnel + crest + jet
    spin = 3 * th + 9 * rho - 10 * tau * np.pi + 0.5 * n2
    arms = 0.5 + 0.5 * np.cos(spin)
    swirl = smooth((arms - 0.72) / 0.16) * smooth((rho - 0.1) / 0.12) * eye_t * (1 - 0.6 * drain)
    return z, wet, swirl, crest, hc, rho, funnel


def frame(k):
    tau = k / (N - 1)
    z, wet, swirl, crest, hc, rho, funnel = heightfield(tau)
    dzdx = np.gradient(z, axis=1) / 0.5
    dzdy = -np.gradient(z, axis=0) / 0.5
    nrm = np.stack([-dzdx, -dzdy, np.ones_like(z)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    diff = np.clip(nrm @ LIGHT, 0, 1)
    half = LIGHT + np.array([0, 0.6, 1.0])
    half /= np.linalg.norm(half)
    spec = np.clip(nrm @ half, 0, 1) ** 40
    base = SEA_D + (SEA_M - SEA_D) * np.clip(diff * 1.1, 0, 1)[..., None]
    base = base + (SEA_L - SEA_M) * np.clip((diff - 0.75) * 3, 0, 1)[..., None]
    slope = np.hypot(dzdx, dzdy)
    crestfoam = smooth((crest - 0.55 * hc) / (0.3 * hc + 1e-3)) if hc > 0.5 else 0 * z
    foam = np.clip(swirl * 0.95 + crestfoam + smooth((slope - 3.0) / 2.0) * 0.5 + smooth((z - 18) / 12), 0, 1)
    foam *= smooth((NOISE[0] + 2.0) / 1.5)
    col = base + (FOAM - base) * foam[..., None] + 255 * spec[..., None] * 0.7
    col = col * (1 - 0.55 * smooth(-funnel / 12))[..., None]
    col = np.clip(col, 0, 255)
    # voxel-space render: every screen column, front to back, drawing up to the horizon so far
    cv = Canvas()
    Hs, Ws = H * SS, W * SS
    img = np.zeros((Hs, Ws, 3))
    alpha = np.zeros((Hs, Ws))
    cols = ((WX + CX) * SS).astype(int)
    ybuf = np.full(len(WX), float(Hs))
    prev = np.full(len(WX), float(Hs))            # screen y of the sample in front (same column)
    prev_wet = np.zeros(len(WX), bool)
    for j in range(len(WY)):
        sy = (CY + WY[j] / 2 - z[j]) * SS
        ground = (CY + WY[j] / 2) * SS
        bottom = np.minimum(ybuf, np.maximum(np.where(prev_wet, prev, ground), sy + 1))
        m = wet[j] & (sy < ybuf)
        for c in np.nonzero(m)[0]:
            y0 = int(max(sy[c], 0))
            y1 = int(min(np.ceil(bottom[c]), Hs))
            if y1 > y0:
                span = y1 - y0
                shade = np.ones(span)
                if span > 2:                            # a side face: darker water going down
                    shade[1:] = np.linspace(0.78, 0.5, span - 1)
                c3 = col[j, c][None, :] * shade[:, None] + SEA_D[None, :] * (1 - shade[:, None]) * 0.6
                for cc in (cols[c], cols[c] + 1):
                    if 0 <= cc < Ws:
                        img[y0:y1, cc] = c3
                        alpha[y0:y1, cc] = 1
        ybuf = np.where(m, np.minimum(ybuf, sy), ybuf)
        prev, prev_wet = sy, wet[j]
    cv.rgb, cv.a = img, alpha
    # spray: drops thrown by the burst and off the crest
    rng = np.random.default_rng(5)
    drops = 160
    ang = rng.uniform(0, 2 * np.pi, drops)
    spd = rng.uniform(0.3, 1.0, drops)
    vz = rng.uniform(50, 105, drops)
    t0 = rng.uniform(0, 0.12, drops)
    size = rng.uniform(0.8, 2.2, drops)
    for jd in np.argsort(np.sin(ang)):
        tt = (tau - t0[jd]) * 1.9
        if tt <= 0:
            continue
        r = spd[jd] * min(tt, 1.0)
        zz = vz[jd] * tt - 150 * tt * tt
        if zz < -1:
            continue
        x = CX + r * RX * np.cos(ang[jd])
        y = CY + r * RY * np.sin(ang[jd]) - zz
        cv.disc(x, y, size[jd] * (1 - 0.35 * tt), SEA_L + (FOAM - SEA_L) * np.clip(zz / 40, 0, 1))
    if hc > 3:
        R = 0.08 + 0.92 * smooth(tau / 0.32)
        rs = np.random.default_rng(100 + k)
        for a in rs.uniform(0, 2 * np.pi, 60):
            x = CX + R * RX * np.cos(a) + rs.normal(0, 1.5)
            y = CY + R * RY * np.sin(a) - hc * rs.uniform(1.0, 1.4)
            cv.disc(x, y, rs.uniform(0.7, 1.5), FOAM)
    return cv.result()


def quantize(rgb, a, pal):
    idx = np.zeros(a.shape, np.uint8)
    m = a > 0.45
    p = pal[1:].astype(float)
    c = rgb[m] / np.maximum(a[m, None], 1e-3) * np.minimum(a[m, None] * 1.3, 1)   # premultiplied edges
    d = ((c[:, None, :] - p[None, :, :]) ** 2).sum(2)
    idx[m] = 1 + np.argmin(d, 1)
    return idx


def main(out):
    os.makedirs(out, exist_ok=True)
    pal = make_palette()
    frames = [quantize(*frame(k), pal) for k in range(N)]
    write_shp(os.path.join(out, 'tidecat.shp'), W, H, frames)
    with open(os.path.join(out, 'tidecat.pal'), 'wb') as f:
        f.write((pal >> 2).astype(np.uint8).tobytes())           # .pal stores 6-bit values
    return frames, pal


if __name__ == '__main__':
    main(sys.argv[1])
