"""Historical specifications for the 27 aircraft.

Each builder returns (Plane, Livery). Dimensions are real-world metres taken
from the aircraft's published data (span, length, fuselage proportions,
wing taper/dihedral, tail layout, engine type, propeller diameter/blades).
x runs from the tail (0) to the spinner tip (overall length); z = 0 is the
fuselage datum line; y is to the right (left wing = negative y).
"""
import numpy as np

from builder import (BLACK, BOMB, DARK, ENGINE, EXHAUST, FRAME, GLASS, GUN, INTAKE, METAL, RED, REMAP, SKIN, WHITE,
                     YELLOW, Plane)
import paint as P
from paint import Livery

REG = {}

RLM70P = (46, 56, 40)          # German propeller blades
IJ_PROP = (110, 80, 50)        # Japanese brown propeller blades
IJ_TIP = (180, 30, 30)

# Carrier-launched (Spawned=yes) aircraft keep the in-game size of the earlier
# models they replace: ~5.2 voxels per metre instead of the 8.2 used for fighters.
CARRIER_S = 5.2


def reg(code, desc):
    def deco(f):
        REG[code] = (f, desc)
        return f
    return deco


# ------------------------------------------------------------------ helpers
class W:
    """Wing description reused for painting passes (tips, LE strips...)."""

    def __init__(self, xle, cr, ct, b, sweep=0.0, z0=0.0, dihedral=None, tips=0.1, tc=(0.15, 0.09), ellip=False,
                 qc=0.25, te_straight=False):
        self.kw = dict(xle=xle, cr=cr, ct=ct, b=b, sweep=sweep, z0=z0, dihedral=dihedral, tips=tips, tc=tc,
                       ellip=ellip, qc=qc, te_straight=te_straight)
        self.b = b

    def build(self, p, **extra):
        kw = dict(self.kw)
        kw.update(extra)
        p.surface(**kw)
        return self

    def le_x(self, y):
        k = self.kw
        if k['te_straight']:
            t = abs(y) / (k['b'] / 2)
            return (k['xle'] - k['cr']) + k['cr'] + (k['ct'] - k['cr']) * t
        if k['ellip']:
            B = k['b'] / 2
            c = k['cr'] * np.sqrt(max(1 - (abs(y) / B) ** 2, 0))
            return k['xle'] - k['qc'] * k['cr'] - abs(y) * np.tan(np.radians(k['sweep'])) + k['qc'] * c
        return k['xle'] - abs(y) * np.tan(np.radians(k['sweep']))

    def z_at(self, y):
        k = self.kw
        if not k['dihedral']:
            return k['z0']
        return k['z0'] + np.interp(abs(y), [a for a, _ in k['dihedral']], [d for _, d in k['dihedral']])

    def tips_remap(self, p, frac=0.92):
        self.build(p, ymin=self.b / 2 * frac, mat=REMAP, mode='paint')

    def le_strip(self, p, y0, y1, mat=YELLOW):
        self.build(p, ymin=y0, ymax=y1, xcr=(0.0, 0.14), mat=mat, mode='paint')

    def guns(self, p, ys, length=0.45, r=0.05, dz=0.0):
        for y in ys:
            x = self.le_x(y)
            z = self.z_at(y) + dz
            p.cyl((x - 0.2, y, z), (x + length, y, z), r, GUN, mirror=True)


class Fin:
    def __init__(self, xle, cr, ct, h, z0, sweep=30, tips=0.45, y0=0.0, tc=(0.12, 0.09)):
        self.kw = dict(xle=xle, cr=cr, ct=ct, b=h, z0=z0, sweep=sweep, tips=tips, y0=y0, tc=tc, vertical=True)
        self.h = h

    def build(self, p, mirror=False, **extra):
        kw = dict(self.kw)
        kw.update(extra)
        p.surface(**kw)
        if mirror:
            kw['y0'] = -kw['y0']
            p.surface(**kw)
        return self

    def top_remap(self, p, frac=0.75, mirror=False):
        self.build(p, mirror=mirror, ymin=self.h * frac, mat=REMAP, mode='paint')


def nacelle(p, x_front, x_back, r, y, z, hh=None, mirror=True, n=2.2, rear_z=None):
    """Engine nacelle body (without the cowling front), tapering aft."""
    hh = hh or r
    rz = z if rear_z is None else rear_z
    L = x_front - x_back
    st = [(x_back, 0.12, 0.12, rz), (x_back + 0.3 * L, r * 0.75, hh * 0.8, (rz + z) / 2),
          (x_front - 0.25 * L, r, hh, z), (x_front, r, hh, z)]
    p.fuselage(st, n=n, y0=y, main=False, mirror=mirror)


def inline_nose(p, x_front, length, r, y, z, mirror=True, spinner_len=None, spinner_r=None):
    """Pointed liquid-cooled engine cowling + spinner (Merlin / Jumo / VK-105)."""
    st = [(x_front - length, r, r * 1.1, z), (x_front - length * 0.4, r * 0.95, r * 1.05, z),
          (x_front, r * 0.55, r * 0.6, z)]
    p.fuselage(st, n=2.1, y0=y, main=False, mirror=mirror)
    p.spinner(x_front - 0.05, spinner_len or r * 1.2, spinner_r or r * 0.55, y=y, z=z, mirror=mirror)


def annular_nose(p, x_front, length, r, y, z, mirror=True):
    """Jumo 211 with annular radiator: round blunt cowling with a dark ring."""
    st = [(x_front - length, r * 0.9, r * 0.95, z), (x_front - 0.3, r, r, z), (x_front, r * 0.92, r * 0.92, z)]
    p.fuselage(st, n=2.0, y0=y, main=False, mirror=mirror)
    for yy in ([y, -y] if mirror else [y]):
        sl, X, Y, Z = p._sub(x_front - 0.2, x_front + 0.05, yy - r, yy + r, z - r, z + r)
        rr = np.sqrt((Y - yy) ** 2 + (Z - z) ** 2)
        p._apply(sl, (X > x_front - 0.12) & (rr > r * 0.55) & (rr < r * 0.85), INTAKE, 'paint')
    p.spinner(x_front - 0.05, r * 1.0, r * 0.5, y=y, z=z, mirror=mirror)


def turret(p, x, z, r, guns=2, gun_len=1.0, direction=(1, 0, 0), y=0.0, rz=None, mat=GLASS, spacing=0.18):
    p.ellipsoid((x, y, z), (r, r, rz or r * 0.85), mat, zcut=z - (rz or r) * 0.2)
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    for k in range(guns):
        off = (k - (guns - 1) / 2) * spacing
        a = np.array([x, y + off, z + (rz or r) * 0.2])
        p.cyl(a, a + d * (r + gun_len), 0.05, GUN)


def ball_turret(p, x, z, r, gun_len=1.0):
    p.ellipsoid((x, 0, z), (r, r, r), GLASS)
    p.ellipsoid((x, 0, z), (r * 1.01, r * 1.01, r * 1.01), FRAME, mode='under')
    for off in (-0.12, 0.12):
        p.cyl((x, off, z - 0.1), (x - r - gun_len, off, z - 0.35), 0.05, GUN)


def bomb(p, x0, x1, r, y=0.0, z=0.0, mirror=False, mat=BOMB, fins=True, pylon=0.45):
    L = x1 - x0
    st = [(x0, r * 0.35, r * 0.35, z), (x0 + L * 0.3, r, r, z), (x1 - L * 0.25, r, r, z), (x1, r * 0.3, r * 0.3, z)]
    p.fuselage(st, n=2.0, y0=y, main=False, mat=mat, mirror=mirror)
    # pylon so the store is attached to the airframe instead of floating
    p.box(x0 + L * 0.35, x1 - L * 0.35, y - 0.1, y + 0.1, z + r * 0.5, z + r + pylon, DARK, mirror=mirror)
    if fins:
        for yy in ([y, -y] if mirror else [y]):
            p.box(x0 - 0.05, x0 + L * 0.2, yy - r * 1.1, yy + r * 1.1, z - 0.03, z + 0.03, mat)
            p.box(x0 - 0.05, x0 + L * 0.2, yy - 0.03, yy + 0.03, z - r * 1.1, z + r * 1.1, mat)


def sky_band(lv, x0, x1, ymax=0.7):
    return lv.band(x0, x1, P.RAF_SKY, ymax=ymax)


# ======================================================================
# USA
# ======================================================================
@reg('falc', 'P-40E Warhawk')
def p40e():
    p = Plane('falc', 11.38, 9.66, height=2.2)
    p.fuselage([(0.0, 0.07, 0.30, 0.62), (0.9, 0.22, 0.42, 0.52), (2.8, 0.40, 0.60, 0.32), (4.4, 0.49, 0.72, 0.22),
                (5.6, 0.52, 0.74, 0.18), (6.8, 0.50, 0.70, 0.12), (8.0, 0.44, 0.58, 0.05), (8.9, 0.36, 0.46, 0.02),
                (9.2, 0.30, 0.34, 0.02)], n=2.3)
    # the big Allison chin radiator bath
    p.fuselage([(6.9, 0.10, 0.10, -0.40), (7.4, 0.34, 0.34, -0.52), (8.6, 0.38, 0.42, -0.52), (9.0, 0.32, 0.36, -0.45)],
               n=2.2, main=False)
    p.ellipsoid((9.0, 0, -0.52), (0.07, 0.27, 0.27), INTAKE)
    w = W(6.95, 2.60, 1.25, 11.38, sweep=4, z0=-0.40, dihedral=[(0, 0), (5.69, 0.62)], tips=0.12,
          tc=(0.16, 0.09)).build(p)
    p.surface(1.55, 1.15, 0.70, 4.0, sweep=6, z0=0.50, tips=0.4, tc=(0.12, 0.09))
    fin = Fin(1.75, 1.45, 0.55, 1.45, 0.55, sweep=38).build(p)
    p.canopy(4.55, 6.35, 0.36, 0.44, 0.72, style='framed', frames=(5.0, 5.55, 6.05), rail=0.55)
    p.spinner(9.15, 0.62, 0.30)
    p.prop((9.42, 0, 0.02), 3.35, 3)
    w.guns(p, (1.95, 2.2, 2.45), 0.5, dz=0.05)
    p.exhausts(7.7, 8.8, 6, 0.40, 0.22)
    w.tips_remap(p)
    fin.top_remap(p, 0.78)
    lv = Livery(P.scheme_two(P.OD, P.NGRAY))
    lv.top('us42', 6.0, -3.9, 0.72, both=False).side('us42', 3.1, 0.25, 0.46, ymax=0.7)
    lv.sharkmouth(9.1, -0.45, 1.8, 0.45)
    return p, lv


