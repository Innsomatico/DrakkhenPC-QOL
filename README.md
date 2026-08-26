# DrakkhenPC-QOL

Quality-of-life patch for **Drakkhen** on PC (Infogrames, 1990) — the MS-DOS version sold on GOG
(US release, VGA), as played under DOSBox. A set of small binary mods that make the game
dramatically more playable without changing its character.

## Features

| Mod | What it does |
|---|---|
| **Compass** | A needle in the top-right of the 3D view that tracks your heading. Navigation as it always should have been. |
| **World map on `M`** | Press M in the world view: a full-viewport map of the island with your position flashing. Any key closes it. |
| **Readable spells** | The runic spell/phial font replaced with Latin letters — spell names are plain English (they always were underneath; one rune = one letter). |
| **Party-shared XP** | Kill XP is split: every living party member gets 1/4 of each award instead of 100% to the killer (Final Fantasy style). |
| **Item identification** | Rings, staffs and phials show *which* one they are — the contained spell's name is drawn next to the type name. |
| **Bow buff** | The bow ships as the weakest weapon in the game (power 6, tied with the bludgeon). Now power 8 — on par with the short sword, worth carrying without breaking the curve — and renamed from "arch". |
| **Working rings & sceptres** | Stock Drakkhen shipped seven passive effects (Invisibility, Protection, Recuperation, Acceleration, Power, Understanding, Impalpability) that no item ever granted — worn rings did nothing. Now a worn ring/sceptre grants its spell's effect; Recuperation doubles regen. |
| **Quest hints on `H`** | An opt-in hint list for the main quest: SPACE reveals the next step, so spoilers are your choice. |
| **Class stat growth** | The stock game grants NO stat growth on level-up, ever. Now each class gains stats per level along class-appropriate lines (capped safely at 99). |
| **No copy-protection prompt** | The "DRAKKHEN CODES" wheel-code interruption never fires. |
| **Straight to VGA** | The video-card selection menu at launch is skipped. |

## Install

Two installers, **identical behavior** — pick whichever you trust more. Both let you **choose
which mods to install**: PowerShell shows a checkbox dialog (with Check-all); Python shows a
numbered checklist. Or skip the question entirely with `-All` / `--all`, or pick on the command
line with `-Mods compass,map,bow` / `--mods compass,map,bow` (`--list` shows the keys).
Dependencies are handled for you (e.g. the world map needs the compass hook).

**PowerShell** (no dependencies on any Windows machine):

1. Copy `install.ps1` into your Drakkhen game folder — the one containing `DRAKKHEN.COM` and
   `DRAKM.CC1` (for GOG typically `C:\Program Files\GOG Galaxy\Games\Drakkhen`).
