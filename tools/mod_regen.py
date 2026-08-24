"""Mod: sorcerer/priest MP regen at 1.5x while the party stands still in the world view.

MEASURED FACT (memprobe.py, 2026-08-23): the engine's regen routine 0C82:146C is called only by the
two characters-DEPLOYED main loops (sites 0x2DE0 outdoor / 0x4C7D indoor).  In the packed world
view it never runs - stock Drakkhen regenerates NOTHING while you travel.  A first version of this
mod spliced the 0x2DE0 site; that boosted outdoor-deployed regen (where party X/Y never changes,
so "standing still" was always true - combat included) and did nothing in the world view.  Wrong on
both counts.

This version chains onto the scene-routine tail at 19F7:09A9 instead, which fires once per main-loop
iteration in the packed world view ONLY (the same property that makes the compass vanish when the
characters are out).  Per iteration, if party X/Y (DS:02F0/02F2) is unchanged, each living caster
(class id even, see NOTES.md) below max MP has the engine's own countdown (+0x58) decremented; when
it reaches 0 we grant +1 MP (clamped to +0x5C) and reset the countdown to RESETVAL=75 instead of the
engine's 0x78-4*class = 112 - i.e. ~1.5x the deployed-mode rate, driven through the engine's own
counter so switching modes transitions seamlessly.  Deployed-mode regen is stock.

Chain: this mod takes over the 19F7:09A9 splice from mod_map and far-calls the map's world entry
first (which in turn calls the compass) - build order compass, map, regen matters.
"""
PARTY_X, PARTY_Y = 0x2F0, 0x2F2
CHAR0, STRIDE, NCHARS = 0x5A2E, 0x19A, 4
F_HP, F_CTDOWN, F_MP, F_MPMAX, F_CLASS = 0x51, 0x58, 0x5B, 0x5C, 0x56
GAINMP = (0x0A4A, 0x06F8)                    # engine gain-MP: add + clamp + UI dirty flag
# Gauge redraw for one char: NEAR function 0A4A:08D6 (img 0xAD76), one word arg (char index),
# caller cleans.  Called from our hook via a manufactured near-call: we push our own far return,
# then the offset of a RETF inside segment 0A4A (the gain fn's tail at 0A4A:072F), then far-jmp in;
# the routine's near RET lands on that RETF, which returns to us.  A direct far call would
# unbalance the stack of a near function.
GAUGE_OFF = 0x08D6
RETF_OFF  = 0x072F
RESETVAL = 75                                # 1.5x (engine deployed reset is 112). NOTE: this mod is
                                             # NOT in the build - dropped after a pack-transition crash.
SPLICE = (0x19F7, 0x09A9)

def source(dgroup, map_seg, map_off):
    return f'''
    lcall {map_seg:#06x}:{map_off:#06x}
    pusha
    push ds
    mov ax, {dgroup:#06x}
    mov ds, ax
    mov ax, [{PARTY_X:#06x}]
    mov dx, [{PARTY_Y:#06x}]
    cmp ax, cs:[oldx]
    jne moved
    cmp dx, cs:[oldy]
    jne moved
    mov bx, {CHAR0:#06x}
    mov cx, {NCHARS}
charloop:
    mov al, [bx+{F_CLASS:#04x}]
    test al, 1
    jnz next
    cmp byte ptr [bx+{F_HP:#04x}], 0
    je next
    mov al, [bx+{F_MP:#04x}]
    cmp al, [bx+{F_MPMAX:#04x}]
    jae next
    cmp byte ptr [bx+{F_CTDOWN:#04x}], 0
    je grant
    dec byte ptr [bx+{F_CTDOWN:#04x}]
    jnz next
grant:
    ; grant through the ENGINE's gain-MP routine (0A4A:06F8): it adds, clamps to max AND raises
    ; the char's stat-changed flag so the portrait gauge repaints. A bare inc left the UI stale.
    push cx
    push ds
    push bx
    mov ax, 1
    push ax
    push ds
    push bx
    lcall {GAINMP[0]:#06x}:{GAINMP[1]:#06x}
    add sp, 6
    pop bx
    pop ds
    pop cx
    mov byte ptr [bx+{F_CTDOWN:#04x}], {RESETVAL}
    ; repaint this character's gauges NOW - nothing in the packed world view consumes the dirty
    ; flag, so without this the bars stay stale until the characters deploy.
    push cx
    push ds
    push bx
    mov ax, {NCHARS}
    sub ax, cx
    push cs
    mov dx, 0x1234
    push dx
    push ax
    mov ax, {RETF_OFF:#06x}
    push ax
    .byte 0xEA,{GAUGE_OFF & 0xFF},{GAUGE_OFF >> 8},{GAINMP[0] & 0xFF},{GAINMP[0] >> 8}
gaugeret:
    add sp, 2
    pop bx
    pop ds
    pop cx
next:
    add bx, {STRIDE:#05x}
    loop charloop
    jmp done
moved:
    mov cs:[oldx], ax
    mov cs:[oldy], dx
done:
    pop ds
    popa
    .byte 0xcb
oldx:
    .word 0
oldy:
    .word 0
'''

def apply(b):
    import struct, drakmod
    dg = drakmod.DGROUP
    mseg, moff = b.map_world_entry                # chain: map (which chains the compass) runs first
    size = len(drakmod.assemble(source(dg, mseg, moff), 0))
    seg, off, lin = b.alloc(size)
    code = drakmod.assemble(source(dg, mseg, moff), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    map_call = bytes([0x9A]) + struct.pack('<HH', moff, mseg)
    assert code.find(map_call) == 0, 'chain call must be first'
    # take over the splice from mod_map
    p = SPLICE[0]*16 + SPLICE[1]
    assert bytes(b.img[p:p+5]) == map_call, 'map splice not where expected'
    b.img[p:p+5] = bytes([0x9A]) + struct.pack('<HH', off, seg)

    b.add_reloc(seg, off + 3)                     # segment word of the chained map call
    gcall = bytes([0x9A]) + struct.pack('<HH', GAINMP[1], GAINMP[0])
    i = code.find(gcall)
    assert i > 0, 'gain-MP call not found'
    b.add_reloc(seg, off + i + 3)
    gjmp = bytes([0xEA]) + struct.pack('<HH', GAUGE_OFF, GAINMP[0])
    i = code.find(gjmp)
    assert i > 0, 'gauge far-jmp not found'
    b.add_reloc(seg, off + i + 3)
    # patch the 0x1234 marker with the real offset of the instruction after the far jmp
    gaugeret = off + i + 5
    m = code.find(bytes([0xBA, 0x34, 0x12]))
    assert m > 0 and code.find(bytes([0xBA, 0x34, 0x12]), m + 1) < 0, 'gaugeret marker not unique'
    code = bytearray(code)
    struct.pack_into('<H', code, m + 1, gaugeret)
    b.put(lin, bytes(code))
    i = code.find(bytes([0xB8]) + struct.pack('<H', dg))
    assert i > 0, 'DGROUP immediate not found'
    b.add_reloc(seg, off + i + 1)
    print('  regen: %d bytes at %04x:%04x (world-view frame chain, reset=%d)' % (len(code), seg, off, RESETVAL))
