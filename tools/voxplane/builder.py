"""Parametric voxel aircraft builder for Red Alert 2 / Yuri's Revenge.

All geometry is described in metres (x = forward, from the tail at x=0 to the
nose at x=L; y = right; z = up) and voxelised at a per-aircraft resolution.
The finished model follows the conventions of the reference model NAFAF:
  * unit voxel spacing (bounds size == voxel count) for every section,
  * body bounds centred on x/y, about 30% of the height below the origin,
  * smooth normals computed from the geometry (RA2 normal mode 4),
  * propellers as separate sections with the pivot on the hub, turning in
    PROP_FRAMES small steps over one blade pitch (a 2-frame 60 degree flip of a
    big propeller shows in game as a ghost rocking left and right).
"""
import os

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter

from vxlio import Section

HERE = os.path.dirname(os.path.abspath(__file__))
NORMALS = np.loadtxt(os.path.join(HERE, 'ra2_normals.txt'))
PALETTE = np.loadtxt(os.path.join(HERE, 'ra2_unit_palette.txt')).astype(np.uint8)

PROP_FRAMES = 6

# Material labels
SKIN, GLASS, FRAME, GUN, ENGINE, REMAP, BLACK, METAL, BOMB, INTAKE, YELLOW, WHITE, RED, EXHAUST, DARK = range(1, 16)


def scale_for_span(span):
    """Voxels per metre. Fighters use a true common scale (~8.2 vox/m, the
    scale NAFAF is built at); large aircraft are compressed so a heavy bomber
    stays within ~180 voxels of wingspan."""
    base = 8.2
    if span <= 12.0:
        return base
    return base * 12.0 * (span / 12.0) ** 0.6 / span


def pchip(xs, ys):
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    f = PchipInterpolator(xs, ys, extrapolate=False)

    def g(x):
        return np.nan_to_num(f(np.clip(x, xs[0], xs[-1])))
    return g


def naca(xc, tc):
    xc = np.clip(xc, 0, 1)
    return 5 * tc * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1015 * xc ** 4)


