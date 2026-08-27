"""Small mod framework for Drakkhen's VGA engine (DRAKM.CC1).

Adding a mod = one entry in MODS.  The framework handles the fiddly parts that took a long time to
get right, so a new mod never has to rediscover them:

  * BPE container unpack/repack (drakpack.py)
  * placing code in verified-dead space, with an allocator so mods cannot overlap
  * splicing a call over an existing instruction and fixing up relocations correctly
  * hard invariants that would otherwise produce silent corruption

Invariants enforced on every build (each one cost a debugging round to learn):
  1. The unpacked image size must not change.  Enlarging it starves the graphics loader and the
     game reports "insert Disk 3" - DOS gives the program 640K and Drakkhen already needs ~563K.
  2. Code must not live in BSS (DS:4960..70E2) - the C startup zero-fills it at launch.
  3. Code must not live in a region the engine uses as cs:-relative variables; the "empty" zero
     runs inside code segments are exactly that, and overwriting them crashes with "Divide error".
  4. A splice site that was already a far call ALREADY has a relocation on its segment word.
     Adding another relocates it twice and sends the call into garbage.
  5. A splice over "mov ax,DGROUP / mov ds,ax" must REPOINT that instruction's existing relocation
     to the new call's segment word, or the loader corrupts the call's offset.
  6. keystone in 16-bit mode emits 32-bit ret/retf/call (66 C3 / 66 CB / 66 E8).  Use no call/ret
     inside hooks; emit the far return as a raw 0xCB byte.

Free space: the engine ships three filename tables but the selector at 03AD:1918/1924 only ever
installs two, so the third table (DS:1958, 112 bytes) and the 288-byte duplicate string set it
points at (DS:204E..216E) are unreachable.  Both are initialised data, so they survive the BSS
zero-fill.  That is all the verified-dead space found so far - see SPACE below.
"""
import struct, sys, os
sys.setrecursionlimit(10000)
import drakpack

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
ORIG = os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1')
OUT  = os.path.join(GAME, 'DRAKM.CC1')

DGROUP = 0x1FD4

# Verified-dead regions, as (DGROUP offset, length, description).
# The engine ships FOUR filename tables (one per disk configuration) with a string set each, but the
# selector at 03AD:1918/1924 only ever installs table 3 (0x1A30) or table 4 (0x1A9C).  Tables 1 and 2
# and the two string sets they alone point at are unreachable.  Initialised data, so they survive the
# startup BSS zero-fill.
SPACE = [
    (0x2050, 0x226E - 0x2050, 'orphan filename strings, sets 1-2 (DS:204E..226E)'),
    (0x1958, 0x1A30 - 0x1958, 'orphan filename tables 1-2 (DS:1958..1A30)'),
]

# Code-segment dead space, given as absolute image-linear ranges (not DGROUP-relative).
# The copy-protection routine 0D7E:19B1..0D7E:1B78 (img 0xF191..0xF359, 456 B) is unreachable once
# mod_noprotect disables the gate: an exhaustive scan of every near/far call and jmp in the image
# finds exactly ONE entry into that range - the gate's own `call 0x19B1` at img 0xF38A, which the
# counter patch guarantees never executes. Everything the routine used (dialog draw 0D7E:18B0, the
# quete.fnt table) is only referenced from inside it.
# REQUIRES mod_noprotect to be in the build - assert it before allocating here.
CODE_SPACE = [
    (0xF191, 0xF359 - 0xF191, 'copy-protection routine (dead once mod_noprotect is applied)'),
]

