"""Coastal gun (GAGUN) built from the mod's own China Cannon art (GAGCNN_A).

The China Cannon stands next to the coastal gun in every allied base and is a
prerendered 1x1 turret with the look of the other defences. Its 32 facings are
reused pixel for pixel, the single gun is turned into two side-by-side guns,
and the armour gets a scheme of its own, so lighting, normals and outlines stay
those of the original art.

  python3 coasttwin.py SRC_DIR OUT_DIR [scheme]   write gg/ga gun, guntur, gunmk
  python3 coasttwin.py SRC_DIR --preview SHOT OUT  concept sheet in a screenshot

SRC_DIR holds gggcnn_a.shp and gggcnnmk.shp (from the mod's own files).
"""
import os
import sys

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shpio import palette, read_shp, to_rgb, write_shp  # noqa: E402

C = np.array([99.5, 99.7])     # gun trunnion on screen (200x200 canvas), fitted on the side views
TIP = 57.5                     # muzzle distance from C for a gun seen side-on
R0 = 30.0                      # the barrel leaves the mantlet here
HALF = 2.6                     # barrel half width (px)
SEP = 4.5                      # half spacing of the two guns, same units as TIP
SHIFT = (-23, -30)             # 2x2 art canvas 200x200 -> 1x1 canvas 155x171 (footprint centre)
W1, H1 = 155, 171


def u(i):
    """Screen direction of facing i (0 = north, counter-clockwise), iso: y halved."""
    a = np.radians(i * 11.25)
    return np.array([-np.sin(a), -0.5 * np.cos(a)])


def band(i, off=np.zeros(2), shape=(200, 200)):
    """Pixels within HALF of the barrel axis of facing i, shifted by off."""
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    v = np.stack([xs - C[0] - off[0], ys - C[1] - off[1]], -1)
    d = u(i)
    L = np.hypot(*d)
    dn = d / L
    t = v @ dn
    q = v @ np.array([-dn[1], dn[0]])
    return (t >= R0 * L) & (t <= TIP * L + 0.5) & (np.abs(q) <= HALF)


def twin(img, i, base):
    """Replace the single barrel of facing i by two guns side by side."""
    turret = (img != base) & (img > 0)
    B = band(i) & (img > 0) & (turret | (base == 0))
    s = SEP * u(i + 8)                                  # lateral offset (perpendicular in the world)
    away = np.cos(np.radians(i * 11.25)) > 0.2         # gun points away: the house hides its root
    out = img.copy()
    body = turret & ~B
    # take the barrel out and close the hole from what surrounds it
    hole = B.copy()
    keep = ~hole
    idx = ndimage.distance_transform_edt(~keep, return_distances=False, return_indices=True)
    fill = img[idx[0], idx[1]]
    near_body = body[idx[0], idx[1]]
    out[hole] = np.where(near_body[hole], fill[hole], base[hole])
    ys, xs = np.nonzero(B)
    order = sorted([s, -s], key=lambda o: o[1])        # far gun (higher on screen) first
    for o in order:
        ox, oy = int(round(o[0])), int(round(o[1]))
        ty, tx = ys + oy, xs + ox
        ok = (ty >= 0) & (ty < img.shape[0]) & (tx >= 0) & (tx < img.shape[1])
        ty, tx, sy, sx = ty[ok], tx[ok], ys[ok], xs[ok]
        if away:                                        # behind the gun house: do not paint over it
            vis = ~body[ty, tx]
            ty, tx, sy, sx = ty[vis], tx[vis], sy[vis], sx[vis]
        out[ty, tx] = img[sy, sx]
    return out


def twin_shadow(sh, i):
    """Shadow frames: add the second gun's shadow next to the first one."""
    s = SEP * u(i + 8) * 2.0 * 0.6
    far = np.zeros_like(sh, bool)
    ys, xs = np.nonzero(sh)
    if len(ys):
        cy, cx = ys.mean(), xs.mean()
        far[ys, xs] = np.hypot(xs - cx, (ys - cy) * 2) > 26
    moved = ndimage.shift(far.astype(float), (s[1], s[0]), order=0) > 0.5
    out = sh.copy()
    out[moved & (out == 0)] = sh.max() or 1
    return out


def scheme_map(pal, name):
    """Palette index map recolouring the purple armour."""
    m = np.arange(256)
    if name == 'purple':
        return m
    rgb = pal.astype(float)
    mx, mn = rgb.max(1), rgb.min(1)
    sat = (mx - mn) / np.maximum(mx, 1)
    purple = (rgb[:, 2] > rgb[:, 1] + 8) & (rgb[:, 0] > rgb[:, 1] - 4) & (sat > 0.12)
    purple[:32] = False                                  # keep index 0..15 specials and the remap range
    lum = rgb @ [0.3, 0.59, 0.11]
    if name == 'steel':
        target = [80, 84, 88]                            # neutral gunmetal, like the base domes
        tint = np.array([1.0, 1.02, 1.08])
    elif name == 'olive':
        target = None
        tint = np.array([1.0, 1.0, 0.72])
    cand = np.nonzero((sat < 0.35) & (np.arange(256) >= 32) & (lum > 8))[0]
    for k in np.nonzero(purple)[0]:
        want = lum[k] * 1.05 * tint
        if name == 'olive':
            want = lum[k] * np.array([0.95, 1.0, 0.68]) * 1.05
        d = ((rgb[cand] - want) ** 2).sum(1)
        m[k] = cand[np.argmin(d)]
    return m