2. Run it:

   ```
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

**Python** (any Python 3, standard library only, nothing to pip install):

```
python install.py "C:\Program Files\GOG Galaxy\Games\Drakkhen"
```

Uninstall with `install.ps1 -Restore` or `python install.py --restore` respectively.

The installer **verifies your files are the stock US GOG version by SHA256 before touching
anything**, backs them up to `_backup\original\`, rebuilds the patched files from *your own* game
data, and verifies the result byte-for-byte against the reference build. If any check fails, it
stops without changing your game. Save files are never touched.

## Is this safe to run?

A healthy question for any script off the internet. What you can check yourself:

- **Both installers are plain text.** Open them in any editor — every line is auditable. There is
  no obfuscation, no downloading, no network access of any kind, and nothing touched outside the
  game folder you point them at.
- **They refuse to run on anything but the exact stock files.** Your game files are SHA256-verified
  before a single byte changes, and the rebuilt files are verified against the reference build
  after. Any mismatch aborts with nothing modified.
- **Your originals are backed up first** (`_backup\original\`) and one command restores them.
- **Checksums of both installers are published** in [`SHA256SUMS.txt`](SHA256SUMS.txt). Verify your
  download with `certutil -hashfile install.ps1 SHA256` (Windows) or `sha256sum` before running.
- Both installers are **generated from the sources in [`tools/`](tools/)** — you can rebuild them
  yourself and diff the result.

A signed `.exe` installer would actually be *less* inspectable than these scripts; transparency is
the trust model here.

## No game files here

This repository contains **no Drakkhen game data**. The installer ships only the patch itself: a
few KB of binary diff (the mod code), a replacement 5×5 font drawn for this project, and a world-map
image created for this project. Your own legally-owned game files are the input — the patch is
useless without them. Compatibility is deliberately strict: only the US GOG release is supported,
enforced by checksum.

## How it works

The mods live in 758 bytes of verified-dead space inside the game's engine (orphaned filename
tables that the code can never reach), spliced into the engine's own routines via the MZ relocation
table. Everything is generated by a small Python framework from pristine originals — see
[docs/MODDING.md](docs/MODDING.md) for the framework and the hard-won constraints, and
[docs/NOTES.md](docs/NOTES.md) for the reverse-engineering reference (file formats, engine
addresses, the item catalog, spell records, save format).

[docs/ROADMAP.md](docs/ROADMAP.md) records what was built, what was dropped and why (including a
full post-mortem of the MP-regen attempt), and what a future contributor would need to pick any of
it back up.

## Building from source

Requires Python 3 with `keystone-engine` (and `capstone` for the analysis tools), plus a Drakkhen
US GOG install providing the pristine originals in `_backup/original/`:

```
python tools/drakmod.py        # build the modded DRAKM.CC1 + RESI_VGA.6C0
python tools/make_patcher.py   # regenerate install.ps1 from the current build
```

## Who this is for

If you ever bounced off Drakkhen on PC, it was probably one of these — each is what this patch fixes:

- **"How do I know where I am?"** — the DOS version shipped with no in-game map and no compass.
  You navigated a featureless 3D plain by memory. This patch adds both: a world map on the `M` key
  showing your position, and an always-on compass in the 3D view.
- **"Why are the spell names unreadable symbols?"** — spells and phials are labeled in a runic
  display font. Underneath, the names were always English (one rune per letter); this patch swaps
  the font so HEALMIN, TELEPOR and friends read as themselves.
- **"Which ring / staff / phial is this?"** — inventory just says "ring". The patch shows the
  contained spell's name next to the item type.
- **"Only the killer gets XP?"** — kill experience now splits evenly among living party members.
- **"The bow is useless"** — it shipped as the weakest weapon in the game; now it's worth carrying.

The **US GOG and Steam releases** are both supported — the installer verifies your files by checksum and
refuses anything else (floppy versions, other regions, and the SNES/Amiga ports are different
builds entirely).

## Optional: run it on a modern DOSBox

GOG and Steam both ship **DOSBox 0.74 (2010)**. [DOSBox Staging](https://dosbox-staging.github.io/)
is a maintained fork with sharper output, CRT and "HD" shaders, much better AdLib music emulation,
and modern fullscreen handling (a borderless window rather than a display-mode switch).

**This project ships no emulator.** Download Staging's portable zip yourself, unpack it anywhere,
then:

```
python tools/staging_setup.py "<your Drakkhen folder>" "<your unpacked Staging folder>"
```

It backs up the original emulator, installs Staging where your store's launcher already looks, and
writes a matching config — so the **GOG Galaxy / Steam Play button** launches Staging with no
change to how you start the game. Both store layouts are handled automatically.

Undo: `python tools/staging_setup.py "<your Drakkhen folder>" --restore` (restores the original
emulator byte-for-byte and removes every Staging file).

Note: verifying/repairing game files in Steam or GOG Galaxy restores their bundled DOSBox — just
run the setup again if that happens.

Shaders are a one-line change in the generated config (`glshader = crt/vga-1080p`,
`scaler/xbr-lv3`, `interpolation/sharp`, …); the file lists what's available.

## Credits

Reverse engineering, mods and tooling: Innsomatico, with Claude (Anthropic).
Drakkhen is © Infogrames 1990. This project is an unaffiliated fan patch; no game assets are
distributed.
