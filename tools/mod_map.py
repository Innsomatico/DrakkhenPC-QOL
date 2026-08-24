"""Mod: world map on the M key.

Hooked at the SAME place as the compass - 19F7:09A9, the tail of the scene routine, just before it
presents the frame.  The main loop calls that routine every iteration (0055:0E84), so this runs every
frame in the world view, which is what makes M responsive there.  Hooking the input/click dispatcher
(070E:1F77) instead only worked while the characters were out, because that is the only mode whose
loop reaches it.  It must not be hooked on the engine's timer callback either (1B27:02B6): that table
is dispatched from INT 8, installed at 1BC6:004F, where DOS calls and blocking are unsafe.

The compass already owns 19F7:09A9, so this mod takes the splice over and chains - the map hook far-
calls the compass hook first, then does its own work.

Map data lives OUTSIDE the engine in MAP.DRK and is never held in memory.  Loading it through the
engine's own loader allocates from the heap, and the game has under 5 KB of headroom - doing that
starved the graphics loader and produced the "insert Disk 3" failure.  Instead MAP.DRK is a raw
320x192 image (61440 bytes, one byte per pixel in the game's palette) that DOS reads straight into
the frame with a single INT 21h read: no allocation, no decompression, no buffer.  The map is 320 px
wide precisely so its rows line up with the screen and the file is a byte-for-byte image of it.

Pressing M reads the map STRAIGHT INTO VIDEO MEMORY and blocks in a small loop flashing the party
marker until a key is pressed - one file read per press.  It deliberately never touches the frame
buffer: the frame still holds the intact scene and HUD, so the engine's next present restores the
whole screen by itself.  Writing the map into the frame instead left map pixels in the panel areas,
because the engine only repaints those when their contents change.
"""
MAPFILE = 'MAP.DRK'
# The engine remaps scancodes through an AZERTY layout table at DS:3D07 when [3E06] is set (it is,
# = 0x2000), so physical M arrives as 0x27 rather than 0x32.  Accept both.
KEY_M, KEY_M_ALT = 0x27, 0x32
SCANCODE, PARTY_X, PARTY_Y = 0x3DCE, 0x2F0, 0x2F2
FRAME   = 0x3DF6
# The map is drawn ONLY inside the 3D viewport, which the engine repaints every frame - so closing
# it needs no restore at all.  Earlier full-screen versions covered the side and bottom panels, and
# those are only repainted when their contents change (e.g. deploying characters), so map pixels
# lingered there.  256x128 at (64,3) is exactly the viewport, matching how the character sheet
# occupies the same area.
VIEW_X, VIEW_Y, VIEW_W, VIEW_H = 64, 3, 256, 128
TILE_W, TILE_H = 8, 4
C_MARK_A, C_MARK_B = 38, 16          # marker flashes red / white
SPLICE   = (0x19F7, 0x09A9)                          # world view: tail of the scene routine
DISPATCH = (0x070E, 0x1F77)                          # characters-out: main-loop click dispatcher
DISPATCH_SITES = [(0x02DE, 0x0005), (0x04C8, 0x0007)]
FRAMECTR = 0x2FE                                     # main loop repaints the UI when this %32 == 0
# The map covers the side/bottom panels, which the engine only repaints occasionally, so they are
# redrawn explicitly on exit.  0055:0BC5 is the full-HUD draw the game itself runs after loading
# a save (03AD:0C49).  All four take no arguments (verified at their call sites).
# Redraw sequence lifted from the deploy-characters path (0055:0D3B..0D48), which is the action
# that visibly restores the panels.  UI_A takes one word argument; the other two take none.
UI_A, UI_B, UI_C = (0x1AC6, 0x0257), (0x0564, 0x01BA), (0x0055, 0x0BC5)

