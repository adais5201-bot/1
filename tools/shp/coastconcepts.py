"""Coastal gun concepts to choose from: python3 coastconcepts.py SCREENSHOT OUT.png

Four designs in the style of the defences around it in the game (dark
gunmetal, house-colour armour plates, chunky shapes, bright edge highlights),
each rendered as building art (base and turret on one canvas, so what the
preview shows is what the game shows) and pasted into an in-game screenshot
at the coastal gun's place, in green house colour.
"""
import os
import sys

import numpy as np
from scipy.ndimage import binary_dilation, convolve, gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'voxplane'))
from builder import to_index                      # noqa: E402
from shpio import palette, to_rgb                 # noqa: E402
from coastbattery import Model, octagon           # noqa: E402

W, H = 155, 171
GROUND = np.array([76.5, 97.0])
VOX = 48.0                    # a little bigger than the old 1x1 gun, like its neighbours
PX_X = np.array([30.0, 15.0]) / VOX
PX_Y = np.array([-30.0, 15.0]) / VOX
PX_Z = 36.9 / VOX
SS = 4
LIGHT = np.array([-0.50, -0.40, 0.77])
LIGHT /= np.linalg.norm(LIGHT)
VIEW = np.array([0.62, 0.62, 0.48])
VIEW /= np.linalg.norm(VIEW)
HALF = (LIGHT + VIEW) / np.linalg.norm(LIGHT + VIEW)

GUN = (96, 100, 112)          # gunmetal of the neighbouring defences
GUN_D = (56, 58, 68)
GUN_L = (150, 156, 170)
CONC = (146, 146, 150)
CONC_D = (100, 100, 106)
BAG = (128, 118, 80)
BAG_D = (84, 76, 50)
DARK = (30, 32, 38)
HOUSE = (190, 190, 190)


def render(model, angle=0.0):
    occ = model.occ
    f = gaussian_filter(occ.astype(np.float32), 1.0)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    nrm = np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))[occ]
    k = np.zeros((7, 7, 7), np.float32)
    k[:, :, 3:] = 1
    ao = (convolve(occ.astype(np.float32), k, mode='constant') / k.sum())[occ]
    local = (convolve(occ.astype(np.float32), np.ones((3, 3, 3), np.float32), mode='constant') / 27.0)[occ]
    P = np.stack([model.X[occ], model.Y[occ], model.Z[occ]], -1)
    rgb, rem, metal = model.rgb[occ], model.remap[occ], model.metal[occ]
    ca, sa = np.cos(angle), np.sin(angle)
    R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])
    P, nrm = P @ R.T, nrm @ R.T
    lam = np.clip(nrm @ LIGHT, 0, 1)
    spec = np.clip(nrm @ HALF, 0, 1) ** 14 * np.where(metal, 0.35, 0.06)
    edge = np.clip((0.55 - local) * 1.4, 0, 0.25)              # bright worn edges
    shade = (0.3 + 0.78 * lam) * (1.0 - 0.5 * np.clip(ao - 0.3, 0, 1)) * (1 + edge)
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
    avg[sil] *= 0.5
    remap = rbuf.reshape(H, SS, W, SS).mean((1, 3)) > 0.5
    img = np.zeros((H, W), np.uint8)
    img[m] = to_index(avg[m], remap[m])
    G = P.copy()
    G[:, 0] += P[:, 2] * 0.9
    G[:, 1] += P[:, 2] * 0.35
    s = GROUND + G[:, 0:1] * PX_X + G[:, 1:2] * PX_Y
    sh = np.zeros((H, W), bool)
    sh[np.clip(np.round(s[:, 1]).astype(int), 0, H - 1), np.clip(np.round(s[:, 0]).astype(int), 0, W - 1)] = True
    return img, binary_dilation(sh, iterations=1)


# ------------------------------------------------------------------ bases
def base_steel():
    """stepped octagonal steel platform with house-colour corner plates"""
    m = Model(80, 22)
    X, Y, Z = m.X, m.Y, m.Z
    ang = np.arctan2(Y, X)
    step1 = octagon(X, Y, 27 - 0.3 * Z) & (Z < 4)
    step2 = octagon(X, Y, 21) & (Z >= 4) & (Z < 13)
    m.put(step1, CONC)
    m.paint(step1 & (Z < 1.5), CONC_D)
    m.put(step2, GUN, metal=True)
    m.paint(step2 & (Z >= 12), GUN_L)
    for a in np.arange(4) * np.pi / 2 + np.pi / 4:                  # corner armour plates
        cx, cy = 22 * np.cos(a), 22 * np.sin(a)
        u = (X - cx) * np.cos(a) + (Y - cy) * np.sin(a)
        v = -(X - cx) * np.sin(a) + (Y - cy) * np.cos(a)
        plate = (np.abs(v) < 3.2) & (u > -6) & (u < 5) & (Z < 7 - 0.6 * np.clip(u, 0, None))
        m.put(plate, HOUSE, remap=True)
    oct_ang = (ang + np.pi / 8) % (np.pi / 4)
    m.paint(step2 & ((oct_ang < 0.05) | (oct_ang > np.pi / 4 - 0.05)), GUN_D)
    return m, 13.0


