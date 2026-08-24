"""Mod: make the bow a viable ranged weapon (damage 6 -> 12, price 8 -> 16).

The item catalog is an array of 6-byte records (flags, tier, POWER, id, PRICE, 0) - see NOTES.md.
The bow ("arch", id 0x41) is catalog index 0x32, record at DS:2048, and ships as the weakest weapon
in the game: power 6 (bludgeon 6, sword 8, sabre 32, drags 55) at price 8.  Shops and drops copy
this record, so patching it upgrades every bow the player acquires from now on.  Bows already in a
save keep their old bytes (the inventory holds a copy) - drop/rebuy to upgrade one.

This was the fallback from the "Longbow" plan (a real second bow id): the id-indexed tables around
DS:1B38..1CFD are packed edge-to-edge, so a new id means relocating tables and patching every
reader - see ROADMAP.md item 12.
"""
BOW_REC = 0x1FD40 + 0x2048          # image-linear address of the bow's catalog record
OLD = bytes.fromhex('2f 01 06 41 08 00'.replace(' ', ''))
NEW = bytes.fromhex('2f 01 0c 41 10 00'.replace(' ', ''))   # power 12, price 16

def apply(b):
    cur = bytes(b.img[BOW_REC:BOW_REC + 6])
    assert cur == OLD, 'bow catalog record not as expected: %s' % cur.hex()
    b.img[BOW_REC:BOW_REC + 6] = NEW
    print('  bow: power 6->12, price 8->16 (catalog record at DS:2048)')