def source(dgroup, compass_seg, compass_off):
    return f'''
    lcall {compass_seg:#06x}:{compass_off:#06x}
    jmp checkmap
    lcall {DISPATCH[0]:#06x}:{DISPATCH[1]:#06x}
    jmp checkmap
checkmap:
    pusha
    push ds
    push es
    mov ax, {dgroup:#06x}
    mov ds, ax
    mov al, [{SCANCODE:#06x}]
    cmp al, cs:[lastkey]
    je done
    mov cs:[lastkey], al
    cmp al, {KEY_M}
    je openmap
    cmp al, {KEY_M_ALT}
    jne done
openmap:
    push ds
    mov ax, cs
    mov ds, ax
    mov dx, fname
    mov ax, 0x3d00
    int 0x21
    pop ds
    jb done
    mov bx, ax
    mov si, {VIEW_H}
    mov dx, {VIEW_Y*320 + VIEW_X}
rowread:
    push ds
    mov ax, 0xa000
    mov ds, ax
    mov cx, {VIEW_W}
    mov ah, 0x3f
    int 0x21
    pop ds
    add dx, 320
    dec si
    jnz rowread
    mov ah, 0x3e
    int 0x21
waitrel:
    cmp byte ptr [{SCANCODE:#06x}], 0
    jne waitrel
flash:
    inc byte ptr cs:[tick]
    mov ax, [{PARTY_X:#06x}]
    mov cl, 6
    shr ax, cl
    and al, {256 - TILE_W}
    add ax, {VIEW_X + 2}
    mov bx, ax
    mov ax, [{PARTY_Y:#06x}]
    mov cl, 7
    shr ax, cl
    and al, {256 - TILE_H}
    add ax, {VIEW_Y + 1}
    mov dx, 320
    mul dx
    add bx, ax
    mov ax, 0xa000
    mov es, ax
    mov al, {C_MARK_A}
    test byte ptr cs:[tick], 1
    jz gotcol
    mov al, {C_MARK_B}
gotcol:
    mov dx, 5
markrow:
    mov di, bx
    mov cx, 5
    rep stosb
    add bx, 320
    dec dx
    jnz markrow
    mov cx, 0
delay:
    dec cx
    jnz delay
    cmp byte ptr [{SCANCODE:#06x}], 0
    je flash
    mov al, [{SCANCODE:#06x}]
    mov cs:[lastkey], al
done:
    pop es
    pop ds
    popa
    .byte 0xcb
lastkey:
    .byte 0
tick:
    .byte 0
fname:
    .byte {','.join(str(c) for c in MAPFILE.encode())},0
'''

def apply(b):
    import struct, drakmod
    dg = drakmod.DGROUP
    cseg, coff = b.compass_entry               # chain: run the compass hook first
    size = len(drakmod.assemble(source(dg, cseg, coff), 0))
    seg, off, lin = b.alloc(size)
    code = drakmod.assemble(source(dg, cseg, coff), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    chain_call = bytes([0x9A]) + struct.pack('<HH', coff, cseg)
    disp_call  = bytes([0x9A]) + struct.pack('<HH', DISPATCH[1], DISPATCH[0])
    e_chain = code.find(chain_call); assert e_chain == 0, 'chain entry must be first'
    e_disp  = code.find(disp_call);  assert e_disp > 0, 'dispatcher entry missing'

    # world view: take over the compass's splice, calling it from our hook instead
    p = SPLICE[0]*16 + SPLICE[1]
    assert bytes(b.img[p:p+5]) == chain_call, 'compass splice is not where expected'
    b.img[p:p+5] = bytes([0x9A]) + struct.pack('<HH', off + e_chain, seg)
    # characters-out mode: the world loop never reaches the click dispatcher, so hook it too
    for s_seg, s_off in DISPATCH_SITES:
        b.splice_call(s_seg, s_off, seg, off + e_disp, expect=disp_call)

    b.map_world_entry = (seg, off + e_chain)    # published so mod_regen can take over the splice
    b.add_reloc(seg, off + e_chain + 3)         # segment word of the chained compass call
    b.add_reloc(seg, off + e_disp + 3)          # segment word of the wrapped dispatcher call
    i = code.find(bytes([0xB8]) + struct.pack('<H', dg))
    assert i > 0, 'DGROUP immediate not found'
    b.add_reloc(seg, off + i + 1)
    print('  map: %d bytes at %04x:%04x (world entry +%d, characters-out entry +%d)'
          % (len(code), seg, off, e_chain, e_disp))
