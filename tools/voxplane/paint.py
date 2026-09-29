"""Paint schemes, national insignia and markings for the voxel aircraft."""
import numpy as np

from builder import (BLACK, BOMB, DARK, ENGINE, EXHAUST, FRAME, GLASS, GUN, INTAKE, MATCOL, METAL, RED, REMAP,
                     SKIN, WHITE, YELLOW, to_index)

# --------------------------------------------------------------- colours
OD = (92, 90, 58)            # US olive drab 41
NGRAY = (150, 150, 150)      # US neutral grey 43
NMF = (148, 150, 156)        # natural metal (RA2 lighting brightens it)
SEABLUE = (48, 58, 92)       # USN non-specular sea blue
INTBLUE = (84, 100, 134)     # USN intermediate blue
NWHITE = (225, 225, 225)
RAF_GREEN = (68, 78, 46)
RAF_OCEAN = (92, 96, 100)
RAF_EARTH = (96, 78, 50)
RAF_MSG = (160, 162, 165)    # medium sea grey
RAF_SKY = (190, 200, 170)
RLM70 = (46, 56, 40)
RLM71 = (70, 84, 52)
RLM65 = (150, 176, 196)
RLM74 = (78, 82, 84)
RLM75 = (108, 104, 112)
RLM76 = (180, 196, 204)
RLM81 = (88, 80, 58)
RLM82 = (84, 104, 60)
IT_SAND = (190, 162, 110)
IT_GREEN = (82, 86, 50)
IT_GREY = (160, 160, 158)
SOV_BGREY = (116, 120, 122)  # AMT-11
SOV_DGREY = (80, 82, 84)     # AMT-12
SOV_LBLUE = (150, 176, 196)  # AMT-7
SOV_GREEN = (84, 98, 56)     # AMT-4
SOV_BLACK = (40, 40, 36)
IJN_AMEIRO = (176, 170, 140)
IJN_GREEN = (52, 64, 46)
IJN_GREY = (168, 168, 160)
IJA_GREEN = (70, 80, 48)
BLUE_US = (40, 50, 110)
RED_I = (190, 20, 20)
YEL = (235, 200, 40)


def _c(c, n):
    return np.tile(np.array(c, float), (n, 1))


def upper_mask(ctx, split=-0.25):
    return ctx.nz > split


def fus_side(ctx, extra=0.12):
    zc, hh, hw = ctx.fus_axis()
    on_fus = np.abs(ctx.y) <= hw + extra
    return on_fus & (ctx.nz < 0.5)


def splinter(ctx, seed, cell=3.0, lines=5):
    """Straight-edged Luftwaffe splinter pattern in the top view (x,y)."""
    rng = np.random.default_rng(seed)
    L = ctx.plane.length
    B = ctx.plane.span
    v = np.zeros(ctx.n, bool)
    for _ in range(lines):
        ang = rng.uniform(0, np.pi)
        px, py = rng.uniform(0, L), rng.uniform(-B / 2, B / 2)
        side = (ctx.x - px) * np.sin(ang) - (np.abs(ctx.y) * rng.choice([1, -1]) - py) * np.cos(ang) > 0
        v ^= side
    return v


def blob(ctx, sigma, seed, thresh=0.0):
    return ctx.noise(sigma, seed) > thresh


# --------------------------------------------------------------- schemes
def scheme_two(top, bottom, split=-0.25):
    def f(ctx):
        return np.where(upper_mask(ctx, split)[:, None], _c(top, ctx.n), _c(bottom, ctx.n))
    return f


def scheme_camo(c1, c2, bottom, kind='blob', sigma=1.0, seed=3, side=None, side_mottle=None, split=-0.25,
                bottom_side=False):
    """Two colour disruptive upper surfaces.

    side: colour of the fuselage sides (e.g. RLM76 on Bf 109); side_mottle adds
    blotches of c1/c2 on the sides. bottom_side paints the sides in the
    bottom colour (RAF bombers: black sides)."""
    def f(ctx):
        if kind == 'splinter':
            m = splinter(ctx, seed)
        elif kind == 'mottle':
            m = blob(ctx, sigma, seed, 0.6)
        else:
            m = blob(ctx, sigma, seed)
        top = np.where(m[:, None], _c(c1, ctx.n), _c(c2, ctx.n))
        if kind == 'mottle':
            top = np.where(blob(ctx, sigma, seed + 7, 0.9)[:, None], _c(c1, ctx.n) * 0.85, top)
        out = np.where(upper_mask(ctx, split)[:, None], top, _c(bottom, ctx.n))
        if side is not None or bottom_side:
            sm = fus_side(ctx)
            sc = _c(bottom if bottom_side else side, ctx.n)
            if side_mottle:
                mm = blob(ctx, side_mottle, seed + 11, 0.2)
                sc = np.where(mm[:, None], np.where(m[:, None], _c(c1, ctx.n), _c(c2, ctx.n)), sc)
            out = np.where(sm[:, None], sc, out)
        return out
    return f