@reg('beag', 'P-51D Mustang')
def p51d():
    p = Plane('beag', 11.28, 9.83, height=2.3)
    p.fuselage([(0.0, 0.07, 0.28, 0.58), (1.0, 0.20, 0.42, 0.48), (3.0, 0.38, 0.62, 0.26), (4.5, 0.45, 0.72, 0.16),
                (5.6, 0.47, 0.72, 0.10), (7.0, 0.45, 0.66, 0.05), (8.4, 0.40, 0.55, 0.0), (9.25, 0.32, 0.38, 0.0)],
               n=2.3)
    # ventral radiator scoop
    p.fuselage([(2.6, 0.10, 0.08, -0.45), (3.3, 0.30, 0.28, -0.66), (4.7, 0.33, 0.33, -0.72),
                (5.25, 0.30, 0.30, -0.70)], n=2.3, main=False)
    p.ellipsoid((5.26, 0, -0.74), (0.05, 0.26, 0.22), INTAKE)
    # dorsal fin fillet
    p.surface(3.2, 2.0, 0.1, 0.35, sweep=78, z0=0.55, tips=0, vertical=True)
    w = W(6.95, 2.62, 1.26, 11.28, sweep=3, z0=-0.45, dihedral=[(0, 0), (5.64, 0.50)], tips=0.06,
          tc=(0.16, 0.11)).build(p)
    p.surface(1.45, 1.25, 0.75, 4.1, sweep=5, z0=0.40, tips=0.2)
    fin = Fin(1.55, 1.45, 0.60, 1.45, 0.50, sweep=35, tips=0.4).build(p)
    p.canopy(4.55, 6.35, 0.38, 0.52, 0.66, style='teardrop', frames=(6.1,))
    p.spinner(9.2, 0.62, 0.31)
    p.prop((9.45, 0, 0.0), 3.40, 4)
    w.guns(p, (2.0, 2.2, 2.4), 0.35, dz=0.05)
    p.exhausts(7.7, 8.7, 6, 0.40, 0.25)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_nmf())
    lv.zone(lambda c: (c.x > 6.5) & (c.x < 9.1) & (c.nz > 0.55) & (np.abs(c.y) < 0.42), P.OD)
    lv.band(8.35, 9.15, 125, ymax=0.8, remap=True)    # squadron nose colours
    lv.stripes(1.3, 0.38, 5, x_fus=1.6, fus_width=0.5)
    lv.top('us', 5.6, -3.9, 0.58, both=False).side('us', 2.7, 0.2, 0.40, ymax=0.7)
    return p, lv


@reg('su37', 'P-38L Lightning')
def p38l():
    L = 11.53
    p = Plane('su37', 15.85, L + 0.4, height=2.4)
    yb = 2.9
    # central gondola: rounded gun nose, cockpit, tapering tail cone over the wing
    p.fuselage([(4.9, 0.12, 0.12, 0.15), (5.8, 0.52, 0.55, 0.15), (7.2, 0.70, 0.80, 0.12), (9.0, 0.68, 0.76, 0.06),
                (10.4, 0.55, 0.58, 0.0), (11.2, 0.38, 0.38, -0.02), (11.53, 0.16, 0.16, -0.02)], n=2.2)
    # twin booms: fat Allison nacelles tapering into slim tail booms
    for sgn in (1, -1):
        y = sgn * yb
        p.fuselage([(0.25, 0.20, 0.30, 0.22), (1.5, 0.26, 0.36, 0.16), (3.8, 0.36, 0.46, 0.10), (6.0, 0.55, 0.70, 0.05),
                    (8.2, 0.62, 0.78, 0.0), (9.6, 0.58, 0.70, -0.04), (10.3, 0.46, 0.52, -0.02),
                    (10.55, 0.36, 0.38, 0.0)], n=2.2, y0=y, main=False)
        # chin intake under the propeller
        p.fuselage([(8.6, 0.10, 0.08, -0.55), (9.3, 0.30, 0.22, -0.66), (10.1, 0.28, 0.20, -0.58)], n=2.2,
                   y0=y, main=False)
        p.ellipsoid((10.1, y, -0.58), (0.04, 0.22, 0.14), INTAKE)
        # GE turbo-supercharger on top of the boom behind the wing
        p.ellipsoid((5.9, y, 0.62), (0.75, 0.30, 0.22))
        p.ellipsoid((5.9, y, 0.78), (0.28, 0.2, 0.08), METAL)
        # coolant radiator scoops on the boom sides
        for s2 in (1, -1):
            p.fuselage([(2.6, 0.06, 0.08, 0.18), (3.2, 0.20, 0.32, 0.2), (4.4, 0.22, 0.34, 0.16), (4.9, 0.16, 0.24, 0.12)],
                       n=2.0, y0=y + s2 * 0.36, main=False)
            p.ellipsoid((3.22, y + s2 * 0.42, 0.2), (0.04, 0.14, 0.26), INTAKE)
        p.spinner(10.5, 0.62, 0.34, y=y, z=0.0)
        p.exhausts(7.3, 8.1, 2, y + sgn * 0.55, 0.3, size=0.1, mirror=False)
    w = W(8.7, 3.25, 1.1, 15.85, sweep=2.5, z0=0.0, dihedral=[(0, 0), (yb, 0.0), (7.9, 0.30)], tips=0.1,
          tc=(0.16, 0.09)).build(p)
    # tailplane between the booms with elevator mass balance
    p.surface(1.75, 1.45, 1.45, 2 * yb + 0.4, sweep=0, z0=0.32, tips=0, tc=(0.12, 0.12))
    p.box(1.9, 2.2, -0.1, 0.1, 0.38, 0.62, DARK)
    # the Lightning's oval twin fins, above and below each boom
    fin = Fin(2.3, 2.0, 1.35, 2.5, -0.75, sweep=5, tips=0.6, y0=yb).build(p, mirror=True)
    fin.build(p, mirror=True, xcr=(0.66, 0.70), mat=DARK, mode='paint')         # rudder hinge line
    p.canopy(6.7, 8.8, 0.46, 0.55, 0.72, style='bubble', frames=(7.15, 8.3))
    for dy, dz in ((0.14, 0.28), (-0.14, 0.28), (0.24, 0.08), (-0.24, 0.08), (0.0, -0.12)):
        p.cyl((11.0, dy, dz), (11.95, dy, dz), 0.05, GUN)
    p.prop((10.72, yb, 0.0), 3.5, 3, mirror=True)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8, mirror=True)
    lv = Livery(P.scheme_nmf())
    lv.zone(lambda c: (c.x > 8.9) & (c.x < 11.3) & (c.nz > 0.5) & (np.abs(c.y) < 0.5), P.OD)
    lv.zone(lambda c: (c.x > 8.4) & (c.x < 10.3) & (c.nz > 0.55) & (np.abs(np.abs(c.y) - yb) < 0.25), P.OD)
    lv.band(10.0, 10.45, 125, remap=True)                                  # squadron colour on the nacelle noses
    lv.stripes(3.4, 0.36, 5, x_fus=5.6, fus_width=0.4)
    lv.top('us', 7.0, -6.1, 0.62, both=False).side('us', 4.0, 0.12, 0.34)
    return p, lv


@reg('b2bomber', 'B-17G Flying Fortress')
def b17g():
    L = 22.66
    p = Plane('b2bomber', 31.62, L, height=4.8, zlow=2.0)
    p.fuselage([(0.0, 0.28, 0.45, 0.45), (1.2, 0.45, 0.62, 0.40), (3.5, 0.75, 0.92, 0.28), (6.5, 1.0, 1.12, 0.15),
                (10.0, 1.15, 1.22, 0.05), (14.0, 1.18, 1.22, 0.0), (17.5, 1.1, 1.18, 0.0), (19.8, 0.95, 1.0, -0.1),
                (21.4, 0.70, 0.72, -0.18), (22.4, 0.40, 0.42, -0.22), (22.66, 0.15, 0.18, -0.22)], n=2.1)
    p.glaze(21.0, 22.7, 0.45, 0.35)
    w = W(15.9, 5.9, 2.0, 31.62, z0=-0.45, dihedral=[(0, 0), (15.8, 1.2)], tips=0.08, tc=(0.18, 0.09),
          te_straight=True).build(p)
    # 4 Wright R-1820 nacelles
    for y, xf in ((3.45, 18.25), (7.2, 17.5)):
        nacelle(p, xf - 0.6, 12.2, 0.66, y, -0.35, rear_z=-0.25)
        p.radial_cowl(xf, 1.5, 0.74, y=y, z=-0.35, mirror=True)
        p.spinner(xf - 0.05, 0.35, 0.22, y=y, z=-0.35, mat=METAL, mirror=True)
        p.prop((xf + 0.1, y, -0.35), 3.53, 3, mirror=True)
        p.exhausts(xf - 1.6, xf - 1.0, 2, y + 0.66, -0.25)
    # tail group: big dorsal fin with fillet
    p.surface(3.6, 3.3, 1.55, 13.4, sweep=16, z0=0.45, tips=0.3, tc=(0.12, 0.09))
    fin = Fin(4.6, 4.6, 1.3, 3.5, 0.9, sweep=38, tips=0.3).build(p)
    p.surface(10.5, 5.6, 0.2, 0.75, sweep=80, z0=1.0, tips=0, vertical=True)     # dorsal fillet
    p.canopy(17.6, 19.8, 0.78, 0.55, 0.95, style='framed', frames=(18.0, 18.55, 19.2), rail=0.5)
    turret(p, 16.9, 1.25, 0.55, 2, 1.4, (1, 0, 0.12))                  # Sperry top turret
    ball_turret(p, 10.8, -1.2, 0.62, 0.8)                                # Sperry ball
    turret(p, 21.7, -0.85, 0.42, 2, 0.9, (1, 0, -0.05), rz=0.4)         # Bendix chin turret
    p.glaze(0.0, 1.0, 0.3, 0.3, zmin=0.1)                                 # Cheyenne tail position
    for off in (-0.12, 0.12):
        p.cyl((0.4, off, 0.45), (-0.9, off, 0.45), 0.05, GUN)
    for sgn in (1, -1):                                                   # staggered waist windows
        p.box(7.4 + (0.6 if sgn > 0 else 0), 8.4 + (0.6 if sgn > 0 else 0), sgn * 0.9, sgn * 1.25, 0.2, 0.75, DARK)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.62)
    lv = Livery(P.scheme_two(P.OD, P.NGRAY), panel=1.9)
    lv.top('us', 13.0, -10.5, 1.25, both=False).side('us', 6.8, 0.15, 0.85)
    return p, lv


