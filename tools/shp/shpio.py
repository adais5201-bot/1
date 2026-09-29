"""Read / write Tiberian Sun / Red Alert 2 SHP files and render them.

    python3 shpio.py OUT.png FILE.shp [FILE.shp ...]    # contact sheet of frames 0..n/2
"""
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def read_shp(path):
    data = open(path, 'rb').read()
    zero, W, H, n = struct.unpack_from('<4H', data, 0)
    assert zero == 0
    frames = []
    for i in range(n):
        x, y, w, h, flags = struct.unpack_from('<4HB', data, 8 + 24 * i)
        offset = struct.unpack_from('<I', data, 8 + 24 * i + 20)[0]
        colour = data[8 + 24 * i + 12:8 + 24 * i + 16]
        img = np.zeros((H, W), np.uint8)
        if w and h and offset:
            pix = np.zeros((h, w), np.uint8)
            p = offset
            if flags & 2:                     # per line: u16 length, then RLE (3) or raw (2)
                for row in range(h):
                    ln = struct.unpack_from('<H', data, p)[0]
                    q, end, col = p + 2, p + ln, 0
                    while q < end and col < w:
                        v = data[q]
                        if v == 0 and flags == 3:
                            col += data[q + 1]
                            q += 2
                        else:
                            pix[row, col] = v
                            col += 1
                            q += 1
                    p = end
            else:                             # raw
                pix = np.frombuffer(data, np.uint8, w * h, p).reshape(h, w).copy()
            img[y:y + h, x:x + w] = pix
        frames.append({'img': img, 'x': x, 'y': y, 'w': w, 'h': h, 'flags': flags, 'colour': colour})
    return {'W': W, 'H': H, 'frames': frames}


def write_shp(path, W, H, images):
    """images: list of (H, W) uint8 arrays; cropped and RLE (type 3) encoded."""
    head = struct.pack('<4H', 0, W, H, len(images))
    entries, blobs = [], []
    offset = 8 + 24 * len(images)
    for img in images:
        ys, xs = np.nonzero(img)
        if len(xs) == 0:
            entries.append(struct.pack('<4HB3xI4xI', 0, 0, 0, 0, 0, 0, 0))
            continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        crop = img[y0:y1, x0:x1]
        out = bytearray()
        for row in crop:
            line = bytearray()
            i = 0
            while i < len(row):
                if row[i] == 0:
                    j = i
                    while j < len(row) and row[j] == 0 and j - i < 255:
                        j += 1
                    line += bytes((0, j - i))
                    i = j
                else:
                    line.append(row[i])
                    i += 1
            out += struct.pack('<H', len(line) + 2) + line
        while len(out) % 8:
            out.append(0)
        entries.append(struct.pack('<4HB3x', x0, y0, x1 - x0, y1 - y0, 3) + b'\0\0\0\0' + b'\0\0\0\0'
                       + struct.pack('<I', offset))
        blobs.append(bytes(out))
        offset += len(out)
    open(path, 'wb').write(head + b''.join(entries) + b''.join(blobs))


def palette():
    return np.loadtxt(os.path.join(HERE, '..', 'voxplane', 'ra2_unit_palette.txt')).astype(np.uint8)


def to_rgb(img, pal, bg=(48, 64, 80), remap=None):
    rgb = pal[img].copy()
    if remap is not None:
        m = (img >= 16) & (img <= 31)
        t = 1 - (img[m] - 16) / 15.0
        rgb[m] = (np.array(remap)[None, :] * (0.25 + 0.75 * t[:, None])).astype(np.uint8)
    rgb[img == 0] = bg
    return rgb


if __name__ == '__main__':
    from PIL import Image, ImageDraw
    pal = palette()
    tiles = []
    for f in sys.argv[2:]:
        s = read_shp(f)
        n = len(s['frames'])
        im = to_rgb(s['frames'][0]['img'], pal, remap=(200, 40, 40))
        t = Image.fromarray(im).resize((s['W'] * 2, s['H'] * 2), Image.NEAREST)
        c = Image.new('RGB', (t.width, t.height + 16), (20, 20, 20))
        c.paste(t, (0, 16))
        ImageDraw.Draw(c).text((3, 2), '%s %dx%d n=%d' % (os.path.basename(f), s['W'], s['H'], n),
                               fill=(255, 230, 90))
        tiles.append(c)
    W = sum(t.width for t in tiles) + 4 * len(tiles)
    H = max(t.height for t in tiles)
    S = Image.new('RGB', (W, H), (12, 12, 12))
    x = 0
    for t in tiles:
        S.paste(t, (x, 0))
        x += t.width + 4
    S.save(sys.argv[1])
