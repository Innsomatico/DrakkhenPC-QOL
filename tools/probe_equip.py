"""Read-only live diff: a character the player re-equipped in game vs ones only flagged worn.

Finds the running DOSBox's emulated RAM by searching for the party's name signature, then dumps
each character record and reports which fields differ between character 1 and the rest.  That is
the ground truth for what "equipped" really means beyond bit 7 of the item flags.

Reads only - it never writes to the emulator process.
"""
import ctypes, ctypes.wintypes as wt, struct, sys, subprocess

k32 = ctypes.windll.kernel32
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x0010, 0x0400
STRIDE = 0x19A


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_size_t), ('AllocationBase', ctypes.c_size_t),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


def pids():
    out = subprocess.check_output(['tasklist', '/FO', 'CSV'], text=True, errors='ignore')
    found = []
    for line in out.splitlines()[1:]:
        p = [x.strip('"') for x in line.split('","')]
        if len(p) > 1 and 'dosbox' in p[0].lower():
            found.append((p[0], int(p[1])))
    return found


def read(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]


def scan(h, sig):
    addr, hits, mbi = 0, [], MBI()
    while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and mbi.RegionSize < 0x4000000:
            d = read(h, mbi.BaseAddress, mbi.RegionSize)
            if d:
                i = d.find(sig)
                while i >= 0:
                    hits.append(mbi.BaseAddress + i)
                    i = d.find(sig, i + 1)
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    return hits


def main():
    names = [n.encode() for n in (sys.argv[1:] or ['MOTHER', 'DAVID', 'XEA', 'CHEWY'])]
    procs = pids()
    print('dosbox processes:', procs or 'NONE')
    for pname, pid in procs:
        h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            print('  pid %d: cannot open' % pid); continue
        sig = names[0] + b'\0'
        for base in scan(h, sig):
            blob = read(h, base, STRIDE * 4)
            if not blob:
                continue
            got = [bytes(blob[n * STRIDE:n * STRIDE + 8]).rstrip(b'\0') for n in range(4)]
            if not all(names[n] in got[n] for n in range(min(4, len(names)))):
                continue
            print('\nparty found in pid %d at 0x%X: %s' % (pid, base, [g.decode() for g in got]))
            recs = [blob[n * STRIDE:(n + 1) * STRIDE] for n in range(4)]
            print('\nkey fields:')
            for n, r in enumerate(recs):
                worn = [s for s in range(8) if r[0x64 + s * 6 + 3] and r[0x64 + s * 6] & 0x80]
                print('  %-8s +0x56=%02x +0x57=%02x +0x58=%02x  flags[0C..0F]=%s  worn=%s'
                      % (got[n].decode(), r[0x56], r[0x57], r[0x58], r[0x0C:0x10].hex(), worn))
            print('\nfields where char 1 (re-equipped) differs from chars 2-4:')
            for o in range(0, 0x64):
                a = recs[0][o]; rest = [recs[n][o] for n in (1, 2, 3)]
                if all(a != x for x in rest):
                    print('   +%02x  P1=%02x   others=%s' % (o, a, ' '.join('%02x' % x for x in rest)))
            print('\nitem arrays:')
            for n, r in enumerate(recs):
                print('  %-8s items %s' % (got[n].decode(),
                      ' | '.join(r[0x64 + s * 6:0x64 + s * 6 + 6].hex() for s in range(6))))
            return 0
        k32.CloseHandle(h)
    print('party signature not found - is the game on the character screen / in play?')
    return 1


if __name__ == '__main__':
    sys.exit(main())
