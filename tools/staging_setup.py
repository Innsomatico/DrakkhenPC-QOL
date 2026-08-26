"""Point the GOG / Steam Play button at DOSBox Staging (or put the original emulator back).

Ships NO binaries: the user supplies a portable DOSBox Staging folder (the official zip, unpacked
anywhere). Because that layout is self-contained - exe, DLLs, glshaders, no registry - installing
it is just copying files into the directory the store launcher already runs, and uninstalling is
restoring the files we moved aside. Nothing system-wide is touched.

How each store launches (verified from the shipped metadata, 2026-08-25):
  GOG   goggame-*.info playTask: path 'DOSBOX\\dosbox.exe', workingDir 'DOSBOX',
        args -conf "..\\dosbox_drakkhen.conf" -conf "..\\dosbox_drakkhen_single.conf"
             -noconsole -c "exit"        <- Staging accepts every one of those flags
  STEAM runs 'dosbox.exe' in the game root with no -conf; Staging then auto-loads the local
        dosbox.conf from the working directory (that is what -nolocalconf exists to disable).

So in both cases replacing dosbox.exe + rewriting the config it reads is enough; the store's
Play button needs no changes at all.

Caveats the caller must surface to the user:
  * "Verify integrity of game files" (Steam) or GOG Galaxy's repair will restore the ORIGINAL
    emulator. Harmless - just re-run this - but it looks like the patch broke.
  * Staging is GPL software owned by its authors; this only copies what the user downloaded.
"""
import os, shutil, sys

MARKER = 'staging-installed.txt'      # records what we replaced, so restore is exact


def detect(game):
    """Return (kind, exedir, gamedir) for the store layout, or (None, ...)."""
    if os.path.exists(os.path.join(game, 'DOSBOX', 'dosbox.exe')):
        return 'gog', os.path.join(game, 'DOSBOX'), game
    if os.path.exists(os.path.join(game, 'game', 'DRAKM.CC1')) and \
       os.path.exists(os.path.join(game, 'dosbox.exe')):
        return 'steam', game, os.path.join(game, 'game')
    return None, None, None


GOG_MAIN = """# Drakkhen - DOSBox Staging (installed by the Drakkhen QOL patcher)
# The GOG launcher passes this file plus dosbox_drakkhen_single.conf; both are Staging-native now.
[sdl]
fullscreen      = false
fullresolution  = desktop
display         = 0
output          = opengl
integer_scaling = vertical
vsync           = true

[dosbox]
machine = svga_s3
memsize = 16

[cpu]
core   = auto
cycles = auto

[render]
aspect   = true
# Picture style - change this line and relaunch. Run `dosbox --list-glshaders` for the full list.
#   interpolation/sharp   faithful crisp pixels (default)
#   crt/vga-1080p         CRT scanlines; use -1440p or -4k to match your monitor
#   scaler/xbr-lv3        "HD" smoothing of the pixel art
glshader = interpolation/sharp

[mixer]
rate = 48000

[sblaster]
sbtype  = sb16
sbbase  = 220
irq     = 7
dma     = 1
hdma    = 5
oplmode = auto
# Cycle-accurate OPL: the original FM score, rendered far better than DOSBox 0.74 managed.
oplemu  = nuked

[midi]
mididevice = auto

[dos]
xms = true
ems = true
umb = true
"""

# workingDir is DOSBOX\, so ".." is the game folder
GOG_SINGLE = """# Drakkhen - autoexec (Staging). Working directory is DOSBOX\\, so ".." is the game folder.
[autoexec]
@echo off
mount c ".."
c:
cls
drakkhen.com
exit
"""

STEAM_CONF = GOG_MAIN.replace(
    '# The GOG launcher passes this file plus dosbox_drakkhen_single.conf; both are Staging-native now.',
    '# Steam runs dosbox.exe with no -conf; Staging auto-loads this local dosbox.conf.'
) + """
[autoexec]
@echo off
mount c "game"
c:
cls
drakkhen.com
exit
"""


def install(game, staging):
    kind, exedir, gamedir = detect(game)
    if not kind:
        print('ERROR: not a recognised Drakkhen layout: %s' % game); return 1
    src = staging
    if not os.path.exists(os.path.join(src, 'dosbox.exe')):
        # allow pointing at the zip's parent folder
        subs = [d for d in os.listdir(src) if d.lower().startswith('dosbox-staging')]
        if subs and os.path.exists(os.path.join(src, subs[0], 'dosbox.exe')):
            src = os.path.join(src, subs[0])
        else:
            print('ERROR: dosbox.exe not found in %s' % staging); return 1
    bak = os.path.join(gamedir, '_backup', 'dosbox-original')
    if os.path.exists(os.path.join(exedir, MARKER)):
        print('Staging already installed here. Restore first if you want to re-install.'); return 0

    os.makedirs(bak, exist_ok=True)
    confs = (['dosbox_drakkhen.conf', 'dosbox_drakkhen_single.conf'] if kind == 'gog'
             else ['dosbox.conf'])
    saved = []
    for f in ['dosbox.exe'] + ([] if kind == 'gog' else []):
        p = os.path.join(exedir, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bak, f)); saved.append(f)
    for f in confs:
        p = os.path.join(game, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bak, f)); saved.append(f)
    print('backed up %s -> %s' % (', '.join(saved), bak))

    copied = []
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(exedir, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
        copied.append(name)
    print('installed Staging (%d entries) into %s' % (len(copied), exedir))

    if kind == 'gog':
        open(os.path.join(game, 'dosbox_drakkhen.conf'), 'w', newline='\r\n').write(GOG_MAIN)
        open(os.path.join(game, 'dosbox_drakkhen_single.conf'), 'w', newline='\r\n').write(GOG_SINGLE)
    else:
        open(os.path.join(game, 'dosbox.conf'), 'w', newline='\r\n').write(STEAM_CONF)
    open(os.path.join(exedir, MARKER), 'w').write('\n'.join(copied))
    print('wrote Staging configs for the %s layout' % kind.upper())
    print()
    print('Done - your %s Play button now launches DOSBox Staging.' % kind.upper())
    print('NOTE: verifying/repairing game files in the store will restore the original emulator;')
    print('      just run this again if that happens.')
    return 0


def restore(game):
    kind, exedir, gamedir = detect(game)
    if not kind:
        print('ERROR: not a recognised Drakkhen layout: %s' % game); return 1
    marker = os.path.join(exedir, MARKER)
    bak = os.path.join(gamedir, '_backup', 'dosbox-original')
    if not os.path.exists(marker):
        print('Staging was not installed by us here - nothing to undo.'); return 0
    for name in open(marker).read().split('\n'):
        if not name:
            continue
        p = os.path.join(exedir, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            os.remove(p)
    for f in os.listdir(bak):
        dst = os.path.join(exedir if f == 'dosbox.exe' else game, f)
        shutil.copy2(os.path.join(bak, f), dst)
    os.remove(marker)
    print('original DOSBox and configs restored.')
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print('usage: staging_setup.py <gamefolder> <staging-folder>')
        print('       staging_setup.py <gamefolder> --restore')
        return 1
    game = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == '--restore':
        return restore(game)
    if len(sys.argv) < 3:
        print('need the path to your unpacked DOSBox Staging folder'); return 1
    return install(game, sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