@reg('f1172', 'B-24D Liberator')
def b24d():
    L = 20.22
    p = Plane('f1172', 33.53, L, height=4.2, zlow=2.4)
    p.fuselage([(0.0, 0.35, 0.55, 0.65), (1.2, 0.55, 0.85, 0.55), (4.0, 0.82, 1.25, 0.35), (8.0, 1.0, 1.48, 0.15),
                (13.0, 1.05, 1.52, 0.05), (16.5, 1.02, 1.45, 0.0), (18.5, 0.92, 1.25, -0.12),
                (19.7, 0.70, 0.95, -0.25), (20.22, 0.45, 0.55, -0.35)], n=3.2)
    p.glaze(18.8, 20.3, 0.35, 0.35, zmax=0.4)
    # Davis high-aspect shoulder wing
    w = W(14.1, 4.9, 1.9, 33.53, sweep=3, z0=1.15, dihedral=[(0, 0), (16.7, 0.9)], tips=0.08,
          tc=(0.21, 0.09)).build(p)
    for y, xf in ((3.6, 15.9), (7.3, 15.5)):
        nacelle(p, xf - 0.5, 10.4, 0.66, y, 0.75, hh=0.72, rear_z=0.9)
        # the B-24's oval cowlings (oil coolers on the sides)
        p.fuselage([(xf - 1.3, 0.78, 0.66, 0.75), (xf - 0.4, 0.80, 0.68, 0.75), (xf, 0.72, 0.60, 0.75)], n=2.0,
                   y0=y, main=False, mirror=True)
        p.ellipsoid((xf, y, 0.75), (0.06, 0.58, 0.46), ENGINE, mirror=True)
        p.prop((xf + 0.1, y, 0.75), 3.53, 3, mirror=True)
        p.exhausts(xf - 1.9, xf - 1.3, 2, y + 0.7, 0.6)
    p.surface(2.8, 2.2, 1.7, 7.95, sweep=4, z0=0.95, tips=0, tc=(0.12, 0.09))
    fin = Fin(3.1, 2.4, 1.6, 3.2, -0.55, sweep=4, tips=0.55, y0=3.95).build(p, mirror=True)
    p.canopy(16.2, 18.2, 0.85, 0.45, 1.25, style='framed', frames=(16.8, 17.4), rail=0.5)
    turret(p, 14.4, 1.65, 0.55, 2, 1.3, (1, 0, 0.1))                    # Martin top turret
    p.glaze(0.0, 0.9, 0.3, 0.3)                                           # Consolidated tail turret
    for off in (-0.12, 0.12):
        p.cyl((0.4, off, 0.65), (-0.8, off, 0.65), 0.05, GUN)
    p.cyl((19.9, 0, -0.1), (20.9, 0, -0.1), 0.05, GUN)
    for sgn in (1, -1):
        p.box(6.2, 7.4, sgn * 0.95, sgn * 1.12, 0.3, 0.9, DARK)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.8, mirror=True)
    lv = Livery(P.scheme_two(P.OD, P.NGRAY), panel=1.9)
    lv.top('us', 12.4, -11.0, 1.3, both=False).side('us', 5.2, 0.35, 0.9)
    return p, lv


@reg('kpln', 'B-25J Mitchell')
def b25j():
    L = 16.13
    p = Plane('kpln', 20.60, L, height=3.2, zlow=2.0)
    p.fuselage([(0.0, 0.25, 0.42, 0.38), (1.5, 0.48, 0.66, 0.30), (5.0, 0.70, 0.92, 0.15), (9.0, 0.80, 1.02, 0.0),
                (12.2, 0.80, 1.0, -0.05), (14.5, 0.65, 0.82, -0.15), (15.6, 0.45, 0.55, -0.22),
                (16.13, 0.18, 0.22, -0.28)], n=2.5)
    p.glaze(14.8, 16.2, 0.32, 0.3)
    w = W(11.1, 3.5, 1.3, 20.60, sweep=3.5, z0=-0.1, dihedral=[(0, 0), (2.9, 0.40), (10.3, 0.36)], tips=0.1,
          tc=(0.17, 0.10)).build(p)
    for sgn in (1, -1):
        nacelle(p, 11.6, 6.8, 0.68, sgn * 2.9, 0.1, mirror=False, rear_z=0.3)
        p.radial_cowl(12.6, 1.3, 0.76, y=sgn * 2.9, z=0.1)
        p.spinner(12.55, 0.35, 0.22, y=sgn * 2.9, z=0.1, mat=METAL)
        p.exhausts(11.3, 11.6, 1, sgn * 2.9 + 0.75, 0.0, size=0.15, mirror=False)
    p.prop((12.72, 2.9, 0.1), 3.81, 3, mirror=True)
    p.surface(2.3, 1.8, 1.3, 6.7, sweep=4, z0=0.35, tips=0, tc=(0.12, 0.09))
    fin = Fin(2.3, 1.7, 1.0, 2.3, -0.5, sweep=16, tips=0.4, y0=3.3).build(p, mirror=True)
    p.canopy(12.2, 13.9, 0.66, 0.42, 0.85, style='framed', frames=(12.7, 13.3), rail=0.5)
    turret(p, 11.1, 1.05, 0.5, 2, 1.2, (1, 0, 0.1))                    # Bendix top turret
    p.glaze(0.0, 0.8, 0.28, 0.28, zmin=0.0)                               # tail gunner
    for off in (-0.1, 0.1):
        p.cyl((0.4, off, 0.4), (-0.7, off, 0.4), 0.05, GUN)
    for dz in (0.0, -0.25):                                               # package guns
        p.cyl((13.2, 0.82, dz), (14.4, 0.82, dz), 0.07, GUN, mirror=True)
    p.cyl((15.9, 0, 0.1), (16.8, 0, 0.1), 0.05, GUN)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.78, mirror=True)
    lv = Livery(P.scheme_two(P.OD, P.NGRAY), panel=1.6)
    lv.top('us', 9.7, -7.0, 0.95, both=False).side('us', 4.2, 0.1, 0.62)
    return p, lv


@reg('f2002', 'P-47D Thunderbolt')
def p47d():
    L = 11.0
    p = Plane('f2002', 12.43, L, height=2.4)
    p.fuselage([(0.0, 0.08, 0.30, 0.62), (1.2, 0.28, 0.50, 0.50), (3.0, 0.50, 0.76, 0.30), (5.0, 0.62, 0.90, 0.12),
                (6.5, 0.66, 0.94, 0.02), (8.0, 0.68, 0.90, -0.04), (9.4, 0.72, 0.82, -0.08), (9.6, 0.72, 0.82, -0.08)],
               n=2.2)
    # R-2800 oval cowl with the characteristic chin intake
    p.fuselage([(9.3, 0.74, 0.82, -0.10), (10.2, 0.76, 0.84, -0.10), (10.5, 0.70, 0.78, -0.10)], n=2.0,
               main=False)
    p.ellipsoid((10.5, 0, 0.0), (0.06, 0.58, 0.58), ENGINE)
    p.ellipsoid((10.5, 0, -0.62), (0.07, 0.42, 0.14), INTAKE)
    p.spinner(10.45, 0.45, 0.24, mat=METAL)
    w = W(7.75, 2.95, 1.0, 12.43, z0=-0.45, dihedral=[(0, 0), (6.2, 0.43)], ellip=True, qc=0.3,
          tc=(0.16, 0.10)).build(p)
    p.surface(1.8, 1.5, 0.8, 4.9, ellip=True, z0=0.48, qc=0.3, tc=(0.12, 0.09))
    fin = Fin(1.9, 1.75, 0.6, 1.65, 0.55, sweep=30, tips=0.55).build(p)
    p.surface(3.4, 1.8, 0.1, 0.35, sweep=78, z0=0.75, tips=0, vertical=True)      # dorsal fillet
    p.canopy(5.3, 7.1, 0.40, 0.50, 0.80, style='teardrop', frames=(6.9,))
    p.prop((10.62, 0, -0.02), 4.01, 4, chord=0.12)
    w.guns(p, (2.55, 2.8, 3.05, 3.3), 0.45, dz=0.02)
    p.exhausts(3.6, 4.2, 1, 0.64, -0.55, size=0.16)                       # turbo exhaust
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.78)
    lv = Livery(P.scheme_nmf())
    lv.zone(lambda c: (c.x > 7.0) & (c.x < 10.0) & (c.nz > 0.55) & (np.abs(c.y) < 0.5), P.OD)
    lv.band(9.8, 10.6, 125, remap=True)                                    # coloured cowl band
    lv.stripes(1.6, 0.42, 5, x_fus=1.4, fus_width=0.7)
    lv.top('us', 6.0, -4.2, 0.65, both=False).side('us', 3.0, 0.2, 0.48, ymax=0.9)
    return p, lv


@reg('whog', 'A-26B Invader')
def a26b():
    L = 15.24
    p = Plane('whog', 21.34, L, height=3.4, zlow=1.8)
    p.fuselage([(0.0, 0.18, 0.35, 0.45), (2.0, 0.42, 0.62, 0.35), (6.0, 0.62, 0.85, 0.18), (10.0, 0.68, 0.90, 0.05),
                (12.5, 0.62, 0.80, -0.05), (14.3, 0.45, 0.55, -0.15), (15.24, 0.18, 0.22, -0.2)], n=2.4)
    w = W(9.4, 3.4, 1.2, 21.34, sweep=4, z0=0.2, dihedral=[(0, 0), (10.67, 0.6)], tips=0.08,
          tc=(0.17, 0.10)).build(p)
    for sgn in (1, -1):
        nacelle(p, 10.9, 5.6, 0.72, sgn * 2.75, 0.05, mirror=False, rear_z=0.25)
        p.radial_cowl(11.9, 1.3, 0.78, y=sgn * 2.75, z=0.05)
        p.spinner(11.85, 0.45, 0.28, y=sgn * 2.75, z=0.05)
    p.prop((12.05, 2.75, 0.05), 3.81, 3, mirror=True)
    p.surface(2.3, 1.9, 1.0, 6.9, sweep=6, z0=0.55, tips=0.2, dihedral=[(0, 0), (3.45, 0.55)])
    fin = Fin(2.5, 2.4, 0.95, 2.6, 0.6, sweep=32, tips=0.35).build(p)
    p.canopy(10.2, 12.1, 0.52, 0.45, 0.75, style='framed', frames=(10.8, 11.5), rail=0.55)
    for dy in (-0.28, -0.1, 0.1, 0.28):                                    # 8-gun solid nose (4 shown per row)
        for dz in (-0.05, -0.25):
            p.cyl((14.8, dy * 0.8, dz), (15.75, dy * 0.8, dz), 0.045, GUN)
    turret(p, 5.6, 0.95, 0.38, 2, 0.9, (1, 0, 0.05), mat=DARK)            # remote dorsal barbette
    turret(p, 5.0, -0.85, 0.36, 2, 0.8, (-1, 0, -0.05), rz=0.3, mat=DARK)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_nmf(), panel=1.6)
    lv.zone(lambda c: (c.x > 12.0) & (c.x < 14.8) & (c.nz > 0.55) & (np.abs(c.y) < 0.5), P.OD)
    lv.band(12.35, 12.6, 125, remap=True)
    lv.top('us', 8.2, -7.4, 0.9, both=False).side('us', 4.0, 0.2, 0.58)
    return p, lv


