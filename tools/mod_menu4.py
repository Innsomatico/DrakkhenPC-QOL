"""Mod: remove "Select video card" from the launcher's main menu - 4 items, renumbered.

Pure DRAKKHEN.COM data patch. With mod_novideomenu pinning the card to VGA, the F3 entry is a
foot-gun: choosing any other card rewrites Config.tat and the next Play loads a DIFFERENT
executable (DRAKE/DRAKC/DRAKT*) that none of this project's mods live in - every QOL feature
silently vanishes.  Removing the entry closes the only in-game path off the patched binary.

The menu is not a list widget; it is a static text block plus a parallel jump table, so a proper
removal needs both halves (see NOTES.md "The launcher, DRAKKHEN.COM"):

  * text lines at com:04D1/04FA/0523 (36 chars each, in the block drawn from com:040A):
    F3 becomes Joystick calibration, F4 becomes Return to DOS, the F5 line goes blank.
  * jump table at com:01C3 (5 words, dispatched via `jmp word cs:[bx+0x1C3]` at com:104E):
    slot 2 -> 0x13C7 (joystick), slot 3 -> 0x1053 (exit), slot 4 -> 0x103B (redraw loop,
    so a stray F5 press does nothing instead of exiting).

The key filter at com:1041 accepts F1..F5 before the table dispatch, which is why slot 4 must
stay valid rather than being dropped.

First-boot note: on a stock install the loader forces the card menu once (cs:[0x1A5A] == -1).
That path is untouched and still works; mod_novideomenu preempts it entirely, which is why this
mod requires it - together there is no reachable card selection at all.

Verified live (2026-08-27): memory probe of the running launcher shows the redrawn menu -
F1 Creation / F2 Game / F3 Joystick calibration / F4 Return to DOS, no fifth entry.
"""
import hashlib, os, struct

FILE = 'DRAKKHEN.COM'
STOCK_SHA = '32060c0ff0dfa42a37462889ca8995c83809796cc7408f1295241d8d50888704'  # GOG == Steam

LINES = [
    (0x04D1, '  F3   Joystick calibration         '),
    (0x04FA, '  F4   Return to DOS                '),
    (0x0523, ' ' * 36),
]
JT_ADDR = 0x01C3
JT_OLD = (0x12D1, 0x12DB, 0x1265, 0x13C7, 0x1053)
JT_NEW = (0x12D1, 0x12DB, 0x13C7, 0x1053, 0x103B)


def runs():
    """The patch as (com_offset, bytes) runs - what the installers embed."""
    out = [(a, t.encode()) for a, t in LINES]
    out.append((JT_ADDR, struct.pack('<5H', *JT_NEW)))
    return out


def apply_data(src_dir, out_dir):
    src = os.path.join(src_dir, FILE)
    d = bytearray(open(src, 'rb').read())
    assert hashlib.sha256(d).hexdigest() == STOCK_SHA, 'DRAKKHEN.COM is not the stock US build'
    assert struct.unpack_from('<5H', d, JT_ADDR - 0x100) == JT_OLD, 'jump table not as expected'
    for a, b in runs():
        d[a - 0x100:a - 0x100 + len(b)] = b
    open(os.path.join(out_dir, FILE), 'wb').write(d)
    print('  menu4: %s - video-card entry removed, menu renumbered to 4 items' % FILE)


def demo():
    import tempfile, shutil
    g = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as t:
        apply_data(g, t)
        d = open(os.path.join(t, FILE), 'rb').read()
        assert b'Select video card' not in d
        assert b'  F3   Joystick calibration' in d
        assert struct.unpack_from('<5H', d, JT_ADDR - 0x100) == JT_NEW
        assert len(d) == 6953
    print('mod_menu4 self-check OK')


if __name__ == '__main__':
    demo()