def scheme_nmf(base=NMF, var=0.05, seed=5, panel=1.6):
    """Natural metal: slightly different tone per panel."""
    def f(ctx):
        rng = np.random.default_rng(seed)
        tbl = 1 + rng.uniform(-var, var, 4096)
        k = (np.floor(ctx.x / panel).astype(int) * 131 + np.floor(np.abs(ctx.y) / (panel * 1.4)).astype(int) * 17 +
             np.floor(ctx.z / panel).astype(int) * 7) % 4096
        return _c(base, ctx.n) * tbl[k][:, None]
    return f


def scheme_navy(ctx):
    top = _c(SEABLUE, ctx.n)
    mid = _c(INTBLUE, ctx.n)
    low = _c(NWHITE, ctx.n)
    out = np.where((ctx.nz > 0.45)[:, None], top, mid)
    return np.where((ctx.nz < -0.35)[:, None], low, out)


# --------------------------------------------------------------- shapes
def poly_mask(u, v, poly):
    inside = np.zeros(u.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > v) != (y2 > v)) & (u < (x2 - x1) * (v - y1) / (y2 - y1 + 1e-12) + x1)
        inside ^= cond
    return inside


def star(u, v, R, inner=0.382):
    pts = []
    for i in range(10):
        a = np.pi / 2 + i * np.pi / 5
        r = R if i % 2 == 0 else R * inner
        pts.append((r * np.cos(a), r * np.sin(a)))
    return poly_mask(u, v, pts)


def disc(u, v, R):
    return u ** 2 + v ** 2 <= R ** 2


def rect(u, v, hu, hv, cu=0.0, cv=0.0):
    return (np.abs(u - cu) <= hu) & (np.abs(v - cv) <= hv)


def insignia_layers(kind, u, v, R):
    """Return list of (mask, rgb) in paint order for a national marking."""
    L = []
    if kind == 'us':           # 1943+ star and bar with blue surround
        ol = R * 0.14
        L.append((disc(u, v, R + ol) | rect(u, v, 2 * R + ol, R * 0.5 + ol), BLUE_US))
        L.append((rect(u, v, 2 * R, R * 0.5), NWHITE))
        L.append((disc(u, v, R), BLUE_US))
        L.append((star(u, v, R * 0.97), NWHITE))
    elif kind == 'us42':       # 1942 star in circle
        L.append((disc(u, v, R), BLUE_US))
        L.append((star(u, v, R * 0.97), NWHITE))
    elif kind == 'rafB':
        L.append((disc(u, v, R), (40, 48, 110)))
        L.append((disc(u, v, R * 0.42), (170, 30, 30)))
    elif kind == 'rafC1':
        L.append((disc(u, v, R), YEL))
        L.append((disc(u, v, R * 0.85), (40, 48, 110)))
        L.append((disc(u, v, R * 0.52), NWHITE))
        L.append((disc(u, v, R * 0.40), (170, 30, 30)))
    elif kind == 'rafC':
        L.append((disc(u, v, R), (40, 48, 110)))
        L.append((disc(u, v, R * 0.55), NWHITE))
        L.append((disc(u, v, R * 0.42), (170, 30, 30)))
    elif kind == 'balken':
        a = R * 0.22
        wb = R * 0.16
        L.append((rect(u, v, R, a + wb) | rect(u, v, a + wb, R), NWHITE))
        L.append((rect(u, v, R, a) | rect(u, v, a, R), (25, 25, 25)))
    elif kind == 'balken44':   # late war outline-only cross
        a = R * 0.22
        wb = R * 0.14
        L.append((rect(u, v, R, a + wb) | rect(u, v, a + wb, R), NWHITE))
        L.append((rect(u, v, R, a) | rect(u, v, a, R), RLM74))
    elif kind == 'sov':
        L.append((star(u, v, R * 1.16, 0.40), NWHITE))
        L.append((star(u, v, R), RED_I))
    elif kind == 'sov_plain':
        L.append((star(u, v, R), RED_I))
    elif kind == 'hino':
        L.append((disc(u, v, R), RED_I))
    elif kind == 'hino_w':
        L.append((disc(u, v, R * 1.2), NWHITE))
        L.append((disc(u, v, R), RED_I))
    elif kind == 'it_wing':    # fasces roundel, simplified
        L.append((disc(u, v, R), (25, 25, 25)))
        L.append((disc(u, v, R * 0.82), NWHITE))
        for k in (-0.35, 0, 0.35):
            L.append((rect(u, v, R * 0.09, R * 0.6, cu=k * R), (25, 25, 25)))
    elif kind == 'it_cross':   # Savoy white cross on the rudder
        L.append((rect(u, v, R * 0.18, R) | rect(u, v, R * 0.6, R * 0.18, cv=R * 0.15), NWHITE))
    return L


