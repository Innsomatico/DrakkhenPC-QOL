"""Mod: Anak temple healing and resurrection are free, ungated, and FULL - one visit heals all.

The stock fee is level-CUBED scaled ([bx+0x53] = level): heal = lvl^3 x 5, revive = lvl^3 x 20.
Payment goes through a pay-richest helper (img 0x0ACC1) that scans the party for the fattest
purse (money is 32-bit per character at record +0x10/+0x12), FAILS with 0xFFFF if even that
character cannot afford it, and on failure the priest shows text 0x5F - "Riches cannot win your
head. Die and without jade stay dead!"  Hence the classic softlock: a first-fight death leaves a
corpse whose revival costs more jade than a fresh party owns, forever.

The temple service routine (img 0x2A98) computes the amount in two branches:

    02AD6  dead:  xor dx,dx / xor cx,cx / mov bx,0x14 / lcall 0:0x412   ; amount = lvl^3 * 20
    02AEA  alive: mov ax,[bp-6] / ...   / mov bx,0x05 / lcall 0:0x412   ; amount = lvl^3 * 5

Patching both multiplier immediates to ZERO makes the amount 0: pay_richest(0) always succeeds
(anyone's purse >= 0), subtracts nothing, and returns a payer - the heal/revive path runs
unconditionally and free.  Two one-byte edits; the failure branch and the taunt text become
unreachable from this path.  The pay-richest helper itself is untouched: its only other caller
is the priest's pay-for-information dialogue, which stays a paid (flavor) service.
"""
DEAD_MUL  = 0x02ADA   # mov bx,0x14  (revive: x20)
ALIVE_MUL = 0x02AF1   # mov bx,0x05  (heal:   x5)

# The heal itself is +5 HP per visit (img 0x2B70: add byte es:[bx+0x51],5 then clamp to
# es:[bx+0x4F]).  Rewritten to HP_cur = HP_max outright - one visit fully heals, and a revive
# comes back at full HP instead of 5.  The routine's own follow-up (Recuperation flags 0x6000,
# status clear at +0x2C) is untouched.
HEAL_SITE = 0x02B70
HEAL_OLD  = bytes.fromhex('2680475105268a4751263a474f7608268a474f26884751')
HEAL_NEW  = bytes.fromhex('268a474f26884751') + bytes([0x90]) * 15


def apply(b):
    assert bytes(b.img[DEAD_MUL:DEAD_MUL + 3])  == bytes.fromhex('bb1400'), \
        'revive multiplier not as expected'
    assert bytes(b.img[ALIVE_MUL:ALIVE_MUL + 3]) == bytes.fromhex('bb0500'), \
        'heal multiplier not as expected'
    b.img[DEAD_MUL + 1] = 0
    b.img[ALIVE_MUL + 1] = 0
    assert bytes(b.img[HEAL_SITE:HEAL_SITE + 23]) == HEAL_OLD, 'heal add+clamp not as expected'
    b.img[HEAL_SITE:HEAL_SITE + 23] = HEAL_NEW
    print('  freetemple: temple free (x5/x20 -> x0) and FULL - heal sets HP to max in one visit')
