"""Generates the distributable patcher: ../DrakkhenQOL/install.ps1 (+ README.txt).

Philosophy: never distribute Infogrames' data.  The installer rebuilds our modded files from the
CUSTOMER'S OWN stock files - it embeds only our edits: a sparse diff of the decoded engine image
(a few KB for all five mods), the 80-byte Latin font block, and MAP.DRK (our own artwork).  The
customer's stock files are verified by SHA256 before anything is touched, and the rebuilt outputs
are verified against the hashes of the exact files running on the reference install, so the result
is byte-identical or the installer refuses.

Re-run this after any mod change: it re-diffs the current build outputs automatically.
The PowerShell embeds a C# port of drakpack's BPE decoder / raw repacker (pure PS is far too slow).
"""
import sys, os, struct, hashlib, base64
sys.setrecursionlimit(100000)
import drakpack

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
OUT  = os.path.join(GAME, 'DrakkhenQOL')

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def runs_of_diff(a, b, gap=8):
    assert len(a) == len(b)
    d = [i for i in range(len(a)) if a[i] != b[i]]
    assert d, 'no differences?'
    runs, s, p = [], d[0], d[0]
    for i in d[1:]:
        if i - p > gap:
            runs.append((s, p + 1)); s = i
        p = i
    runs.append((s, p + 1))
    return runs

def main():
    os.makedirs(OUT, exist_ok=True)

    stock_drakm = open(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1'), 'rb').read()
    mod_drakm   = open(os.path.join(GAME, 'DRAKM.CC1'), 'rb').read()
    stock_resi  = open(os.path.join(GAME, '_backup', 'original', 'RESI_VGA.6C0'), 'rb').read()
    mod_resi    = open(os.path.join(GAME, 'RESI_VGA.6C0'), 'rb').read()
    mapdrk      = open(os.path.join(GAME, 'MAP.DRK'), 'rb').read()

    so = [raw for *_, raw in drakpack.unpack_container(stock_drakm)]
    sm = [raw for *_, raw in drakpack.unpack_container(mod_drakm)]
    assert len(so) == len(sm) == 2 and so[0] == sm[0] and len(so[1]) == len(sm[1])
    diff = runs_of_diff(so[1], sm[1])
    diff_lines = '\n'.join('%d:%s' % (s, sm[1][s:e].hex()) for s, e in diff)

    r_stock, _ = drakpack.bpe_decode(stock_resi, 8)
    r_mod, _   = drakpack.bpe_decode(mod_resi, 8)
    assert len(r_stock) == len(r_mod)
    rdiff = runs_of_diff(bytes(r_stock), bytes(r_mod))
    rdiff_lines = '\n'.join('%d:%s' % (s, bytes(r_mod)[s:e].hex()) for s, e in rdiff)

    # sanity: our packers, re-run on the stock chunks + diff, must reproduce the shipped files
    patched = bytearray(so[1])
    for s, e in diff:
        patched[s:e] = sm[1][s:e]
    assert drakpack.pack_container([so[0], bytes(patched)]) == mod_drakm, 'container roundtrip failed'
    rp = bytearray(r_stock)
    for s, e in rdiff:
        rp[s:e] = bytes(r_mod)[s:e]
    body = drakpack.bpe_encode_raw(bytes(rp))
    assert struct.pack('>II', len(body), len(rp)) + body == mod_resi, 'resi roundtrip failed'

    subst = {
        'STOCK_DRAKM_SHA': sha(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1')),
        'STOCK_RESI_SHA':  sha(os.path.join(GAME, '_backup', 'original', 'RESI_VGA.6C0')),
        'MOD_DRAKM_SHA':   sha(os.path.join(GAME, 'DRAKM.CC1')),
        'MOD_RESI_SHA':    sha(os.path.join(GAME, 'RESI_VGA.6C0')),
        'MAP_SHA':         sha(os.path.join(GAME, 'MAP.DRK')),
        'DIFF_LINES':      diff_lines,
        'RDIFF_LINES':     rdiff_lines,
        'MAP_B64':         base64.b64encode(mapdrk).decode(),
    }
    tpl = open(os.path.join(HERE, 'patcher_template.ps1'), encoding='utf-8').read()
    for k, v in subst.items():
        tpl = tpl.replace('@@' + k + '@@', v)
    assert '@@' not in tpl, 'unsubstituted placeholder left in template'
    open(os.path.join(OUT, 'install.ps1'), 'w', encoding='utf-8', newline='\r\n').write(tpl)

    open(os.path.join(OUT, 'README.txt'), 'w', newline='\r\n').write('''Drakkhen QOL patch (US GOG version)
====================================

Mods included:
  * Compass in the 3D view (needle tracks your heading)
  * World map on the M key, with your position flashing
  * Spell/phial runes replaced with readable English letters
  * Sorcerer/Priest MP regen at 1.5x while standing still in the world view
  * Kill XP shared: every living party member gets 1/4 of each award
  * Rings/staffs/phials show WHICH one they are next to the type name

Install:
  1. Copy install.ps1 into your Drakkhen game folder
     (the one containing DRAKKHEN.COM and DRAKM.CC1 - for GOG typically
      C:\\Program Files\\GOG Galaxy\\Games\\Drakkhen)
  2. Right-click install.ps1 -> Run with PowerShell
     (or from a terminal:  powershell -ExecutionPolicy Bypass -File install.ps1)

The installer verifies your files are the stock US GOG version before touching
anything, backs them up to _backup\\original\\, rebuilds the patched files from
YOUR OWN game data, and verifies the result byte-for-byte. If any check fails
it stops without changing your game.

Uninstall:
  powershell -ExecutionPolicy Bypass -File install.ps1 -Restore

Save files are never touched by install or restore.
''')
    print('wrote %s (install.ps1 %d bytes)' % (OUT, os.path.getsize(os.path.join(OUT, 'install.ps1'))))

if __name__ == '__main__':
    main()
