"""Change aircraft names in ra2md.csf; every other string is copied byte for byte.

    python3 patch_csf.py ORIG_ra2md.csf OUT_ra2md.csf
"""
import struct
import sys

# Aircraft names that did not fit the WWII aircraft the models now show
# (the mod's other names such as 雷霆, 黑鯊, 暗星 are kept).
# label (case-insensitive) -> new text
NAMES = {
    'Name:ORCA':     '戰鷹戰機',            # P-40E Warhawk                      was 入侵者戰機
    'Name:AORCA':    '戰鷹戰機',
    'Name:BEAGLE':   '野馬戰機',            # P-51D Mustang                      was 黑鷹戰機
    'Name:STBOMBER': '閃電戰機',            # P-38L Lightning                    was 光劍戰機
    'Name:F2002':    '海盜戰機',            # F4U-1D Corsair                     was 冰魄戰機
    'Name:B2BOMBER': '空中堡壘轟炸機',      # B-17G Flying Fortress              was 隱形轟炸機
    'Name:F1172':    '鐵雨轟炸機',          # B-24D, carpet of cluster bombs     was 隱形戰機
    'Name:BEAG2':    '風暴戰機',            # Me 262 (Sturmvogel, "storm bird")  was 基因突變機
    'Name:JAPVP':    '零式戰機',            # A6M2 Zero                          was 藍心戰機
    'Name:JAGDS':    '疾風戰機',            # Ki-84 Hayate                       was 暗影戰機
    'Name:F23':      '飛燕戰機',            # Ki-61 Hien                         was 幽灵战机
}

# Skin names keep their livery name; only the aircraft part changes.
# label -> (old aircraft part, new aircraft part)
SKIN_NAMES = {
    'Name:FALCA': ('入侵者戰機', '戰鷹戰機'), 'Name:BEAGA': ('黑鷹戰機', '野馬戰機'),
    'Name:F2002A': ('冰魄戰機', '海盜戰機'), 'Name:F2002B': ('冰魄戰機', '海盜戰機'),
    'Name:F2002C': ('冰魄戰機', '海盜戰機'),
    'Name:MIG2000A': ('急凍戰機', 'Fw 190戰機'),
}


def decode(vbytes):
    return bytes(b ^ 0xFF for b in vbytes).decode('utf-16-le')


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
    skins = {k.lower(): v for k, v in SKIN_NAMES.items()}
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
            if label.lower() in skins:
                old_part, new_part = skins.pop(label.lower())
                text = decode(vbytes)
                assert old_part in text, (label, text)
                new = text.replace(old_part, new_part)
            if new is not None:
                vbytes, vlen = encode(new)
                print('%s -> %s' % (label, new))
            out += stag + struct.pack('<I', vlen) + vbytes + extra
            pos = end
    assert pos == len(data), 'trailing data'
    assert not todo and not skins, 'labels not found: %s' % (list(todo) + list(skins))
    open(dst, 'wb').write(bytes(out))


if __name__ == '__main__':
    patch(sys.argv[1], sys.argv[2])
