"""GAGUN coast gun rework: geometry, materials, palette ramps.

World units are screen pixels (RA2 orthographic view, 30 deg elevation). Origin = ground centre of the
1x1 foundation cell; the cell spans +-21.2 in X and Y.
"""
import numpy as np
from sdf import Scene, box, cyl, cone, octa, planes, S2

# ------------------------------------------------------------------ materials
STEEL, DARK, BRASS, REMAP, CONC, BARREL, GLASS, BLACK, SNOW = range(1, 10)

# light: shadows of the original art (and of the neighbouring buildings) fall to the lower right,
# so the key light comes from world (-0.92, 0.39) at ~45 deg elevation
_h = np.array([-0.92, 0.39, 0.0]); _h /= np.linalg.norm(_h)
LIGHT = _h * np.cos(np.radians(45)) + np.array([0, 0, 1.0]) * np.sin(np.radians(45))

# palette ramps, bright -> dark (indices into the unit palette; only 16..203 are used)
RAMPS = {
    STEEL: list(range(36, 62)),                 # d3d3d3 .. 171717 neutral gun-metal
    BARREL: list(range(34, 62)),
    DARK: list(range(52, 63)),
    BRASS: [128, 129, 130, 144, 145, 146, 147, 148, 149, 150, 151, 153, 155, 157, 159, 160, 161, 162, 163],
    REMAP: list(range(16, 32)),
    CONC: list(range(66, 80)),                  # warm khaki-grey concrete
    GLASS: [194, 195, 196, 197, 198, 199],
    BLACK: [58, 59, 60, 61, 62],
    SNOW: [32, 33, 34, 35, 36, 80, 81, 82, 83, 84, 85, 86, 87, 88],
}
# (brightness at full light, gamma) per material
TONE = {
    STEEL: (0.60, 1.25), BARREL: (0.68, 1.2), DARK: (0.50, 1.0), BRASS: (0.80, 1.1),
    REMAP: (0.86, 1.05), CONC: (0.62, 1.1), GLASS: (0.9, 1.0), BLACK: (1.0, 1.0), SNOW: (1.12, 0.9),
}
SPEC = {STEEL: 0.30, BARREL: 0.42, BRASS: 0.35, REMAP: 0.12, CONC: 0.0, DARK: 0.05, GLASS: 0.35, BLACK: 0.0, SNOW: 0.15}


def rot2(p, ang):
    c, s = np.cos(ang), np.sin(ang)
    return p[..., 0] * c + p[..., 1] * s, -p[..., 0] * s + p[..., 1] * c


def local(p, ang):
    u, v = rot2(p, ang)
    return np.stack([u, v, p[..., 2]], -1)


def octr(p):
    x = np.abs(p[..., 0]); y = np.abs(p[..., 1])
    return np.maximum(np.maximum(x, y), (x + y) * S2)


def noise3(p):
    """cheap deterministic value noise in [0,1]"""
    x = p[..., 0]; y = p[..., 1]; z = p[..., 2]
    v = np.sin(x * 1.7 + np.sin(y * 1.3) * 2.1) * np.cos(y * 1.9 - z * 0.7) + 0.6 * np.sin(z * 2.3 + x * 0.9 - y * 1.1)
    v += 0.5 * np.sin(x * 3.1 - y * 2.7 + 1.3) * np.cos(z * 3.7 + 0.4)
    return (v + 2.1) / 4.2


# ------------------------------------------------------------------ base
RING_Z = 12.6          # top of the roller race = bottom of the turret
FRONT_FACE = np.radians(45)   # skirt face that looks straight at the viewer


