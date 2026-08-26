"""Mod: skip the "Select Video Card" screen at launch - always VGA.

Pure CONFIG.TAT data patch; DRAKKHEN.COM is not modified.

The loader (DRAKKHEN.COM, a menu shell shared with Infogrames' HOSTAGE) reads CONFIG.TAT into a
buffer at 0x1A50 and then does:

    1030  cmp word ptr cs:[0x1a5a], -1   ; 0x1A5A == CONFIG.TAT+0x0A: chosen video card
    1036  jne 0x103b                     ; already chosen -> skip the menu
    1038  call 0x10f1                    ; otherwise SHOW "Select Video Card"

So the whole menu is gated on one word of a config file.  The menu itself is built at runtime by
walking the 5-word availability list at CONFIG.TAT+0x0E (0x0018 CGA, 0x00DA EGA, 0x013B Tandy,
0x0079 Hercules, 0x019C VGA - each a byte offset to a driver/engine record), which is why the
on-screen order is CGA/EGA/Tandy/HERCULES/VGA.  The stored value is the MENU INDEX into that list,
not a record offset: VGA = 4.  (Verified empirically - 8 and 9, the record indices, gave "insert
disk 1" and an instant exit respectively.)

Setting it to 4 boots straight into the VGA game.  Restoring 0xFFFF brings the menu back.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
FILE = 'CONFIG.TAT'
SEL_OFF = 0x0A          # chosen video card (0xFFFF = ask)
VGA_INDEX = 4           # index into the availability list at +0x0E
ASK = 0xFFFF


def apply_data(src_dir, out_dir):
    raw = bytearray(open(os.path.join(src_dir, FILE), 'rb').read())
    cur = int.from_bytes(raw[SEL_OFF:SEL_OFF + 2], 'little')
    assert cur in (ASK, VGA_INDEX), \
        '%s: unexpected video selection %#06x - refusing to patch' % (FILE, cur)
    # sanity: the availability list must be the known 5 records, VGA last
    want = [0x0018, 0x00DA, 0x013B, 0x0079, 0x019C]
    got = [int.from_bytes(raw[0x0E + 2 * i:0x10 + 2 * i], 'little') for i in range(5)]
    assert got == want, '%s: unexpected card list %s - refusing to patch' % (FILE, got)

    raw[SEL_OFF:SEL_OFF + 2] = VGA_INDEX.to_bytes(2, 'little')
    out = os.path.join(out_dir, FILE)
    open(out, 'wb').write(bytes(raw))
    print('  novideomenu: %s video select %#06x -> %d (VGA), menu skipped'
          % (FILE, cur, VGA_INDEX))
    return out
