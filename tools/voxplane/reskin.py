"""Repaint vehicle / ship skins in WWII colour schemes (camouflage, no stripes):

    python3 reskin.py SRC_DIR OUT_DIR [SKIN ...]

The skin keeps its base unit's geometry. Colours come from the base model's
voxels: house colour (remap 16-31) and dark metal (tracks, guns, vents) stay,
every painted voxel takes the scheme colour at its position, shaded by its
original brightness so panel detail survives. Body, turret and barrel use
one pattern in a shared coordinate frame.
"""
import os
import sys

import numpy as np
from scipy.ndimage import gaussian_filter

from builder import PALETTE, surface_normals, to_index
from vxlio import read_vxl, write_vxl

LUM = np.array([0.30, 0.59, 0.11])


def field(shape, sigma, seed):
    rng = np.random.default_rng(seed)
    f = gaussian_filter(rng.standard_normal(shape), sigma, mode='wrap')
    return f / (f.std() + 1e-9)


def blotches(base, layers, sigma=5.0, seed=1, dots=None):
    """layers: [(colour, threshold)]; later layers paint over earlier ones."""
    def fn(P, shape):
        col = np.tile(np.array(base, float), (len(P), 1))
        for k, (c, thr) in enumerate(layers):
            f = field(shape, sigma, seed + k)[tuple(P.T)]
            col[f > thr] = c
        if dots is not None:              # Hinterhalt: light dots over dark patches
            c, thr = dots
            d = field(shape, 0.9, seed + 99)[tuple(P.T)]
            dark = (col != np.array(base, float)).any(1)
            col[dark & (d > thr)] = c
        return col
    return fn


def soft_blotches(base, layers, sigma=6.0, seed=1, edge=0.18):
    """like blotches, with a soft blended edge instead of a hard cut."""
    def fn(P, shape):
        col = np.tile(np.array(base, float), (len(P), 1))
        for k, (c, thr) in enumerate(layers):
            f = field(shape, sigma, seed + k)[tuple(P.T)]
            w = np.clip((f - thr) / edge + 0.5, 0, 1)[:, None]
            col = col * (1 - w) + np.array(c, float) * w
        return col
    return fn


def mottle(base, spot, sigma=1.6, thr=0.9, seed=1):
    """fine sponge mottle (US 1943 field-applied pattern)."""
    def fn(P, shape):
        col = np.tile(np.array(base, float), (len(P), 1))
        f = field(shape, sigma, seed)[tuple(P.T)]
        g = field(shape, 5.0, seed + 7)[tuple(P.T)]
        col[(f > thr) & (g > -0.3)] = spot
        return col
    return fn


def two_tone_naval(lower, upper, split=0.45, deck=None, top=0.8):
    """Measure 22 style: dark lower hull up to a level line, light above."""
    def fn(P, shape):
        z = P[:, 2] / max(shape[2] - 1, 1)
        col = np.tile(np.array(upper, float), (len(P), 1))
        col[z <= split] = lower
        if deck is not None:
            col[z > top] = deck
        return col
    return fn


def solid_weathered(base, dust, dust_below=0.3, seed=1):
    def fn(P, shape):
        col = np.tile(np.array(base, float), (len(P), 1))
        z = P[:, 2] / max(shape[2] - 1, 1)
        n = field(shape, 2.0, seed)[tuple(P.T)] * 0.08
        w = np.clip((dust_below - z) / dust_below + n, 0, 1)[:, None] * 0.6
        return col * (1 - w) + np.array(dust, float) * w
    return fn


def naval(hull, deck, top=0.72):
    def fn(P, shape):
        z = P[:, 2] / max(shape[2] - 1, 1)
        col = np.tile(np.array(hull, float), (len(P), 1))
        col[z > top] = deck
        return col
    return fn


def whitewash(white, under, seed=1):
    def fn(P, shape):
        col = np.tile(np.array(white, float), (len(P), 1))
        f = field(shape, 2.5, seed)[tuple(P.T)]
        col[f > 0.55] = under                      # worn-through patches
        return col
    return fn


