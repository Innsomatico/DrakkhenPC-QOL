"""Mod: the scout starts with a bow instead of a dagger.

This one lives in DRAKM.CC1 **chunk 0**, the character creator - a separate MZ image from the
game engine that every other mod here patches.  That distinction is the whole reason starting
gear resisted two earlier attempts: the engine's loot tier tables (DS:1C0F / DS:1C3F) drive
random drops, not creation, and patching them changed nothing.  See NOTES.md for the full map.

The creator grants gear as one 27-byte block per item - a straight 6-byte memcpy from its own
copy of the item catalog (DS:0DA4) into the character's item slot, no table lookup:

    mov ax,6 / push ax / mov dx,[bp+8] / mov ax,[bp+6] / add ax,<slot>
    push dx / push ax / push ds / mov ax,<catalog record> / push ax / lcall 02AD:00D8

so changing a class's starting item is a two-byte edit of that `mov ax,imm16` operand.

The scout's weapon block is at chunk-0 img 0x02E86 and points at the dagger (DS:0E8E).  It is
repointed to the bow (DS:0EB8, catalog index 46, the last record).  The bow's power byte in the
creator's catalog is also raised 6 -> 8 to match mod_bow: the creator carries its own catalog,
so mod_bow's edit to the engine's copy does not reach an item handed out at creation, and
without this the scout would start with a stock power-6 bow that silently disagrees with every
other bow in the game.

Slots: gear goes to record +0x70 / +0x76 / +0x7C / +0x82, i.e. item slots 2..5.  Slots 0 and 1
are the innate attack / defence slots the monster spawner uses, and stay empty for players.
"""
HDR = 0x0A00                     # chunk 0's MZ header; b.img0 is the whole chunk, so all
                                 # image addresses below are biased by it
DG = HDR + 0x6B80                # chunk-0 DGROUP (0x06B8), as a chunk offset

SCOUT_WEAPON_IMM = HDR + 0x02E86  # imm16 operand of the `mov ax` in the scout weapon block
DAGGER = 0x0E8E                  # catalog index 39
BOW    = 0x0EB8                  # catalog index 46

BOW_REC   = DG + BOW             # the creator's own bow record
BOW_OLD   = bytes.fromhex('2f0106410100')
BOW_NEW   = bytes.fromhex('2f0108410100')   # power 6 -> 8, matching mod_bow


def apply(b):
    i = b.img0
    # the whole 27-byte grant block must look exactly as documented before touching it
    blk = bytes(i[HDR + 0x02E75:HDR + 0x02E8E])
    assert blk.startswith(bytes.fromhex('b80600' '50' '8b5608' '8b4606' '057c00')), \
        'scout weapon grant block not as expected: %s' % blk.hex()
    assert int.from_bytes(i[SCOUT_WEAPON_IMM:SCOUT_WEAPON_IMM + 2], 'little') == DAGGER, \
        'scout weapon source is not the dagger'
    i[SCOUT_WEAPON_IMM:SCOUT_WEAPON_IMM + 2] = BOW.to_bytes(2, 'little')

    assert bytes(i[BOW_REC:BOW_REC + 6]) == BOW_OLD, \
        'creator bow record not as expected: %s' % bytes(i[BOW_REC:BOW_REC + 6]).hex()
    i[BOW_REC:BOW_REC + 6] = BOW_NEW
    print('  startgear: scout starts with a bow (power 8) instead of a dagger')


def demo():
    """Self-check: apply to the stock creator and confirm the grant now copies the bow."""
    import drakmod
    b = drakmod.Builder()
    apply(b)
    imm = int.from_bytes(b.img0[SCOUT_WEAPON_IMM:SCOUT_WEAPON_IMM + 2], 'little')
    assert imm == BOW, imm
    assert bytes(b.img0[DG + imm:DG + imm + 6]) == BOW_NEW
    # every other class's weapon source must be untouched
    for off, want in ((HDR + 0x02E1E, 0x0E94), (HDR + 0x02EEE, 0x0EB2),
                      (HDR + 0x02F56, 0x0EAC)):
        assert int.from_bytes(b.img0[off:off + 2], 'little') == want, hex(off)
    # and all four classes still start with the same shoes record
    for off in (HDR + 0x02DCD, HDR + 0x02E50, HDR + 0x02EB8, HDR + 0x02F20):
        assert int.from_bytes(b.img0[off:off + 2], 'little') == 0x0DA4, hex(off)
    print('mod_startgear self-check OK')


if __name__ == '__main__':
    demo()