@reg('hornet', 'SBD-5 Dauntless')
def sbd():
    L = 10.09
    p = Plane('hornet', 12.66, L, height=2.4, s=CARRIER_S)
    p.fuselage([(0.0, 0.08, 0.30, 0.58), (1.2, 0.25, 0.46, 0.46), (3.5, 0.45, 0.66, 0.26), (5.5, 0.53, 0.74, 0.14),
                (7.5, 0.60, 0.74, 0.04), (8.7, 0.66, 0.68, 0.0), (9.2, 0.66, 0.66, 0.0)], n=2.2)
    p.radial_cowl(9.62, 1.2, 0.69, lip=REMAP)
    p.spinner(9.58, 0.4, 0.22, mat=METAL)
    w = W(7.4, 3.3, 1.3, 12.66, z0=-0.45, dihedral=[(0, 0), (1.5, 0.0), (6.33, 0.55)], tips=0.15,
          tc=(0.15, 0.09), te_straight=True).build(p)
    # perforated split dive flaps (the Dauntless trademark)
    x_te = 7.4 - 3.3

    def flaps(X, Y, Z):
        ay = np.abs(Y)
        m = (X > x_te - 0.05) & (X < x_te + 0.75) & (ay > 0.55) & (ay < 4.3)
        holes = ((np.floor(X * p.s / 2) + np.floor(ay * p.s / 2)) % 2 == 0)
        return m & holes
    p.paint(flaps, (x_te - 0.1, x_te + 0.8, -4.4, 4.4, -1.0, 0.5), DARK)
    p.surface(1.45, 1.35, 0.8, 4.4, sweep=8, z0=0.40, tips=0.3)
    fin = Fin(1.55, 1.55, 0.7, 1.55, 0.5, sweep=30, tips=0.45).build(p)
    p.canopy(4.4, 7.3, 0.40, 0.46, 0.72, style='framed', frames=(4.9, 5.5, 6.1, 6.7), rail=0.55)
    for off in (-0.1, 0.1):                                                # twin .30 rear gun
        p.cyl((4.6, off, 1.0), (3.5, off, 1.2), 0.045, GUN)
    bomb(p, 5.3, 7.2, 0.23, z=-0.95)                                        # 1000 lb bomb on the crutch
    bomb(p, 6.3, 7.1, 0.12, y=2.6, z=-0.75, mirror=True)
    p.cyl((8.6, 0.25, 0.62), (9.5, 0.25, 0.62), 0.05, GUN, mirror=True)
    p.prop((9.78, 0, 0.0), 3.2, 3)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_navy)
    lv.top('us', 6.2, -4.3, 0.65, both=False).side('us', 2.7, 0.25, 0.46, ymax=0.8)
    return p, lv


@reg('j35', 'TBF-1C Avenger')
def tbf():
    L = 12.48
    p = Plane('j35', 16.51, L, height=2.8, zlow=2.0, s=CARRIER_S)
    p.fuselage([(0.0, 0.10, 0.34, 0.75), (1.5, 0.34, 0.60, 0.55), (4.0, 0.60, 0.92, 0.28), (6.5, 0.72, 1.08, 0.08),
                (8.5, 0.75, 1.10, -0.02), (10.3, 0.74, 0.92, 0.0), (11.3, 0.74, 0.80, 0.05)], n=2.4)
    p.radial_cowl(11.95, 1.2, 0.78, z=0.05, lip=REMAP)
    p.spinner(11.9, 0.45, 0.25, z=0.05, mat=METAL)
    p.box(5.0, 6.2, -0.22, 0.22, -1.25, -0.8, SKIN)                        # ventral gun step
    p.glaze(5.0, 5.4, 0.2, 0.2, zmax=-0.8)
    w = W(9.5, 3.1, 1.4, 16.51, sweep=6, z0=-0.3, dihedral=[(0, 0), (2.2, 0.0), (8.25, 0.62)], tips=0.1,
          tc=(0.15, 0.09)).build(p)
    p.surface(1.75, 1.8, 1.0, 6.3, sweep=6, z0=0.55, tips=0.25)
    fin = Fin(1.85, 2.0, 0.85, 2.1, 0.6, sweep=26, tips=0.4).build(p)
    p.canopy(6.9, 10.3, 0.46, 0.55, 0.95, style='framed', frames=(7.4, 8.0, 8.6, 9.2, 9.8), rail=0.55)
    turret(p, 6.4, 1.35, 0.55, 1, 1.2, (-1, 0, 0.15))                    # Grumman 150SE ball turret
    w.guns(p, (2.8,), 0.3, dz=0.03)
    p.cyl((10.8, 0.3, 0.72), (11.8, 0.3, 0.72), 0.045, GUN)
    p.prop((12.1, 0, 0.05), 3.96, 3)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_navy, panel=1.4)
    lv.top('us', 8.0, -5.4, 0.8, both=False).side('us', 3.5, 0.35, 0.55, ymax=0.9)
    return p, lv


# ======================================================================
# UK
# ======================================================================
@reg('ferd', 'Typhoon Mk.Ib')
def typhoon():
    L = 9.73
    p = Plane('ferd', 12.67, L, height=2.4)
    p.fuselage([(0.0, 0.08, 0.32, 0.62), (1.2, 0.25, 0.46, 0.50), (3.5, 0.46, 0.68, 0.30), (5.5, 0.55, 0.76, 0.20),
                (7.3, 0.56, 0.78, 0.12), (8.6, 0.50, 0.72, 0.08), (9.25, 0.42, 0.55, 0.08)], n=2.3)
    # Napier Sabre chin radiator
    p.fuselage([(7.0, 0.15, 0.12, -0.45), (7.8, 0.42, 0.40, -0.66), (9.0, 0.46, 0.44, -0.66), (9.3, 0.44, 0.42, -0.62)],
               n=2.2, main=False)
    p.ellipsoid((9.3, 0, -0.64), (0.06, 0.36, 0.34), INTAKE)
    p.spinner(9.2, 0.55, 0.40)
    w = W(7.1, 2.95, 1.55, 12.67, sweep=2, z0=-0.45, dihedral=[(0, 0), (6.33, 0.61)], tips=0.15,
          tc=(0.19, 0.12)).build(p)
    p.surface(1.45, 1.3, 0.8, 4.9, sweep=6, z0=0.45, tips=0.35)
    fin = Fin(1.6, 1.45, 0.6, 1.5, 0.55, sweep=30, tips=0.4).build(p)
    p.canopy(5.0, 6.7, 0.38, 0.48, 0.82, style='bubble', frames=(5.5,))
    for y in (2.05, 2.5):                                                  # 4 x Hispano 20 mm, long fairings
        x = w.le_x(y)
        z = w.z_at(y)
        p.cyl((x - 0.2, y, z), (x + 0.45, y, z), 0.09, SKIN, mirror=True)
        p.cyl((x + 0.4, y, z), (x + 1.05, y, z), 0.05, GUN, mirror=True)
    p.prop((9.45, 0, 0.08), 4.1, 4)
    p.exhausts(7.5, 8.9, 4, 0.52, 0.3, size=0.14)
    w.tips_remap(p, 0.94)
    fin.top_remap(p, 0.82)
    lv = Livery(P.scheme_camo(P.RAF_GREEN, P.RAF_OCEAN, P.RAF_MSG, sigma=0.9, seed=11))
    sky_band(lv, 1.45, 1.8)
    w.le_strip(p, 2.9, 5.6)
    lv.stripes(1.6, 0.34, 5, x_fus=2.0, fus_width=0.62)
    lv.top('rafB', 5.4, 4.5, 0.62).side('rafC1', 3.3, 0.3, 0.52, ymax=0.75)
    lv.zone(lambda c: (c.x > 0.3) & (c.x < 0.62) & (c.z > 0.8) & (c.z < 1.7) & (np.abs(c.y) < 0.2), (170, 30, 30))
    return p, lv