def base_scene(damaged=False, snow=False):
    sc = Scene()
    # concrete apron with chamfered top edge
    sc.add(lambda p: np.maximum(octa(p, -1, 2.6, 22.3, 21.3), octa(p, -1, 3.6, 24.3, 20.3)), CONC)
    # sloped armoured skirt
    sc.add(lambda p: octa(p, 2.0, 11.4, 19.8, 15.2), STEEL)
    # 8 buttress ribs at the octagon vertices
    for k in range(8):
        a = np.radians(22.5 + 45 * k)

        def rib(p, a=a):
            q = local(p, a)
            u, v, z = q[..., 0], q[..., 1], q[..., 2]
            top = (z + (u - 15.0) * 1.1 - 12.2) / np.sqrt(1 + 1.1 ** 2)
            return np.maximum.reduce([np.abs(v) - 1.3, u - 21.7, 13.0 - u, top, -z - 1])
        sc.add(rib, STEEL)
        sc.add(lambda p, a=a: box(local(p, a), (20.3, 0, 3.3), (0.8, 0.85, 0.6), 0.2), BRASS)
    # deck plate, dark groove, brass roller race
    sc.add(lambda p: cyl(p, (0, 0, 0), 16.0, 10.4, 11.8), STEEL)
    sc.add(lambda p: cyl(p, (0, 0, 0), 15.0, 11.4, 12.0), BLACK)
    sc.add(lambda p: cyl(p, (0, 0, 0), 14.5, 11.4, RING_Z), BRASS)
    sc.add(lambda p: cyl(p, (0, 0, 0), 12.8, 11.4, RING_Z + 0.15), STEEL)
    # front ammunition hatch
    sc.add(lambda p: box(local(p, FRONT_FACE), (19.2, 0, 5.4), (1.1, 3.4, 2.9), 0.3), BRASS)
    sc.cut(lambda p: box(local(p, FRONT_FACE), (20.4, 0, 5.2), (1.3, 2.3, 2.1), 0.0), BLACK)
    if damaged:
        sc.cut(lambda p: box(local(p, np.radians(22.5 + 45 * 7)), (17.0, 0, 9.0), (4.5, 2.6, 3.5), 0), DARK)
        sc.cut(lambda p: box(local(p, np.radians(180)), (17.8, 2.0, 8.2), (3.0, 3.2, 2.4), 0), DARK)
        sc.cut(lambda p: cyl(p, (-9, 13, 0), 3.4, 1.8, 4.5), DARK)
        sc.cut(lambda p: box(local(p, np.radians(-45)), (18.5, -3.0, 4.2), (2.0, 1.6, 1.6), 0), DARK)

    def paint(p, m):
        z = p[..., 2]
        r = octr(p)
        # faction-colour inset panels on the lower skirt, between the ribs (not on the hatch face)
        ang = np.arctan2(p[..., 1], p[..., 0])
        fa = np.round(ang / (np.pi / 4)) * (np.pi / 4)
        v = np.abs(-p[..., 0] * np.sin(fa) + p[..., 1] * np.cos(fa))
        front = np.abs(np.angle(np.exp(1j * (fa - FRONT_FACE)))) < 0.1
        panel = (m == STEEL) & (z > 3.3) & (z < 7.2) & (v < 3.7) & (r > 16.5) & ~front
        m = np.where(panel, REMAP, m)
        seam = (m == STEEL) & (z > 7.7) & (z < 8.3) & (r > 16.0)
        m = np.where(seam, DARK, m)
        if damaged:
            n = noise3(p * 0.33)
            m = np.where((m != BLACK) & (n > 0.60), DARK, m)
            m = np.where((m != BLACK) & (n > 0.76), BLACK, m)
        return m
    sc.paint = paint
    sc.snow = snow
    return sc


# ------------------------------------------------------------------ turret
GUN_Z = 18.6
U_DIR = np.array([-S2, -S2])     # screen up   = facing 0
L_DIR = np.array([-S2, S2])      # screen left = facing 8 (frames advance counter-clockwise on screen)


def facing_angle(k):
    a = 2 * np.pi * k / 32
    d = np.cos(a) * U_DIR + np.sin(a) * L_DIR
    return np.arctan2(d[1], d[0])


