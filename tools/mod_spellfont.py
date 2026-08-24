"""Mod: replace the runic spell/phial font with readable Latin letters.

This is a DATA patch, not a code patch - it touches no engine bytes and costs none of the
dead-space budget in drakmod.py.

The game stores spell names as plain ASCII ("HEALMIN", "LIGHTNG", ... at DS:0AA1) and draws each
character through a 5x5 runic glyph set.  One rune = one letter, so nothing needs translating:
swapping the glyph art alone makes the existing strings readable.

The glyph set lives in RESI_VGA.6C0, which is a BARE BPE CHUNK - u32be packed, u32be unpacked,
then BPE blocks (22988 -> 40256 bytes).  It has no container header, so it does not look like the
`.?C1` files, but it is compressed all the same.

*** Do not patch this file in place. ***  The font bytes are legible in the compressed stream
because they are literal bytes in a block whose pair table happens not to code those values.  Write
different values there and some of them ARE pair codes, which expand to two bytes each and
desynchronise every byte after them - the file still has the right length and the diff looks tiny
and clean, but the decode is garbage from that point on.  The game boots (other files are fine) and
then dies when it needs this one.  That cost a debugging round; decode, patch, re-encode instead.

In the DECODED data the font is an 80-byte block at offset 36216: five 16-byte rows, each holding
25 glyph-rows of 5 bits packed end to end.  Glyph N therefore occupies bits [5N, 5N+5) of every one
of the five rows - it is NOT five consecutive bytes, which is why a byte-aligned search finds
nothing.  A 2-byte-per-glyph table follows at 36296: (width<<4 | row, x offset) = (0x50, 0/5/10...),
exactly 25 entries.  25 glyphs = 125 bits, so a row has 3 bits spare and the set covers A..Y; 'Z'
would spill past the row and is garbage in the original too.  Spell names use A..V only.

Found by reading the drawn glyphs out of a 320x200 screen capture, then searching every file - and
then every file's decompressed form - for that bit pattern at every stride and bit offset.
"""
import os, struct, sys

sys.setrecursionlimit(100000)
import drakpack

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
FILE = 'RESI_VGA.6C0'
OFF, ROW_BYTES, NGLYPH = 36216, 16, 25
TABLE_OFF = OFF + ROW_BYTES * 5          # 25 * (width<<4|row, xoff) pairs

# 5x5 uppercase, one 5-bit value per row, MSB = leftmost pixel.
FONT = {
    'A': (0x0E, 0x11, 0x1F, 0x11, 0x11), 'B': (0x1E, 0x11, 0x1E, 0x11, 0x1E),
    'C': (0x0F, 0x10, 0x10, 0x10, 0x0F), 'D': (0x1E, 0x11, 0x11, 0x11, 0x1E),
    'E': (0x1F, 0x10, 0x1C, 0x10, 0x1F), 'F': (0x1F, 0x10, 0x1C, 0x10, 0x10),
    'G': (0x0F, 0x10, 0x13, 0x11, 0x0E), 'H': (0x11, 0x11, 0x1F, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x0E), 'J': (0x07, 0x02, 0x02, 0x12, 0x0C),
    'K': (0x11, 0x12, 0x1C, 0x12, 0x11), 'L': (0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x11, 0x11), 'N': (0x11, 0x19, 0x15, 0x13, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x0E), 'P': (0x1E, 0x11, 0x1E, 0x10, 0x10),
    'Q': (0x0E, 0x11, 0x15, 0x12, 0x0D), 'R': (0x1E, 0x11, 0x1E, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x0E, 0x01, 0x1E), 'T': (0x1F, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x0E), 'V': (0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x15, 0x1B, 0x11), 'X': (0x11, 0x0A, 0x04, 0x0A, 0x11),
    'Y': (0x11, 0x0A, 0x04, 0x04, 0x04),
}


def _get(block, r, n):
    """Read glyph n's row r (5 bits) out of the packed block."""
    v = 0
    for c in range(5):
        i = r * ROW_BYTES * 8 + n * 5 + c
        v = (v << 1) | ((block[i >> 3] >> (7 - (i & 7))) & 1)
    return v