@reg('germ', 'Lancaster B.I')
def lancaster():
    L = 21.18
    p = Plane('germ', 31.09, L, height=4.0, zlow=2.2)
    p.fuselage([(0.0, 0.30, 0.50, 0.40), (1.3, 0.52, 0.75, 0.32), (5.0, 0.80, 1.05, 0.15), (10.0, 0.90, 1.18, 0.0),
                (15.0, 0.90, 1.15, -0.05), (18.3, 0.80, 1.0, -0.15), (20.2, 0.55, 0.70, -0.25),
                (21.18, 0.28, 0.35, -0.3)], n=2.9)
    turret(p, 20.75, 0.2, 0.62, 2, 1.1, (1, 0, 0.05))                    # FN5 nose turret
    p.ellipsoid((20.6, 0, -0.55), (0.7, 0.5, 0.42), GLASS)               # bomb aimer's blister
    w = W(15.0, 5.3, 1.9, 31.09, sweep=4, z0=-0.1, dihedral=[(0, 0), (3.3, 0.0), (15.5, 1.3)], tips=0.1,
          tc=(0.19, 0.10)).build(p)
    for y, xf in ((3.35, 18.0), (7.3, 17.4)):
        nacelle(p, xf - 1.2, 11.6, 0.62, y, -0.25, hh=0.72, rear_z=-0.1)
        inline_nose(p, xf, 1.7, 0.62, y, -0.1)
        p.fuselage([(xf - 1.9, 0.1, 0.1, -0.7), (xf - 1.3, 0.38, 0.30, -0.85), (xf - 0.6, 0.38, 0.30, -0.8)], n=2.0,
                   y0=y, main=False, mirror=True)                            # radiator bath
        p.prop((xf + 0.05, y, -0.1), 3.96, 3, mirror=True)
        p.exhausts(xf - 1.6, xf - 0.8, 3, y + 0.62, 0.05, size=0.1)
    p.surface(2.1, 2.6, 2.0, 10.0, sweep=3, z0=0.45, tips=0.08, tc=(0.12, 0.09))
    fin = Fin(2.4, 2.6, 1.5, 3.2, -1.1, sweep=4, tips=0.55, y0=5.0).build(p, mirror=True)
    p.canopy(15.6, 18.3, 0.72, 0.62, 0.92, style='framed', frames=(16.2, 16.9, 17.6), rail=0.55)
    turret(p, 9.6, 1.2, 0.58, 2, 1.3, (-1, 0, 0.08))                     # FN50 mid-upper
    p.glaze(0.0, 0.95, 0.3, 0.3)                                           # FN20 tail turret
    for off in (-0.18, -0.06, 0.06, 0.18):
        p.cyl((0.4, off, 0.4), (-0.8, off, 0.4), 0.045, GUN)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.82, mirror=True)
    lv = Livery(P.scheme_camo(P.RAF_GREEN, P.RAF_EARTH, (30, 30, 30), sigma=1.4, seed=21, bottom_side=True,
                              split=0.35), panel=1.9)
    lv.top('rafB', 12.2, 10.5, 1.15).side('rafC1', 6.2, 0.25, 0.75)
    return p, lv


@reg('gers', 'Spitfire Mk.IX')
def spitfire():
    L = 9.47
    p = Plane('gers', 11.23, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.20, 0.40, 0.45), (3.0, 0.36, 0.58, 0.28), (4.5, 0.42, 0.66, 0.20),
                (5.6, 0.43, 0.66, 0.15), (7.0, 0.40, 0.60, 0.10), (8.3, 0.34, 0.50, 0.08), (8.85, 0.30, 0.36, 0.05)],
               n=2.2)
    p.spinner(8.8, 0.68, 0.30)
    w = W(6.95, 2.51, 1.0, 11.23, z0=-0.38, dihedral=[(0, 0), (5.6, 0.59)], ellip=True, qc=0.3,
          tc=(0.13, 0.08)).build(p)
    for sgn in (1, -1):                                                    # underwing radiators
        p.fuselage([(5.4, 0.05, 0.05, -0.5), (5.9, 0.26, 0.18, -0.58), (6.8, 0.26, 0.18, -0.56)], n=3.0,
                   y0=sgn * 1.65, main=False)
        p.ellipsoid((6.82, sgn * 1.65, -0.57), (0.04, 0.2, 0.12), INTAKE)
    p.surface(1.15, 1.15, 0.5, 3.3, ellip=True, z0=0.42, qc=0.3, tc=(0.12, 0.09))
    fin = Fin(1.25, 1.25, 0.45, 1.3, 0.5, sweep=28, tips=0.6).build(p)
    p.canopy(4.5, 5.95, 0.33, 0.42, 0.72, style='bubble', frames=(4.9,))
    for y in (1.7,):
        x = w.le_x(y)
        p.cyl((x - 0.1, y, -0.32), (x + 0.55, y, -0.32), 0.05, GUN, mirror=True)
    p.prop((9.05, 0, 0.05), 3.27, 4)
    p.exhausts(7.4, 8.4, 3, 0.36, 0.22, size=0.14)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RAF_GREEN, P.RAF_OCEAN, P.RAF_MSG, sigma=0.8, seed=5))
    sky_band(lv, 1.35, 1.65, ymax=0.6)
    w.le_strip(p, 2.2, 4.5)
    lv.top('rafB', 5.5, 3.6, 0.6).side('rafC1', 2.7, 0.25, 0.44, ymax=0.6)
    lv.zone(lambda c: (c.x < 0.9) & (c.z > 0.8) & (np.abs(c.y) < 0.18), (170, 30, 30))
    return p, lv


# ======================================================================
# Germany
# ======================================================================
@reg('beag2', 'Me 262A-1a')
def me262():
    L = 10.60
    p = Plane('beag2', 12.65, L, height=2.2)
    # triangular section: rounded top, wide flat lower chines
    p.fuselage([(0.0, 0.08, 0.30, 0.50), (1.5, 0.28, 0.45, 0.36), (4.0, 0.46, 0.60, 0.18), (6.0, 0.50, 0.62, 0.08),
                (8.5, 0.46, 0.52, 0.02), (9.8, 0.32, 0.38, -0.04), (10.6, 0.08, 0.10, -0.06)], n=2.0)
    p.fuselage([(1.5, 0.30, 0.20, 0.10), (4.0, 0.62, 0.32, -0.12), (7.0, 0.66, 0.34, -0.16), (9.4, 0.46, 0.24, -0.14),
                (10.4, 0.18, 0.10, -0.08)], n=2.4, main=False)
    w = W(6.75, 3.25, 1.3, 12.65, sweep=18.5, z0=-0.38, dihedral=[(0, 0), (6.3, 0.62)], tips=0.05,
          tc=(0.12, 0.09)).build(p)
    for sgn in (1, -1):                                                    # Jumo 004 turbojets
        y = sgn * 2.35
        xw = w.le_x(2.35)
        z = w.z_at(2.35) - 0.42
        p.fuselage([(xw - 3.4, 0.30, 0.30, z), (xw - 2.6, 0.42, 0.42, z), (xw - 0.6, 0.47, 0.47, z),
                    (xw + 0.55, 0.44, 0.44, z), (xw + 0.75, 0.38, 0.38, z)], n=2.0, y0=y, main=False)
        p.ellipsoid((xw + 0.74, y, z), (0.05, 0.3, 0.3), INTAKE)
        p.spinner(xw + 0.55, 0.35, 0.16, y=y, z=z, mat=METAL)            # Riedel starter bullet
        p.ellipsoid((xw - 3.4, y, z), (0.08, 0.2, 0.2), EXHAUST)
    p.surface(1.3, 1.25, 0.65, 3.8, sweep=22, z0=0.72, tips=0.25)
    fin = Fin(1.6, 1.55, 0.55, 1.65, 0.45, sweep=32, tips=0.3).build(p)
    p.canopy(4.9, 6.7, 0.36, 0.46, 0.6, style='teardrop', frames=(6.35, 5.5))
    for dy in (-0.14, 0.14):                                               # MK 108 ports
        p.box(9.3, 9.9, dy - 0.05, dy + 0.05, 0.28, 0.36, DARK)
    w.tips_remap(p, 0.94)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM81, P.RLM82, P.RLM76, kind='splinter', seed=4, side=P.RLM76, side_mottle=0.35))
    lv.band(2.2, 2.6, 125, remap=True)
    lv.top('balken44', 5.0, 4.3, 0.55).side('balken44', 3.3, 0.18, 0.42, ymax=0.7)
    return p, lv


@reg('alpha', 'He 111H-6')
def he111():
    L = 16.40
    p = Plane('alpha', 22.60, L, height=3.4, zlow=2.2)
    p.fuselage([(0.0, 0.10, 0.30, 0.45), (2.0, 0.45, 0.60, 0.35), (5.0, 0.75, 0.90, 0.20), (9.0, 0.85, 1.00, 0.05),
                (12.5, 0.85, 1.00, 0.0), (14.5, 0.80, 0.95, 0.0), (15.8, 0.60, 0.70, 0.0), (16.4, 0.20, 0.22, 0.0)],
               n=2.1)
    p.glaze(14.2, 16.5, 0.34, 0.3, dy=0.34)                               # stepless glazed nose
    p.fuselage([(9.2, 0.10, 0.10, -0.85), (9.9, 0.40, 0.34, -1.02), (12.3, 0.40, 0.34, -1.02),
                (12.9, 0.18, 0.18, -0.9)], n=2.3, main=False)            # Bola gondola
    p.glaze(9.2, 9.9, 0.25, 0.25, zmax=-0.75)
    w = W(11.5, 4.9, 1.9, 22.60, sweep=5, z0=-0.45, dihedral=[(0, 0), (2.8, 0.0), (11.3, 0.9)], tips=0.28,
          tc=(0.17, 0.10)).build(p)
    for sgn in (1, -1):
        y = sgn * 3.05
        nacelle(p, 12.3, 8.2, 0.60, y, -0.25, hh=0.66, mirror=False, rear_z=-0.1)
        annular_nose(p, 13.3, 1.2, 0.62, y, -0.2, mirror=False)
        p.exhausts(12.3, 12.9, 3, y + 0.6, -0.05, size=0.08, mirror=False)
    p.prop((13.45, 3.05, -0.2), 3.5, 3, blade=RLM70P, tip=RLM70P, mirror=True)
    p.surface(2.2, 2.2, 1.0, 7.4, ellip=True, z0=0.55, qc=0.3, tc=(0.12, 0.09))
    fin = Fin(2.2, 2.3, 1.2, 2.0, 0.6, sweep=16, tips=0.55).build(p)
    p.canopy(6.4, 8.3, 0.36, 0.38, 0.9, style='teardrop', frames=(7.0, 7.6))
    p.cyl((6.7, 0, 1.15), (5.3, 0, 1.45), 0.05, GUN)
    p.cyl((16.2, 0.2, 0.1), (17.0, 0.2, 0.1), 0.05, GUN)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM70, P.RLM71, P.RLM65, kind='splinter', seed=8), panel=1.6)
    lv.band(3.2, 3.6, 125, remap=True)
    lv.top('balken', 9.6, 7.3, 0.9).side('balken', 5.2, 0.2, 0.6)
    return p, lv