class Builder:
    def __init__(self):
        chunks = [raw for *_, raw in drakpack.unpack_container(open(ORIG, 'rb').read())]
        self.chunks = chunks
        self.exe = bytearray(chunks[1])
        # Chunk 0 is a SECOND MZ image: the character creator (DGROUP 0x06B8).  Mods that
        # change what a new character starts with live there - see NOTES.md.  It needs no
        # relocation bookkeeping because those edits are immediate operands, so it is kept
        # as one flat buffer and journalled separately as 'writes0'.
        self.img0 = bytearray(chunks[0])
        self.h = list(struct.unpack_from('<14H', self.exe))
        self.hdr = self.h[4] * 16
        self.img = bytearray(self.exe[self.hdr:])
        self._len = len(self.img)
        self.ro, self.nrel = self.h[12], self.h[3]
        self.relocs = {}
        for i in range(self.nrel):
            off, seg = struct.unpack_from('<HH', self.exe, self.ro + 4*i)
            self.relocs[seg*16 + off] = i
        self.added = []
        self.repointed = []            # (old_linear, new_off, new_seg) - journaled for fragments
        self.allocated = []            # (linear start, size) of every alloc()
        self.free = [[DGROUP*16 + o, n, d] for o, n, d in SPACE]
        self.code_free = [[o, n, d] for o, n, d in CODE_SPACE]
        self.noprotect = False        # set by mod_noprotect; gates use of CODE_SPACE
        assert self.img[DGROUP*16+4: DGROUP*16+11] == b'Turbo-C', 'not the expected engine build'

    # --- space -------------------------------------------------------------
    def alloc(self, size, want_paragraph=True):
        """Reserve `size` bytes of verified-dead space; returns (seg, off, linear)."""
        for blk in self.free:
            base, avail = blk[0], blk[1]
            start = (base + 15) & ~15 if want_paragraph else base
            pad = start - base
            if avail - pad >= size:
                blk[0], blk[1] = start + size, avail - pad - size
                self.allocated.append((start, size))
                # The orphan filename TABLES are full of far pointers, so the loader's relocation
                # table has entries pointing INTO this region.  Left in place, the loader would
                # "relocate" words of our code at load time and corrupt it silently.  Drop them.
                stale = [lin for lin in self.relocs if start <= lin < start + size]
                for lin in stale:
                    del self.relocs[lin]
                if stale:
                    print('  (dropped %d stale relocations inside allocated region %05x..%05x)'
                          % (len(stale), start, start + size))
                return start >> 4, start & 0xF, start
        raise RuntimeError('out of verified-dead space; need %d bytes (free: %s)'
                           % (size, [b[1] for b in self.free]))

    def alloc_code(self, size, want_paragraph=True):
        """Reserve dead CODE space (see CODE_SPACE). Only legal once mod_noprotect has run."""
        assert self.noprotect, 'alloc_code() requires mod_noprotect in the build (it is what kills '                                'the only path into that code)'
        for blk in self.code_free:
            base, avail = blk[0], blk[1]
            start = (base + 15) & ~15 if want_paragraph else base
            pad = start - base
            if avail - pad >= size:
                blk[0], blk[1] = start + size, avail - pad - size
                self.allocated.append((start, size))
                stale = [lin for lin in self.relocs if start <= lin < start + size]
                for lin in stale:
                    del self.relocs[lin]
                if stale:
                    print('  (dropped %d stale relocations inside code region %05x..%05x)'
                          % (len(stale), start, start + size))
                return start >> 4, start & 0xF, start
        raise RuntimeError('out of dead code space; need %d bytes (free: %s)'
                           % (size, [b[1] for b in self.code_free]))

    def remaining(self):
        return sum(b[1] for b in self.free)

    def remaining_code(self):
        return sum(b[1] for b in self.code_free)

    # --- placement ---------------------------------------------------------
    def put(self, lin, blob):
        self.img[lin:lin+len(blob)] = blob

    def add_reloc(self, seg, off):
        lin = seg*16 + off
        assert lin not in self.relocs, 'word at %04x:%04x is already relocated' % (seg, off)
        self.added.append((off, seg))

    def repoint_reloc(self, old_lin, seg, off):
        i = self.relocs.pop(old_lin, None)
        assert i is not None, 'no existing relocation at %#x' % old_lin
        struct.pack_into('<HH', self.exe, self.ro + 4*i, off, seg)
        self.relocs[seg*16 + off] = i
        self.repointed.append((old_lin, off, seg))

    def splice_call(self, seg, off, target_seg, target_off, expect=None):
        """Overwrite 5 bytes with `lcall target`, handling the site's existing relocation."""
        p = seg*16 + off
        if expect is not None:
            assert self.img[p:p+5] == expect, 'unexpected bytes at %04x:%04x: %s' % (
                seg, off, self.img[p:p+5].hex())
        was_far_call = self.img[p] == 0x9A
        self.img[p:p+5] = b'\x9a' + struct.pack('<HH', target_off, target_seg)
        if was_far_call:
            assert p + 3 in self.relocs, 'far call site should already be relocated'
        else:
            # e.g. "mov ax,DGROUP / mov ds,ax": its immediate is relocated - move that entry
            self.repoint_reloc(p + 1, seg, off + 3)

    # --- finish ------------------------------------------------------------
    def save(self, path=OUT):
        # Rebuild the relocation table from scratch: surviving originals (minus the stale entries
        # dropped by alloc()) followed by the mods' additions.  Repointed entries were edited in
        # place and survive via their original index.
        entries = []
        for i in sorted(self.relocs.values()):
            entries.append(struct.unpack_from('<HH', self.exe, self.ro + 4*i))
        entries += [(off, seg) for off, seg in self.added]
        for k, (off, seg) in enumerate(entries):
            struct.pack_into('<HH', self.exe, self.ro + 4*k, off, seg)
        self.h[3] = len(entries)
        assert self.ro + self.h[3]*4 <= self.hdr, 'relocation table overflow'
        assert len(self.img) == self._len, 'image size changed - would break the loader'
        seen = set()
        for i in range(self.h[3]):
            off, seg = struct.unpack_from('<HH', self.exe, self.ro + 4*i)
            lin = seg*16 + off
            assert lin not in seen, 'duplicate relocation at %04x:%04x' % (seg, off)
            seen.add(lin)
        struct.pack_into('<14H', self.exe, 0, *self.h)
        assert len(self.img0) == len(self.chunks[0]), 'creator image size changed'
        self.chunks[0] = bytes(self.img0)
        self.chunks[1] = bytes(self.exe[:self.hdr]) + bytes(self.img)
        open(path, 'wb').write(drakpack.pack_container(self.chunks))
        return path