def _set(block, r, n, v):
    for c in range(5):
        i = r * ROW_BYTES * 8 + n * 5 + c
        bit = (v >> (4 - c)) & 1
        if bit:
            block[i >> 3] |= 0x80 >> (i & 7)
        else:
            block[i >> 3] &= ~(0x80 >> (i & 7)) & 0xFF


def render(block):
    """Return the 25 glyphs as lists of 5 strings - used by the self-check and for eyeballing."""
    return [[''.join('#' if _get(block, r, n) & (1 << (4 - c)) else '.' for c in range(5))
             for r in range(5)] for n in range(NGLYPH)]


def _decode(path):
    d = open(path, 'rb').read()
    packed, unpacked = struct.unpack_from('>II', d)
    raw, _ = drakpack.bpe_decode(d, 8)
    assert len(raw) == unpacked, '%s: decoded %d bytes, header says %d' % (FILE, len(raw), unpacked)
    return bytearray(raw)


def apply_data(src_dir, out_dir):
    raw = _decode(os.path.join(src_dir, FILE))
    before = len(raw)
    block = bytearray(raw[OFF:OFF + ROW_BYTES * 5])
    assert tuple(_get(block, r, 7) for r in range(5)) == (0x1F, 0x11, 0x11, 0x11, 0x11), \
        'rune H is not at offset %d - unexpected build of %s' % (OFF, FILE)
    assert raw[TABLE_OFF:TABLE_OFF + 6] == b'\x50\x00\x50\x05\x50\x0a', \
        'glyph table not where expected - refusing to patch'
    for n in range(NGLYPH):
        rows = FONT[chr(ord('A') + n)]
        for r in range(5):
            _set(block, r, n, rows[r])
    raw[OFF:OFF + ROW_BYTES * 5] = block
    assert len(raw) == before, 'decoded size changed - would alter the load footprint'

    body = drakpack.bpe_encode_raw(bytes(raw))
    out = os.path.join(out_dir, FILE)
    open(out, 'wb').write(struct.pack('>II', len(body), len(raw)) + body)
    print('  spellfont: %d glyphs rewritten in %s (decoded size %d unchanged, file %d bytes)'
          % (NGLYPH, FILE, len(raw), 8 + len(body)))
    return out


def _check():
    """Round-trip: pack the new font, read it back, confirm every glyph survives bit-packing."""
    block = bytearray(ROW_BYTES * 5)
    for n in range(NGLYPH):
        for r, v in enumerate(FONT[chr(ord('A') + n)]):
            _set(block, r, n, v)
    for n in range(NGLYPH):
        want = FONT[chr(ord('A') + n)]
        got = tuple(_get(block, r, n) for r in range(5))
        assert got == want, 'glyph %s round-trip failed: %r != %r' % (chr(65 + n), got, want)
    # the original must DECODE to the known runic 'H' - guards against a wrong OFF
    orig = _decode(os.path.join(GAME, '_backup', 'original', FILE))
    ob = bytearray(orig[OFF:OFF + ROW_BYTES * 5])
    assert tuple(_get(ob, r, 7) for r in range(5)) == (0x1F, 0x11, 0x11, 0x11, 0x11), \
        'original rune H not at the expected offset - RESI_VGA.6C0 is not the expected build'
    # and the repack must round-trip through the BPE decoder byte for byte
    body = drakpack.bpe_encode_raw(bytes(orig))
    back, _ = drakpack.bpe_decode(struct.pack('>II', len(body), len(orig)) + body, 8)
    assert bytes(back) == bytes(orig), 'BPE repack does not round-trip'
    print('mod_spellfont self-check ok (%d glyphs, repack round-trips)' % NGLYPH)


if __name__ == '__main__':
    _check()
    orig = _decode(os.path.join(GAME, '_backup', 'original', FILE))
    glyphs = render(bytearray(orig[OFF:OFF + ROW_BYTES * 5]))
    for r in range(5):
        print('  '.join(glyphs[n][r] for n in range(NGLYPH)))
