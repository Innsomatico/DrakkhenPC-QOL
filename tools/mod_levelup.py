"""Mod: class-based stat growth on level-up.

Stock Drakkhen grants NO stat growth on level-up - only max HP (+1/16, clamp 250) and max MP
(class table DS:1BB7, clamp 254).  The six stats only ever move via the IMPROV spell (+1 random).
This mod adds a per-class, per-stat gain applied on every level gained:

    stat order [Str, Dex, Int, Edu, Con, Luck] (record +0x42..+0x47, manual-verified)
    class 0 fighter/amazon:    3 2 1 1 3 1
    class 1 scout:             2 3 1 1 2 2
    class 2 magician/sorceress:1 1 2 3 2 2
    class 3 priest/priestess:  1 1 3 2 2 2
    (equal 5/level totals; the +2s sit on each class's manual-defined signature stats)

Every stat is clamped at 99: creation max ~23 + 24 levels x 3 = 95, so the clamp is honest headroom
above natural growth, two display digits, and far from the 255 byte wrap.  (IMPROV's own +1 has no
clamp in the engine; ~80 casts could push past 99 - harmless below 255.)

Hook: the level-up routine (img 0xCBB0..0xCD25) computes the new level in [bp-0x10], the class index
in [bp-0x12] (the engine's own 0..3 class, via char+0x37 -> DS:1BAE), and the char far ptr at [bp+6].
We splice the 7 bytes at img 0xCCD8:

    c4 5e 06        les bx, [bp+6]
    26 88 47 53     mov es:[bx+0x53], al     ; al = new level; +0x53 = current level

with `lcall hook / nop / nop`.  The hook replicates both instructions - reading the OLD level first,
so delta = new - old handles multi-level jumps - then applies gains x delta with the clamp.  BP still
frames the caller's locals across a far call, so [bp-0x10]/[bp-0x12]/[bp+6] are directly readable.
This site runs exactly once per level-up event, for party members only.

Lives in the DGROUP data pool (moved out of the code carcass to make room for mod_ring).
"""
# v2 (user request): v1 minus 1 across the board - +3s were compounding too fast.
GAINS = [
    [2, 1, 0, 0, 2, 0],
    [1, 2, 0, 0, 1, 1],
    [0, 0, 1, 2, 1, 1],
    [0, 0, 2, 1, 1, 1],
]
STATCAP = 99
SPLICE_LIN = 0xCCD8                      # image-linear; site is 7 bytes (les + mov)
OLDBYTES = bytes.fromhex('c45e0626884753')


def source():
    rows = ','.join(str(v) for row in GAINS for v in row)
    return f'''
    les bx, [bp+6]
    mov dl, es:[bx+0x53]
    mov es:[bx+0x53], al
    sub al, dl
    jbe out
    pusha
    mov cl, al
    mov ch, 0
    mov si, [bp-0x12]
    and si, 3
    shl si, 1
    mov ax, si
    shl si, 1
    add si, ax
levloop:
    push cx
    push si
    mov cx, 6
    mov di, 0x42
statloop:
    mov al, cs:[si+gains]
    add al, es:[bx+di]
    cmp al, {STATCAP}
    jbe store
    mov al, {STATCAP}
store:
    mov es:[bx+di], al
    inc si
    inc di
    loop statloop
    pop si
    pop cx
    loop levloop
    popa
out:
    .byte 0xcb
gains:
    .byte {rows}
'''


def apply(b):
    import struct, drakmod
    size = len(drakmod.assemble(source(), 0))
    seg, off, lin = b.alloc(size, want_paragraph=False)
    code = drakmod.assemble(source(), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    assert bytes(b.img[SPLICE_LIN:SPLICE_LIN + 7]) == OLDBYTES, \
        'level-up splice site not as expected: %s' % bytes(b.img[SPLICE_LIN:SPLICE_LIN + 7]).hex()
    b.img[SPLICE_LIN:SPLICE_LIN + 7] = (bytes([0x9A]) + struct.pack('<HH', off, seg)
                                        + bytes([0x90, 0x90]))
    b.add_reloc((SPLICE_LIN + 3) >> 4, (SPLICE_LIN + 3) & 0xF)
    print('  levelup: %d bytes at %04x:%04x (class stat growth, cap %d)' % (len(code), seg, off, STATCAP))
