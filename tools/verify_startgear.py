"""Proof for mod_startgear: run the creator's own gear code and read back the inventory.

Rather than trust a reading of the disassembly, this loads DRAKM.CC1 chunk 0 (the character
creator), applies its MZ relocations, and actually EXECUTES each class's gear routine under
unicorn against a blank character record - then decodes the item slots the code wrote.

The output is directly comparable to a real PERSO.SAV: item slots live at record +0x64 and the
save stores the party at file offset 4, so save[4 + n*0x19A + 0x64 ...] is the same bytes.
"""
import struct, sys, os
sys.setrecursionlimit(100000)
import drakpack
from unicorn import *
from unicorn.x86_const import *

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)

BASE   = 0x1000        # load segment for the creator image
RECSEG = 0x8000        # scratch character record
STKSEG = 0x9000
SENT   = 0xF000        # sentinel far-return segment
FUNCS  = [('Fighter', 0x02DB9), ('Scout', 0x02E3C), ('Mage', 0x02F0C), ('Priest', 0x02EA4)]

# the creator's catalog, for naming what came out
CAT_DS, NAMES = 0x0DA4, {
    0x08: 'shoes', 0x0a: 'boots', 0x0c: 'greaves', 0x0d: 'tunic', 0x0e: 'jacket',
    0x0f: 'leather', 0x17: 'priest robe', 0x1a: 'mage robe', 0x2d: 'buckler',
    0x36: 'dagger', 0x38: 'sword', 0x3e: 'rod', 0x3f: 'bludgeon', 0x41: 'BOW',
}


def load(path):
    c = [x for *_, x in drakpack.unpack_container(open(path, 'rb').read())][0]
    return relocate(c)


def relocate(c):
    h = struct.unpack_from('<14H', c)
    hdr, nrel, ro = h[4] * 16, h[3], h[12]
    img = bytearray(c[hdr:])
    for i in range(nrel):                       # relocate to BASE so the lcall lands right
        off, seg = struct.unpack_from('<HH', c, ro + 4 * i)
        p = seg * 16 + off
        struct.pack_into('<H', img, p, (struct.unpack_from('<H', img, p)[0] + BASE) & 0xFFFF)
    return bytes(img)


def run(img, entry):
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    uc.mem_write(BASE * 16, img)
    uc.mem_write(RECSEG * 16, b'\0' * 0x19A)
    ds = BASE + 0x6B8
    for r in (UC_X86_REG_DS, UC_X86_REG_ES): uc.reg_write(r, ds)
    uc.reg_write(UC_X86_REG_SS, STKSEG)
    sp = 0xFF00
    def push(v):
        nonlocal sp
        sp -= 2
        uc.mem_write(STKSEG * 16 + sp, struct.pack('<H', v & 0xFFFF))
    push(RECSEG); push(0)          # far pointer arg: seg then offset
    push(SENT); push(0)            # far return address -> sentinel
    uc.reg_write(UC_X86_REG_SP, sp)
    uc.reg_write(UC_X86_REG_CS, BASE)
    uc.emu_start(BASE * 16 + entry, SENT * 16, count=20000)
    return bytes(uc.mem_read(RECSEG * 16, 0x19A))


SPELLS = {4: 'INVISIB', 6: 'STRENGH', 7: 'LANGUAG', 8: 'SHIELD',
          16: 'SPEED', 18: 'RESTORE', 22: 'TELEPOR'}
MAGIC = {0x04: 'type0', 0x05: 'sceptre', 0x06: 'phial', 0x07: 'RING', 0x42: 'type4', 0x43: 'type5'}


def slots(rec, base=0x64):
    """Decode one 8-slot x 6-byte array. base 0x64 = items, 0x94 = magic items."""
    out = []
    for s in range(8):
        r = rec[base + s * 6: base + s * 6 + 6]
        if not r[3]:
            out.append((s, r.hex(), 'empty')); continue
        nm = MAGIC.get(r[3]) if base == 0x94 else NAMES.get(r[3], '-')
        nm = nm or '-'
        if r[3] in (0x05, 0x07):                 # ring / sceptre carry a spell in byte +1
            nm += ' ' + SPELLS.get(r[1], '?%d' % r[1])
        if r[0] & 0x80:
            nm += '  (worn)'
        out.append((s, r.hex(), nm))
    return out


