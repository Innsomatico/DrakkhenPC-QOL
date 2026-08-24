"""Mod: party-shared XP (FF-style).

Kill XP normally goes 100% to the killer.  The engine has two award sites that do
`add es:[bx+0x14],ax / adc es:[bx+0x16],dx` with es:bx = the killer's char record and dx:ax = the
amount (img 0xCFD2: victim's whole remaining pool on a flagged kill; img 0xD075: the per-hit share
damage * victim_pool / victim_maxHP).  Each site is 8 bytes and carries no relocation, so the mod
overwrites it with `lcall hook` + 3 nops and registers the new relocation itself.

The hook gives every LIVING party member (char +0x51 > 0) amount/4, and the killer additionally the
remainder (amount & 3) so no XP is created or destroyed when all four live; dead members' shares are
simply lost, per the user's spec.  Registers are fully preserved - the code after each site reuses
dx:ax to debit the victim's XP pool.

The third `add [bx+0x14]` site (img 0x15916, via ptr [0x67D0]) is a scripted/event reward to a
specific character and is deliberately left stock.
"""
SITES = [0xCFD2, 0xD075]                     # image-linear offsets of the add/adc pairs
ORIG   = bytes.fromhex('26014714 26115716'.replace(' ', ''))
CHAR0, STRIDE, NCHARS = 0x5A2E, 0x19A, 4
F_HP, F_XP = 0x51, 0x14

SRC = f'''
    pusha
    push ds
    mov si, es
    mov ds, si
    mov si, {CHAR0:#06x}
    mov bp, bx
    mov di, dx
    mov bx, ax
    shr di, 1
    rcr bx, 1
    shr di, 1
    rcr bx, 1
    and ax, 3
    mov cx, {NCHARS}
xloop:
    cmp byte ptr [si+{F_HP:#04x}], 0
    je xskip
    add [si+{F_XP:#04x}], bx
    adc [si+{F_XP+2:#04x}], di
    cmp si, bp
    jne xskip
    add [si+{F_XP:#04x}], ax
    adc word ptr [si+{F_XP+2:#04x}], 0
xskip:
    add si, {STRIDE:#05x}
    loop xloop
    pop ds
    popa
    .byte 0xcb
'''

def apply(b):
    import struct, drakmod
    size = len(drakmod.assemble(SRC, 0))
    seg, off, lin = b.alloc(size)
    code = drakmod.assemble(SRC, off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)
    for p in SITES:
        assert bytes(b.img[p:p+8]) == ORIG, 'unexpected bytes at award site %#x: %s' % (
            p, bytes(b.img[p:p+8]).hex())
        b.img[p:p+8] = bytes([0x9A]) + struct.pack('<HH', off, seg) + b'\x90\x90\x90'
        b.add_reloc(p >> 4, (p & 0xF) + 3)
    print('  partyxp: %d bytes at %04x:%04x (2 award sites spliced)' % (len(code), seg, off))
