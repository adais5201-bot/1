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

from builder import PALETTE, to_index
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


DUNKELGELB = (190, 166, 108)
OLIVE_DE = (84, 96, 58)
ROTBRAUN = (116, 66, 44)
US_OD = (92, 92, 60)

# skin: (base image, pattern, name)
SCHEMES = {
    'KAMMA':   ('KAMM', blotches(DUNKELGELB, [(OLIVE_DE, 0.45), (ROTBRAUN, 0.75)], 6.0, 11,
                                  dots=(DUNKELGELB, 1.9)),
                '战争收藏家: 1945 "Hinterhalt" ambush camouflage'),
    'FERCB':   ('FERC', soft_blotches((196, 184, 148), [((88, 96, 76), 0.35)], 7.0, 13),
                '破晓者: British 1942 light stone with soft dark green "Mickey Mouse" patches'),
    'GERJA':   ('GERJ', blotches(US_OD, [((100, 78, 52), 0.55), ((42, 42, 38), 0.95)], 4.5, 21),
                '变色龙: US Normandy olive drab with black and earth brown'),
    'PALEWB':  ('PALEW', whitewash((220, 222, 216), (80, 86, 90), 31),
                '深冬之狼: worn winter whitewash over grey'),
    'GEROB':   ('GERO', two_tone_naval((66, 82, 102), (178, 184, 188), 0.17),
                '破冰者: Measure 22 (navy blue lower hull, haze grey above)'),
    'GERHA':   ('GERH', solid_weathered((76, 82, 88), (122, 112, 90), 0.35, 51),
                '深海孤航: panzer grey, dust on the lower hull'),
    'HOUBEIA': ('HOUBEI', naval((60, 72, 88), (78, 82, 90)),
                '午夜蓝调: US Navy Measure 21 navy blue, deck blue'),
    'FEREA':   ('FERE', soft_blotches((198, 172, 122), [((136, 78, 50), 0.55)], 4.0, 61),
                '烈火: desert sand with soft red-brown cloud'),
    'IDRAGB':  ('IDRAG', blotches((106, 118, 128), [((64, 74, 90), 0.35)], 3.0, 71),
                '蓝闪蝶: blue-grey with dark slate-blue patches'),
    'GERYC':   ('GERY', mottle(US_OD, (150, 132, 92), 1.4, 0.85, 91),
                '圣杯: olive drab with sand sponge mottle (Sicily 1943)'),
    'GERAA':   ('GERA', soft_blotches(DUNKELGELB, [(OLIVE_DE, 0.2), (ROTBRAUN, 0.7)], 5.0, 81),
                '流火: German three-tone, soft sprayed edges'),
}


def repaint(sections, pattern, offset):
    for s in sections:
        idx = s.color[s.filled].astype(int)
        rgb = PALETTE[idx].astype(float)
        lum = rgb @ LUM
        remap = (idx >= 16) & (idx <= 31)
        dark = min(48.0, 0.5 * np.median(lum[~remap])) if (~remap).any() else 48.0
        keep = remap | (lum < dark)
        paint = ~keep
        if not paint.any():
            continue
        ref = np.median(lum[paint])
        P = np.argwhere(s.filled)
        Pf = P + offset
        shape = tuple(int(v) for v in np.maximum(np.array(s.filled.shape) + offset, 1) + 8)
        col = pattern(np.clip(Pf, 0, np.array(shape) - 1).astype(int), shape)
        k = np.clip(lum / ref, 0.6, 1.35) ** 0.8
        new = np.clip(col * k[:, None], 0, 255)
        out = idx.copy()
        out[paint] = to_index(new[paint])
        s.color[s.filled] = out


def reskin(src, out, skin):
    base, pattern, _ = SCHEMES[skin]
    for suf, off in (('', (0, 0, 0)), ('tur', (8, 4, 10)), ('barl', (30, 4, 12))):
        path = os.path.join(src, base.lower() + suf + '.vxl')
        dst = os.path.join(out, skin.lower() + suf + '.vxl')
        if not os.path.exists(path) or not os.path.exists(os.path.join(src, skin.lower() + suf + '.vxl')):
            continue
        v = read_vxl(path)
        repaint(v['sections'], pattern, np.array(off))
        write_vxl(dst, v['sections'], v['pal'], v['remap'])
        print('%-12s <- %-12s %s' % (skin.lower() + suf, base.lower() + suf, SCHEMES[skin][2]))


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for sk in sys.argv[3:] or SCHEMES:
        reskin(src, out, sk)
