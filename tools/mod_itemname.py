"""Mod: show WHICH ring/staff/phial an item is, using its variant byte.

The inventory list draw (img 0xBA19) prints only the generic type name: idx = [DS:1CBB + id-4],
then the far pointer from the name table [0x6CE8] is pushed and drawn by `lcall 0A4A:0241
(x, y, name.lo, name.hi)` at img 0xBAA0 - the item's variant byte is never consulted.  But rings,
sceptres, rods and phials each have a SINGLE type id (0x07/0x05/0x3E/0x06); what distinguishes them
is byte +1 of the 6-byte item record ("empty phial" = variant 0), which the item creator (img
0x14AE5) stores from a parameter.  Working hypothesis, per the fill/give mechanics: the variant is a
SPELL INDEX, so the spell-name strings already resident at DS:08C4 records can label the item -
"ring TELEPOR" - with no new string data at all.

Hook = wrapper spliced over the name-draw far call.  It re-pushes the four argument words (the
callee is cdecl - our extra far return address would shift its [bp+n] frame otherwise), draws the
generic name, then for id in {sceptre, phial, ring, rod} with variant 1..23 pushes the spell
record's name far-ptr and draws it at x+0x1E on the same row (tightened per user feedback).  The item record is reached through
the caller's own saved pointer at [caller_bp-0x10/-0x0E], so any misreading of the record layout
elsewhere cannot desync this mod.  Unknown or zero variants draw nothing extra.
"""
CALLSITE = (0x0BAA, 0x0000)                  # linear 0xBAA0: lcall 0A4A:0241 (name draw)
DRAW     = (0x0A4A, 0x0241)
SPELLREC, RECSZ, NSPELL = 0x08C4, 14, 23
IDS = (0x05, 0x06, 0x07, 0x3E)               # sceptre, phial, ring, rod
SUFFIX_DX = 0x2A                             # x offset for the spell name

def source():
    ids = IDS
    return f'''
    push bp
    mov bp, sp
    push word ptr [bp+12]
    push word ptr [bp+10]
    push word ptr [bp+8]
    push word ptr [bp+6]
    lcall {DRAW[0]:#06x}:{DRAW[1]:#06x}
    add sp, 8
    push ds
    push es
    push bx
    push ax
    mov bx, [bp+0]
    mov ax, ss
    mov ds, ax
    mov ax, [bx-0x10]
    mov bx, [bx-0x0e]
    mov ds, bx
    mov bx, ax
    mov al, [bx+3]
    cmp al, {ids[0]:#04x}
    je isvar
    cmp al, {ids[1]:#04x}
    je isvar
    cmp al, {ids[2]:#04x}
    je isvar
    cmp al, {ids[3]:#04x}
    jne done
isvar:
    mov al, [bx+1]
    cmp al, 1
    jb done
    cmp al, {NSPELL}
    ja done
    mov ah, 0
    mov bx, ax
    shl bx, 1
    shl bx, 1
    shl bx, 1
    shl ax, 1
    add bx, ax
    shl ax, 1
    add bx, ax
    add bx, {SPELLREC:#06x}
    push word ptr [bx+2]
    push word ptr [bx]
    push word ptr [bp+8]
    mov ax, [bp+6]
    add ax, {SUFFIX_DX:#04x}
    push ax
    lcall {DRAW[0]:#06x}:{DRAW[1]:#06x}
    add sp, 8
done:
    pop ax
    pop bx
    pop es
    pop ds
    pop bp
    .byte 0xcb
'''

def apply(b):
    import struct, drakmod
    size = len(drakmod.assemble(source(), 0))
    seg, off, lin = b.alloc(size)
    code = drakmod.assemble(source(), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    orig = bytes([0x9A]) + struct.pack('<HH', DRAW[1], DRAW[0])
    b.splice_call(CALLSITE[0], CALLSITE[1], seg, off, expect=orig)
    # both embedded lcalls to the draw routine need their segment words relocated
    n = 0
    i = -1
    while True:
        i = code.find(orig, i + 1)
        if i < 0:
            break
        b.add_reloc(seg, off + i + 3)
        n += 1
    assert n == 2, 'expected exactly 2 embedded draw calls, found %d' % n
    print('  itemname: %d bytes at %04x:%04x (variant suffix for ids %s)'
          % (len(code), seg, off, ','.join(hex(i) for i in IDS)))