@reg('jafsd', 'Ju 88A-4')
def ju88():
    L = 14.36
    p = Plane('jafsd', 20.08, L, height=3.4, zlow=2.0)
    p.fuselage([(0.0, 0.10, 0.30, 0.40), (2.0, 0.45, 0.55, 0.30), (5.0, 0.72, 0.80, 0.15), (8.0, 0.80, 0.85, 0.05),
                (10.5, 0.80, 0.86, 0.0), (12.2, 0.78, 0.92, 0.06), (13.6, 0.62, 0.78, 0.05), (14.36, 0.22, 0.28, -0.05)],
               n=2.1)
    p.canopy(11.2, 13.8, 0.78, 0.55, 0.55, style='framed', frames=(11.8, 12.4, 13.0), rail=0.5)
    p.glaze(12.9, 14.4, 0.3, 0.3, dy=0.35)                                # "beetle eye" nose
    p.fuselage([(10.3, 0.10, 0.10, -0.8), (10.9, 0.34, 0.30, -0.95), (12.9, 0.36, 0.30, -0.95),
                (13.3, 0.15, 0.15, -0.85)], n=2.3, y0=0.18, main=False)  # offset Bola
    p.glaze(10.3, 10.9, 0.22, 0.22, zmax=-0.7)
    w = W(9.5, 3.7, 1.6, 20.08, sweep=4, z0=-0.3, dihedral=[(0, 0), (10.04, 0.96)], tips=0.04,
          tc=(0.15, 0.10)).build(p)
    for sgn in (1, -1):
        y = sgn * 2.75
        nacelle(p, 10.8, 5.6, 0.64, y, -0.2, hh=0.70, mirror=False, rear_z=-0.05)
        annular_nose(p, 11.8, 1.1, 0.68, y, -0.18, mirror=False)
        p.exhausts(10.9, 11.4, 3, y + 0.66, -0.05, size=0.08, mirror=False)
    p.prop((11.95, 2.75, -0.18), 3.5, 3, blade=RLM70P, tip=RLM70P, mirror=True)
    for y in (4.2, 5.0, 5.8):                                              # dive brake slats
        p.box(w.le_x(y) - 0.7, w.le_x(y) - 0.55, y - 0.35, y + 0.35, w.z_at(y) - 0.35, w.z_at(y) - 0.2, DARK,
              mirror=True)
    p.surface(1.8, 1.9, 1.15, 7.0, sweep=6, z0=0.45, tips=0.2)
    fin = Fin(1.9, 2.3, 1.05, 2.2, 0.55, sweep=24, tips=0.3).build(p)
    p.cyl((12.4, 0.2, 0.95), (11.2, 0.2, 1.25), 0.05, GUN)
    p.cyl((14.2, -0.2, 0.2), (15.0, -0.2, 0.2), 0.05, GUN)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM70, P.RLM71, P.RLM65, kind='splinter', seed=13), panel=1.6)
    lv.band(3.0, 3.35, 125, remap=True)
    lv.top('balken', 8.2, 6.6, 0.85).side('balken', 4.6, 0.2, 0.55)
    return p, lv


@reg('gerz', 'Bf 109G-6')
def bf109():
    L = 9.02
    p = Plane('gerz', 9.92, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.30, 0.60), (1.0, 0.20, 0.42, 0.50), (3.0, 0.36, 0.55, 0.30), (4.8, 0.43, 0.62, 0.18),
                (5.7, 0.44, 0.63, 0.10), (7.0, 0.42, 0.60, 0.05), (8.2, 0.35, 0.50, 0.0), (8.55, 0.30, 0.36, 0.0)],
               n=2.6)
    p.ellipsoid((7.35, 0.40, 0.36), (0.32, 0.12, 0.12), mirror=True)    # MG 131 "Beulen"
    p.cyl((7.0, -0.44, 0.08), (7.6, -0.48, 0.08), 0.11, SKIN)             # supercharger intake
    p.ellipsoid((7.62, -0.48, 0.08), (0.03, 0.08, 0.08), INTAKE)
    p.fuselage([(7.3, 0.1, 0.1, -0.45), (7.7, 0.18, 0.14, -0.55), (8.2, 0.14, 0.12, -0.5)], n=2.0, main=False)
    p.spinner(8.5, 0.52, 0.30)
    w = W(6.6, 2.0, 1.1, 9.92, sweep=3, z0=-0.40, dihedral=[(0, 0), (4.96, 0.56)], tips=0.2,
          tc=(0.14, 0.11)).build(p)
    for sgn in (1, -1):                                                    # underwing radiators
        p.box(5.3, 6.2, sgn * 1.05, sgn * 1.6, -0.62, -0.38, SKIN)
        p.box(6.15, 6.22, sgn * 1.1, sgn * 1.55, -0.6, -0.42, INTAKE)
    p.surface(1.35, 1.0, 0.65, 3.0, sweep=5, z0=0.62, tips=0.4)
    fin = Fin(1.4, 1.25, 0.6, 1.25, 0.52, sweep=30, tips=0.45).build(p)
    p.canopy(4.75, 6.1, 0.32, 0.38, 0.62, style='framed', frames=(5.25, 5.75), rail=0.6)
    p.cyl((8.4, 0, 0.0), (9.15, 0, 0.0), 0.05, GUN)                        # MG 151 through the hub
    p.prop((8.68, 0, 0.0), 3.0, 3, blade=RLM70P, tip=RLM70P)
    p.exhausts(7.3, 8.1, 6, 0.36, 0.08, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM74, P.RLM75, P.RLM76, kind='splinter', seed=2, side=P.RLM76, side_mottle=0.3))
    lv.band(1.95, 2.3, P.YEL, ymax=0.6)                                    # Eastern front theatre band
    lv.zone(lambda c: (c.x > 7.4) & (c.z < -0.1) & (np.abs(c.y) < 0.5), P.YEL)
    lv.top('balken', 5.7, 3.4, 0.5).side('balken', 3.0, 0.2, 0.40, ymax=0.6)
    return p, lv


@reg('gerl', 'Ju 87D-5 Stuka')
def ju87():
    L = 11.5
    p = Plane('gerl', 13.8, L, height=2.6, zlow=2.5)
    p.fuselage([(0.0, 0.07, 0.30, 0.62), (1.5, 0.30, 0.50, 0.46), (4.0, 0.50, 0.70, 0.25), (6.5, 0.58, 0.80, 0.15),
                (8.5, 0.55, 0.78, 0.10), (10.2, 0.48, 0.62, 0.05), (10.9, 0.38, 0.46, 0.0), (11.05, 0.30, 0.36, 0.0)],
               n=2.6)
    # chin radiator of the Jumo 211J
    p.fuselage([(8.9, 0.12, 0.1, -0.5), (9.6, 0.42, 0.36, -0.68), (10.7, 0.44, 0.36, -0.62),
                (10.95, 0.40, 0.32, -0.55)], n=2.4, main=False)
    p.ellipsoid((10.95, 0, -0.58), (0.05, 0.34, 0.26), INTAKE)
    p.spinner(11.0, 0.5, 0.30)
    # inverted gull wing
    w = W(8.3, 2.9, 1.4, 13.8, sweep=5, z0=-0.6, dihedral=[(0, 0), (2.1, -0.46), (6.9, 0.25)], tips=0.22,
          tc=(0.16, 0.10)).build(p)
    # fixed trousered main gear at the gull kink
    zk = w.z_at(2.1)
    xk = w.le_x(2.1) - 0.9
    p.fuselage([(xk - 0.75, 0.10, 0.12, zk - 0.6), (xk - 0.3, 0.22, 0.55, zk - 0.55), (xk + 0.35, 0.24, 0.62, zk - 0.6),
                (xk + 0.8, 0.12, 0.25, zk - 0.35)], n=2.0, y0=2.1, main=False, mirror=True)
    p.cyl((xk, 2.1 - 0.1, zk - 1.25), (xk, 2.1 + 0.1, zk - 1.25), 0.36, BLACK, mirror=True)
    for y in np.linspace(2.6, 5.4, 5):                                    # dive brakes under the outer wing
        p.box(w.le_x(y) - 0.55, w.le_x(y) - 0.42, y - 0.3, y + 0.3, w.z_at(y) - 0.42, w.z_at(y) - 0.28, DARK,
              mirror=True)
    bomb(p, 5.9, 8.0, 0.26, z=-1.25)                                       # SC 500
    bomb(p, 6.9, 7.8, 0.13, y=3.4, z=w.z_at(3.4) - 0.35, mirror=True)    # SC 50s
    p.surface(1.5, 1.3, 0.9, 4.9, sweep=4, z0=0.55, tips=0.2)
    fin = Fin(1.55, 1.55, 0.8, 1.6, 0.6, sweep=14, tips=0.35).build(p)
    p.canopy(5.1, 8.7, 0.38, 0.46, 0.76, style='framed', frames=(5.7, 6.4, 7.1, 7.8, 8.3), rail=0.55)
    for off in (-0.08, 0.08):                                              # MG 81Z
        p.cyl((5.4, off, 1.0), (4.3, off, 1.2), 0.045, GUN)
    p.prop((11.2, 0, 0.0), 3.4, 3, blade=RLM70P, tip=RLM70P)
    p.exhausts(9.7, 10.6, 6, 0.46, 0.18, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM70, P.RLM71, P.RLM65, kind='splinter', seed=17))
    lv.band(2.6, 2.95, P.YEL, ymax=0.7)
    lv.top('balken', 6.9, 4.6, 0.6).side('balken', 3.7, 0.25, 0.5, ymax=0.8)
    return p, lv


@reg('mig2000', 'Fw 190F-8')
def fw190():
    L = 9.0
    p = Plane('mig2000', 10.51, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.30, 0.55), (1.0, 0.22, 0.42, 0.45), (3.0, 0.40, 0.58, 0.25), (4.7, 0.50, 0.66, 0.12),
                (6.0, 0.55, 0.70, 0.05), (7.3, 0.60, 0.64, 0.0), (7.6, 0.62, 0.63, 0.0)], n=2.3)
    p.radial_cowl(8.55, 1.15, 0.64)
    p.spinner(8.5, 0.5, 0.36)
    for dy in (-0.15, 0.15):                                               # MG 131 troughs
        p.box(7.2, 7.9, dy - 0.05, dy + 0.05, 0.55, 0.62, DARK)
    w = W(6.7, 2.35, 1.2, 10.51, sweep=5, z0=-0.38, dihedral=[(0, 0), (5.25, 0.46)], tips=0.12,
          tc=(0.15, 0.09)).build(p)
    p.surface(1.35, 1.0, 0.7, 3.65, sweep=6, z0=0.50, tips=0.35)
    fin = Fin(1.45, 1.4, 0.6, 1.35, 0.5, sweep=34, tips=0.4).build(p)
    p.canopy(4.4, 6.0, 0.36, 0.44, 0.6, style='teardrop', frames=(5.95,))
    w.guns(p, (0.95,), 0.35, dz=0.1)                                       # MG 151 wing root cannon
    bomb(p, 4.4, 6.3, 0.2, z=-0.95)                                         # SC 250 on the ETC 501
    for y in (1.9, 2.6):
        bomb(p, 5.6, 6.4, 0.1, y=y, z=w.z_at(y) - 0.3, mirror=True)     # SC 50 on ETC 71
    p.prop((8.65, 0, 0.0), 3.3, 3, blade=RLM70P, tip=RLM70P, chord=0.12)
    p.exhausts(7.0, 7.4, 3, 0.58, -0.25, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.RLM74, P.RLM75, P.RLM76, kind='splinter', seed=6, side=P.RLM76, side_mottle=0.3))
    lv.band(1.85, 2.2, P.YEL, ymax=0.7)
    lv.top('balken', 5.9, 3.5, 0.55).side('balken', 2.9, 0.2, 0.42, ymax=0.7)
    return p, lv