def base_pit():
    """sandbag ring round a concrete pad"""
    m = Model(80, 16)
    X, Y, Z = m.X, m.Y, m.Z
    rr, ang = np.hypot(X, Y), np.arctan2(Y, X)
    m.put(octagon(X, Y, 22) & (Z < 3), CONC)
    ring = (rr >= 22) & (rr <= 29)
    course = np.where(Z < 3.8, 0, 1)
    phase = (ang * 18 / (2 * np.pi) + 0.5 * course) % 1.0
    bulge = 1.0 - 4 * (phase - 0.5) ** 2
    ctop = np.where(course == 0, 3.8, 7.6)
    top = ctop - 1.8 * (1 - bulge) ** 2
    outer = 29 - 2.4 * (1 - bulge) ** 2 - 1.2 * course
    bags = ring & (Z < top) & (rr <= outer)
    m.put(bags, BAG)
    m.paint(bags & ((phase < 0.09) | (phase > 0.91) | (np.abs(Z - 3.8) < 0.45)), BAG_D)
    m.put((rr <= 10) & (Z >= 3) & (Z < 4.5), GUN_D, metal=True)
    return m, 3.0


# ------------------------------------------------------------------ turrets
def barrel(m, z, y=0.0, r=2.6, x0=12, x1=58, brake=True):
    X, Y, Z = m.X, m.Y, m.Z
    rr = np.hypot(Y - y, Z - z)
    m.put((X > x0) & (X <= x1) & (rr <= r - 0.01 * (X - x0)), GUN, metal=True)
    m.put((X > x0) & (X <= x0 + 8) & (rr <= r + 0.8), GUN_D, metal=True)
    if brake:
        m.put((X > x1 - 4) & (X <= x1) & (rr <= r + 0.9), GUN_D, metal=True)
        m.cut((X > x1 - 1) & (rr <= r - 1.0))


def turret_heavy(z0):
    m = Model(130, int(z0) + 22)
    X, Y, Z = m.X, m.Y, m.Z
    body = (((X + 2) / 17) ** 2 + (Y / 15) ** 2 + ((Z - z0) / 12) ** 2 <= 1) & (Z >= z0)
    m.put(body, GUN, metal=True)
    m.paint(body & (np.abs(Y) > 11) & (Z > z0 + 2) & (Z < z0 + 6) & (X < 8), HOUSE, remap=True)
    m.paint(body & (Z > z0 + 10.5), GUN_L)
    m.put((np.hypot(X + 8, Y - 5) <= 3) & (Z >= z0 + 9) & (Z < z0 + 12.5), GUN_D, metal=True)
    m.put((X > 10) & (X <= 17) & (np.abs(Y) <= 5) & (np.abs(Z - (z0 + 6)) <= 4.5), GUN_D, metal=True)
    barrel(m, z0 + 6.5, r=3.0, x0=14, x1=60)
    return m


def turret_twin(z0):
    m = Model(130, int(z0) + 20)
    X, Y, Z = m.X, m.Y, m.Z
    hw = 15.0 - 0.1 * np.clip(X, 0, None) - 0.3 * np.clip(Z - z0 - 5, 0, None)
    top = z0 + 11 - 0.5 * np.clip(X - 8, 0, None)
    house = (X >= -16) & (X <= 16) & (np.abs(Y) <= hw) & (Z >= z0) & (Z < top)
    m.put(house, GUN, metal=True)
    m.paint(house & (Z >= top - 1), GUN_L)
    m.paint(house & (np.abs(Y) > hw - 1.5) & (X > -12) & (X < 8) & (Z > z0 + 3) & (Z < z0 + 7.5), HOUSE, remap=True)
    m.put((np.abs(X + 12) <= 2) & (np.abs(Y) <= 18) & (Z >= top - 2) & (Z < top + 1.5), GUN_D, metal=True)
    for y in (-5, 5):
        barrel(m, z0 + 5.5, y=y, r=2.2, x0=15, x1=58)
    return m


