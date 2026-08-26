"""Mod: wire up rings and sceptres - a worn ring/sceptre grants its spell's passive effect.

The engine SHIPS seven passive-effect flags its character-sheet lister names (Power, Invisibility,
Acceleration, Understanding, Recuperation, Protection, Impalpability) and its regen/status code
checks - but nothing ever SETS them from equipment: a worn ring is inert (verified live).  Ring and
sceptre items carry a spell index in their variant byte, so the natural wiring is spell -> matching
effect:

    variant  4 INVISIB -> Invisibility  (LO 0x0100)
    variant  6 STRENGH -> Power         (HI 0x0008)
    variant  7 LANGUAG -> Understanding (LO 0x0001)
    variant  8 SHIELD  -> Protection    (HI 0x0002)
    variant 16 SPEED   -> Acceleration  (LO 0x1000)
    variant 18 RESTORE -> Recuperation  (LO 0x8000 MP + LO 0x4000 HP: regen countdowns halved)
    variant 22 TELEPOR -> Impalpability (HI 0x0010)

v1 wired only RESTORE; user-verified in game: regen doubles and "Recuperation" appears in the
ability list (the sheet redraws on reopen, not instantly on equip - known cosmetic limitation).

Hook: both deployed-mode call sites of the per-tick regen routine 0C82:146C (linear 0x2DE0
outdoor, 0x4C7D indoor) are spliced with a wrapper that scans each character's 14 inventory slots
for EQUIPPED (flags bit 7) rings (id 0x07) or sceptres (id 0x05), accumulates the mapped effect
bits, and rewrites just those bits in the flag dword at char+0xC (stateless: unequip reverts on
the next tick).  Then it chains to the real routine - the actual behaviors are engine code.

Lives in the copy-protection carcass (mod_levelup moved to the data pool to make room).
"""
REGEN = (0x0C82, 0x146C)
SITES = [(0x02DE, 0x0000), (0x04C7, 0x000D)]
CHAR0, STRIDE, NCHARS = 0x5A2E, 0x19A, 4
SLOT0, SLOTEND = 0x64, 0x64 + 14 * 6
RING_ID, SCEPTRE_ID = 0x07, 0x05

#            variant   LO mask  HI mask
TABLE = [
    (4,  0x0100, 0x0000),
    (6,  0x0000, 0x0008),
    (7,  0x0001, 0x0000),
    (8,  0x0000, 0x0002),
    (16, 0x1000, 0x0000),
    (18, 0xC000, 0x0000),
    (22, 0x0000, 0x0010),
]
ALL_LO = 0
ALL_HI = 0
for _, lo, hi in TABLE:
    ALL_LO |= lo
    ALL_HI |= hi


def source(dgroup):
    rows = ','.join('%d,%d,%d,%d,%d' % (v, lo & 0xFF, lo >> 8, hi & 0xFF, hi >> 8)
                    for v, lo, hi in TABLE)
    return f'''
    pusha
    push ds
    mov ax, {dgroup:#06x}
    mov ds, ax
    mov bx, {CHAR0:#06x}
    mov cx, {NCHARS}
charloop:
    push cx
    xor dx, dx
    xor bp, bp
    mov si, {SLOT0:#04x}
slots:
    mov al, [bx+si]
    test al, 0x80
    jz nexts
    mov al, [bx+si+3]
    cmp al, {RING_ID}
    je isring
    cmp al, {SCEPTRE_ID}
    jne nexts
isring:
    mov al, [bx+si+1]
    push si
    mov si, 0
findv:
    cmp al, cs:[si+vartab]
    jne nextv
    push ax
    mov al, cs:[si+vartab+1]
    or dl, al
    mov al, cs:[si+vartab+2]
    or dh, al
    mov al, cs:[si+vartab+3]
    mov ah, cs:[si+vartab+4]
    or bp, ax
    pop ax
nextv:
    add si, 5
    cmp si, {5 * len(TABLE)}
    jb findv
    pop si
nexts:
    add si, 6
    cmp si, {SLOTEND:#04x}
    jb slots
    mov ax, [bx+0xC]
    and ax, {(~ALL_LO) & 0xFFFF:#06x}
    or ax, dx
    mov [bx+0xC], ax
    mov ax, [bx+0xE]
    and ax, {(~ALL_HI) & 0xFFFF:#06x}
    or ax, bp
    mov [bx+0xE], ax
    add bx, {STRIDE:#05x}
    pop cx
    loop charloop
    pop ds
    popa
    lcall {REGEN[0]:#06x}:{REGEN[1]:#06x}
    .byte 0xcb
vartab:
    .byte {rows}
'''


def apply(b):
    import struct, drakmod
    dg = drakmod.DGROUP
    size = len(drakmod.assemble(source(dg), 0))
    seg, off, lin = b.alloc_code(size, want_paragraph=False)
    code = drakmod.assemble(source(dg), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    expect = bytes([0x9A]) + struct.pack('<HH', REGEN[1], REGEN[0])
    for s_seg, s_off in SITES:
        b.splice_call(s_seg, s_off, seg, off, expect=expect)

    i = code.find(expect)
    assert i > 0, 'chained regen call not found'
    b.add_reloc(seg, off + i + 3)
    i = code.find(bytes([0xB8]) + struct.pack('<H', dg))
    assert i >= 0, 'DGROUP immediate not found'
    b.add_reloc(seg, off + i + 1)
    print('  ring: %d bytes at %04x:%04x (%d ring/sceptre effects wired)' % (len(code), seg, off, len(TABLE)))