# ======================================================================
# Italy
# ======================================================================
@reg('firefox', 'MC.205V Veltro')
def mc205():
    L = 8.85
    p = Plane('firefox', 10.58, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.30, 0.60), (1.0, 0.20, 0.42, 0.50), (3.0, 0.38, 0.58, 0.30), (4.6, 0.44, 0.64, 0.18),
                (5.6, 0.45, 0.65, 0.12), (7.0, 0.42, 0.58, 0.05), (8.1, 0.34, 0.46, 0.02), (8.4, 0.30, 0.36, 0.02)],
               n=2.2)
    p.fuselage([(3.9, 0.08, 0.08, -0.5), (4.4, 0.30, 0.24, -0.66), (5.3, 0.32, 0.24, -0.66), (5.6, 0.3, 0.22, -0.62)],
               n=2.3, main=False)                                         # ventral radiator
    p.ellipsoid((5.6, 0, -0.64), (0.04, 0.24, 0.16), INTAKE)
    p.fuselage([(7.2, 0.08, 0.08, -0.4), (7.6, 0.16, 0.12, -0.5), (8.0, 0.14, 0.1, -0.45)], n=2.0, main=False)
    p.spinner(8.35, 0.5, 0.30)
    w = W(6.3, 2.3, 1.1, 10.58, sweep=4, z0=-0.38, dihedral=[(0, 0), (5.29, 0.55)], tips=0.2,
          tc=(0.15, 0.10)).build(p)
    p.surface(1.3, 1.0, 0.6, 3.3, sweep=5, z0=0.42, tips=0.4)
    fin = Fin(1.35, 1.2, 0.55, 1.25, 0.5, sweep=24, tips=0.6).build(p)
    p.canopy(4.6, 6.0, 0.34, 0.40, 0.66, style='framed', frames=(5.1, 5.6), rail=0.6)
    for dy in (-0.14, 0.14):
        p.box(7.2, 7.9, dy - 0.04, dy + 0.04, 0.52, 0.58, DARK)
    w.guns(p, (2.1,), 0.45, dz=0.03)
    p.prop((8.5, 0, 0.02), 3.05, 3)
    p.exhausts(7.1, 8.0, 6, 0.36, 0.1, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.82)

    def smoke_rings(ctx):
        n = ctx.noise(0.45, 31)
        ring = (n > 0.25) & (n < 1.0)
        top = np.where(ring[:, None], P._c(P.IT_GREEN, ctx.n), P._c(P.IT_SAND, ctx.n))
        return np.where((ctx.nz > -0.25)[:, None], top, P._c(P.IT_GREY, ctx.n))
    lv = Livery(smoke_rings)
    lv.band(2.0, 2.4, P.NWHITE, ymax=0.7)
    lv.top('it_wing', 5.5, 3.5, 0.5).side('it_cross', 0.55, 1.2, 0.5)
    return p, lv


# ======================================================================
# USSR
# ======================================================================
@reg('stfighter', 'Yak-3')
def yak3():
    L = 8.50
    p = Plane('stfighter', 9.20, L, height=2.0)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.20, 0.40, 0.45), (3.0, 0.36, 0.55, 0.25), (4.4, 0.42, 0.60, 0.15),
                (5.4, 0.43, 0.62, 0.10), (6.8, 0.40, 0.55, 0.05), (7.8, 0.33, 0.44, 0.02), (8.05, 0.28, 0.34, 0.02)],
               n=2.2)
    p.fuselage([(3.6, 0.08, 0.08, -0.45), (4.1, 0.34, 0.2, -0.6), (5.0, 0.36, 0.22, -0.6), (5.5, 0.34, 0.2, -0.55)],
               n=2.6, main=False)                                         # radiator in the wing centre section
    p.ellipsoid((5.52, 0, -0.58), (0.04, 0.26, 0.14), INTAKE)
    p.spinner(8.0, 0.5, 0.28)
    w = W(6.2, 2.35, 1.1, 9.20, sweep=5, z0=-0.36, dihedral=[(0, 0), (4.6, 0.48)], tips=0.15,
          tc=(0.14, 0.10)).build(p)
    w.le_strip(p, 0.45, 0.95, mat=INTAKE)                                   # oil cooler inlets at the roots
    p.surface(1.2, 1.0, 0.6, 3.0, sweep=5, z0=0.40, tips=0.4)
    fin = Fin(1.25, 1.1, 0.55, 1.2, 0.5, sweep=25, tips=0.5).build(p)
    p.canopy(4.3, 5.7, 0.32, 0.40, 0.62, style='teardrop', frames=(4.75,))
    for dy in (-0.12, 0.12):
        p.box(6.9, 7.6, dy - 0.04, dy + 0.04, 0.5, 0.56, DARK)
    p.cyl((7.9, 0, 0.02), (8.75, 0, 0.02), 0.05, GUN)
    p.prop((8.15, 0, 0.02), 2.85, 3)
    p.exhausts(6.8, 7.7, 6, 0.36, 0.1, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.SOV_BGREY, P.SOV_DGREY, P.SOV_LBLUE, sigma=0.8, seed=9))
    lv.band(7.55, 7.95, 125, remap=True)
    lv.side('sov', 3.0, 0.22, 0.42, ymax=0.6).side('sov', 0.72, 1.12, 0.36)
    return p, lv


@reg('gern', 'La-5FN')
def la5fn():
    L = 8.67
    p = Plane('gern', 9.80, L, height=2.1)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.22, 0.42, 0.45), (3.0, 0.40, 0.58, 0.25), (4.5, 0.50, 0.66, 0.10),
                (5.7, 0.56, 0.68, 0.02), (6.8, 0.62, 0.66, 0.0), (7.1, 0.64, 0.65, 0.0)], n=2.2)
    p.radial_cowl(8.25, 1.2, 0.67, lip=REMAP)
    p.spinner(8.2, 0.47, 0.30)
    p.fuselage([(7.1, 0.06, 0.06, 0.6), (7.5, 0.16, 0.14, 0.72), (8.15, 0.16, 0.14, 0.72)], n=2.2, main=False)
    p.ellipsoid((8.15, 0, 0.72), (0.03, 0.12, 0.1), INTAKE)                # FN supercharger intake
    p.fuselage([(5.3, 0.06, 0.06, -0.5), (5.8, 0.24, 0.18, -0.64), (6.6, 0.24, 0.18, -0.64)], n=2.2, main=False)
    w = W(6.3, 2.45, 1.2, 9.80, sweep=4, z0=-0.36, dihedral=[(0, 0), (4.9, 0.45)], tips=0.15,
          tc=(0.15, 0.10)).build(p)
    p.surface(1.3, 1.05, 0.65, 3.45, sweep=5, z0=0.45, tips=0.4)
    fin = Fin(1.35, 1.2, 0.55, 1.3, 0.5, sweep=25, tips=0.45).build(p)
    p.canopy(4.4, 5.8, 0.34, 0.42, 0.62, style='teardrop', frames=(4.85,))
    for dy in (-0.15, 0.15):                                               # 2 x ShVAK
        p.cyl((7.0, dy, 0.55), (8.3, dy, 0.55), 0.05, GUN)
    p.prop((8.35, 0, 0.0), 3.1, 3)
    p.exhausts(6.9, 7.3, 4, 0.6, -0.1, size=0.08)
    w.tips_remap(p, 0.92)
    fin.top_remap(p, 0.8)
    lv = Livery(P.scheme_camo(P.SOV_BGREY, P.SOV_DGREY, P.SOV_LBLUE, sigma=0.8, seed=19))
    lv.side('sov', 2.9, 0.22, 0.42, ymax=0.7).side('sov', 0.75, 1.15, 0.38)
    return p, lv


@reg('gerr', 'Pe-2')
def pe2():
    L = 12.66
    p = Plane('gerr', 17.16, L, height=2.8, zlow=1.8)
    p.fuselage([(0.0, 0.12, 0.30, 0.45), (2.0, 0.40, 0.52, 0.35), (5.0, 0.60, 0.72, 0.20), (8.0, 0.66, 0.80, 0.05),
                (10.5, 0.64, 0.78, 0.0), (11.8, 0.55, 0.65, -0.05), (12.66, 0.22, 0.26, -0.1)], n=2.2)
    p.glaze(11.4, 12.7, 0.3, 0.26, zmax=0.25)
    w = W(8.6, 2.9, 1.2, 17.16, sweep=5, z0=-0.2, dihedral=[(0, 0), (2.2, 0.0), (8.58, 0.75)], tips=0.1,
          tc=(0.15, 0.09)).build(p)
    w.le_strip(p, 0.7, 1.8, mat=INTAKE)                                     # radiator inlets in the centre section
    for sgn in (1, -1):
        y = sgn * 2.4
        nacelle(p, 9.4, 5.4, 0.52, y, -0.12, hh=0.6, mirror=False)
        inline_nose(p, 10.5, 1.4, 0.52, y, -0.05, mirror=False)
        p.exhausts(9.6, 10.2, 3, y + 0.5, 0.1, size=0.08, mirror=False)
    p.prop((10.6, 2.4, -0.05), 3.0, 3, mirror=True)
    p.surface(1.8, 1.5, 1.15, 5.6, sweep=4, z0=0.5, tips=0, dihedral=[(0, 0), (2.8, 0.38)])
    fin = Fin(1.9, 1.5, 1.05, 1.65, 0.2, sweep=10, tips=0.5, y0=2.8).build(p, mirror=True)
    p.canopy(7.6, 10.7, 0.46, 0.50, 0.62, style='framed', frames=(8.2, 8.9, 9.6, 10.2), rail=0.55)
    p.cyl((7.9, 0, 1.0), (6.9, 0, 1.2), 0.05, GUN)
    p.cyl((12.4, 0.25, 0.1), (13.1, 0.25, 0.1), 0.05, GUN)
    w.tips_remap(p, 0.93)
    fin.top_remap(p, 0.8, mirror=True)
    lv = Livery(P.scheme_camo(P.SOV_GREEN, P.SOV_BLACK, P.SOV_LBLUE, sigma=1.1, seed=23), panel=1.5)
    lv.side('sov', 4.4, 0.2, 0.52, ymax=0.8).side('sov', 1.15, 1.2, 0.4)
    return p, lv


