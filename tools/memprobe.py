"""Read-only probe of the dev DOSBox instance: sample the MP regen state of the 4 characters.

Finds the emulated RAM by scanning for a unique in-game byte signature, then samples
char +0x58 (MP countdown), +0x5B (cur MP), +0x5C (max MP) for each character over time.
Reads only - never writes to the process.
"""
import ctypes, ctypes.wintypes as wt, struct, sys, time

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
k32 = ctypes.windll.kernel32

class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_size_t), ('AllocationBase', ctypes.c_size_t),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]

def find_pid(name=b'DOSBox.exe'):
    import subprocess
    out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq DOSBox.exe', '/FO', 'CSV'])
    for line in out.splitlines()[1:]:
        parts = line.split(b'","')
        if len(parts) > 1:
            return int(parts[1])
    raise SystemExit('no DOSBox process')

def read(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]

def find_sig(h, sig):
    addr, hits = 0, []
    mbi = MBI()
    while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and mbi.RegionSize < 0x4000000:
            data = read(h, mbi.BaseAddress, mbi.RegionSize)
            if data:
                i = data.find(sig)
                while i >= 0:
                    hits.append(mbi.BaseAddress + i)
                    i = data.find(sig, i + 1)
        addr = mbi.BaseAddress + mbi.RegionSize
        if addr == 0:
            break
    return hits

def main():
    pid = find_pid()
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    assert h, 'OpenProcess failed'
    # record 1's name field is unique in RAM
    hits = find_sig(h, b'SAORCHIESE')
    print('signature hits:', [hex(x) for x in hits])
    if not hits:
        raise SystemExit('party not in memory yet')
    base = hits[0] - (0x5A2E + 0x19A)      # -> live address of DS:0000
    names = ['BUNS  ', 'SAORCH', 'SALMON', 'CHEIES']
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    t0 = time.time()
    print('t     ' + '  '.join('%s ctd cur/max' % n for n in names))
    while time.time() - t0 < secs:
        row = []
        for c in range(4):
            rec = base + 0x5A2E + c * 0x19A
            b = read(h, rec + 0x56, 8)      # +0x56..+0x5D
            cls, ctd, mp, mpmax = b[0], b[2], b[5], b[6]
            row.append('cls%d %3d %2d/%2d' % (cls, ctd, mp, mpmax))
        print('%5.1f  %s' % (time.time() - t0, '   '.join(row)))
        time.sleep(1.0)

if __name__ == '__main__':
    main()
