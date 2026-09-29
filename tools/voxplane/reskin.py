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
from scipy.ndimage import distance_transform_edt, gaussian_filter

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


def ornate(base, trim, panel=None, panel_in=4.0, frames=(), ribs=None, hatch=None, side_bands=(),
           emblem=None, lower=None, accents=()):
    """Designed, mirror-symmetric livery (like the mod's 失落神殿 / 占星师 skins):
    `trim` border following the hull outline on the upper surfaces and along
    the top edge of the sides, concentric `frames` [(d_from, d_to, colour)]
    measured from the outline, an inner `panel`, transverse `ribs`
    (every, width, colour, inset), chevron `hatch` in the border
    (colour, period, width, band), `side_bands` [(z_from, z_to, colour)],
    a turret-roof `emblem` (shape, radius, colour) and a dark `lower` hull.
    Colours may be RGB tuples or a palette index (int) for bright accents
    (2 cyan, 9 light cyan, 5 yellow, 7 amber, 15 white)."""
    def put(col, idx, mask, c):
        if isinstance(c, int):
            idx[mask] = c
        else:
            col[mask] = c
            idx[mask] = -1

    def fn(ctx):
        n = len(ctx.P)
        col = np.tile(np.array(base, float), (n, 1))
        idx = np.full(n, -1)
        # distances are in "飓风 voxels": the design keeps its proportions on
        # wider hulls instead of shrinking to a thin line
        k = ctx.scale
        top, d, sy, x, zs = ctx.top, ctx.d / k, ctx.sy / k, ctx.P[:, 0] / k, ctx.zs
        side = ~top
        if panel is not None:
            put(col, idx, top & (d >= panel_in), panel)
        for d0, d1, c in frames:
            put(col, idx, top & (d >= d0) & (d < d1), c)
        if ribs is not None:
            every, width, c, inset = ribs
            put(col, idx, top & (d >= inset) & ((x % every) < width), c)
        for z0, z1, c in side_bands:
            put(col, idx, side & (zs >= z0) & (zs < z1), c)
        put(col, idx, top & (d < 1.6), trim)
        put(col, idx, side & (zs >= 0.86) & (d < 3.0), trim)
        if hatch is not None:
            c, period, width, band = hatch
            put(col, idx, top & (d >= 1.6) & (d < band) & (((x + sy) % period) < width), c)
        for c, dd, ww in accents:                     # thin accent line at a distance from the outline
            put(col, idx, top & (np.abs(d - dd) < ww / 2), c)
        if emblem is not None and ctx.kind in ('tur', 'body_only'):
            shape, r, c = emblem
            cx = ctx.shape_xy[0] / 2.0 / k
            dx, dy = x - cx, sy
            rr = np.hypot(dx, dy)
            th = np.arctan2(dy, dx)
            if shape == 'star':
                m = rr <= r * (0.45 + 0.55 * np.abs(np.cos(4 * th)) ** 3)
            elif shape == 'diamond':
                m = (np.abs(dx) + np.abs(dy)) <= r
            else:
                m = np.abs(rr - r) < 0.9
            put(col, idx, top & m, c)
        if lower is not None:
            put(col, idx, side & (zs < 0.22), lower)
        if ctx.kind == 'barl':
            col[:] = trim if not isinstance(trim, int) else base
            idx[:] = -1
        return col, idx
    fn.ctx = True
    return fn


class Ctx:
    def __init__(self, P, shape, N, zf, raw=None, filled=None, kind='body'):
        self.P, self.shape, self.N, self.zf = P, shape, N, zf
        self.kind = kind
        if raw is not None:                     # geometry for ornate liveries
            foot = filled.any(2)
            d2 = distance_transform_edt(np.pad(foot, 1))[1:-1, 1:-1]
            self.d = d2[raw[:, 0], raw[:, 1]]
            self.sy = np.abs(raw[:, 1] - (filled.shape[1] - 1) / 2.0)
            self.zs = raw[:, 2] / max(filled.shape[2] - 1, 1)
            self.top = N[:, 2] > 0.45
            self.shape_xy = filled.shape[:2]
            self.scale = max(1.0, filled.shape[1] / 32.0)      # 飓风 (PALEW) hull is 32 wide
            self.P = raw


GOLD = (204, 166, 84)
BRONZE = (70, 64, 46)
IVORY = (222, 212, 184)

DUNKELGELB = (190, 166, 108)
OLIVE_DE = (84, 96, 58)
ROTBRAUN = (116, 66, 44)
US_OD = (92, 92, 60)