class Plane:
    def __init__(self, name, span, length, height=4.0, s=None, zlow=None):
        self.name = name
        self.span = span
        self.length = length
        self.s = s or scale_for_span(span)
        s = self.s
        m = 1.5
        self.g0 = np.array([-m, -span / 2 - m, -(zlow if zlow is not None else height) - m])
        g1 = np.array([length + m, span / 2 + m, height + m])
        self.shape = tuple(int(np.ceil(v)) for v in (g1 - self.g0) * s)
        self.xs = self.g0[0] + (np.arange(self.shape[0]) + 0.5) / s
        self.ys = self.g0[1] + (np.arange(self.shape[1]) + 0.5) / s
        self.zs = self.g0[2] + (np.arange(self.shape[2]) + 0.5) / s
        self.occ = np.zeros(self.shape, bool)
        self.lab = np.zeros(self.shape, np.uint8)
        self.hmin = 1.0 / s          # minimum half thickness -> surfaces >= 2 voxels
        self.props = []               # (hub xyz in metres, prop dict)
        self.fus = None               # main fuselage stations for painters

    # ------------------------------------------------------------ helpers
    def _sub(self, x0, x1, y0, y1, z0, z1):
        def rng(a, b, g0, n):
            i0 = int(np.floor((a - g0) * self.s)) - 1
            i1 = int(np.ceil((b - g0) * self.s)) + 1
            return max(i0, 0), min(i1, n)
        ix = rng(x0, x1, self.g0[0], self.shape[0])
        iy = rng(y0, y1, self.g0[1], self.shape[1])
        iz = rng(z0, z1, self.g0[2], self.shape[2])
        sl = (slice(*ix), slice(*iy), slice(*iz))
        X = self.xs[sl[0]][:, None, None]
        Y = self.ys[sl[1]][None, :, None]
        Z = self.zs[sl[2]][None, None, :]
        return sl, X, Y, Z

    def _apply(self, sl, mask, mat, mode='over'):
        occ = self.occ[sl]
        lab = self.lab[sl]
        if mode == 'over':          # add volume, overwrite material
            lab[mask] = mat
            occ |= mask
        elif mode == 'under':       # add volume only where empty
            m = mask & ~occ
            lab[m] = mat
            occ |= m
        elif mode == 'paint':       # recolour existing voxels only
            lab[mask & occ] = mat
        elif mode == 'cut':
            occ &= ~mask
            lab[mask] = 0

    # ---------------------------------------------------------- primitives
    def fuselage(self, st, n=2.2, mat=SKIN, y0=0.0, mode='over', main=True, mirror=False):
        """st: list of (x, half_width, half_height, z_centre)."""
        st = sorted(st)
        xs = [a[0] for a in st]
        fw = pchip(xs, [a[1] for a in st])
        fh = pchip(xs, [a[2] for a in st])
        fz = pchip(xs, [a[3] for a in st])
        if main and self.fus is None:
            self.fus = (xs[0], xs[-1], fw, fh, fz)
        wmax = max(a[1] for a in st)
        zlo = min(a[3] - a[2] for a in st)
        zhi = max(a[3] + a[2] for a in st)
        for yc in ([y0, -y0] if mirror else [y0]):
            sl, X, Y, Z = self._sub(xs[0], xs[-1], yc - wmax, yc + wmax, zlo, zhi)
            w = np.maximum(fw(X), 0.6 / self.s)
            h = np.maximum(fh(X), 0.6 / self.s)
            inside = (np.abs(Y - yc) / w) ** n + (np.abs(Z - fz(X)) / h) ** n <= 1.0
            inside &= (X >= xs[0]) & (X <= xs[-1])
            self._apply(sl, inside, mat, mode)

    def surface(self, xle, cr, ct, b, sweep=0.0, z0=0.0, dihedral=None, tc=(0.15, 0.09), tips=0.1,
                ellip=False, qc=0.25, mat=SKIN, mode='over', vertical=False, y0=0.0, ymin=0.0,
                tip_x=None, te_straight=False, cut_root=None, xcr=(0.0, 1.0), ymax=None):
        """Wing / stabiliser / fin.

        Horizontal surfaces are mirrored: b is the full span.  Vertical ones
        (fins) extend upward from z0 with height b, placed at y=y0.
        xle: x of the root leading edge, sweep: leading edge sweep in degrees
        (positive = swept back).  dihedral: list of (spanwise distance, dz).
        """
        B = b if vertical else b / 2.0
        if vertical:
            sl, X, Y, Z = self._sub(xle - cr - B * 1.5 - 1, xle + 1 + B * 0.5, y0 - cr * 0.3 - 1,
                                    y0 + cr * 0.3 + 1, z0 - 0.5, z0 + B + 0.5)
            yy = Z - z0
            tcoord = Y - y0
        else:
            dz = max([abs(d) for _, d in (dihedral or [(0, 0)])]) + cr * 0.3 + 0.5
            sl, X, Y, Z = self._sub(xle - cr - B * 1.5 - 1, xle + 1 + B * 0.5, -B - 0.5, B + 0.5,
                                    z0 - dz, z0 + dz)
            yy = np.abs(Y)
        yy = np.broadcast_to(yy, np.broadcast_shapes(X.shape, Y.shape, Z.shape))
        t = np.clip(yy / B, 0, 1)
        if ellip:
            c = cr * np.sqrt(np.clip(1 - t ** 2, 0, 1))
            xq = xle - qc * cr - yy * np.tan(np.radians(sweep))
            le = xq + qc * c
        else:
            clin = cr + (ct - cr) * t
            lel = xle - yy * np.tan(np.radians(sweep))
            if te_straight:  # straight trailing edge, all taper on the leading edge
                lel = (xle - cr) + clin
            if tips > 0:
                u = np.clip((t - (1 - tips)) / tips, 0, 1)
                f = np.sqrt(np.clip(1 - u ** 2, 0, 1))
            else:
                f = np.ones_like(t)
            c = clin * f
            le = lel - (1 - f) * 0.35 * clin
        xc = (le - X) / np.maximum(c, 1e-6)
        tcv = tc[0] + (tc[1] - tc[0]) * t
        half = np.maximum(naca(xc, tcv) * c, self.hmin)
        if vertical:
            inside = (np.abs(tcoord) <= half)
        else:
            if dihedral:
                dy = [a for a, _ in dihedral]
                dzv = [d for _, d in dihedral]
                zm = z0 + np.interp(yy, dy, dzv)
            else:
                zm = z0
            inside = np.abs(Z - zm) <= half
        inside &= (xc >= xcr[0]) & (xc <= xcr[1]) & (yy <= B) & (yy >= ymin) & (c > 0.5 / self.s)
        if ymax is not None:
            inside &= yy <= ymax
        self._apply(sl, inside, mat, mode)

    def ellipsoid(self, c, r, mat=SKIN, mode='over', mirror=False, zcut=None, xcut=None):
        for cy in ([c[1], -c[1]] if mirror else [c[1]]):
            sl, X, Y, Z = self._sub(c[0] - r[0], c[0] + r[0], cy - r[1], cy + r[1], c[2] - r[2], c[2] + r[2])
            inside = ((X - c[0]) / r[0]) ** 2 + ((Y - cy) / r[1]) ** 2 + ((Z - c[2]) / r[2]) ** 2 <= 1
            if zcut is not None:
                inside &= Z >= zcut
            if xcut is not None:
                inside &= X <= xcut
            self._apply(sl, inside, mat, mode)

    def cyl(self, p0, p1, r, mat=GUN, mode='over', mirror=False, r1=None):
        r1 = r if r1 is None else r1
        for sgn in ([1, -1] if mirror else [1]):
            a = np.array([p0[0], p0[1] * sgn, p0[2]], float)
            b = np.array([p1[0], p1[1] * sgn, p1[2]], float)
            rr = max(r, r1, 0.5 / self.s)
            lo = np.minimum(a, b) - rr
            hi = np.maximum(a, b) + rr
            sl, X, Y, Z = self._sub(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
            d = b - a
            L2 = d @ d
            tt = np.clip(((X - a[0]) * d[0] + (Y - a[1]) * d[1] + (Z - a[2]) * d[2]) / L2, 0, 1)
            dist2 = (X - a[0] - tt * d[0]) ** 2 + (Y - a[1] - tt * d[1]) ** 2 + (Z - a[2] - tt * d[2]) ** 2
            rad = np.maximum(r + (r1 - r) * tt, 0.55 / self.s)
            self._apply(sl, dist2 <= rad ** 2, mat, mode)

    def box(self, x0, x1, y0, y1, z0, z1, mat=SKIN, mode='over', mirror=False):
        for sgn in ([1, -1] if mirror else [1]):
            ya, yb = sorted((y0 * sgn, y1 * sgn))
            sl, X, Y, Z = self._sub(x0, x1, ya, yb, z0, z1)
            inside = (X >= x0) & (X <= x1) & (Y >= ya) & (Y <= yb) & (Z >= z0) & (Z <= z1)
            self._apply(sl, inside, mat, mode)

    def canopy(self, x0, x1, hw, hh, zb, y0=0.0, style='bubble', frames=(), rail=None, sink=0.25, mat=GLASS):
        sl, X, Y, Z = self._sub(x0, x1, y0 - hw, y0 + hw, zb - sink, zb + hh)
        u = np.clip((X - x0) / (x1 - x0), 0, 1)
        if style == 'bubble':
            h = hh * np.sin(np.pi * u) ** 0.55
            w = hw * np.sin(np.pi * u) ** 0.35
        elif style == 'teardrop':  # steep windscreen, long tapering rear
            prof = np.where(u > 0.7, ((1 - u) / 0.3) ** 0.6, np.clip(u / 0.7, 0, 1) ** 0.35)
            h = hh * prof
            w = hw * np.maximum(prof, 0.001) ** 0.5
        else:  # 'framed' greenhouse: windscreen in front, long flat roof
            prof = np.minimum(np.clip(u / 0.15, 0, 1) ** 0.6, np.clip((1 - u) / 0.25, 0, 1) ** 0.7)
            h = hh * prof
            w = hw * np.maximum(prof, 0.001) ** 0.3
        inside = ((Y - y0) / np.maximum(w, 1e-6)) ** 2 + ((Z - zb) / np.maximum(h, 1e-6)) ** 2 <= 1
        inside &= (Z >= zb - sink) & (X >= x0) & (X <= x1)
        self._apply(sl, inside, mat, 'over')
        fm = np.zeros_like(inside)
        for xf in frames:
            fm |= np.abs(X - xf) < 0.6 / self.s
        if rail is not None:
            fm |= np.abs(Z - (zb + rail * hh)) < 0.55 / self.s
        fm |= Z < zb - sink + 0.9 / self.s
        self._apply(sl, inside & fm, FRAME, 'paint')

    def glaze(self, x0, x1, dx, dz, zmin=-99, zmax=99, dy=None, frame_mat=FRAME, ymax=99):
        """Turn existing skin in a nose/tail region into framed glazing."""
        sl, X, Y, Z = self._sub(x0, x1, -ymax, ymax, zmin, zmax)
        m = (X >= x0) & (X <= x1) & (Z >= zmin) & (Z <= zmax) & (np.abs(Y) <= ymax)
        m = m & self.occ[sl] & (self.lab[sl] == SKIN)
        fr = np.zeros(m.shape, bool)
        fr |= (np.abs(((X - x1) / dx) - np.round((X - x1) / dx)) * dx < 0.55 / self.s)
        fr |= (np.abs((Z / dz) - np.round(Z / dz)) * dz < 0.55 / self.s)
        if dy:
            fr |= (np.abs((Y / dy) - np.round(Y / dy)) * dy < 0.55 / self.s)
        lab = self.lab[sl]
        lab[m] = GLASS
        lab[m & fr] = frame_mat

    def cut(self, fn, bbox):
        sl, X, Y, Z = self._sub(*bbox)
        self._apply(sl, fn(X, Y, Z), 0, 'cut')

    def paint(self, fn, bbox, mat):
        sl, X, Y, Z = self._sub(*bbox)
        self._apply(sl, fn(X, Y, Z), mat, 'paint')

    # ------------------------------------------------------------ assemblies
    def radial_cowl(self, x_front, length, r, y=0.0, z=0.0, mirror=False, mat=SKIN, lip=None, face=ENGINE):
        """Short radial-engine cowling with dark engine face and ring lip."""
        st = [(x_front - length, r * 0.92, r * 0.92, z), (x_front - length * 0.5, r, r, z),
              (x_front - 0.02, r * 0.97, r * 0.97, z), (x_front, r * 0.9, r * 0.9, z)]
        self.fuselage(st, n=2.0, mat=mat, y0=y, main=False, mirror=mirror)
        ys = [y, -y] if mirror else [y]
        for yy in ys:
            self.cyl((x_front - 0.25, yy, z), (x_front + 0.02, yy, z), r * 0.78, face, mode='over')
            if lip is not None:
                sl, X, Y, Z = self._sub(x_front - 0.35, x_front + 0.05, yy - r, yy + r, z - r, z + r)
                rr = np.sqrt((Y - yy) ** 2 + (Z - z) ** 2)
                self._apply(sl, (X > x_front - 0.3) & (rr > r * 0.7), lip, 'paint')

    def spinner(self, x_base, length, r, y=0.0, z=0.0, mat=REMAP, mirror=False):
        st = [(x_base, r, r, z), (x_base + length * 0.5, r * 0.8, r * 0.8, z), (x_base + length, 0.05, 0.05, z)]
        self.fuselage(st, n=2.0, mat=mat, y0=y, main=False, mirror=mirror)

    def exhausts(self, x0, x1, n, y, z, size=0.12, mirror=True):
        for i in range(n):
            xx = x0 + (x1 - x0) * (i + 0.5) / n
            self.box(xx - size, xx + size, y - 0.02, y + size * 1.4, z - size, z + size, EXHAUST, 'over', mirror=mirror)

    def prop(self, hub, diameter, blades, tip=YELLOW, blade=BLACK, chord=0.10, mirror=False):
        for yy in ([hub[1], -hub[1]] if mirror else [hub[1]]):
            self.props.append((np.array([hub[0], yy, hub[2]], float),
                               dict(d=diameter, n=blades, tip=tip, blade=blade, chord=chord,
                                    flip=(yy < 0))))

    # -------------------------------------------------------------- output
    def finish(self, painter, zfrac=0.3):
        occ = self.occ
        idx = np.argwhere(occ)
        lo = idx.min(0)
        hi = idx.max(0) + 1
        lo = np.maximum(lo - 1, 0)
        hi = np.minimum(hi + 1, self.shape)
        crop = tuple(slice(a, b) for a, b in zip(lo, hi))
        occ = occ[crop]
        lab = self.lab[crop]
        size = tuple(int(v) for v in occ.shape)
        # geometry normals
        nrm = surface_normals(occ)
        P = np.stack(np.meshgrid(self.xs[crop[0]], self.ys[crop[1]], self.zs[crop[2]], indexing='ij'), -1)
        ctx = Ctx(self, P[occ], nrm[occ], lab[occ], occ, crop)
        colors = painter(ctx)
        body = Section('body')
        body.size = size
        body.filled = occ
        body.color = np.zeros(size, np.uint8)
        body.color[occ] = colors
        body.normal = np.zeros(size, np.uint8)
        body.normal[occ] = quantize_normals(nrm[occ])
        body.minb = np.array([-size[0] / 2.0, -size[1] / 2.0, -round(size[2] * zfrac)])
        body.maxb = body.minb + np.array(size)
        sections = []
        mats_frames = []
        for i, (hub, pd) in enumerate(self.props):
            sec = make_prop(self.s, pd, painter)
            sec.name = 'Propeller' if len(self.props) == 1 else 'Propeller%d' % (i + 1)
            cont = (hub - self.g0) * self.s - lo      # continuous index (voxel centre = i + 0.5)
            pos = body.minb + cont                    # body-space coordinate of hub
            T = pos / sec.scale
            frames = []
            for k in range(PROP_FRAMES):
                # small steady steps over one blade pitch: the propeller turns
                # smoothly instead of jumping between two blade positions
                ang = np.radians(360.0 / pd['n'] * k / PROP_FRAMES) * (-1 if pd.get('flip') else 1)
                m = np.eye(3, 4)
                m[1, 1], m[1, 2], m[2, 1], m[2, 2] = np.cos(ang), -np.sin(ang), np.sin(ang), np.cos(ang)
                m[:, 3] = T
                frames.append(m)
            sections.append(sec)
            mats_frames.append(frames)
        # NAFAF order: propellers first, body last
        sections.append(body)
        nf = PROP_FRAMES if self.props else 1
        mats_frames.append([np.eye(3, 4)] * nf)
        mats = np.array(mats_frames).transpose(1, 0, 2, 3)    # (frames, sections, 3, 4)
        return sections, mats


class Ctx:
    """Data handed to painters: per-voxel positions (m), normals, labels."""

    def __init__(self, plane, P, N, L, occ, crop):
        self.plane = plane
        self.P = P
        self.x, self.y, self.z = P[:, 0], P[:, 1], P[:, 2]
        self.N = N
        self.nx, self.ny, self.nz = N[:, 0], N[:, 1], N[:, 2]
        self.L = L
        self.n = len(L)
        self.occ = occ
        self.crop = crop
        self.s = plane.s

    def noise(self, sigma_m, seed=1):
        rng = np.random.default_rng(seed)
        f = gaussian_filter(rng.standard_normal(self.occ.shape), sigma_m * self.s, mode='wrap')
        f /= f.std() + 1e-9
        return f[self.occ]

    def fus_axis(self):
        """z centre / half height / half width of the main fuselage at each voxel's x."""
        x0, x1, fw, fh, fz = self.plane.fus
        xx = np.clip(self.x, x0, x1)
        return fz(xx), fh(xx), fw(xx)


def surface_normals(occ, sigma=1.1):
    f = gaussian_filter(occ.astype(np.float32), sigma)
    g = -np.stack(np.gradient(f), -1)
    ln = np.linalg.norm(g, axis=-1, keepdims=True)
    g = np.where(ln > 1e-6, g / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))
    return g