def turret_shield(z0):
    m = Model(130, int(z0) + 24)
    X, Y, Z = m.X, m.Y, m.Z
    m.put((np.hypot(X, Y) <= 7) & (Z >= z0) & (Z < z0 + 6), GUN_D, metal=True)       # pedestal
    m.put((np.abs(X + 2) <= 8) & (np.abs(Y) <= 5) & (Z >= z0 + 6) & (Z < z0 + 11), GUN, metal=True)   # cradle
    ang = np.arctan2(Y, X - 2)
    rr = np.hypot(X - 2, Y)
    shield = (rr >= 12) & (rr <= 14) & (np.abs(ang) < 1.25) & (Z >= z0 + 1) & (Z < z0 + 17 - 0.1 * np.abs(Y))
    m.put(shield, GUN, metal=True)
    m.paint(shield & (Z >= z0 + 7) & (Z < z0 + 12), HOUSE, remap=True)
    m.paint(shield & (Z >= z0 + 15.5), GUN_L)
    m.cut((rr >= 11) & (rr <= 15) & (np.abs(Y) <= 3.2) & (np.abs(Z - (z0 + 10)) <= 3.2))
    barrel(m, z0 + 10, r=2.6, x0=2, x1=56)
    return m


def turret_dome(z0):
    m = Model(130, int(z0) + 22)
    X, Y, Z = m.X, m.Y, m.Z
    dome = ((X / 18) ** 2 + (Y / 18) ** 2 + ((Z - z0) / 13) ** 2 <= 1) & (Z >= z0)
    m.put(dome, GUN, metal=True)
    m.paint(dome & (Z >= z0 + 2) & (Z < z0 + 5.5), HOUSE, remap=True)
    m.paint(dome & (Z > z0 + 11), GUN_L)
    m.cut((X > 8) & (np.abs(Y) <= 3.5) & (np.abs(Z - (z0 + 7)) <= 3.5))                # gun slot
    m.put((np.hypot(X + 6, Y + 6) <= 3) & (Z >= z0 + 10) & (Z < z0 + 14), GUN_D, metal=True)   # periscope
    barrel(m, z0 + 7, r=2.8, x0=6, x1=58)
    return m


CONCEPTS = [
    ('A 重型单管炮塔', base_steel, turret_heavy),
    ('B 双联装甲炮塔', base_steel, turret_twin),
    ('C 炮盾海岸炮', base_pit, turret_shield),
    ('D 穹顶碉堡炮', base_steel, turret_dome),
]


def building(base_fn, tur_fn, facing):
    bm, top = base_fn()
    bimg, bsh = render(bm)
    timg, tsh = render(tur_fn(top), np.radians(225.0) - np.radians(360.0 / 32 * facing))
    img = np.where(timg > 0, timg, bimg)
    return img, (bsh | tsh) & (img == 0)


def main(shot, out):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 26)
    pal = palette()
    scr = np.array(Image.open(shot).convert('RGB')).astype(float)
    # the old coastal gun (floating turret and its base) is covered with sand
    x0, y0, x1, y1 = 690, 592, 792, 680
    sand = scr[612:652, 540:600]                      # plain sand west of the pillbox
    rng = np.random.default_rng(1)
    for yy in range(y0, y1, 8):                       # tile it with random offsets, soft edges
        for xx in range(x0, x1, 8):
            sy, sx = rng.integers(0, sand.shape[0] - 8), rng.integers(0, sand.shape[1] - 8)
            hh, ww = min(8, y1 - yy), min(8, x1 - xx)
            scr[yy:yy + hh, xx:xx + ww] = sand[sy:sy + hh, sx:sx + ww]
    scr[y0 - 3:y1 + 3, x0 - 3:x1 + 3] = gaussian_filter(scr[y0 - 3:y1 + 3, x0 - 3:x1 + 3], (0.8, 0.8, 0))
    anchor = np.array([722, 664])                     # cell centre of the coastal gun on the ground
    tiles = []
    for name, bf, tf in CONCEPTS:
        img, sh = building(bf, tf, 22)
        rgb = to_rgb(img, pal, remap=(40, 190, 60)).astype(float)
        view = scr.copy()
        ox, oy = (anchor - GROUND).astype(int)
        sub = view[oy:oy + H, ox:ox + W]
        sub[sh] *= 0.55
        m = img > 0
        sub[m] = rgb[m]
        crop = view[540:780, 520:980]
        im = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).resize((920, 480), Image.NEAREST)
        t = Image.new('RGB', (920, 520), (16, 16, 16))
        t.paste(im, (0, 40))
        ImageDraw.Draw(t).text((10, 6), name, font=font, fill=(255, 230, 90))
        tiles.append(t)
    sheet = Image.new('RGB', (2 * 926, 2 * 526), (8, 8, 8))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * 926, (i // 2) * 526))
    sheet.save(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