# skin: (base image, pattern, name)
SCHEMES = {
    'FERCB':   ('FERC', soft_blotches((196, 184, 148), [((88, 96, 76), 0.35)], 7.0, 13),
                '破晓者: British 1942 light stone with soft dark green "Mickey Mouse" patches'),
    'GERJA':   ('GERJ', blotches(US_OD, [((100, 78, 52), 0.55), ((42, 42, 38), 0.95)], 4.5, 21),
                '变色龙: US Normandy olive drab with black and earth brown'),
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
    'SSMB':    ('SSM', livery((62, 66, 74), top=(96, 100, 108), lower=(40, 42, 46), low=0.35,
                              patches=[((74, 82, 62), 0.3, 5.0, 91)]),
                '不速之客: night raider graphite with soft dark olive patches'),
    # The liveries below follow 深冬之狼, the one that worked: a strong
    # two-tone contrast, a bold chevron border, one thin frame, a simple emblem.
    'NEWTNKA': ('NEWTNK', ornate((48, 44, 38), GOLD, panel=(40, 36, 32), panel_in=5.0,
                                 frames=[(3.0, 3.8, (150, 120, 64))], hatch=(GOLD, 7, 2.2, 4.5),
                                 side_bands=[(0.5, 0.57, (150, 120, 64))],
                                 emblem=('star', 5.5, GOLD), lower=(30, 28, 26)),
                '黄金罗盘: black bronze with gold chevrons, gold trim, gold compass star', {'detail': 0.3}),
    'SSMA':    ('SSM', ornate((146, 160, 178), (236, 238, 240), panel=(128, 142, 162), panel_in=4.5,
                              frames=[(2.6, 3.4, (70, 80, 98))], hatch=((236, 238, 240), 5, 1.8, 4.0),
                              side_bands=[(0.5, 0.57, (70, 80, 98))],
                              emblem=('diamond', 3.5, (236, 238, 240)), lower=(70, 80, 98)),
                '北境幽灵: ice blue-grey with white chevrons, slate frame', {'detail': 0.3}),
    'PALEWB':  ('PALEW', ornate((72, 78, 88), (232, 234, 236), panel=(60, 64, 72), panel_in=4.5,
                                frames=[(2.6, 3.4, (150, 158, 170))], hatch=((232, 234, 236), 6, 2.0, 4.5),
                                side_bands=[(0.5, 0.58, (150, 158, 170))],
                                emblem=('diamond', 3.5, (232, 234, 236)), lower=(40, 42, 48)),
                '深冬之狼: charcoal with white fang chevrons and silver frames', {'detail': 0.3, 'dark': 8}),
    'PALEWC':  ('PALEW', ornate((226, 230, 234), (40, 42, 48), panel=(212, 218, 226), panel_in=4.5,
                                frames=[(2.6, 3.4, (150, 158, 170))], hatch=((40, 42, 48), 6, 2.0, 4.5),
                                side_bands=[(0.5, 0.58, (150, 158, 170))],
                                emblem=('diamond', 3.5, (40, 42, 48)), lower=(120, 128, 140)),
                '白夜猎手: white with black fang chevrons and silver frame (深冬之狼 inverted)',
                {'detail': 0.3, 'dark': 8}),
    'KAMMA':   ('KAMM', ornate((74, 84, 52), (206, 180, 116), panel=(66, 76, 46), panel_in=5.0,
                               frames=[(3.0, 3.8, ROTBRAUN)], hatch=((206, 180, 116), 6, 2.2, 4.5),
                               side_bands=[(0.48, 0.58, ROTBRAUN)],
                               emblem=('star', 5.0, (206, 180, 116)), lower=(46, 50, 34)),
                '战争收藏家: dark olive with dunkelgelb chevrons and trim, red-brown frame, sand star',
                {'detail': 0.3, 'dark': 20}),
    'GERBA':   ('GERB', ornate((108, 134, 80), GOLD, panel=(98, 122, 72), panel_in=5.0,
                               frames=[(3.2, 4.0, GOLD)], hatch=((164, 36, 28), 7, 2.4, 3.2),
                               side_bands=[(0.5, 0.6, (164, 36, 28))],
                               emblem=('star', 5.5, GOLD), lower=(48, 58, 38)),
                '执旗者: Soviet green with red banner chevrons, gold trim and frame, gold star',
                {'detail': 0.15, 'dark': 10}),
    'GEROB':   ('GERO', ornate((74, 92, 128), (236, 238, 240), panel=(66, 82, 116), panel_in=4.0,
                               frames=[(2.4, 3.2, 9)], hatch=((236, 238, 240), 8, 2.5, 4.0),
                               side_bands=[(0.40, 0.46, (236, 238, 240))], lower=(32, 40, 60)),
                '破冰者: navy with white ice chevrons, light-cyan frame, white waterline', {'detail': 0.3}),
}

def repaint(sections, pattern, offset, detail=0.8, zsize=None, dark_max=48.0, kind='body'):
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
            res = pattern(Ctx(Pc, shape, N, zf, raw=P, filled=s.filled, kind=kind))
        else:
            res = pattern(Pc, shape)
        col, forced = res if isinstance(res, tuple) else (res, None)
        k = np.clip(lum / ref, 0.6, 1.35) ** detail
        new = np.clip(col * k[:, None], 0, 255)
        out = idx.copy()
        out[paint] = to_index(new[paint])
        if forced is not None:
            f = paint & (forced >= 0)
            out[f] = forced[f]
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
        kind = {'': 'body', 'tur': 'tur', 'barl': 'barl'}[suf]
        if kind == 'body' and not os.path.exists(os.path.join(src, base.lower() + 'tur.vxl')):
            kind = 'body_only'
        repaint(v['sections'], pattern, np.array(off), detail, zsize, dark_max, kind)
        write_vxl(dst, v['sections'], v['pal'], v['remap'])
        print('%-12s <- %-12s %s' % (skin.lower() + suf, base.lower() + suf, SCHEMES[skin][2]))


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for sk in sys.argv[3:] or SCHEMES:
        reskin(src, out, sk)
