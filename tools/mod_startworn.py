"""Mod: new characters start with their gear already equipped.

Stock behaviour: the creator hands out gear but nothing is worn - every starting item has bit 7
of its flags byte clear, so a new party walks out unarmed and unarmoured until the player opens
each character sheet and equips four items by hand, twice over for a full party.

Bit 7 of an item record's flags byte IS the "equipped" flag - confirmed against a played save,
where worn items read 0xDF / 0xD4 / 0xBF and the same items unworn read 0x5F / 0x54 / 0x3F.
Multiple items are worn at once there (tunic + jacket + shield + sword together), so setting the
bit on every starting item is exactly what the game does itself.

Because a granted item is a VERBATIM copy of a record in the creator's private catalog (see
NOTES.md), equipping is done at the source: set bit 7 on the flags byte of every record the grant
blocks copy from.  No code changes, one byte per record.

The list is the union of every record any grant block can point at, in ANY mod selection - the
ten stock sources plus the bow (live only with mod_startgear) and the mod_startring pool (live
only with that mod).  Writing the bit on a record that the current selection does not use is
harmless: those records are unreachable dead space.  The union is spelled out rather than
scanned from the blocks so that this mod's recorded fragment does not depend on which other
mods happened to be in the reference build.

Bit 4 (0x10) is deliberately NOT set.  It means "revealed in the inventory list": the list draw
skips items without it (img 0x0BA39) and the game bulk-sets it on every slot when the inventory
opens (img 0x0B2F0).  That is why played saves have it everywhere and fresh ones do not.

BIT 7 ALONE IS NOT ENOUGH - it only lights the item up in the inventory.  What makes a character
actually WIELD a weapon is **record +0x56, the slot index of the held weapon** (0x7F = empty
handed).  The engine's own equip handler maintains it (img 0x0B6D4):

    xor es:[bx], 0x80              ; toggle worn on the item
    test es:[bx], 0x20             ; bit 5 marks the item as a weapon
       charptr[+0x56] = 0x7F       ;   nothing held
       if now worn: charptr[+0x56] = that item's slot index

Confirmed live: a character the player re-equipped in game read +0x56 = 02 with the weapon in
slot 2, while characters given gear by this mod read +0x56 = 0x7F and held nothing, exactly as
reported.  Armour needs nothing extra - only weapons (flags bit 5) have an index field.

The creator sets +0x56 = 0x7F in four `mov byte es:[bx+0x56], 0x7F` instructions.  Those are one
unrolled loop over the four PARTY SLOTS (each is followed by `add [bp-4], 0x19A`), not per class,
so they cannot carry a per-class value.  The fix is therefore to make every class hold its weapon
in the SAME slot and write that one index: the fighter's buckler and sword destinations are
swapped so its sword lands in slot 4 like every other class's weapon, and all four writes become
slot 4.  Both halves are immediate edits; no code is added.
"""
HDR = 0x0A00
DG  = HDR + 0x6B80

# (creator-catalog address, what it is) - every record a grant block can copy from
SOURCES = [
    (0x0DA4, 'shoes'),      (0x0DBC, 'jacket'),   (0x0DC2, 'leather'),
    (0x0DF2, 'priest robe'), (0x0E04, 'mage robe'), (0x0E58, 'buckler'),
    (0x0E8E, 'dagger'),     (0x0E94, 'sword'),    (0x0EAC, 'rod'),
    (0x0EB2, 'bludgeon'),
    (0x0EB8, 'bow'),        # only reached when mod_startgear repoints the scout
    (0x0DC8, 'startring pool: the rod copy the widened block writes to +0x7C'),
]
WORN = 0x80

# The creator's four `mov byte es:[bx+0x56], 0x7F` - one per party slot.  Immediate at +4.
HELD_SITES = [HDR + a + 4 for a in (0x02C34, 0x02CAE, 0x02D2B, 0x02DA8)]
HELD_NONE = 0x7F
WEAPON_SLOT = 4                     # every class's weapon lands in item slot 4

# Fighter block destinations to swap, so its SWORD (not the buckler) sits in slot 4.
F_BUCKLER_DST = HDR + 0x02DFD       # `add ax,0x7C` operand  (slot 4) -> slot 5
F_SWORD_DST   = HDR + 0x02E18       # `add ax,0x82` operand  (slot 5) -> slot 4


def apply(b):
    i = b.img0
    for off, what in SOURCES:
        p = DG + off
        f = i[p]
        assert not f & WORN, 'record %s (DS:%04x) is already flagged worn: %02x' % (what, off, f)
        assert f & 0x0F, 'DS:%04x does not look like an item record (%02x) - %s' % (off, f, what)
        i[p] = f | WORN
    # Fighter: swap buckler/sword destinations so the sword is in slot 4 like everyone else's.
    a = int.from_bytes(i[F_BUCKLER_DST:F_BUCKLER_DST + 2], 'little')
    b_ = int.from_bytes(i[F_SWORD_DST:F_SWORD_DST + 2], 'little')
    assert (a, b_) == (0x7C, 0x82), 'fighter block destinations are not 0x7C/0x82: %02x/%02x' % (a, b_)
    i[F_BUCKLER_DST:F_BUCKLER_DST + 2] = (0x82).to_bytes(2, 'little')
    i[F_SWORD_DST:F_SWORD_DST + 2] = (0x7C).to_bytes(2, 'little')

    # ...then tell all four party slots which item slot the held weapon is in.
    for p in HELD_SITES:
        assert i[p] == HELD_NONE, 'held-weapon slot at 0x%05x is %02x, expected %02x' % (p, i[p], HELD_NONE)
        i[p] = WEAPON_SLOT
    print('  startworn: %d gear records flagged equipped, held-weapon slot = %d for all 4 party slots'
          % (len(SOURCES), WEAPON_SLOT))


def demo():
    import drakmod
    b = drakmod.Builder()
    apply(b)
    for off, what in SOURCES:
        assert b.img0[DG + off] & WORN, what
    for p in HELD_SITES:
        assert b.img0[p] == WEAPON_SLOT, hex(p)
    assert int.from_bytes(b.img0[F_SWORD_DST:F_SWORD_DST + 2], 'little') == 0x7C
    assert int.from_bytes(b.img0[F_BUCKLER_DST:F_BUCKLER_DST + 2], 'little') == 0x82
    # the ring mod_startring plants is already worn, and must stay a ring
    ring = bytes(b.img0[DG + 0x0DC8 + 24: DG + 0x0DC8 + 30])
    print('  pool+24 (ring slot, only meaningful with mod_startring): %s' % ring.hex())
    print('mod_startworn self-check OK')


if __name__ == '__main__':
    demo()
