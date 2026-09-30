"""Build the reworked coast gun (GAGUN) SHP set.

    python3 build.py [out_dir] [gg|ga ...] [--reuse-turret]

Writes, per theater variant (GG = generic/temperate fallback, GA = snow):
    <pfx>gun_rework_v01.shp     6 frames : normal, damaged, damaged, + 3 shadows       (base)
    <pfx>guntur_rework_v01.shp  64 frames (identical for GG/GA): 32 facings (0 = north/up, counter-clockwise) + 32 shadows
    <pfx>gunmk_rework_v01.shp   26 frames: 13 buildup frames (ends on base + turret facing 0) + 13 shadows
All canvases are 155x171 with the foundation's ground centre at (77, 97), like the original art.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shp import write_shp, read_shp          # noqa: E402
from pipeline import W, H, render_frame, shadow_frame   # noqa: E402
from model import base_scene, turret_scene, RING_Z      # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'shp')
os.makedirs(OUT, exist_ok=True)

BASE_CLIPS = [1.2, 2.8, 4.6, 6.4, 8.2, 10.0, 11.4]         # buildup frames 0-6: base rises
TUR_CLIPS = [14.8, 17.0, 19.4, 21.8, 24.4]                 # buildup frames 7-11: turret assembles


def build_turret():
    tur, tsh = [], []
    for k in range(32):
        print('turret facing', k, flush=True)
        ts = turret_scene(k)
        tur.append(render_frame(ts))
        tsh.append(shadow_frame(ts))
    return tur, tsh


def build(pfx, snow, tur, tsh):
    print(pfx, 'base...', flush=True)
    b0 = base_scene(snow=snow)
    bd = base_scene(damaged=True, snow=snow)
    base = render_frame(b0)
    dmg = render_frame(bd)
    bsh = shadow_frame(b0)
    dsh = shadow_frame(bd)
    write_shp(os.path.join(OUT, f'{pfx}gun_rework_v01.shp'), W, H, [base, dmg, dmg, bsh, dsh, dsh])

    write_shp(os.path.join(OUT, f'{pfx}guntur_rework_v01.shp'), W, H, tur + tsh)

    print(pfx, 'buildup...', flush=True)
    mk, mksh = [], []
    for c in BASE_CLIPS:
        mk.append(render_frame(b0, clip=c)); mksh.append(shadow_frame(b0, clip=c))
    t0 = turret_scene(0)
    for c in TUR_CLIPS:
        t = render_frame(t0, clip=c); s = shadow_frame(t0, clip=c)
        mk.append(np.where(t > 0, t, base)); mksh.append(np.maximum(s, bsh))
    mk.append(np.where(tur[0] > 0, tur[0], base)); mksh.append(np.maximum(tsh[0], bsh))
    write_shp(os.path.join(OUT, f'{pfx}gunmk_rework_v01.shp'), W, H, mk + mksh)


if __name__ == '__main__':
    args = sys.argv[2:]
    reuse = '--reuse-turret' in args
    variants = [a for a in args if not a.startswith('--')] or ['gg', 'ga']
    if reuse:   # take the already-built turret frames instead of re-rendering all 32 facings
        _, _, fr = read_shp(os.path.join(OUT, 'ggguntur_rework_v01.shp'))
        tur = [f['img'] for f in fr[:32]]; tsh = [f['img'] for f in fr[32:]]
    else:
        tur, tsh = build_turret()          # the turret carries no terrain-specific detail: shared by all variants
    for v in variants:
        build(v, (v == 'ga'), tur, tsh)
    # round-trip check
    for f in sorted(os.listdir(OUT)):
        w, h, fr = read_shp(os.path.join(OUT, f))
        print(f, w, h, len(fr))