def quantize_normals(n):
    return np.argmax(n @ NORMALS.T, axis=1).astype(np.uint8)


# Palette indices usable for ordinary colours (no specials, no remap, no magenta)
_ALLOWED = np.array([i for i in range(32, 204)])
_PALF = PALETTE[_ALLOWED].astype(float)


def to_index(rgb, remap_mask=None):
    rgb = np.asarray(rgb, float)
    uniq, inv = np.unique(np.round(rgb).astype(int), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    w = np.array([0.30, 0.59, 0.11]) * 3
    d = (((uniq[:, None, :] - _PALF[None, :, :]) ** 2) * w).sum(-1)
    # also penalise hue shift (compare chroma vectors)
    cu = uniq - uniq.mean(1, keepdims=True)
    cp = _PALF - _PALF.mean(1, keepdims=True)
    d += 0.8 * ((cu[:, None, :] - cp[None, :, :]) ** 2).sum(-1)
    out = _ALLOWED[np.argmin(d, 1)][inv]
    if remap_mask is not None and remap_mask.any():
        lum = rgb[remap_mask] @ np.array([0.30, 0.59, 0.11]) / 255.0
        out[remap_mask] = 16 + np.clip(np.round((1 - lum) * 15), 0, 15).astype(int)
    return out.astype(np.uint8)


def make_prop(s, pd, painter):
    R = pd['d'] / 2 * s                       # radius in voxels
    D = int(2 * np.ceil(R) + 1)
    D += (D % 2 == 0)
    xs = 5
    c = (np.array([xs, D, D]) - 1) / 2.0
    X, Y, Z = np.meshgrid(*[np.arange(n) - cc for n, cc in zip((xs, D, D), c)], indexing='ij')
    r = np.sqrt(Y ** 2 + Z ** 2)
    phi = np.arctan2(Z, Y)
    occ = np.zeros(X.shape, bool)
    lab = np.zeros(X.shape, np.uint8)
    n = pd['n']
    chord = pd['chord'] * pd['d'] * s
    sense = -1 if pd.get('flip') else 1
    for k in range(n):
        th = 2 * np.pi * k / n + np.pi / 2
        d = np.angle(np.exp(1j * (phi - th)))
        along = r * np.cos(d)
        tang = r * np.sin(d)
        rr = np.clip(along / R, 0, 1)
        w = chord * (0.55 + 0.45 * np.sin(np.pi * np.clip(rr * 1.1, 0, 1))) * np.where(rr > 0.9, np.sqrt(np.clip(1 - ((rr - 0.9) / 0.1) ** 2, 0, 1)), 1)
        pitch = 0.9 - 0.5 * rr
        xoff = sense * tang * pitch * 0.6
        m = (along > 0) & (along <= R) & (np.abs(tang) <= np.maximum(w / 2, 0.55)) & (np.abs(X - xoff) <= 0.9)
        occ |= m
        lab[m] = 1
        tipm = m & (along > R * 0.9)
        lab[tipm] = 2
    hub = (r <= max(1.2, 0.08 * R)) & (np.abs(X) <= 1.5)
    occ |= hub
    lab[hub] = 1
    sec = Section('Propeller')
    sec.size = occ.shape
    sec.filled = occ
    nrm = surface_normals(occ, 0.8)
    sec.normal = np.zeros(occ.shape, np.uint8)
    sec.normal[occ] = quantize_normals(nrm[occ])
    sec.color = np.zeros(occ.shape, np.uint8)
    cols = {}
    for k, key in ((1, 'blade'), (2, 'tip')):
        v = pd[key]
        cols[k] = MATCOL.get(v, (40, 40, 40)) if isinstance(v, (int, np.integer)) else v
    rgb = np.array([cols[l] for l in lab[occ]], float)
    sec.color[occ] = to_index(rgb)
    sec.minb = -np.array(occ.shape) / 2.0
    sec.maxb = np.array(occ.shape) / 2.0
    return sec


MATCOL = {
    BLACK: (35, 35, 35), YELLOW: (235, 200, 40), METAL: (175, 175, 180), GUN: (45, 45, 45),
    ENGINE: (70, 70, 70), EXHAUST: (60, 50, 40), INTAKE: (25, 25, 25), WHITE: (235, 235, 235),
    RED: (190, 20, 20), BOMB: (80, 85, 60), DARK: (50, 50, 50),
}
