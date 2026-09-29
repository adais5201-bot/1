"""Change unit names in ra2md.csf; every other string is copied byte for byte.

    python3 patch_csf.py ORIG_ra2md.csf OUT_ra2md.csf
"""
import struct
import sys

# label (case-insensitive) -> new text
NAMES = {
    'Name:BEAG2': 'Me 262 喷气战斗机',     # was 基因突變機 ("mutation plane")
}


def encode(text):
    raw = text.encode('utf-16-le')
    return bytes(b ^ 0xFF for b in raw), len(raw) // 2


def patch(src, dst):
    data = open(src, 'rb').read()
    assert data[:4] == b' FSC'
    n_labels = struct.unpack_from('<I', data, 8)[0]
    out = bytearray(data[:24])
    pos = 24
    todo = {k.lower(): v for k, v in NAMES.items()}
    for _ in range(n_labels):
        tag, n_pairs, llen = struct.unpack_from('<4sII', data, pos)
        assert tag == b' LBL'
        label = data[pos + 12:pos + 12 + llen].decode('latin-1')
        out += data[pos:pos + 12 + llen]
        pos += 12 + llen
        for _ in range(n_pairs):
            stag, vlen = struct.unpack_from('<4sI', data, pos)
            vbytes = data[pos + 8:pos + 8 + 2 * vlen]
            end = pos + 8 + 2 * vlen
            extra = b''
            if stag == b'WRTS':
                elen = struct.unpack_from('<I', data, end)[0]
                extra = data[end:end + 4 + elen]
                end += 4 + elen
            new = todo.pop(label.lower(), None)
            if new is not None:
                vbytes, vlen = encode(new)
                print('%s -> %s' % (label, new))
            out += stag + struct.pack('<I', vlen) + vbytes + extra
            pos = end
    assert pos == len(data), 'trailing data'
    assert not todo, 'labels not found: %s' % list(todo)
    open(dst, 'wb').write(bytes(out))


if __name__ == '__main__':
    patch(sys.argv[1], sys.argv[2])
