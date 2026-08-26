"""Mod: make the bow a viable ranged weapon (power 6 -> 12, price 8 -> 16), and call it "bow".

The item catalog is an array of 6-byte records (flags, tier, POWER, id, PRICE, 0) - see NOTES.md.
The bow ("arch", id 0x41) is catalog index 0x32, record at DS:2048, and ships as the weakest weapon
in the game: power 6 (bludgeon 6, sword 8, sabre 32, drags 55) at price 8.  Shops and drops copy
this record, so patching it upgrades every bow the player acquires from now on.  Bows already in a
save keep their old bytes (the inventory holds a copy) - drop/rebuy to upgrade one.

The display name string "arch" (a mistranslation of French "arc") at DS:308E is rewritten to "bow"
in place - one byte shorter, NUL-terminated, same footprint.

This was the fallback from the "Longbow" plan (a real second bow id): the id-indexed tables around
DS:1B38..1CFD are packed edge-to-edge, so a new id means relocating tables and patching every
reader - see ROADMAP.md item 12.
"""
BOW_REC = 0x1FD40 + 0x2048          # image-linear address of the bow's catalog record
OLD = bytes.fromhex('2f0106410800')
NEW = bytes.fromhex('2f010c411000')   # power 12, price 16

NAME_ARCH = 0x1FD40 + 0x308E        # 'arch' + NUL in the item name strings


def apply(b):
    cur = bytes(b.img[BOW_REC:BOW_REC + 6])
    assert cur == OLD, 'bow catalog record not as expected: %s' % cur.hex()
    b.img[BOW_REC:BOW_REC + 6] = NEW
    assert bytes(b.img[NAME_ARCH:NAME_ARCH + 5]) == b'arch\x00', 'arch string not found'
    b.img[NAME_ARCH:NAME_ARCH + 5] = b'bow\x00\x00'
    print('  bow: power 6->12, price 8->16, renamed arch->bow')