def assemble(src, org):
    """Assemble 16-bit code.

    keystone in 16-bit mode silently emits 32-bit forms for ret / retf / near call
    (66 C3 / 66 CB / 66 E8 rel32), which corrupt the stack.  Blobs may embed data, so
    disassembling the output to detect that is unreliable - the source is checked instead:
    use lcall for calls, and a raw ".byte 0xcb" for the far return.
    """
    lines = [l.split(';')[0] for l in src.split(chr(10))]
    for n, l in enumerate(lines, 1):
        m = l.strip().split()
        if not m:
            continue
        op = m[0].lower()
        if op in ('ret', 'retf', 'retn', 'call'):
            raise AssertionError(
                'line %d: "%s" - keystone emits a 32-bit form here; use lcall, '
                'or ".byte 0xcb" for a far return' % (n, l.strip()))
    from keystone import Ks, KS_ARCH_X86, KS_MODE_16
    return bytes(Ks(KS_ARCH_X86, KS_MODE_16).asm(chr(10).join(lines), org)[0])

def build(mods):
    """mods: list of (name, apply_fn). Applies all, saves, and journals each mod's exact
    contribution (image writes, relocation adds, relocation drops) to fragments.json so the
    distributable installer can apply any user-selected subset."""
    import json
    b = Builder()
    frags = {}
    order = []
    for name, m in mods:
        img_before = bytes(b.img)
        img0_before = bytes(b.img0)
        relocs_before = set(b.relocs.keys())
        added_before = len(b.added)
        rep_before = len(b.repointed)
        m(b)
        # image writes as runs (chunk-relative: header + image offset)
        d = [i for i in range(len(b.img)) if b.img[i] != img_before[i]]
        runs = []
        if d:
            s0 = p0 = d[0]
            for i in d[1:]:
                if i - p0 > 8:
                    runs.append((s0, p0 + 1)); s0 = i
                p0 = i
            runs.append((s0, p0 + 1))
        d0 = [i for i in range(len(b.img0)) if b.img0[i] != img0_before[i]]
        runs0 = []
        if d0:
            s0 = p0 = d0[0]
            for i in d0[1:]:
                if i - p0 > 8:
                    runs0.append((s0, p0 + 1)); s0 = i
                p0 = i
            runs0.append((s0, p0 + 1))
        frags[name] = {
            'writes0': [[s0, bytes(b.img0[s0:e0]).hex()] for s0, e0 in runs0],
            'writes': [[b.hdr + s0, bytes(b.img[s0:e0]).hex()] for s0, e0 in runs],
            'radd':   [[off, seg] for off, seg in b.added[added_before:]],
            'rrep':   [[o, off, seg] for o, off, seg in b.repointed[rep_before:]],
            'rdrop':  sorted((relocs_before - set(b.relocs.keys()))
                             - {o for o, _, _ in b.repointed[rep_before:]}),
        }
        order.append(name)
    p = b.save()
    json.dump({'order': order, 'frags': frags},
              open(os.path.join(HERE, 'fragments.json'), 'w'), indent=0)
    print('built %s  (%d mods, %d B data dead space + %d B code dead space left; fragments.json written)'
          % (os.path.basename(p), len(mods), b.remaining(), b.remaining_code()))
    return p

if __name__ == '__main__':
    import mod_compass, mod_map, mod_regen, mod_partyxp, mod_itemname, mod_bow, mod_noprotect, mod_journal, mod_levelup, mod_ring, mod_startgear, mod_startring, mod_startworn, mod_freetemple
    import mod_spellfont, mod_novideomenu, mod_menu4, mod_menucolor
    # mod_regen is DROPPED (user's call, 2026-08-23): a crash on packing characters ended it.
    # The mod file and the research in NOTES.md/ROADMAP.md remain if it is ever revisited.
    build([('compass', mod_compass.apply), ('map', mod_map.apply),
           ('partyxp', mod_partyxp.apply), ('itemname', mod_itemname.apply),
           ('bow', mod_bow.apply), ('noprotect', mod_noprotect.apply),
           ('hints', mod_journal.apply), ('levelup', mod_levelup.apply),
           ('ring', mod_ring.apply), ('startgear', mod_startgear.apply), ('startring', mod_startring.apply),
           ('freetemple', mod_freetemple.apply),
           # startworn LAST: it flags the gear records other start* mods may have edited
           ('startworn', mod_startworn.apply)])
    # Data-only mods: these patch loose game files, not the engine, so they cost no dead space.
    orig = os.path.join(GAME, '_backup', 'original')
    mod_spellfont.apply_data(orig, GAME)
    mod_novideomenu.apply_data(orig, GAME)
    mod_menu4.apply_data(orig, GAME)
    mod_menucolor.apply_data(orig, GAME)
