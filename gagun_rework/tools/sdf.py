"""Minimal numpy SDF toolkit + RA2 orthographic renderer (30 deg elevation, 1 world unit = 1 px)."""
import numpy as np

S2 = np.sqrt(0.5)
# camera: direction from scene toward viewer
CAM = np.array([np.cos(np.radians(30)) * S2, np.cos(np.radians(30)) * S2, 0.5])
RIGHT = np.array([S2, -S2, 0.0])
UP = np.array([-0.5 * S2, -0.5 * S2, np.cos(np.radians(30))])


def project(P):
    """world -> screen offsets (sx, sy) relative to the ground centre."""
    P = np.asarray(P, float)
    return P @ RIGHT, -(P @ UP)


# ---------------------------------------------------------------- primitives
def box(p, c, h, r=0.0):
    q = np.abs(p - np.asarray(c, float)) - (np.asarray(h, float) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def cyl(p, c, r, h0, h1, axis=2):
    """cylinder along an axis (0/1/2) with radius r, spanning [h0,h1] on that axis (c gives the other coords)."""
    c = np.asarray(c, float)
    idx = [i for i in range(3) if i != axis]
    d2 = np.sqrt((p[..., idx[0]] - c[idx[0]]) ** 2 + (p[..., idx[1]] - c[idx[1]]) ** 2) - r
    mid, hh = (h0 + h1) / 2, (h1 - h0) / 2
    d1 = np.abs(p[..., axis] - mid) - hh
    return np.minimum(np.maximum(d1, d2), 0) + np.sqrt(np.maximum(d1, 0) ** 2 + np.maximum(d2, 0) ** 2)


def cone(p, axis, a0, a1, r0, r1, c=(0, 0, 0)):
    """truncated cone along axis from a0 (radius r0) to a1 (radius r1). Approximate but Lipschitz-safe."""
    c = np.asarray(c, float)
    idx = [i for i in range(3) if i != axis]
    rad = np.sqrt((p[..., idx[0]] - c[idx[0]]) ** 2 + (p[..., idx[1]] - c[idx[1]]) ** 2)
    t = np.clip((p[..., axis] - a0) / (a1 - a0), 0, 1)
    r = r0 + (r1 - r0) * t
    k = np.sqrt(1 + ((r1 - r0) / (a1 - a0)) ** 2)
    d2 = (rad - r) / k
    mid, hh = (a0 + a1) / 2, abs(a1 - a0) / 2
    d1 = np.abs(p[..., axis] - mid) - hh
    return np.minimum(np.maximum(d1, d2), 0) + np.sqrt(np.maximum(d1, 0) ** 2 + np.maximum(d2, 0) ** 2)


def octa(p, z0, z1, r0, r1, c=(0, 0)):
    """octagonal frustum (inradius r0 at z0 -> r1 at z1), flat faces aligned to world X/Y axes and diagonals."""
    x = np.abs(p[..., 0] - c[0]); y = np.abs(p[..., 1] - c[1])
    rad = np.maximum(np.maximum(x, y), (x + y) * S2)
    t = np.clip((p[..., 2] - z0) / (z1 - z0), 0, 1)
    r = r0 + (r1 - r0) * t
    k = np.sqrt(1 + ((r1 - r0) / (z1 - z0)) ** 2)
    d2 = (rad - r) / k
    d1 = np.abs(p[..., 2] - (z0 + z1) / 2) - (z1 - z0) / 2
    return np.maximum(d1, d2)


def planes(p, pl):
    """convex polytope: max over (n, d) of n.p - d (normals unit)."""
    out = None
    for n, d in pl:
        n = np.asarray(n, float); n = n / np.linalg.norm(n)
        v = p @ n - d
        out = v if out is None else np.maximum(out, v)
    return out


class Scene:
    """list of (fn(p)->dist, material, subtract?)"""

    def __init__(self):
        self.parts = []

    def add(self, fn, mat):
        self.parts.append((fn, mat, False))

    def cut(self, fn, mat=None):
        self.parts.append((fn, mat, True))

    def eval(self, p):
        d = np.full(p.shape[:-1], 1e9); m = np.zeros(p.shape[:-1], int)
        for fn, mat, sub in self.parts:
            v = fn(p)
            if sub:
                nd = np.maximum(d, -v)
                if mat is not None:  # cut surfaces get the cut material (e.g. dark recesses)
                    m = np.where((nd > d) & (-v > d - 1e-6), mat, m)
                d = nd
            else:
                closer = v < d
                m = np.where(closer, mat, m); d = np.where(closer, v, d)
        return d, m


def render(scene, W, H, cx, cy, ss=3, clip=None, light=None, t_far=120.0):
    """sphere-trace every sub-pixel. returns dict with per-subsample hit, material, normal, pos, ao."""
    ys, xs = np.mgrid[0:H * ss, 0:W * ss]
    sx = (xs + 0.5) / ss - cx
    sy = (ys + 0.5) / ss - cy
    base = sx[..., None] * RIGHT + (-sy)[..., None] * UP
    o = base + t_far * CAM
    dirv = -CAM
    t = np.zeros(sx.shape)
    hit = np.zeros(sx.shape, bool)
    alive = np.ones(sx.shape, bool)
    f = scene.eval if clip is None else (lambda q: clipped(scene, q, clip))
    for _ in range(220):
        idx = np.nonzero(alive)
        if len(idx[0]) == 0:
            break
        p = o[idx] + t[idx][:, None] * dirv
        d, _ = f(p)
        t[idx] += d * 0.8
        h = d < 0.02
        hit[idx[0][h], idx[1][h]] = True
        dead = h | (t[idx] > 2 * t_far)
        alive[idx[0][dead], idx[1][dead]] = False
    P = o + t[..., None] * dirv
    res = dict(hit=hit, P=P)
    hp = P[hit]
    _, mat = f(hp)
    if hasattr(scene, 'paint'):
        mat = scene.paint(hp, mat)
    e = 0.05
    n = np.stack([f(hp + np.array(v))[0] - f(hp - np.array(v))[0] for v in ([e, 0, 0], [0, e, 0], [0, 0, e])], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    ao = np.ones(len(hp))
    for k, dist in enumerate((0.6, 1.4, 2.6)):
        dd, _ = f(hp + n * dist)
        ao -= np.clip(dist - dd, 0, None) / dist * (0.5 / (k + 1.2))
    res.update(mat=mat, n=n, ao=np.clip(ao, 0, 1), ss=ss, W=W, H=H)
    return res


def clipped(scene, q, clip):
    d, m = scene.eval(q)
    return np.maximum(d, q[..., 2] - clip), m


def ground_shadow(scene, W, H, cx, cy, L, ss=2, clip=None):
    """mask of ground pixels (z=0) whose ray toward the light hits the scene."""
    ys, xs = np.mgrid[0:H * ss, 0:W * ss]
    sx = (xs + 0.5) / ss - cx
    sy = (ys + 0.5) / ss - cy
    # ground point under screen pixel: P = sx*RIGHT + a*G with z=0 -> solve along the view ray
    base = sx[..., None] * RIGHT + (-sy)[..., None] * UP
    tz = base[..., 2] / CAM[2]  # move along -CAM until z = 0
    G = base - tz[..., None] * CAM
    f = scene.eval if clip is None else (lambda q: clipped(scene, q, clip))
    t = np.full(sx.shape, 0.3)
    inside = np.zeros(sx.shape, bool)
    alive = np.ones(sx.shape, bool)
    for _ in range(90):
        idx = np.nonzero(alive)
        if len(idx[0]) == 0:
            break
        p = G[idx] + t[idx][:, None] * L
        d, _ = f(p)
        h = d < 0.05
        inside[idx[0][h], idx[1][h]] = True
        t[idx] += np.maximum(d, 0.05) * 0.9
        dead = h | (t[idx] > 90) | (p[:, 2] > 60)
        alive[idx[0][dead], idx[1][dead]] = False
    m = inside.reshape(H, ss, W, ss).mean((1, 3)) >= 0.5
    return m