def turret_scene(k, snow=False):
    ang = facing_angle(k)
    sc = Scene()
    T = lambda fn: (lambda p: fn(local(p, ang)))   # evaluate in turret space (f forward, s side, z up)

    # turret collar sitting in the roller race
    sc.add(T(lambda q: cyl(q, (0, 0, 0), 15.4, RING_Z, 14.4)), STEEL)
    sc.add(T(lambda q: cyl(q, (0, 0, 0), 15.8, RING_Z, 13.1)), DARK)

    z0, z1 = 14.0, 24.8

    def house(q):
        pl = [
            ((0, 0, -1), -z0), ((0, 0, 1), z1),
            ((1, 0, 0.62), 12.8 + 0.62 * z0),                         # sloped front glacis
            ((-1, 0, 0.18), 15.4 + 0.18 * z0),                        # rear bustle
            ((0, 1, 0.32), 12.6 + 0.32 * z0), ((0, -1, 0.32), 12.6 + 0.32 * z0),   # sloped cheeks
            ((1, 1.25, 0.5), 20.2 + 0.5 * z0), ((1, -1.25, 0.5), 20.2 + 0.5 * z0),  # front chamfers
            ((-1, 1.6, 0.2), 22.4 + 0.2 * z0), ((-1, -1.6, 0.2), 22.4 + 0.2 * z0),  # rear chamfers
            ((0.5, 0, 1), 0.5 * 4.5 + z1),                            # roof front bevel
        ]
        return planes(q, pl)
    sc.add(T(house), STEEL)
    sc.add(T(lambda q: box(q, (-4.0, 0, z1 + 0.3), (8.0, 8.0, 0.5), 0.35)), STEEL)       # raised roof plate
    sc.add(T(lambda q: box(q, (-10.0, -5.2, z1 + 0.45), (2.1, 2.1, 0.5), 0.45)), BRASS)  # roof hatch

    # low stereo rangefinder across the rear roof with armoured end hoods
    RF_F, RF_Z = -7.2, z1 + 1.4
    sc.add(T(lambda q: cyl(q, (RF_F, 0, RF_Z), 1.25, -12.0, 12.0, axis=1)), STEEL)
    for sgn in (-1, 1):
        sc.add(T(lambda q, sgn=sgn: box(q, (RF_F + 0.4, sgn * 12.2, RF_Z - 0.4), (2.6, 1.5, 1.35), 0.5)), STEEL)
        sc.add(T(lambda q, sgn=sgn: box(q, (RF_F + 3.0, sgn * 12.2, RF_Z - 0.35), (0.25, 0.9, 0.6), 0.1)), GLASS)
        sc.add(T(lambda q, sgn=sgn: box(q, (RF_F, sgn * 7.0, z1 + 0.8), (1.0, 0.8, 1.0), 0.25)), BRASS)
    # commander's cupola with periscope slit
    sc.add(T(lambda q: cyl(q, (-0.5, 5.8, 0), 2.7, z1, z1 + 2.6)), STEEL)
    sc.add(T(lambda q: cyl(q, (-0.5, 5.8, 0), 2.85, z1 + 2.6, z1 + 3.2)), BRASS)
    sc.cut(T(lambda q: box(q, (2.0, 5.8, z1 + 1.8), (0.9, 1.5, 0.4), 0)), BLACK)

    # gun mantlet (trunnion housing), recoil sleeve and brass collar
    sc.add(T(lambda q: cyl(q, (11.2, 0, GUN_Z), 4.3, -5.2, 5.2, axis=1)), STEEL)
    sc.add(T(lambda q: cyl(q, (0, 0, GUN_Z), 3.0, 12.0, 17.5, axis=0)), BARREL)
    sc.add(T(lambda q: cyl(q, (0, 0, GUN_Z), 2.6, 17.5, 18.6, axis=0)), BRASS)

    def bq(q):  # slight elevation of the barrel
        return np.stack([q[..., 0], q[..., 1], q[..., 2] - 0.05 * np.maximum(q[..., 0] - 12, 0)], -1)
    sc.add(T(lambda q: cone(bq(q), 0, 18.2, 43.0, 2.1, 1.45, (0, 0, GUN_Z))), BARREL)
    sc.add(T(lambda q: cyl(bq(q), (0, 0, GUN_Z), 2.35, 21.5, 24.0, axis=0)), BARREL)
    sc.add(T(lambda q: cyl(bq(q), (0, 0, GUN_Z), 2.0, 40.5, 44.0, axis=0)), BARREL)
    sc.cut(T(lambda q: cyl(bq(q), (0, 0, GUN_Z), 0.95, 43.2, 45.0, axis=0)), BLACK)

    # rear loading door on the bustle (brass frame, dark door) + two vent louvres
    sc.add(T(lambda q: box(q, (-15.3 - 0.18 * 4, 0, 18.6), (1.0, 3.3, 3.0), 0.3)), BRASS)
    sc.cut(T(lambda q: box(q, (-16.6 - 0.18 * 4, 0, 18.4), (1.3, 2.3, 2.3), 0)), DARK)
    for sgn in (-1, 1):
        sc.cut(T(lambda q, sgn=sgn: box(q, (-15.8, sgn * 7.6, 20.6), (1.2, 1.6, 0.35), 0)), BLACK)
    for sgn in (-1, 1):   # vision slits on the glacis
        sc.cut(T(lambda q, sgn=sgn: box(q, (10.4, sgn * 7.4, 20.4), (1.8, 1.4, 0.45), 0)), BLACK)

    def paint(p, m):
        q = local(p, ang)
        f, s, z = q[..., 0], q[..., 1], q[..., 2]
        band = (m == STEEL) & (np.abs(s) > 9.0) & (z > 16.0) & (z < 17.8) & (f < 0.5) & (f > -17)
        m = np.where(band, REMAP, m)
        seam = (m == STEEL) & (z > 19.4) & (z < 19.95) & (np.abs(s) > 8.5)          # armour plate seam
        m = np.where(seam, DARK, m)
        m = np.where((m == STEEL) & (z > 13.9) & (z < 14.7) & (np.hypot(f, s) > 10.0), BRASS, m)
        return m
    sc.paint = paint
    sc.snow = snow
    return sc
