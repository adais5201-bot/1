"""Preview renderer: lit orthographic top/side/front views and an RA2-like
isometric view, using the voxel normals the way the game does."""
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_erosion

from builder import NORMALS, PALETTE
from vxlio import read_hva, read_vxl

LIGHT = np.array([0.35, -0.55, 0.76])   # from front-left, high
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def remap_rgb(idx):
    col = PALETTE[idx].astype(float)
    rm = (idx >= 16) & (idx <= 31)
    k = (idx[rm] - 16) / 15.0
    col[rm] = np.stack([220 * (1 - k * 0.8), 40 * (1 - k), 40 * (1 - k)], -1)   # red house colour
    return col


def points(sections, mats, frame=0):
    P, C, N = [], [], []
    for i, s in enumerate(sections):
        surf = s.filled & ~binary_erosion(s.filled, border_value=0)
        idx = np.argwhere(surf)
        span = (s.maxb - s.minb) / np.array(s.size)
        p = (idx + 0.5) * span + s.minb
        M = mats[min(frame, len(mats) - 1)][i]
        R = M[:, :3]
        t = M[:, 3] * s.scale * span
        P.append(p @ R.T + t)
        C.append(s.color[surf])
        N.append(NORMALS[np.clip(s.normal[surf], 0, 243)] @ R.T)
    return np.concatenate(P), np.concatenate(C), np.concatenate(N)


def draw(P, C, N, rot, px, W, H, bg=(48, 64, 80)):
    Q = P @ rot.T
    Nr = N @ rot.T
    L = LIGHT @ rot.T
    shade = 0.45 + 0.75 * np.clip(Nr @ L, 0, 1)
    col = remap_rgb(C) * shade[:, None]
    order = np.argsort(Q[:, 2])
    img = np.zeros((H, W, 3))
    img[:] = bg
    u = (Q[:, 0] * px + W / 2).astype(int)
    v = (-Q[:, 1] * px + H / 2).astype(int)
    k = max(1, int(np.ceil(px))) + 1
    for dy in range(k):
        for dx in range(k):
            uu, vv = u[order] + dx, v[order] + dy
            ok = (uu >= 0) & (uu < W) & (vv >= 0) & (vv < H)
            img[vv[ok], uu[ok]] = col[order][ok]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def rotz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rotx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


# view matrices map model (x fwd, y right, z up) -> screen (u right, v up, depth toward viewer)
TOP = np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1]], float)            # nose up
SIDE = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], float)          # nose left, seen from right? (y toward viewer)
FRONT = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float)


def iso(facing_deg):
    # RA2 camera: ~30 deg elevation dimetric-like
    return rotx(-np.radians(60)) @ rotz(np.radians(facing_deg)) @ np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], float)


def sheet(models, out, px=3.0, title=True):
    rows = []
    for name, sections, mats in models:
        P, C, N = points(sections, mats)
        ext = np.abs(P).max(0) + 4
        Wt = int(2 * max(ext[0], ext[1]) * px)
        top = draw(P, C, N, TOP, px, Wt, Wt)
        side = draw(P, C, N, SIDE, px, Wt, int(Wt * 0.42))
        front = draw(P, C, N, FRONT, px, Wt, int(Wt * 0.42))
        isos = [draw(P, C, N, iso(a), px * 0.9, int(Wt * 0.62), int(Wt * 0.62)) for a in (30, 135, 250)]
        W = top.width + side.width + 3 * isos[0].width + 20
        H = max(top.height, side.height + front.height + 6) + 18
        im = Image.new('RGB', (W, H), (20, 20, 20))
        im.paste(top, (0, 18))
        im.paste(side, (top.width + 6, 18))
        im.paste(front, (top.width + 6, 24 + side.height))
        x0 = top.width + side.width + 12
        for k, iv in enumerate(isos):
            im.paste(iv, (x0 + k * (iv.width + 2), 18))
        if title:
            ImageDraw.Draw(im).text((4, 3), name, fill=(255, 255, 0))
        rows.append(im)
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows)
    S = Image.new('RGB', (W, H), (20, 20, 20))
    y = 0
    for r in rows:
        S.paste(r, (0, y))
        y += r.height
    S.save(out)


def load(path_noext):
    v = read_vxl(path_noext + '.vxl')
    h = read_hva(path_noext + '.hva')
    return v['sections'], h['mats']


if __name__ == '__main__':
    out = sys.argv[1]
    models = []
    for p in sys.argv[2:]:
        s, m = load(p)
        models.append((p.split('/')[-1], s, m))
    sheet(models, out)


def gallery(entries, out, cols=3, px=2.2):
    """entries: list of (label, sections, mats). Top view + one isometric view per aircraft."""
    tiles = []
    for label, sections, mats in entries:
        P, C, N = points(sections, mats)
        W = int(200 * px)
        top = draw(P, C, N, TOP, px, W, W)
        iv = draw(P, C, N, iso(35), px, W, W)
        t = Image.new('RGB', (2 * W + 4, W + 22), (20, 20, 20))
        t.paste(top, (0, 22))
        t.paste(iv, (W + 4, 22))
        ImageDraw.Draw(t).text((4, 5), label, fill=(255, 230, 90))
        tiles.append(t)
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * (tw + 6), rows * (th + 6)), (12, 12, 12))
    for i, t in enumerate(tiles):
        S.paste(t, ((i % cols) * (tw + 6), (i // cols) * (th + 6)))
    S.save(out)
