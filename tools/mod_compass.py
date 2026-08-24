"""Mod: compass in the top-right of the 3D view.

Reads the heading vector the engine already maintains (DS:2EC = 16384*cos, DS:2EE = -16384*sin)
and draws a ring, a north tick and a needle into the frame.

Splice point 19F7:09A9 is the tail of the scene routine 19F7:08F8:

    19F7:09A9   mov ax,DGROUP / mov ds,ax     <- spliced
    19F7:09AE   cmp [bp+6], 0
    19F7:09B4   lcall 1998:000E               <- presents the finished frame

That is after all scene drawing but before the present, which is what makes the compass part of the
displayed frame instead of being overdrawn (invisible) or drawn onto an already-shown frame
(flicker).  Hooking any of the routine's callers instead puts the draw after the present - every
such attempt either flickered or vanished.

The compass therefore appears exactly when the 3D view is drawn: world view yes, menus/inventory no.
"""
CX, CY, RAD = 292, 26, 10                 # screen position; the frame is a 320x200 buffer
C_RING, C_NEEDLE, C_TIP, C_NORTH, C_HUB = 16, 38, 16, 220, 0   # GAME.7AL palette indices
FRAME, COS, SIN = 0x3DF6, 0x2EC, 0x2EE
SPLICE_SEG, SPLICE_OFF = 0x19F7, 0x09A9

def ring_points(r):
    import math
    return sorted({(round(r*math.cos(a*math.pi/180)), round(r*math.sin(a*math.pi/180)*0.83))
                   for a in range(0, 360, 8)})

def half_widths(r):
    """One byte per row: the ring is symmetric left-right, so store only the half-width.
    17 bytes instead of a 90-byte list of points."""
    pts = ring_points(r)
    ys = sorted({y for _, y in pts})
    return [max(x for x, yy in pts if yy == y) for y in ys]

def source(dgroup, org):
    pts = ring_points(RAD)
    rows = half_widths(RAD)
    # (dx:ax) >> 14 signed == high word of (dx:ax) << 2; short so loops stay in rel8 jump range
    shr14 = ('    shl ax, 1\n    rcl dx, 1\n    shl ax, 1\n    rcl dx, 1\n    mov ax, dx')
    return f'''
    mov ax, {dgroup:#06x}
    mov ds, ax
    pusha
    push es
    les di, [{FRAME:#06x}]
    mov ax, es
    or ax, ax
    jnz gotframe
    mov ax, 0xa000
    mov es, ax
gotframe:
    mov bx, {(CY-RAD-2)*320+CX}
    mov byte ptr es:[bx], {C_NORTH}
    mov byte ptr es:[bx+1], {C_NORTH}
    mov byte ptr es:[bx-1], {C_NORTH}
    mov cx, 1
nloop:
    mov ax, [{COS:#06x}]
    neg ax
    imul cx
{shr14}
    add ax, {CX}
    mov bx, ax
    mov ax, [{SIN:#06x}]
    imul cx
{shr14}
    add ax, {CY}
    mov dx, 320
    mul dx
    add bx, ax
    mov al, {C_NEEDLE}
    cmp cx, {RAD-2}
    jb nput
    mov al, {C_TIP}
nput:
    mov es:[bx], al
    inc cx
    cmp cx, {RAD}
    jbe nloop
    mov bx, {CY*320+CX}
    mov byte ptr es:[bx], {C_HUB}
    pop es
    popa
    .byte 0xcb
''', pts

def apply(b):
    import struct, drakmod
    # size the code first, then reserve exactly that much dead space
    src, _ = source(drakmod.DGROUP, 0)
    size = len(drakmod.assemble(src, 0))
    seg, off, lin = b.alloc(size)
    src, _ = source(drakmod.DGROUP, off)
    code = drakmod.assemble(src, off)
    b.put(lin, code)
    # the hook performs the two instructions it replaced, so DS/AX are as the caller expects
    b.splice_call(SPLICE_SEG, SPLICE_OFF, seg, off,
                  expect=b'\xb8' + struct.pack('<H', drakmod.DGROUP) + b'\x8e\xd8')
    b.add_reloc(seg, off + 1)        # the DGROUP immediate inside our hook
    b.compass_entry = (seg, off)     # other mods chain onto this hook
    print('  compass: %d bytes at %04x:%04x, spliced at %04x:%04x'
          % (len(code), seg, off, SPLICE_SEG, SPLICE_OFF))
