"""Recursive-descent 16-bit disassembler for the unpacked Drakkhen engine EXEs (Turbo C 2.0, large model).
Usage: python dis.py DRAKM_CC1/01.bin > drakm1.asm
Addresses are seg:off relative to load segment 0. Relocations are applied (load seg 0 -> no-op) and listed.
"""
import struct, sys, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

def load(path):
    d = open(path, 'rb').read()
    h = struct.unpack_from('<14H', d)
    hdr = h[4]*16
    img = bytearray(d[hdr:hdr + h[2]*512 - (512-h[1] if h[1] else 0) - hdr + 0])
    img = bytearray(d[hdr:])
    relocs = set()
    for i in range(h[3]):
        off, seg = struct.unpack_from('<HH', d, h[11] + 4*i)
        relocs.add(seg*16 + off)
    return img, relocs, (h[10], h[9]), (h[7], h[8])   # cs:ip, ss:sp

def disasm(img, relocs, entry):
    md = Cs(CS_ARCH_X86, CS_MODE_16); md.detail = True
    insns = {}
    queue = collections.deque([entry])
    seen_seg = {}     # linear -> seg for display
    calls = collections.defaultdict(set)
    seg_of = {}
    pending = [(entry[0], entry[1])]
    visited = set()
    while pending:
        seg, off = pending.pop()
        lin = seg*16 + off
        if lin in visited or lin >= len(img): continue
        while lin < len(img) and lin not in visited:
            try:
                i = next(md.disasm(bytes(img[lin:lin+15]), off))
            except StopIteration:
                break
            visited.add(lin); insns[lin] = (seg, off, i)
            seg_of[lin] = seg
            m = i.mnemonic
            nxt = None
            if m == 'lcall' or m == 'ljmp':
                if i.operands[0].type == X86_OP_IMM:
                    t = i.operands[0].imm
                    if i.bytes[0] in (0x9a, 0xea):
                        toff, tseg = struct.unpack_from('<HH', bytes(i.bytes), 1)
                        pending.append((tseg, toff)); calls[tseg*16+toff].add(lin)
                if m == 'lcall': nxt = off + i.size
            elif m == 'call' or m.startswith('j') or m.startswith('loop'):
                if i.operands and i.operands[0].type == X86_OP_IMM:
                    t = i.operands[0].imm & 0xffff
                    pending.append((seg, t)); calls[seg*16+t].add(lin)
                if m != 'jmp': nxt = off + i.size
            elif m in ('ret', 'retf', 'iret', 'hlt'):
                nxt = None
            else:
                nxt = off + i.size
            if nxt is None: break
            off = nxt & 0xffff; lin = seg*16 + off
    return insns, calls

def main():
    path = sys.argv[1]
    img, relocs, entry, stack = load(path)
    insns, calls = disasm(img, relocs, entry)
    # Turbo C: find DGROUP from startup "mov dx, seg DGROUP" (BA imm16 with reloc at +1)
    print('; entry %04x:%04x  ss:sp %04x:%04x  image %d bytes  relocs %d' % (entry[0], entry[1], stack[0], stack[1], len(img), len(relocs)))
    dgroup = None
    for lin in sorted(insns):
        seg, off, i = insns[lin]
        if i.bytes[0] == 0xba and (lin+1) in relocs:
            dgroup = struct.unpack_from('<H', bytes(i.bytes), 1)[0]; break
    print('; DGROUP = %04x (linear %05x)' % (dgroup, dgroup*16) if dgroup else '; DGROUP not found')
    for lin in sorted(insns):
        seg, off, i = insns[lin]
        if lin in calls:
            print('\n%04x:%04x  ; <- %s' % (seg, off, ' '.join('%05x' % c for c in sorted(calls[lin])[:8])))
        rel = ' ;R' if any((lin+k) in relocs for k in range(i.size)) else ''
        print('%04x:%04x  %-18s %s %s%s' % (seg, off, i.bytes.hex(), i.mnemonic, i.op_str, rel))

if __name__ == '__main__':
    main()