def check_against_save(save):
    """The strong check: the STOCK creator, emulated, must reproduce a real PERSO.SAV exactly.

    PERSO.SAV is XOR-obfuscated with its own index and the party array lands at file offset 4,
    so character n's item block is at 4 + n*0x19A + 0x64.  Class order in the file is whatever
    order the party was created in, so each emulated class is matched to the record it equals
    rather than assumed positional.
    """
    d = bytes(c ^ (i & 0xFF) for i, c in enumerate(open(save, 'rb').read()))
    stock = load(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1'))
    saved = [d[4 + n * 0x19A + 0x64: 4 + n * 0x19A + 0x64 + 48] for n in range(4)]
    ok = True
    for name, entry in FUNCS:
        got = run(stock, entry)[0x64:0x64 + 48]
        hit = [n for n, s in enumerate(saved) if s == got]
        print('  %-8s emulated gear matches saved character %s' % (name, hit if hit else 'NONE  <-- MISMATCH'))
        ok &= bool(hit)
    assert ok, 'emulated stock creator does not reproduce this save'
    print('  stock creator reproduces %s exactly' % os.path.basename(save))


def held_check(path):
    """The creator sets record +0x56 (held-weapon slot index); 0x7F means empty-handed.

    It is written by the party-init routine, not the gear routines emulated here, so it is read
    straight out of the binary and cross-checked against the slot the gear actually lands in.
    """
    import drakpack, struct
    c = [x for *_, x in drakpack.unpack_container(open(path, 'rb').read())][0]
    h = struct.unpack_from('<14H', c); hdr = h[4] * 16
    vals = [c[hdr + a + 4] for a in (0x02C34, 0x02CAE, 0x02D2B, 0x02DA8)]
    print('held-weapon slot written for party slots 0-3: %s%s'
          % ([('empty(7F)' if v == 0x7F else v) for v in vals],
             '' if len(set(vals)) == 1 else '   <-- INCONSISTENT'))
    return vals


def matrix():
    """Emulate the creator for several mod selections, the way the installer builds them.

    The start* mods are independently selectable, so every combination has to produce sane gear -
    e.g. startworn without startgear must still equip the DAGGER the scout keeps in that case.
    """
    import json, fragsim, drakpack
    meta = json.load(open(os.path.join(HERE, 'fragments.json')))
    stock0 = [x for *_, x in drakpack.unpack_container(
        open(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1'), 'rb').read())][0]
    sels = [set(), {'startgear'}, {'startworn'}, {'startring'},
            {'startgear', 'startworn'}, {'startring', 'startworn'},
            {'startgear', 'startring', 'startworn'}]
    for sel in sels:
        c0 = fragsim.apply_writes0(stock0, meta, sel | {'bow', 'ring', 'noprotect'})
        img = relocate(c0)
        held = [c0[0x0A00 + a + 4] for a in (0x02C34, 0x02CAE, 0x02D2B, 0x02DA8)]
        print('')
        print('selection: %s' % (sorted(sel) or ['(none)']))
        for name, entry in FUNCS:
            rec = run(img, entry)
            it = [nm for _, _, nm in slots(rec, 0x64) if nm != 'empty']
            mg = [nm for _, _, nm in slots(rec, 0x94) if nm != 'empty']
            w = [x for x in range(8) if rec[0x64 + x * 6 + 3] and rec[0x64 + x * 6] & 0x20]
            hs = 'empty' if held[0] == 0x7F else str(held[0])
            tag = 'holds weapon' if w and held[0] == w[0] else ('naked' if held[0] == 0x7F else 'BAD')
            print('   %-8s %s%s' % (name, ', '.join(it), '   | magic: ' + ', '.join(mg) if mg else ''))
            print('            weapon slot %s, held=%s -> %s' % (w, hs, tag))
    return 0


def main():
    # Must be a FRESH save: play rewrites the item array (give_item compacts from slot 0 and
    # sets bit 7 on equipped items), so only an untouched new party proves the grant code.
    save = os.path.join(GAME, '_backup', 'fresh-party', 'PERSO.SAV')
    if os.path.exists(save):
        print('=== check: stock creator vs a real freshly-created save ===')
        check_against_save(save)
        print()
    else:
        print('note: no _backup/fresh-party/PERSO.SAV - skipping the save comparison')
    which = sys.argv[1] if len(sys.argv) > 1 else os.path.join(GAME, 'DRAKM.CC1')
    img = load(which)
    print('creator:', which)
    held = held_check(which)
    print('')
    for name, entry in FUNCS:
        rec = run(img, entry)
        print('')
        print(name)
        print('  items  (record +0x64):')
        for s, hx, nm in slots(rec, 0x64):
            if nm == 'empty' and s > 5: continue
            print('     slot %d  %-14s %s' % (s, hx, nm))
        wslot = [s for s in range(8) if rec[0x64 + s * 6 + 3] and rec[0x64 + s * 6] & 0x20]
        ok = 'OK' if wslot and wslot[0] == held[0] else 'MISMATCH'
        print('     weapon is in slot %s, held-weapon field says %s  -> %s'
              % (wslot, held[0] if held[0] != 0x7F else 'empty(7F)', ok))
        mg = slots(rec, 0x94)
        if any(nm != 'empty' for _, _, nm in mg):
            print('  magic items  (record +0x94):')
            for s, hx, nm in mg:
                if nm == 'empty': continue
                print('     slot %d  %-14s %s' % (s, hx, nm))
    return 0


if __name__ == '__main__':
    sys.exit(matrix() if '--matrix' in sys.argv else main())
