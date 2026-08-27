"""Reference implementation + test of selective fragment application.

This is the exact algorithm both installers embed: given stock DRAKM.CC1 chunks and a SELECTED
subset of mod fragments (fragments.json), produce the patched container.  Run standalone it
verifies: (a) the FULL selection reproduces the reference build byte-for-byte, (b) partial
selections produce structurally valid images (all writes land, relocation table consistent).
"""
import json, struct, sys, os, hashlib
sys.setrecursionlimit(100000)
import drakpack

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)


def apply_writes0(stock_chunk0, meta, selected):
    """Chunk 0 is the character creator.  Its mods are plain immediate edits - no relocation
    bookkeeping - so applying them is just laying the recorded runs back down in order."""
    c = bytearray(stock_chunk0)
    for name in meta['order']:
        if name not in selected:
            continue
        for off, hx in meta['frags'][name].get('writes0', []):
            b = bytes.fromhex(hx)
            c[off:off + len(b)] = b
    return bytes(c)


def apply_selection(stock_chunk1, meta, selected):
    """stock_chunk1: decoded chunk 1 (MZ header + image). Returns patched chunk bytes."""
    c = bytearray(stock_chunk1)
    h = list(struct.unpack_from('<14H', c))
    ro, nrel, hdr = h[12], h[3], h[4] * 16

    # 1. image writes, canonical order
    for name in meta['order']:
        if name not in selected:
            continue
        for off, hx in meta['frags'][name]['writes']:
            b = bytes.fromhex(hx)
            c[off:off + len(b)] = b

    # 2. relocation table: stock entries in stock order, with selected repoints applied and
    #    selected drops removed, then selected adds appended in canonical order.
    reps = {}
    drops = set()
    adds = []
    for name in meta['order']:
        if name not in selected:
            continue
        f = meta['frags'][name]
        for old, off, seg in f['rrep']:
            reps[old] = (off, seg)
        drops.update(f['rdrop'])
        adds += [(off, seg) for off, seg in f['radd']]
    entries = []
    for i in range(nrel):
        off, seg = struct.unpack_from('<HH', c, ro + 4 * i)
        lin = seg * 16 + off
        if lin in drops:
            continue
        if lin in reps:
            off, seg = reps[lin]
        entries.append((off, seg))
    entries += adds
    assert ro + len(entries) * 4 <= hdr, 'relocation table overflow'
    for k, (off, seg) in enumerate(entries):
        struct.pack_into('<HH', c, ro + 4 * k, off, seg)
    h[3] = len(entries)
    struct.pack_into('<14H', c, 0, *h)
    seen = set()
    for off, seg in entries:
        lin = seg * 16 + off
        assert lin not in seen, 'duplicate relocation %05x' % lin
        seen.add(lin)
    return bytes(c)


def main():
    meta = json.load(open(os.path.join(HERE, 'fragments.json')))
    stock = open(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1'), 'rb').read()
    ref = open(os.path.join(GAME, 'DRAKM.CC1'), 'rb').read()
    sc = [r for *_, r in drakpack.unpack_container(stock)]

    # full selection must be byte-identical to the reference build
    full = apply_selection(sc[1], meta, set(meta['order']))
    full0 = apply_writes0(sc[0], meta, set(meta['order']))
    out = drakpack.pack_container([full0, full])
    print('FULL selection == reference build:', out == ref)
    assert out == ref

    # partial selections: structural checks
    cases = [
        {'compass'},
        {'compass', 'map'},
        {'noprotect'},
        {'partyxp', 'bow', 'levelup'},
        {'compass', 'map', 'noprotect', 'hints'},
        {'noprotect', 'ring', 'itemname'},
        {'startgear'},
        {'startgear', 'bow'},
        {'startring', 'ring', 'noprotect'},
        {'startworn'},
        {'startgear', 'startworn', 'bow'},
        {'startgear', 'startring', 'startworn', 'bow', 'ring', 'noprotect'},
    ]
    for sel in cases:
        c = apply_selection(sc[1], meta, sel)
        c0 = apply_writes0(sc[0], meta, sel)
        assert len(c0) == len(sc[0]), 'creator chunk changed size'
        print('partial %-45s ok (relocs=%d)' % (sorted(sel), struct.unpack_from('<H', c, 6)[0]))
    print('all cases pass')


if __name__ == '__main__':
    main()
