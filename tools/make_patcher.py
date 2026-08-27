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
    import mod_menu4, mod_menucolor, hashlib as _h, itertools as _it
    com_stock   = open(os.path.join(GAME, '_backup', 'original', 'DRAKKHEN.COM'), 'rb').read()
    com_stock_sha = _h.sha256(com_stock).hexdigest()
    assert com_stock_sha == mod_menu4.STOCK_SHA
    com_order = ['menu4', 'menucolor']
    com_mods = {'menu4':     [[a, b.hex()] for a, b in mod_menu4.runs()],
                'menucolor': [[a, b.hex()] for a, b in mod_menucolor.runs()]}
    com_desc = {'menu4':     'video-card menu entry removed (4-item main menu)',
                'menucolor': 'colored menu (blue field, gold text)'}
    com_shas = {}
    for _n in (1, 2):
        for _combo in _it.combinations(com_order, _n):
            _cd = bytearray(com_stock)
            for _k in _combo:
                for _a, _hx in com_mods[_k]:
                    _b = bytes.fromhex(_hx)
                    _cd[_a - 0x100:_a - 0x100 + len(_b)] = _b
            com_shas['+'.join(_combo)] = _h.sha256(bytes(_cd)).hexdigest()
    questdrk    = open(os.path.join(GAME, 'QUEST.DRK'), 'rb').read()

    so = [raw for *_, raw in drakpack.unpack_container(stock_drakm)]
    sm = [raw for *_, raw in drakpack.unpack_container(mod_drakm)]
    # chunk 0 is the character creator and IS patched now (mod_startgear); both chunks must
    # keep their exact size, since a larger image starves the loader ("insert Disk 3").
    assert len(so) == len(sm) == 2
    assert len(so[0]) == len(sm[0]) and len(so[1]) == len(sm[1])
    diff0 = runs_of_diff(so[0], sm[0])          # creator chunk (mod_startgear)
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
    patched0 = bytearray(so[0])
    for s, e in diff0:
        patched0[s:e] = sm[0][s:e]
    assert drakpack.pack_container([bytes(patched0), bytes(patched)]) == mod_drakm,         'container roundtrip failed'
    rp = bytearray(r_stock)
    for s, e in rdiff:
        rp[s:e] = bytes(r_mod)[s:e]
    body = drakpack.bpe_encode_raw(bytes(rp))
    assert struct.pack('>II', len(body), len(rp)) + body == mod_resi, 'resi roundtrip failed'

    import json
    frag = json.load(open(os.path.join(HERE, 'fragments.json')))
    # user-facing mod list: key, label, dependencies. Engine frags by key; file mods by kind.
    moddefs = [
        ['compass',   'Compass in the 3D view', []],
        ['map',       'World map on the M key', ['compass']],
        ['hints',     'Quest hints on the H key', ['map', 'noprotect']],
        ['spellfont', 'Readable spell font (English letters)', []],
        ['itemname',  'Item identification (ring/sceptre/phial names)', []],
        ['ring',      'Working ring & sceptre effects', ['noprotect']],
        ['levelup',   'Class-based stat growth on level-up', []],
        ['startgear', 'Scout starts with a bow instead of a dagger', ['bow']],
        ['startring', 'Magician starts wearing a RESTORE ring', ['ring']],
        ['startworn', 'New characters start with their gear equipped', []],
        ['freetemple','Anak temples heal and revive for free', []],
        ['partyxp',   'Party-shared kill XP', []],
        ['bow',       'Bow buff (power 8, arch renamed to bow)', []],
        ['noprotect', 'Remove the copy-protection prompt', []],
        ['vga',       'Skip the video-card menu (always VGA)', []],
        ['menu4',     'Remove Select-video-card from the main menu (4 items)', ['vga']],
        ['menucolor', 'Launcher menu in color (blue field, gold text)', []],
    ]
    subst = {
        'FRAGS_JSON':      json.dumps(frag, separators=(',', ':')),
        # NB: labels must contain no " or \ - MODDEFS_JSON is embedded inside a Python
        # ''' literal, which would eat json.dumps's escapes before json.loads sees them.
        'MODDEFS_JSON':    json.dumps(moddefs, separators=(',', ':')),
        'STOCK_COM_SHA':   com_stock_sha,
        'COM_ORDER':       json.dumps(com_order, separators=(',', ':')),
        'COM_MODS':        json.dumps(com_mods, separators=(',', ':')),
        'COM_SHAS':        json.dumps(com_shas, separators=(',', ':')),
        'COM_DESC':        json.dumps(com_desc, separators=(',', ':')),
        'STOCK_DRAKM_SHA': sha(os.path.join(GAME, '_backup', 'original', 'DRAKM.CC1')),
        # Steam ships DRAKM.CC1 = GOG stock with ONE byte changed (their copy-protection skip:
        # jne->jmp at decoded-chunk offset 0x11D87). The installers normalize it back to stock.
        'STEAM_DRAKM_SHA': '8e25bed91fa4b19e4f553a74c43ebf766b676204613b4d921b16c43eae490b16',
        'STOCK_RESI_SHA':  sha(os.path.join(GAME, '_backup', 'original', 'RESI_VGA.6C0')),
        'MOD_DRAKM_SHA':   sha(os.path.join(GAME, 'DRAKM.CC1')),
        'MOD_RESI_SHA':    sha(os.path.join(GAME, 'RESI_VGA.6C0')),
        'MAP_SHA':         sha(os.path.join(GAME, 'MAP.DRK')),
        'DIFF_LINES':      diff_lines,
        'RDIFF_LINES':     rdiff_lines,
        'MAP_B64':         base64.b64encode(mapdrk).decode(),
        'QUEST_SHA':       __import__('hashlib').sha256(questdrk).hexdigest(),
        'QUEST_B64':       base64.b64encode(questdrk).decode(),
    }
    for tname, oname, nl in (('patcher_template.ps1', 'install.ps1', '\r\n'),
                             ('patcher_template.py', 'install.py', '\n')):
        tpl = open(os.path.join(HERE, tname), encoding='utf-8').read()
        for k, v in subst.items():
            tpl = tpl.replace('@@' + k + '@@', v)
        assert '@@' not in tpl, 'unsubstituted placeholder left in ' + tname
        open(os.path.join(OUT, oname), 'w', encoding='utf-8', newline=nl).write(tpl)
    # published checksums for both installers
    sums = ''
    for f in ('install.ps1', 'install.py'):
        sums += '%s  %s\n' % (sha(os.path.join(OUT, f)), f)
    open(os.path.join(OUT, 'SHA256SUMS.txt'), 'w', newline='\n').write(sums)

    open(os.path.join(OUT, 'README.txt'), 'w', newline='\r\n').write('''Drakkhen QOL patch (US GOG and Steam releases)
==============================================

Mods included:
  * Compass in the 3D view (needle tracks your heading)
  * World map on the M key, with your position flashing
  * Quest hints on the H key (SPACE reveals the next hint - spoilers are your choice)
  * Spell/phial runes replaced with readable English letters
  * Rings/sceptres/phials show WHICH one they are next to the type name
  * Rings and sceptres now WORK: wearing one grants its effect (Invisibility,
    Protection, Recuperation = double regen, Acceleration, Power, Understanding,
    Impalpability). The stock game shipped these effects unwired.
  * Class-based stat growth on level-up (the stock game grants none at all)
  * Kill XP shared: every living party member gets 1/4 of each award
  * Bow buffed from weakest weapon in the game to a real choice (power 8, on par with
    the short sword), renamed from "arch"
  * New characters start with their gear already EQUIPPED (the stock game hands it
    over unworn, so a fresh party walks out unarmed until you equip 14 items by hand)
  * The scout starts with a bow instead of a dagger
  * The magician starts wearing a RESTORE ring (double regen, via the ring mod)
  * Copy-protection code prompt removed; video-card menu skipped (always VGA)

Install:
  1. Copy install.ps1 into your Drakkhen folder:
       GOG   - the folder holding DRAKKHEN.COM and DRAKM.CC1, typically
               C:\\Program Files\\GOG Galaxy\\Games\\Drakkhen
       Steam - the folder ABOVE game\\, typically
               C:\\Program Files (x86)\\Steam\\steamapps\\common\\Drakkhen
               (the installer locates game\\ by itself and says so)
  2. Right-click install.ps1 -> Run with PowerShell
     (or from a terminal:  powershell -ExecutionPolicy Bypass -File install.ps1)

The installer verifies your files are the stock US GOG version before touching
anything, backs them up to _backup\\original\\, rebuilds the patched files from
YOUR OWN game data, and verifies the result byte-for-byte. If any check fails
it stops without changing your game.

Uninstall:
  powershell -ExecutionPolicy Bypass -File install.ps1 -Restore

Save files are never touched by install or restore.

Optional: use a modern DOSBox
-----------------------------
GOG and Steam both ship DOSBox 0.74 (2010). DOSBox Staging is a maintained fork
with sharper output, CRT/HD shaders, far better AdLib music emulation, and
modern fullscreen handling. This patch does NOT include it - download the
portable zip yourself from https://dosbox-staging.github.io/ , then run:

  python staging_setup.py <your game folder> <your unpacked Staging folder>

That points your existing GOG/Steam Play button at Staging (originals backed up;
undo with  staging_setup.py <game folder> --restore ).
''')
    print('wrote %s (install.ps1 %d bytes)' % (OUT, os.path.getsize(os.path.join(OUT, 'install.ps1'))))

if __name__ == '__main__':
    main()