def livery(side, top=None, lower=None, low=0.3, patches=None, flame=None, bands=None, top_min=0.55):
    """Colour by surface: upward faces (`top`), sides (`side`) fading into a
    darker `lower` hull, optional soft `patches` [(colour, threshold, sigma,
    seed)] on the sides, optional `flame` (colour, seed): soft patches that get
    denser toward the bottom, optional height `bands` [(z_from, colour)] for
    ships (boot-top, hull, superstructure)."""
    def fn(ctx):
        n = len(ctx.P)
        col = np.tile(np.array(side, float), (n, 1))
        zf = ctx.zf
        if bands:
            for z0, c in bands:
                col[zf >= z0] = c
        if patches:
            for c, thr, sig, seed in patches:
                f = field(ctx.shape, sig, seed)[tuple(ctx.P.T)]
                w = np.clip((f - thr) / 0.25 + 0.5, 0, 1)[:, None]
                col = col * (1 - w) + np.array(c, float) * w
        if flame:
            c, seed = flame
            f = field(ctx.shape, 3.5, seed)[tuple(ctx.P.T)]
            thr = -0.6 + 2.2 * np.clip(zf, 0, 1)         # dense low, sparse high
            w = np.clip((f - thr) / 0.3 + 0.5, 0, 1)[:, None]
            col = col * (1 - w) + np.array(c, float) * w
        if lower is not None:
            w = np.clip((low - zf) / low, 0, 1)[:, None] ** 1.3
            col = col * (1 - w) + np.array(lower, float) * w
        if top is not None:
            up = np.clip((ctx.N[:, 2] - top_min) / 0.2, 0, 1)[:, None]
            col = col * (1 - up) + np.array(top, float) * up
        return col
    fn.ctx = True
    return fn


class Ctx:
    def __init__(self, P, shape, N, zf):
        self.P, self.shape, self.N, self.zf = P, shape, N, zf


GOLD = (204, 166, 84)
BRONZE = (70, 64, 46)
IVORY = (222, 212, 184)

DUNKELGELB = (190, 166, 108)
OLIVE_DE = (84, 96, 58)
ROTBRAUN = (116, 66, 44)
US_OD = (92, 92, 60)

# skin: (base image, pattern, name)
SCHEMES = {
    'KAMMA':   ('KAMM', livery(DUNKELGELB, lower=(70, 64, 46), low=0.3,
                               patches=[(OLIVE_DE, 0.15, 7.0, 11), (ROTBRAUN, 0.7, 7.0, 12)]),
                '战争收藏家: collector three-tone, large soft patches',
                {'detail': 0.35, 'dark': 20}),
    'FERCB':   ('FERC', soft_blotches((196, 184, 148), [((88, 96, 76), 0.35)], 7.0, 13),
                '破晓者: British 1942 light stone with soft dark green "Mickey Mouse" patches'),
    'GERJA':   ('GERJ', blotches(US_OD, [((100, 78, 52), 0.55), ((42, 42, 38), 0.95)], 4.5, 21),
                '变色龙: US Normandy olive drab with black and earth brown'),
    'PALEWB':  ('PALEW', livery((112, 118, 128), top=(206, 210, 214), lower=(58, 62, 70), low=0.45,
                               top_min=0.85),
                '深冬之狼: wolf grey with snow on the flat tops', {'detail': 0.25, 'dark': 8}),
    'PALEWC':  ('PALEW', livery((222, 226, 232), top=(240, 242, 244), lower=(132, 142, 158), low=0.4,
                               patches=[((164, 176, 192), 0.6, 4.0, 33)]),
                '白夜猎手: arctic white with pale blue-grey patches', {'detail': 0.25, 'dark': 8}),
    'GEROB':   ('GERO', livery((40, 48, 76), top=(150, 136, 110),
                               bands=[(0.07, (150, 180, 204)), (0.30, (226, 230, 232))]),
                '破冰者: ice-white superstructure, pale ice-blue hull, navy boot-top, wood decks'),
    'GERHA':   ('GERH', solid_weathered((76, 82, 88), (122, 112, 90), 0.35, 51),
                '深海孤航: panzer grey, dust on the lower hull'),
    'HOUBEIA': ('HOUBEI', naval((60, 72, 88), (78, 82, 90)),
                '午夜蓝调: US Navy Measure 21 navy blue, deck blue'),
    'FEREA':   ('FERE', livery((150, 58, 40), top=(214, 178, 118), lower=(58, 40, 34), low=0.4, top_min=0.8),
                '烈火: deep oxide red, sand-coloured tops, dark lower hull', {'detail': 0.4}),
    'IDRAGB':  ('IDRAG', blotches((106, 118, 128), [((64, 74, 90), 0.35)], 3.0, 71),
                '蓝闪蝶: blue-grey with dark slate-blue patches'),
    'GERYC':   ('GERY', livery(IVORY, top=GOLD, lower=BRONZE, low=0.35),
                '圣杯: ivory with gold upper surfaces and a bronze lower hull'),
    'GERAA':   ('GERA', livery((74, 56, 42), top=(222, 184, 104), top_min=0.8,
                               bands=[(0.12, (186, 104, 56)), (0.40, (214, 164, 86))]),
                '流火: molten gradient, dark bronze to copper to gold', {'detail': 0.4}),
    'NEWTNKA': ('NEWTNK', livery(BRONZE, top=GOLD, lower=(40, 38, 30), low=0.35),
                '黄金罗盘: dark bronze with polished gold upper surfaces', {'detail': 0.45}),
    'SSMB':    ('SSM', livery((62, 66, 74), top=(96, 100, 108), lower=(40, 42, 46), low=0.35,
                              patches=[((74, 82, 62), 0.3, 5.0, 91)]),
                '不速之客: night raider graphite with soft dark olive patches'),
}


