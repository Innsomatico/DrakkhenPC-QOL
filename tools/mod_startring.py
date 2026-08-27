"""Mod: the magician starts wearing a RESTORE ring (doubled regen, via mod_ring).

Needs mod_ring - a worn ring is inert in the stock engine, so without it this is a cosmetic item.

WHY THIS IS NOT JUST AN ADDRESS SWAP (unlike mod_startgear's bow):
rings are NOT catalog items.  The catalog runs id 0x08..0x41; rings/sceptres/phials live in a
separate id space (0x04,0x05,0x06,0x07,0x42,0x43) produced by the engine's magic-item creator at
img 0x14AB8, which builds a record rather than copying one:

    flags = 0x0F                      byte +1 = variant (spell index)
    byte +2 = (type << 5) | arg       byte +3 = DS:1BF9[type]     price word = 0

DS:1BF9 = {04,05,06,07,42,43}, so type 3 -> id 0x07 = ring.  Cross-checked against a real save:
a phial reads `1f 00 40 06 00 00` (type 2 -> 0x06, byte2 = 2<<5) and the 0x42/0x43 items read
0x80/0xA0 - all three agree.  So a RESTORE ring is:

    8f 12 60 07 00 00     bit7 = worn, variant 0x12 = 18 = RESTORE, (3<<5)|0, id 7, price 0

and the CREATOR has no magic-item maker at all (the type table is absent from chunk 0), so the
record has to be synthesised as data.

WHERE THE BYTES COME FROM:
chunk 0 carries its own private copy of the item catalog at DS:0DA4 and contains NO `mul 6`
indexing anywhere - the only way any code there can reach a catalog record is a direct `mov
ax,imm16`, and all twelve of those are the gear-grant blocks.  Exactly 10 of the 47 records are
referenced; the other 37 (222 bytes) are unreachable.  That is a complete proof of deadness, not a
heuristic, and it is the space this mod uses.

HOW THE RING IS GRANTED WITHOUT NEW CODE:
a grant block's byte count is an immediate too.  The magician's last block copies 6 bytes to
record +0x7C.  Pointing it at 30 contiguous dead bytes laid out as

    [rod] [zeros] [zeros] [zeros] [ring]

and raising the count to 30 makes one memcpy fill +0x7C (rod, unchanged), +0x82/+0x88/+0x8E
(zeros, already zero at creation - harmless) and +0x94, which is item slot 0 of the MAGIC-ITEM
array where rings belong.  The magician keeps every item it had; no code is added or moved.
"""
HDR = 0x0A00
DG  = HDR + 0x6B80

POOL   = 0x0DC8                     # 5 contiguous never-referenced catalog records = 30 bytes
BLOCK  = HDR + 0x02F45              # the magician's rod grant block
CNT    = BLOCK + 1                  # `mov ax,6`   count operand
DST    = BLOCK + 11                 # `add ax,0x7C` destination operand
SRC    = BLOCK + 17                 # `mov ax,0x0EAC` source operand

ROD_SRC = 0x0EAC                    # the record this block copied before it was widened
RING = bytes.fromhex('8f1260070000')            # worn RESTORE ring


def apply(b):
    i = b.img0
    assert int.from_bytes(i[CNT:CNT + 2], 'little') == 6, 'rod block count is not 6'
    assert int.from_bytes(i[DST:DST + 2], 'little') == 0x7C, 'rod block destination is not +0x7C'
    assert int.from_bytes(i[SRC:SRC + 2], 'little') == 0x0EAC, 'rod block source is not the rod'
    assert bytes(i[DG + POOL:DG + POOL + 6]) == bytes.fromhex('4f0528100100'), \
        'dead-pool record 8 not as expected - re-verify the catalog before reusing it'

    # The rod is taken from the catalog as it stands rather than hardcoded, so whatever else
    # edited it (mod_startworn's equipped bit) carries through unchanged.
    rod = bytes(i[DG + ROD_SRC:DG + ROD_SRC + 6])
    blob = rod + bytes(18) + RING   # -> +0x7C, +0x82, +0x88, +0x8E, +0x94
    assert len(blob) == 30
    i[DG + POOL:DG + POOL + 30] = blob
    i[CNT:CNT + 2] = (30).to_bytes(2, 'little')
    i[SRC:SRC + 2] = POOL.to_bytes(2, 'little')
    print('  startring: magician starts wearing a RESTORE ring (rod block widened to 30 B)')


def demo():
    import drakmod
    b = drakmod.Builder()
    apply(b)
    i = b.img0
    assert int.from_bytes(i[CNT:CNT + 2], 'little') == 30
    assert int.from_bytes(i[SRC:SRC + 2], 'little') == POOL
    assert int.from_bytes(i[DST:DST + 2], 'little') == 0x7C          # destination untouched
    assert bytes(i[DG + POOL:DG + POOL + 6]) == bytes(i[DG + ROD_SRC:DG + ROD_SRC + 6])
    assert bytes(i[DG + POOL + 24:DG + POOL + 30]) == RING
    # the other three classes' blocks must still copy 6 bytes
    for blk in (HDR + 0x02DBC, HDR + 0x02E3F, HDR + 0x02EA7):
        assert int.from_bytes(i[blk + 1:blk + 3], 'little') == 6, hex(blk)
    print('mod_startring self-check OK')


if __name__ == '__main__':
    demo()