def hatch_remap(img, base):
    """The two yellow roof hatches take the house colour."""
    rgbp = palette().astype(float)
    y = (rgbp[:, 0] > 150) & (rgbp[:, 1] > 90) & (rgbp[:, 2] < 90) & (rgbp[:, 0] > rgbp[:, 1] + 20)
    y[:32] = False
    out = img.copy()
    m = y[img] & (img != base)
    lum = (rgbp[img[m]] @ [0.3, 0.59, 0.11])
    out[m] = (16 + np.clip((255 - lum) / 255 * 15, 0, 15)).astype(np.uint8)
    return out


def build(src, scheme='steel', hatches=True):
    s = read_shp(os.path.join(src, 'gggcnn_a.shp'))
    A = np.array([f['img'] for f in s['frames']])
    base = np.array([np.bincount(A[:32, y, x], minlength=256).argmax()
                     for y in range(200) for x in range(200)], np.uint8).reshape(200, 200)
    pal = palette()
    cmap = scheme_map(pal, scheme).astype(np.uint8)
    frames = []
    for k in range(64):                                  # 32 normal + 32 damaged
        i = k % 32
        f = twin(A[k], i, base)
        turret = (f != base) & (f > 0)
        g = f.copy()
        g[turret] = cmap[f[turret]]
        if hatches:
            g = hatch_remap(g, base)
        frames.append(g)
    shadows = [twin_shadow(A[64 + k], k % 32) for k in range(64)]
    return frames, shadows


def recanvas(img):
    out = np.zeros((H1, W1), np.uint8)
    dx, dy = SHIFT
    src = img[max(0, -dy):, max(0, -dx):]
    h, w = min(H1, src.shape[0]), min(W1, src.shape[1])
    out[:h, :w] = src[:h, :w]
    return out


def write_all(src, out, scheme):
    frames, shadows = build(src, scheme)
    os.makedirs(out, exist_ok=True)
    norm, dmg = [recanvas(f) for f in frames[:32]], [recanvas(f) for f in frames[32:]]
    sn, sd = [recanvas(f) for f in shadows[:32]], [recanvas(f) for f in shadows[32:]]
    empty = [np.zeros((H1, W1), np.uint8)] * 6           # the base lives in the turret animation
    mk = read_shp(os.path.join(src, 'gggcnnmk.shp'))
    mkf = [recanvas(f['img']) for f in mk['frames']]
    for th in ('gg', 'ga'):
        write_shp(os.path.join(out, th + 'gun.shp'), W1, H1, empty)
        write_shp(os.path.join(out, th + 'guntur.shp'), W1, H1, norm + sn)
        write_shp(os.path.join(out, th + 'guntud.shp'), W1, H1, dmg + sd)
        write_shp(os.path.join(out, th + 'gunmk.shp'), W1, H1, mkf)
    return frames, shadows


def preview(src, shot, outpath):
    from PIL import Image, ImageDraw, ImageFont
    from scipy.ndimage import gaussian_filter
    font = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 26)
    pal = palette()
    scr = np.array(Image.open(shot).convert('RGB')).astype(float)
    # take the old coastal gun out of the shot: harmonic fill from the terrain round it
    H, W = scr.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    hole = (((xx >= 694) & (xx <= 791) & (yy >= 598) & (yy <= 621)) |
            ((xx >= 694) & (xx <= 773) & (yy >= 621) & (yy <= 637)) |
            (((xx - 723) / 31.0) ** 2 + ((yy - 654) / 21.0) ** 2 <= 1))
    known = scr.copy()
    for _ in range(600):
        avg = (np.roll(known, 1, 0) + np.roll(known, -1, 0) + np.roll(known, 1, 1) + np.roll(known, -1, 1)) / 4
        known[hole] = avg[hole]
    rng = np.random.default_rng(1)
    grain = gaussian_filter(rng.normal(0, 9, scr.shape[:2]), 0.7)[..., None]
    scr[hole] = known[hole] + grain[hole]
    anchor = np.array([722, 664])
    ground = np.array([99, 126])                          # footprint centre in the 200x200 canvas
    concepts = [('A 双管 · 原色紫灰装甲', 'purple', False),
                ('B 双管 · 炮钢灰装甲 + 国家色舱盖', 'steel', True),
                ('C 双管 · 橄榄灰装甲 + 国家色舱盖', 'olive', True),
                ('D 双管 · 原色装甲 + 国家色舱盖', 'purple', True)]
    tiles = []
    for name, sch, hat in concepts:
        frames, shadows = build(src, sch, hat)
        view = scr.copy()
        for fac, anc in ((22, anchor),):
            img, sh = frames[fac], shadows[fac] > 0
            rgb = to_rgb(img, pal, remap=(40, 190, 60)).astype(float)
            ox, oy = (anc - ground).astype(int)
            sub = view[oy:oy + 200, ox:ox + 200]
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
    sheet.save(outpath)


if __name__ == '__main__':
    if sys.argv[2] == '--preview':
        preview(sys.argv[1], sys.argv[3], sys.argv[4])
    else:
        write_all(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'steel')
