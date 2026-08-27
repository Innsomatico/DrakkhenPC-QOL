# DrakkhenPC-QOL

[![Latest release](https://img.shields.io/github/v/release/Innsomatico/DrakkhenPC-QOL?label=latest%20release&color=2ea44f)](https://github.com/Innsomatico/DrakkhenPC-QOL/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Innsomatico/DrakkhenPC-QOL/total?color=blue)](https://github.com/Innsomatico/DrakkhenPC-QOL/releases)
[![Wiki](https://img.shields.io/badge/docs-wiki-informational)](https://github.com/Innsomatico/DrakkhenPC-QOL/wiki)

Quality-of-life patch for **Drakkhen** on PC (Infogrames, 1990) — the MS-DOS version sold on GOG
(US release, VGA), as played under DOSBox. A set of small binary mods that make the game
dramatically more playable without changing its character.

## ⬇ Download

**[Get the latest release zip here](https://github.com/Innsomatico/DrakkhenPC-QOL/releases/latest)** —
unzip it, copy the installer into your Drakkhen game folder, run it, pick your mods.
Full steps below in [Install](#install); uninstall any time with `-Restore`.

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
| **Gear equipped at creation** | Stock Drakkhen sends a new party into the world *naked*, with their starting equipment sitting unworn in the inventory — you equip a dozen-plus items by hand before anyone can fight. Now it is all worn from the first step, weapons in hand. |
| **Scout starts with a bow** | The scout begins with a bow instead of a dagger — a ranged opener that actually suits the class. |
| **Magician starts with a RESTORE ring** | The magician begins wearing a RESTORE ring: doubled regeneration from the very first step. (Uses the ring/sceptre mod above.) |
| **Free temple healing** | Anak temples charged level³×5 jade to heal (a miserly +5 HP per visit) and level³×20 to revive — refusing outright if nobody could pay, so a party wiped early could *never* revive anyone. Now free, no gate, and one visit heals to full; the dead come back at full HP. |
| **Class stat growth** | The stock game grants NO stat growth on level-up, ever. Now each class gains stats per level along class-appropriate lines (capped safely at 99). |
| **Free tavern rumors** | Taverns sell information on an *escalating* price ladder — 50, 100, 200, up to 4000 jade per hint, with the tier saved per party. A few early purchases and the keeper's "Come back later. A little richer, if possible!" becomes permanent. Now every rumor is free. |
| **A merchant in the starting zone** | The stock game ships a complete, working item shop — selling, buy-back, even loyalty discounts — placed in exactly **one** building on the whole island, and not in the starting zone. Now the lone inn in the Earth zone is also a merchant (the silent shopkeeper is authentic — Infogrames gave him no lines). Other zones are left untouched so no quest NPC gets overwritten. |
| **Unused-file cleanup** | Optionally moves the 47 CGA/EGA/Tandy files (1.6 MB) that become unreachable once the card is pinned to VGA into the backup folder. Restore brings every one back. |
| **No copy-protection prompt** | The "DRAKKHEN CODES" wheel-code interruption never fires. |
| **Straight to VGA** | The video-card selection menu at launch is skipped. |
| **Launcher menu in color** | The grey launcher screen becomes a deep blue field with gold text and borders — the palette the stock hardware could always do but the menu never used. |
| **Clean 4-item main menu** | "Select video card" is removed from the launcher menu entirely (renumbered: Creation / Game / Joystick / Return to DOS). With the card pinned to VGA it was a trap: choosing another card silently loads an unpatched binary and every mod vanishes. |

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

The installer **verifies your files are a stock US GOG or Steam release by SHA256 before touching
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
useless without them. Compatibility is deliberately strict: only the US GOG and Steam releases are
supported, enforced by checksum.

## How it works

`DRAKM.CC1` turns out to hold **two** MS-DOS executables: the game engine, and a separate
**character creator**. The mods live in verified-dead space inside them — orphaned filename tables
and the carcass of the copy-protection routine in the engine (1,214 bytes between them), and in the
creator, 37 of the 47 records in its private copy of the item catalog, which nothing can reach
because that binary contains no computed indexing into the table at all. Engine hooks are spliced
into the game's own routines via the MZ relocation table; the starting-gear changes are single
immediate operands in the creator's grant code. Nothing is ever appended — the image size cannot
change without starving the graphics loader.

Everything is generated by a small Python framework from pristine originals — see
[docs/MODDING.md](docs/MODDING.md) for the framework and the hard-won constraints, and
[docs/NOTES.md](docs/NOTES.md) for the reverse-engineering reference (file formats, engine
addresses, the item catalog, spell records, save format).

[docs/ROADMAP.md](docs/ROADMAP.md) records what was built, what was dropped and why (including a
full post-mortem of the MP-regen attempt), and what a future contributor would need to pick any of
it back up.

## Building from source

Requires Python 3 with `keystone-engine` (and `capstone` for the analysis tools, `unicorn` for the
verifier), plus a Drakkhen US GOG or Steam install providing the pristine originals in
`_backup/original/`:

```
python tools/drakmod.py               # build the modded DRAKM.CC1 + RESI_VGA.6C0
python tools/fragsim.py               # verify every mod subset rebuilds correctly
python tools/verify_startgear.py      # emulate the character creator, dump the starting gear
python tools/verify_startgear.py --matrix   # ...for every combination of the start* mods
python tools/make_patcher.py          # regenerate install.ps1 / install.py from the build
```

`verify_startgear.py` is worth a mention: rather than trusting a reading of the disassembly, it
loads the character creator, applies its relocations and **actually executes** each class's
gear-granting routine under [Unicorn](https://www.unicorn-engine.org/), then decodes the resulting
character record. Against the unmodified creator it reproduces a real freshly-created `PERSO.SAV`
byte-for-byte.

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
- **"The bow is useless"** — it shipped as the weakest weapon in the game; now it's worth carrying,
  and the scout starts with one.
- **"Why is my new party unarmed?"** — the creator hands out starting gear but never equips any of
  it, so a fresh party walks into a hostile world naked with a sword in its pocket. Now it is worn
  from the first step.
- **"Are there even merchants in this game?"** — there is exactly one shop on the island, hidden in
  an unmarked building outside the starting zone, and the taverns demand escalating jade for hints
  until they price you out forever. Now the Earth-zone inn is a merchant too, and rumors are free.
- **"I died once and the game is over"** — temple revival costs more than a fresh party owns, so an
  early death was permanent. Temples are free now.

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
