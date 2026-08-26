"""Mod: opt-in quest HINT system on the H key (world view), chained onto the same hook as the map.

Reframed from a journal: the page header (baked into QUEST.DRK) says SPACE reveals the next hint,
so spoilers are the player's choice. H toggles, B goes back, any other key closes.

Shows the steps you have completed plus the one you are on, and HIDES everything after it - so the
journal never spoils what is coming.  The reveal costs no code: QUEST.DRK (built by genjournal.py)
is a 256x128 image whose quest steps occupy a fixed number of rows each, so "show steps 1..N" is
literally "read the first ROWS[N] rows of the file and stop".

Key: physical H (0x23). Verified safe: AZERTY remap maps it to itself; no engine compare uses it.

The revealed count is session-only (user's call: re-tapping SPACE is fine, and dropping the
QUEST.STP persistence bought back ~70 bytes). Every launch starts at hint 1.
The step is NOT auto-detected yet: the engine's progress counters at DS:6F38 are the right shape but
their index->quest-step mapping has to be observed during a playthrough (see ROADMAP item 13).

Chain: takes over the 19F7:09A9 splice from whichever mod holds it and far-calls that first, so
compass -> map -> journal all run.
"""
QUESTFILE = 'QUEST.DRK'
KEY_H = 0x23
SCANCODE = 0x3DCE
VIEW_X, VIEW_Y, VIEW_W = 64, 3, 256
KEY_SPACE, KEY_B = 0x39, 0x30
MAXSTEP = 15
SPLICE = (0x19F7, 0x09A9)


def source(dgroup, prev_seg, prev_off, rowtab):
    return f'''
    lcall {prev_seg:#06x}:{prev_off:#06x}
    pusha
    push ds
    push es
    mov ax, {dgroup:#06x}
    mov es, ax
    mov ax, cs
    mov ds, ax
    mov al, es:[{SCANCODE:#06x}]
    cmp al, cs:[lastkey]
    je done
    mov cs:[lastkey], al
    cmp al, {KEY_H}
    jne done
draw:
    mov dx, qname
    mov ax, 0x3d00
    int 0x21
    jb done
    mov bx, ax
    ; rows = ROWTAB[step-1]  (cumulative rows through the current step)
    push bx
    mov al, cs:[step]
    mov ah, 0
    dec ax
    mov si, ax
    mov al, cs:[si+rowtab]
    mov ah, 0
    mov si, ax
    mov bp, si
    pop bx
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
    ; blank the rest of the viewport so going BACK erases previously revealed rows
    push es
    mov ax, 0xa000
    mov es, ax
    mov di, dx
    mov bx, 128
    sub bx, bp
    jz filldone
fillrow:
    xor ax, ax
    mov cx, {VIEW_W}
    rep stosb
    add di, {320 - VIEW_W}
    dec bx
    jnz fillrow
filldone:
    pop es
waitrel:
    cmp byte ptr es:[{SCANCODE:#06x}], 0
    jne waitrel
waitkey:
    cmp byte ptr es:[{SCANCODE:#06x}], 0
    je waitkey
    mov al, es:[{SCANCODE:#06x}]
    mov cs:[lastkey], al
    cmp al, {KEY_SPACE}
    je fwd
    cmp al, {KEY_B}
    je back
    jmp done
fwd:
    cmp byte ptr cs:[step], {MAXSTEP}
    jae waitrel
    inc byte ptr cs:[step]
    jmp draw
back:
    cmp byte ptr cs:[step], 2
    jb waitrel
    dec byte ptr cs:[step]
    jmp draw
done:
    pop es
    pop ds
    popa
    .byte 0xcb
lastkey:
    .byte 0
step:
    .byte 1
qname:
    .byte {','.join(str(c) for c in QUESTFILE.encode())},0
rowtab:
    .byte {','.join(str(v) for v in rowtab)}
'''


def apply(b):
    import struct, json, os, drakmod
    dg = drakmod.DGROUP
    meta = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'journal.json')))
    rows, cum = [], meta.get('header_rows', 0)   # header line is always shown
    for n in meta['rows_per_step']:
        cum += n
        rows.append(cum)
    assert max(rows) <= 128 and len(rows) == MAXSTEP, 'journal.json does not match MAXSTEP/viewport'

    pseg, poff = b.map_world_entry            # chain whatever currently owns the splice
    size = len(drakmod.assemble(source(dg, pseg, poff, rows), 0))
    seg, off, lin = b.alloc_code(size, want_paragraph=False)
    code = drakmod.assemble(source(dg, pseg, poff, rows), off)
    assert len(code) == size, 'code size shifted between passes'
    b.put(lin, code)

    prev_call = bytes([0x9A]) + struct.pack('<HH', poff, pseg)
    assert code.find(prev_call) == 0, 'chain call must be first'
    p = SPLICE[0] * 16 + SPLICE[1]
    assert bytes(b.img[p:p + 5]) == prev_call, 'expected the previous mod to own this splice'
    b.img[p:p + 5] = bytes([0x9A]) + struct.pack('<HH', off, seg)

    b.add_reloc(seg, off + 3)
    i = code.find(bytes([0xB8]) + struct.pack('<H', dg))
    assert i > 0, 'DGROUP immediate not found'
    b.add_reloc(seg, off + i + 1)
    print('  hints: %d bytes at %04x:%04x (H key, %d hints, QUEST.DRK)'
          % (len(code), seg, off, MAXSTEP))
