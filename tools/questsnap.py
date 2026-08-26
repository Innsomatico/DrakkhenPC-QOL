"""Bank a quest-progress snapshot, and show what changed since the last one.

Usage (run right after you SAVE the game in-game, at a known walkthrough step):

    python questsnap.py 4          # "I am now on step 4"

It copies PERSO.SAV to _backup/quest/stepNN.sav and prints which of the 51 progress counters at
DS:6F38 moved since the previous snapshot. Those deltas ARE the mapping we need: the counters that
change while completing step N are step N's markers. Once a few steps are banked, `python
questsnap.py --map` prints the accumulated counter->step table, which is what auto-detection needs.

Read-only with respect to the game: it only ever COPIES the save.
"""
import os, shutil, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
SNAPDIR = os.path.join(GAME, '_backup', 'quest')
NCOUNT, OFF = 51, 0x6FC


def counters(path):
    d = bytearray(open(path, 'rb').read())
    for i in range(0x7C8):
        d[i] ^= i & 0xFF
    return [d[OFF + e * 4] for e in range(NCOUNT)]


def snaps():
    out = []
    for p in sorted(glob.glob(os.path.join(SNAPDIR, 'step*.sav'))):
        n = os.path.basename(p)[4:-4]
        if n.isdigit():
            out.append((int(n), p))
    return sorted(out)


def show_map():
    s = snaps()
    if len(s) < 2:
        print('need at least 2 snapshots; have %d' % len(s)); return
    print('counter -> step it moved on')
    for (n0, p0), (n1, p1) in zip(s, s[1:]):
        a, b = counters(p0), counters(p1)
        moved = [(e, a[e], b[e]) for e in range(NCOUNT) if a[e] != b[e]]
        print('  step %d -> %d : %s' % (n0, n1, ', '.join(
            'entry %d (%d->%d)' % m for m in moved) or 'no counters changed'))


def main():
    if '--map' in sys.argv:
        show_map(); return
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print(__doc__); return
    step = int(sys.argv[1])
    src = os.path.join(GAME, 'PERSO.SAV')
    os.makedirs(SNAPDIR, exist_ok=True)
    prev = snaps()
    dst = os.path.join(SNAPDIR, 'step%02d.sav' % step)
    if prev:
        pn, pp = prev[-1]
        a, b = counters(pp), counters(src)
        moved = [(e, a[e], b[e]) for e in range(NCOUNT) if a[e] != b[e]]
        print('changes since step%02d: %s' % (pn, ', '.join(
            'entry %d (%d->%d)' % m for m in moved) or 'NONE'))
    shutil.copy2(src, dst)
    c = counters(dst)
    print('banked %s' % os.path.basename(dst))
    print('  pattern: %s' % ''.join(str(v) if v else '.' for v in c))


if __name__ == '__main__':
    main()
