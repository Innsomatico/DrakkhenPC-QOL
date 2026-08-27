"""Mod: the launcher menu in color - deep blue stipple field, gold text and borders.

Pure DRAKKHEN.COM data patch, three immediate bytes (user picked blue/gold from live mockups):

  com:146C  the background fill's attribute      0x07 -> 0x01  (the 0xB1 stipple, drawn grey
            by `mov ax,0x07B1` at com:1469..146D, becomes dark blue on black)
  com:14BB  the block-drawer's default attribute 0x07 -> 0x0E  (every text block - box borders,
            title, labels, key strip, copyright - draws gold unless a block embeds its own
            <ATTR> code)
  com:14DD  the drawer's code-5 "reset to default" attribute, kept in lockstep with com:14BB
            (used e.g. after the 'Loading ......' blink, which is <ATTR:87> in the strip block)

The drawer (com:148E) is a tiny display language - 0x0D newline, 0x24/0x00 end, 0x03 skip-N,
0x04 attr-follows, 0x05 attr-reset, 0x02 RLE-run - so finer per-element colouring is possible
later by recomposing blocks in place; these three bytes colour everything wholesale.

No dependencies: colours apply to whatever menu is present (stock 5-item or menu4's 4-item).
"""
FILE = 'DRAKKHEN.COM'
BYTES = [
    (0x146C, 0x07, 0x01),   # field: dark blue
    (0x14BB, 0x07, 0x0E),   # text default: gold
    (0x14DD, 0x07, 0x0E),   # attr-reset: gold
]


def runs():
    return [(a, bytes([new])) for a, _, new in BYTES]


def apply_data(src_dir, out_dir):
    import os
    d = bytearray(open(os.path.join(src_dir, FILE), 'rb').read())
    for a, old, new in BYTES:
        cur = d[a - 0x100]
        assert cur in (old, new), 'attr byte at com:%04X is %02X, expected %02X' % (a, cur, old)
        d[a - 0x100] = new
    out = os.path.join(out_dir, FILE)
    if os.path.exists(out):                      # compose with mod_menu4's output
        d2 = bytearray(open(out, 'rb').read())
        for a, _, new in BYTES:
            d2[a - 0x100] = new
        d = d2
    open(out, 'wb').write(d)
    print('  menucolor: %s - blue field, gold text (3 attr bytes)' % FILE)


def demo():
    import tempfile, os
    g = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as t:
        apply_data(os.path.join(g, '_backup', 'original'), t)
        d = open(os.path.join(t, FILE), 'rb').read()
        assert len(d) == 6953
        for a, _, new in BYTES:
            assert d[a - 0x100] == new
    print('mod_menucolor self-check OK')


if __name__ == '__main__':
    demo()
