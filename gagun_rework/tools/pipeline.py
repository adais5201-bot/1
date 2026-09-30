"""render model -> palette-indexed frames"""
import numpy as np
from sdf import render, ground_shadow, CAM
from model import *

W, H = 155, 171
CX, CY = 77.0, 97.0          # ground centre of the 1x1 foundation inside the 155x171 canvas (matches original art)


def shade_to_index(res):
    ss = res['ss']; hit = res['hit']
    n = res['n']; mat = res['mat']; ao = res['ao']
    diff = np.clip(n @ LIGHT, 0, 1)
    fill = np.clip(n @ CAM, 0, 1)                       # soft front fill so shadow sides are not pure black
    refl = 2 * (n @ LIGHT)[:, None] * n - LIGHT
    spec = np.clip(refl @ CAM, 0, 1) ** 14
    lum = np.zeros(len(mat))
    P = res['P'][hit]
    tex = 1 + 0.10 * (noise3(P * 0.8) - 0.5)                 # subtle weathering / plate variation
    hgt = 0.86 + 0.14 * np.clip(P[:, 2] / 24.0, 0, 1)         # darker toward the ground
    for m in np.unique(mat):
        sel = mat == m
        b, g = TONE.get(m, (0.8, 1))
        lum[sel] = b * ((0.13 + 0.80 * diff[sel] + 0.14 * fill[sel]) * (0.55 + 0.45 * ao[sel])) ** g + SPEC.get(m, 0) * spec[sel]
        lum[sel] *= tex[sel] * hgt[sel]
    L = np.zeros(hit.shape); L[hit] = lum
    M = np.zeros(hit.shape, int); M[hit] = mat
    # resolve sub-samples -> pixels: coverage >= 50%, dominant material, mean luminance of that material
    Hh, Ww = hit.shape[0] // ss, hit.shape[1] // ss
    Lb = L.reshape(Hh, ss, Ww, ss).transpose(0, 2, 1, 3).reshape(Hh, Ww, ss * ss)
    Mb = M.reshape(Hh, ss, Ww, ss).transpose(0, 2, 1, 3).reshape(Hh, Ww, ss * ss)
    cov = (Mb > 0).sum(-1)
    out = np.zeros((Hh, Ww), np.uint8)
    lumpx = np.zeros((Hh, Ww)); matpx = np.zeros((Hh, Ww), int)
    D = (res['P'] @ CAM).reshape(Hh, ss, Ww, ss).transpose(0, 2, 1, 3).reshape(Hh, Ww, ss * ss)
    dep = np.full((Hh, Ww), -1e9)
    for y, x in zip(*np.nonzero(cov * 2 >= ss * ss)):
        ms = Mb[y, x][Mb[y, x] > 0]
        vals, cnt = np.unique(ms, return_counts=True)
        m = vals[cnt.argmax()]
        sel_ = Mb[y, x] == m
        lumpx[y, x] = Lb[y, x][sel_].mean(); matpx[y, x] = m; dep[y, x] = D[y, x][sel_].mean()
    for m in np.unique(matpx):
        if m == 0: continue
        sel = matpx == m; ramp = RAMPS[m]
        pos = np.clip((1 - np.clip(lumpx[sel], 0, 1.2) / 1.0), 0, 1) * (len(ramp) - 1)
        out[sel] = np.array(ramp)[np.clip(np.round(pos).astype(int), 0, len(ramp) - 1)]
    return out, matpx, dep


def darken(idx, steps=1):
    """move an index `steps` darker (negative = lighter) within whatever ramp it belongs to"""
    for m, ramp in RAMPS.items():
        if idx in ramp:
            i = ramp.index(idx); return ramp[int(np.clip(i + steps, 0, len(ramp) - 1))]
    return idx


def outline(img, matpx, dep):
    """RA2-style edge treatment:
    - silhouette pixels on the lower/right (shadow) side -> 2 steps darker
    - silhouette pixels on the upper/left (lit) side      -> 1 step lighter
    - pixels lying behind a nearer part (depth jump)       -> 1 step darker (occlusion / contact line)"""
    out = img.copy(); Hh, Ww = img.shape
    op = img > 0
    for y, x in zip(*np.nonzero(op)):
        dn = y + 1 >= Hh or not op[y + 1, x]
        rt = x + 1 >= Ww or not op[y, x + 1]
        up = y == 0 or not op[y - 1, x]
        lf = x == 0 or not op[y, x - 1]
        if dn or rt:
            out[y, x] = darken(img[y, x], 2); continue
        occl = False
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < Hh and 0 <= xx < Ww and op[yy, xx] and dep[yy, xx] - dep[y, x] > 2.5:
                occl = True
        if occl:
            out[y, x] = darken(img[y, x], 1)
        elif up or lf:
            out[y, x] = darken(img[y, x], -1)
    return out


def render_frame(scene, clip=None):
    res = render(scene, W, H, CX, CY, ss=3, clip=clip)
    img, matpx, dep = shade_to_index(res)
    img = outline(img, matpx, dep)
    return img


def shadow_frame(scene, clip=None):
    m = ground_shadow(scene, W, H, CX, CY, LIGHT, ss=2, clip=clip)
    return np.where(m, 1, 0).astype(np.uint8)