# ======================================================================
# Japan
# ======================================================================
@reg('japvp', 'A6M2 Zero')
def a6m2():
    L = 9.06
    p = Plane('japvp', 12.0, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.20, 0.40, 0.45), (3.0, 0.38, 0.56, 0.25), (4.8, 0.47, 0.64, 0.12),
                (6.2, 0.50, 0.62, 0.05), (7.4, 0.54, 0.58, 0.0), (7.6, 0.55, 0.57, 0.0)], n=2.1)
    p.radial_cowl(8.6, 1.15, 0.58, mat=BLACK)
    p.spinner(8.55, 0.5, 0.28, mat=METAL)
    w = W(6.95, 2.6, 1.2, 12.0, sweep=5, z0=-0.40, dihedral=[(0, 0), (6.0, 0.68)], tips=0.25,
          tc=(0.14, 0.09)).build(p)
    p.surface(1.4, 1.2, 0.7, 4.8, sweep=6, z0=0.45, tips=0.4)
    fin = Fin(1.45, 1.3, 0.6, 1.25, 0.5, sweep=34, tips=0.5).build(p)
    p.canopy(4.5, 6.7, 0.36, 0.42, 0.62, style='framed', frames=(5.0, 5.5, 6.0, 6.4), rail=0.55)
    bomb(p, 4.8, 6.9, 0.25, z=-0.85, mat=SKIN, fins=False)                 # 330 l drop tank
    w.guns(p, (2.6,), 0.2, dz=0.02)
    for dy in (-0.14, 0.14):
        p.box(7.6, 8.1, dy - 0.04, dy + 0.04, 0.52, 0.58, DARK)
    p.prop((8.7, 0, 0.0), 2.9, 3, blade=IJ_PROP, tip=IJ_TIP)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.62)
    lv = Livery(P.scheme_two(P.IJN_AMEIRO, P.IJN_AMEIRO))
    lv.band(1.55, 1.8, 125, remap=True, ymax=0.5)                          # carrier identification band
    lv.top('hino', 6.0, 3.8, 0.62).side('hino', 2.6, 0.2, 0.42, ymax=0.6)
    return p, lv


@reg('s37', 'Ki-84-I Hayate')
def ki84():
    L = 9.92
    p = Plane('s37', 11.24, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.22, 0.42, 0.45), (3.0, 0.40, 0.58, 0.25), (5.0, 0.48, 0.66, 0.12),
                (6.5, 0.52, 0.66, 0.05), (7.8, 0.56, 0.60, 0.0), (8.3, 0.58, 0.59, 0.0)], n=2.2)
    p.radial_cowl(9.45, 1.3, 0.60)
    p.spinner(9.4, 0.52, 0.30)
    w = W(7.3, 2.45, 1.2, 11.24, sweep=4, z0=-0.40, dihedral=[(0, 0), (5.62, 0.59)], tips=0.15,
          tc=(0.15, 0.09)).build(p)
    p.surface(1.4, 1.2, 0.7, 4.0, sweep=6, z0=0.45, tips=0.35)
    fin = Fin(1.45, 1.35, 0.6, 1.35, 0.5, sweep=28, tips=0.45).build(p)
    p.canopy(5.0, 6.6, 0.34, 0.42, 0.66, style='teardrop', frames=(5.5,))
    w.guns(p, (2.3,), 0.35, dz=0.02)
    for dy in (-0.14, 0.14):
        p.box(8.2, 8.8, dy - 0.04, dy + 0.04, 0.55, 0.6, DARK)
    p.prop((9.55, 0, 0.0), 3.05, 4, blade=IJ_PROP, tip=IJ_TIP)
    p.exhausts(8.0, 8.4, 3, 0.58, -0.1, size=0.08)
    w.le_strip(p, 1.0, 3.6)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.55)

    def ija(ctx):
        worn = ctx.noise(0.12, 41) > 1.9                                    # paint chipping
        top = np.where(worn[:, None], P._c(P.NMF, ctx.n), P._c(P.IJA_GREEN, ctx.n))
        return np.where((ctx.nz > -0.25)[:, None], top, P._c(P.NMF, ctx.n))
    lv = Livery(ija)
    lv.top('hino', 6.3, 3.7, 0.6).side('hino_w', 2.7, 0.2, 0.4, ymax=0.6)
    return p, lv


@reg('f23', 'Ki-61-I Hien')
def ki61():
    L = 8.94
    p = Plane('f23', 12.0, L, height=2.2)
    p.fuselage([(0.0, 0.07, 0.28, 0.55), (1.0, 0.20, 0.40, 0.45), (3.0, 0.38, 0.56, 0.25), (4.6, 0.44, 0.64, 0.15),
                (5.6, 0.45, 0.66, 0.10), (6.9, 0.42, 0.60, 0.05), (8.0, 0.34, 0.48, 0.02), (8.4, 0.30, 0.36, 0.02)],
               n=2.3)
    p.fuselage([(3.2, 0.08, 0.08, -0.45), (3.8, 0.32, 0.28, -0.7), (5.0, 0.34, 0.3, -0.72), (5.35, 0.32, 0.28, -0.7)],
               n=2.3, main=False)                                         # belly radiator
    p.ellipsoid((5.36, 0, -0.72), (0.04, 0.26, 0.22), INTAKE)
    p.spinner(8.4, 0.54, 0.30)
    w = W(6.5, 2.3, 1.05, 12.0, sweep=3, z0=-0.40, dihedral=[(0, 0), (6.0, 0.63)], tips=0.18,
          tc=(0.15, 0.09)).build(p)
    p.surface(1.25, 1.1, 0.7, 4.0, sweep=6, z0=0.45, tips=0.4)
    fin = Fin(1.3, 1.25, 0.55, 1.3, 0.5, sweep=28, tips=0.5).build(p)
    p.canopy(4.5, 6.1, 0.34, 0.42, 0.66, style='framed', frames=(5.0, 5.6), rail=0.6)
    for dy in (-0.14, 0.14):
        p.box(7.1, 7.8, dy - 0.04, dy + 0.04, 0.52, 0.58, DARK)
    w.guns(p, (2.2,), 0.3, dz=0.02)
    p.prop((8.55, 0, 0.02), 3.0, 3, blade=IJ_PROP, tip=IJ_TIP)
    p.exhausts(7.1, 8.0, 6, 0.36, 0.1, size=0.08)
    w.le_strip(p, 0.9, 3.4)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.5)

    def hien(ctx):
        mott = ctx.noise(0.25, 43) > 0.35
        top = np.where(mott[:, None], P._c(P.IJA_GREEN, ctx.n), P._c(P.NMF, ctx.n))
        return np.where((ctx.nz > -0.25)[:, None], top, P._c(P.NMF, ctx.n))
    lv = Livery(hien)
    lv.zone(lambda c: (c.x > 6.4) & (c.x < 8.3) & (c.nz > 0.55) & (np.abs(c.y) < 0.35), (30, 30, 30))
    lv.top('hino', 5.6, 3.9, 0.62).side('hino_w', 2.5, 0.2, 0.4, ymax=0.6)
    return p, lv


@reg('su34', 'B5N2 Kate')
def b5n2():
    L = 10.30
    p = Plane('su34', 15.52, L, height=2.4, zlow=2.0, s=CARRIER_S)
    p.fuselage([(0.0, 0.08, 0.30, 0.55), (1.5, 0.28, 0.46, 0.45), (4.0, 0.50, 0.66, 0.25), (6.5, 0.58, 0.72, 0.10),
                (8.3, 0.60, 0.70, 0.02), (8.8, 0.62, 0.64, 0.0)], n=2.1)
    p.radial_cowl(9.9, 1.2, 0.65, mat=BLACK)
    p.spinner(9.85, 0.45, 0.27, mat=METAL)
    w = W(8.2, 2.9, 1.3, 15.52, sweep=5, z0=-0.45, dihedral=[(0, 0), (2.0, 0.0), (7.76, 0.70)], tips=0.2,
          tc=(0.15, 0.09)).build(p)
    p.surface(1.45, 1.3, 0.8, 5.1, sweep=6, z0=0.45, tips=0.35)
    fin = Fin(1.5, 1.5, 0.65, 1.45, 0.5, sweep=30, tips=0.5).build(p)
    p.canopy(4.3, 8.3, 0.40, 0.46, 0.68, style='framed', frames=(4.8, 5.3, 5.8, 6.3, 6.8, 7.3, 7.8), rail=0.55)
    p.cyl((4.5, 0, 1.0), (3.5, 0, 1.2), 0.045, GUN)
    # Type 91 aerial torpedo
    p.fuselage([(4.3, 0.10, 0.10, -1.0), (4.8, 0.23, 0.23, -1.0), (8.8, 0.23, 0.23, -1.0), (9.3, 0.12, 0.12, -1.0)],
               n=2.0, main=False, mat=METAL)
    p.box(4.2, 4.6, -0.32, 0.32, -1.03, -0.97, DARK)
    p.box(4.2, 4.6, -0.03, 0.03, -1.3, -0.7, DARK)
    p.box(6.0, 7.2, -0.14, 0.14, -0.85, -0.40, DARK)                     # torpedo crutch
    p.prop((10.0, 0, 0.0), 3.2, 3, blade=IJ_PROP, tip=IJ_TIP)
    p.exhausts(8.9, 9.3, 3, 0.62, -0.15, size=0.08)
    w.tips_remap(p, 0.95)
    fin.top_remap(p, 0.62)
    lv = Livery(P.scheme_two(P.IJN_GREEN, P.IJN_GREY))
    lv.band(1.9, 2.25, 125, remap=True, ymax=0.5)
    lv.top('hino', 6.5, 4.8, 0.72).side('hino_w', 3.1, 0.2, 0.45, ymax=0.7)
    return p, lv