def repaint(sections, pattern, offset, detail=0.8, zsize=None, dark_max=48.0):
    for s in sections:
        idx = s.color[s.filled].astype(int)
        rgb = PALETTE[idx].astype(float)
        lum = rgb @ LUM
        remap = (idx >= 16) & (idx <= 31)
        dark = min(dark_max, 0.5 * np.median(lum[~remap])) if (~remap).any() else dark_max
        keep = remap | (lum < dark)
        paint = ~keep
        if not paint.any():
            continue
        ref = np.median(lum[paint])
        P = np.argwhere(s.filled)
        Pf = P + offset
        shape = tuple(int(v) for v in np.maximum(np.array(s.filled.shape) + offset, 1) + 8)
        Pc = np.clip(Pf, 0, np.array(shape) - 1).astype(int)
        if getattr(pattern, 'ctx', False):
            N = surface_normals(s.filled)[s.filled]
            zf = Pf[:, 2] / float(zsize or s.filled.shape[2])
            col = pattern(Ctx(Pc, shape, N, zf))
        else:
            col = pattern(Pc, shape)
        k = np.clip(lum / ref, 0.6, 1.35) ** detail
        new = np.clip(col * k[:, None], 0, 255)
        out = idx.copy()
        out[paint] = to_index(new[paint])
        s.color[s.filled] = out


def reskin(src, out, skin):
    base, pattern = SCHEMES[skin][:2]
    opts = SCHEMES[skin][3] if len(SCHEMES[skin]) > 3 else {}
    detail = opts.get('detail', 0.8)       # how much of the base model's shading stays
    dark_max = opts.get('dark', 48.0)      # darker voxels (tracks, vents) keep their colour
    body = os.path.join(src, base.lower() + '.vxl')
    zsize = read_vxl(body)['sections'][0].filled.shape[2] + 10 if os.path.exists(body) else None
    for suf, off in (('', (0, 0, 0)), ('tur', (8, 4, 10)), ('barl', (30, 4, 12))):
        path = os.path.join(src, base.lower() + suf + '.vxl')
        dst = os.path.join(out, skin.lower() + suf + '.vxl')
        if not os.path.exists(path) or not os.path.exists(os.path.join(src, skin.lower() + suf + '.vxl')):
            continue
        v = read_vxl(path)
        repaint(v['sections'], pattern, np.array(off), detail, zsize, dark_max)
        write_vxl(dst, v['sections'], v['pal'], v['remap'])
        print('%-12s <- %-12s %s' % (skin.lower() + suf, base.lower() + suf, SCHEMES[skin][2]))


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for sk in sys.argv[3:] or SCHEMES:
        reskin(src, out, sk)
