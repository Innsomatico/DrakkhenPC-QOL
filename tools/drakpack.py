"""Drakkhen (DOS, Infogrames 1990) .?C1 container unpacker.
Container: u16be nchunks, nchunks*u32be offsets, then chunks.
Chunk: u32be packed, u32be unpacked, then BPE blocks.
Block: u8 npairs, u8 more, u16le len, npairs*code, npairs*left, npairs*right, len bytes.
Decoder reverse-engineered from DRAKKHEN.COM @0x0a8d."""
import struct, sys, os

def bpe_decode(src, pos=0, out=None):
    out = bytearray() if out is None else out
    while True:
        n, more, ln = src[pos], src[pos+1], struct.unpack_from('<H', src, pos+2)[0]
        pos += 4
        if n == 0:
            out += src[pos:pos+ln]; pos += ln
        else:
            code = src[pos:pos+n]; left = src[pos+n:pos+2*n]; right = src[pos+2*n:pos+3*n]
            pos += 3*n
            t = [0]*256; chain = [0]*(n+1)          # t[code] = latest 1-based pair idx
            for i in range(1, n+1):
                chain[i] = t[code[i-1]]; t[code[i-1]] = i
            def expand(b, limit):
                idx = t[b]
                if idx == 0: out.append(b); return
                if limit is not None and limit <= idx:
                    j = idx
                    while True:
                        j = chain[j]
                        if j == 0: out.append(b); return
                        if j < limit: idx = j; break
                expand(left[idx-1], idx); expand(right[idx-1], idx)
            for b in src[pos:pos+ln]: expand(b, None)
            pos += ln
        if not more: return bytes(out), pos

def unpack_container(data):
    n = struct.unpack_from('>H', data)[0]
    offs = [struct.unpack_from('>I', data, 2+4*i)[0] for i in range(n)] + [len(data)-2-4*n]
    base = 2+4*n
    for i in range(n):
        c = data[base+offs[i]:base+offs[i+1]]
        packed, unpacked = struct.unpack_from('>II', c)
        raw, _ = bpe_decode(c, 8)
        yield i, packed, unpacked, raw

if __name__ == '__main__':
    sys.setrecursionlimit(10000)
    for f in sys.argv[1:]:
        d = open(f, 'rb').read()
        outdir = os.path.splitext(os.path.basename(f))[0] + '_' + os.path.splitext(f)[1][1:]
        os.makedirs(outdir, exist_ok=True)
        for i, p, u, raw in unpack_container(d):
            ok = 'OK' if len(raw) == u else 'MISMATCH'
            print('%-14s chunk %2d packed %6d unpacked %6d got %6d %s head=%s' % (f, i, p, u, len(raw), ok, raw[:8].hex(' ')))
            open(os.path.join(outdir, '%02d.bin' % i), 'wb').write(raw)

# ---- repacking (stores chunks as raw n=0 blocks; decoder accepts them, no memory cost) ----
def bpe_encode_raw(raw):
    out = bytearray()
    blocks = [raw[i:i+0xFFC0] for i in range(0, len(raw), 0xFFC0)] or [b'']
    for i, b in enumerate(blocks):
        out += struct.pack('<BBH', 0, 1 if i < len(blocks)-1 else 0, len(b)) + b
    return bytes(out)

def pack_container(chunks):
    """chunks: list of raw bytes -> container bytes"""
    bodies = [struct.pack('>II', len(bpe_encode_raw(c)), len(c)) + bpe_encode_raw(c) for c in chunks]
    offs, o = [], 0
    for b in bodies: offs.append(o); o += len(b)
    return struct.pack('>H', len(chunks)) + b''.join(struct.pack('>I', x) for x in offs) + b''.join(bodies)

def repack_dir(dirname, outfile):
    files = sorted(f for f in os.listdir(dirname) if f.endswith('.bin'))
    chunks = [open(os.path.join(dirname, f), 'rb').read() for f in files]
    open(outfile, 'wb').write(pack_container(chunks))
