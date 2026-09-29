"""Read / write Westwood VXL (Red Alert 2 / Yuri's Revenge) and HVA files."""
import struct

import numpy as np


class Section:
    def __init__(self, name='body'):
        self.name = name
        self.scale = 1.0 / 12.0
        self.transform = np.eye(3, 4)
        self.minb = np.zeros(3)
        self.maxb = np.zeros(3)
        self.size = (0, 0, 0)
        self.nmode = 4  # RA2 normals table (244 entries)
        self.filled = None
        self.color = None
        self.normal = None


def read_vxl(path):
    d = open(path, 'rb').read()
    if not d[:16].startswith(b'Voxel Animation'):
        raise ValueError('%s: not a VXL file' % path)
    _npal, nhdr, _ntail, bodysize = struct.unpack_from('<4I', d, 16)
    remap = (d[32], d[33])
    pal = np.frombuffer(d[34:802], np.uint8).reshape(256, 3).copy()
    off = 802
    secs = []
    for _ in range(nhdr):
        s = Section(d[off:off + 16].split(b'\0')[0].decode('latin1'))
        secs.append(s)
        off += 28
    body = off
    off += bodysize
    for s in secs:
        ss, _se, sd = struct.unpack_from('<3I', d, off)
        s.scale = struct.unpack_from('<f', d, off + 12)[0]
        s.transform = np.array(struct.unpack_from('<12f', d, off + 16)).reshape(3, 4)
        s.minb = np.array(struct.unpack_from('<3f', d, off + 64))
        s.maxb = np.array(struct.unpack_from('<3f', d, off + 76))
        s.size = tuple(d[off + 88:off + 91])
        s.nmode = d[off + 91]
        off += 92
        xs, ys, zs = s.size
        s.color = np.zeros(s.size, np.uint8)
        s.normal = np.zeros(s.size, np.uint8)
        s.filled = np.zeros(s.size, bool)
        starts = struct.unpack_from('<%di' % (xs * ys), d, body + ss)
        for i, st in enumerate(starts):
            if st == -1:
                continue
            x, y = i % xs, i // xs
            p = body + sd + st
            z = 0
            while z < zs:
                skip, cnt = d[p], d[p + 1]
                p += 2
                z += skip
                for _ in range(cnt):
                    s.color[x, y, z] = d[p]
                    s.normal[x, y, z] = d[p + 1]
                    s.filled[x, y, z] = True
                    p += 2
                    z += 1
                p += 1
    return dict(pal=pal, remap=remap, sections=secs)


def write_vxl(path, sections, pal, remap=(16, 31)):
    body = bytearray()
    for s in sections:
        xs, ys, zs = s.size
        assert max(s.size) <= 255, (s.name, s.size)
        starts, ends, data = [], [], bytearray()
        for i in range(xs * ys):
            x, y = i % xs, i // xs
            col = s.filled[x, y]
            if not col.any():
                starts.append(-1)
                ends.append(-1)
                continue
            starts.append(len(data))
            z = 0
            while z < zs:
                skip = 0
                while z < zs and not col[z] and skip < 255:
                    skip += 1
                    z += 1
                run = bytearray()
                cnt = 0
                while z < zs and col[z] and cnt < 255:
                    run += bytes((int(s.color[x, y, z]), int(s.normal[x, y, z])))
                    cnt += 1
                    z += 1
                data += bytes((skip, cnt)) + run + bytes((cnt,))
            ends.append(len(data) - 1)
        s._ss = len(body)
        body += struct.pack('<%di' % len(starts), *starts)
        s._se = len(body)
        body += struct.pack('<%di' % len(ends), *ends)
        s._sd = len(body)
        body += data
    out = bytearray(b'Voxel Animation\0')
    out += struct.pack('<4I', 1, len(sections), len(sections), len(body))
    out += bytes(remap) + np.asarray(pal, np.uint8).tobytes()
    for i, s in enumerate(sections):
        out += s.name.encode('latin1')[:15].ljust(16, b'\0') + struct.pack('<3I', i, 1, 0)
    out += body
    for s in sections:
        out += struct.pack('<3I', s._ss, s._se, s._sd) + struct.pack('<f', s.scale)
        out += struct.pack('<12f', *np.asarray(s.transform, float).flatten())
        out += struct.pack('<3f', *s.minb) + struct.pack('<3f', *s.maxb)
        out += bytes(s.size) + bytes((s.nmode,))
    open(path, 'wb').write(out)


def read_hva(path):
    d = open(path, 'rb').read()
    nf, ns = struct.unpack_from('<2I', d, 16)
    names = [d[24 + 16 * i:40 + 16 * i].split(b'\0')[0].decode('latin1') for i in range(ns)]
    off = 24 + 16 * ns
    m = np.array(struct.unpack_from('<%df' % (nf * ns * 12), d, off)).reshape(nf, ns, 3, 4)
    return dict(name=d[:16].split(b'\0')[0], names=names, mats=m)


def write_hva(path, name, names, mats):
    """mats: array (frames, sections, 3, 4)."""
    nf, ns = mats.shape[:2]
    out = bytearray(name.encode('latin1')[:15].ljust(16, b'\0'))
    out += struct.pack('<2I', nf, ns)
    for n in names:
        out += n.encode('latin1')[:15].ljust(16, b'\0')
    out += struct.pack('<%df' % (nf * ns * 12), *np.asarray(mats, float).flatten())
    open(path, 'wb').write(out)