class Livery:
    """Collects the scheme and markings for one aircraft and paints voxels."""

    def __init__(self, scheme, panel=1.25, glass=(80, 96, 150), frame_dark=0.72, weather=0.035, seed=1,
                 prop_blade=None, prop_tip=None):
        self.scheme = scheme
        self.panel = panel
        self.glass = glass
        self.frame_dark = frame_dark
        self.weather = weather
        self.seed = seed
        self.decals = []      # functions ctx -> list[(mask, rgb, is_remap)]

    # -- decal helpers ------------------------------------------------
    def top(self, kind, x, y, R, both=True, zmin=None):
        def f(ctx):
            out = []
            for yy in ([y, -y] if both else [y]):
                u = ctx.y - yy
                v = ctx.x - x
                sel = (ctx.nz > 0.25)
                if zmin is not None:
                    sel &= ctx.z > zmin
                for m, c in insignia_layers(kind, u, v, R):
                    out.append((m & sel, c, False))
            return out
        self.decals.append(f)
        return self

    def side(self, kind, x, z, R, ymax=None):
        def f(ctx):
            out = []
            u = ctx.x - x
            v = ctx.z - z
            sel = np.abs(ctx.ny) > 0.22
            if ymax is not None:
                sel &= np.abs(ctx.y) <= ymax
            for m, c in insignia_layers(kind, u, v, R):
                out.append((m & sel, c, False))
            return out
        self.decals.append(f)
        return self

    def band(self, x0, x1, rgb, ymax=None, zmin=-99, zmax=99, remap=False, upper_only=False):
        """Fuselage band between x0 and x1 (or any region in that slab)."""
        def f(ctx):
            m = (ctx.x >= x0) & (ctx.x <= x1) & (ctx.z >= zmin) & (ctx.z <= zmax) & (ctx.L == SKIN)
            if ymax is not None:
                m &= np.abs(ctx.y) <= ymax
            if upper_only:
                m &= ctx.nz > -0.3
            return [(m, rgb, remap)]
        self.decals.append(f)
        return self

    def spanband(self, y0, y1, rgb, remap=False, xmin=-99, xmax=99):
        """Spanwise zone (e.g. coloured wingtips) on skin voxels."""
        def f(ctx):
            ay = np.abs(ctx.y)
            m = (ay >= y0) & (ay <= y1) & (ctx.L == SKIN) & (ctx.x >= xmin) & (ctx.x <= xmax)
            return [(m, rgb, remap)]
        self.decals.append(f)
        return self

    def zone(self, fn, rgb, remap=False, skin_only=True):
        def f(ctx):
            m = fn(ctx)
            if skin_only:
                m &= (ctx.L == SKIN)
            return [(m, rgb, remap)]
        self.decals.append(f)
        return self

    def stripes(self, y0, width, n=5, x_fus=None, fus_width=None):
        """D-Day invasion stripes: n alternating white/black bands."""
        def f(ctx):
            out = []
            ay = np.abs(ctx.y)
            for i in range(n):
                c = NWHITE if i % 2 == 0 else (25, 25, 25)
                m = (ay >= y0 + i * width) & (ay < y0 + (i + 1) * width) & (ctx.L == SKIN)
                if fus_width is not None:
                    m &= ay > fus_width
                if x_fus is not None:
                    m2 = (ctx.x >= x_fus + i * width) & (ctx.x < x_fus + (i + 1) * width) & (ctx.L == SKIN)
                    m2 &= ay <= (fus_width or 0.7)
                    m |= m2
                out.append((m, c, False))
            return out
        self.decals.append(f)
        return self

    def sharkmouth(self, x_nose, z_c, length, height, ymax=None):
        """Flying Tigers style shark mouth on the chin/cowling sides."""
        def f(ctx):
            u = (x_nose - ctx.x) / length          # 0 at the front of the mouth, 1 at the corner
            v = (ctx.z - z_c) / height
            sel = (np.abs(ctx.ny) > 0.2) | (ctx.nz < -0.2)
            if ymax is not None:
                sel &= np.abs(ctx.y) <= ymax
            inside = (u >= 0) & (u <= 1)
            upper_lip = 0.55 * (1 - u) ** 0.8
            lower_lip = -0.9 * (1 - u) ** 0.6
            mouth = inside & (v <= upper_lip) & (v >= lower_lip) & sel
            border = inside & (v <= upper_lip + 0.2) & (v >= lower_lip - 0.2) & sel & ~mouth
            # teeth: white triangles along the lips
            tooth = (np.abs(((u * 9) % 1.0) - 0.5) * 2)
            teeth = mouth & ((v > upper_lip - 0.35 * (1 - tooth) - 0.05) | (v < lower_lip + 0.35 * (1 - tooth) + 0.05))
            eye = sel & ((u - 1.25) ** 2 * 6 + (v - 0.55) ** 2 * 3 < 0.35)
            pupil = sel & ((u - 1.25) ** 2 * 6 + (v - 0.55) ** 2 * 3 < 0.10)
            return [(border, (25, 25, 25), False), (mouth, (170, 25, 25), False), (teeth, NWHITE, False),
                    (eye & (ctx.L == SKIN), NWHITE, False), (pupil & (ctx.L == SKIN), (25, 25, 25), False)]
        self.decals.append(f)
        return self

    # -- the painter --------------------------------------------------
    def __call__(self, ctx):
        base = self.scheme(ctx).astype(float)
        rgb = np.zeros((ctx.n, 3))
        remap = np.zeros(ctx.n, bool)
        for lab, col in MATCOL.items():
            rgb[ctx.L == lab] = col
        skin = (ctx.L == SKIN)
        rgb[skin] = base[skin]
        fr = ctx.L == FRAME
        rgb[fr] = base[fr] * self.frame_dark
        g = ctx.L == GLASS
        gl = np.array(self.glass, float)
        hi = (ctx.nz > 0.55) & (ctx.nx > -0.1)
        rgb[g] = gl
        rgb[g & hi] = np.minimum(gl * 1.6 + 30, 255)
        rgb[g & (ctx.nz < 0.1)] = gl * 0.75
        rm = ctx.L == REMAP
        rgb[rm] = (125, 125, 125)
        remap |= rm
        for f in self.decals:
            for m, c, isr in f(ctx):
                if isr:
                    rgb[m] = c if len(np.shape(c)) else (c, c, c)
                    remap[m] = True
                else:
                    rgb[m] = c
                    remap[m] = False
        # panel lines on painted skin (not on markings that are remap)
        P = self.panel
        s = ctx.s
        paintable = (ctx.L == SKIN) & ~remap
        lx = np.abs(((ctx.x / P) % 1.0) - 0.5) * P > P / 2 - 0.5 / s
        zc, hh, hw = ctx.fus_axis()
        on_wing = np.abs(ctx.y) > hw + 1.0 / s
        ly = on_wing & (np.abs(((np.abs(ctx.y) / (P * 1.3)) % 1.0) - 0.5) * P * 1.3 > P * 0.65 - 0.5 / s)
        lines = paintable & (lx | ly) & (np.abs(ctx.nz) > 0.2)
        lines |= paintable & lx & ~on_wing
        rgb[lines] *= 0.86
        # low frequency weathering
        w = 1 + self.weather * ctx.noise(0.8, self.seed + 99)
        rgb[~remap] *= w[~remap, None]
        rgb = np.clip(rgb, 0, 255)
        return to_index(rgb, remap)
