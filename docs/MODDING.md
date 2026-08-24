# Drakkhen (GOG / DOS, VGA) — modding notes



Status: **compass, world map, and readable spell font all complete and verified working.**
Compass: needle + north tick, top-right of the viewport, solid, tracks heading, world view only.
Map: `M` opens a full viewport map with a flashing party marker; any key closes it.
Spell font: runes replaced with Latin letters (data patch, costs no engine space).



## Layout



| File | Purpose |

|---|---|

| `drakpack.py` | BPE codec for the `.?C1` containers (unpack / repack) |

| `drakmod.py` | Mod framework: dead-space allocator, splice + relocation helpers, safety invariants |

| `mod_compass.py` | The compass mod |
| `mod_map.py` | The world map mod (`M`) |
| `mapgrid.py` | Turns `map_src.png` into the 32x32 grid, then renders `../MAP.DRK` |
| `mod_spellfont.py` | Rune -> Latin spell/phial font (patches `RESI_VGA.6C0`, a data file) |
| `mod_regen.py` | 1.5x MP regen for casters while standing still (world view) |
| `mod_partyxp.py` | Kill XP shared: 1/4 to each living member |
| `mod_itemname.py` | Ring/staff/phial variant shown as spell-name suffix |
| `mod_bow.py` | Bow catalog record: power 6->12, price 8->16 |
| `make_patcher.py` + `patcher_template.ps1` | Generate `../DrakkhenQOL/install.ps1` distributable |
| `restore.ps1` | `good` / `stock` one-command restore |
| `ROADMAP.md` | Feature backlog with effort/confidence estimates |

| `drakdis.py` | Recursive-descent 16-bit disassembler used for analysis |

| `NOTES.md` | Reverse-engineering reference (file formats, engine addresses) |

| `_backup/original/` | Pristine copies of every original game file |



Build: `python drakmod.py` → writes `../DRAKM.CC1` (engine mods) and `../RESI_VGA.6C0` (spell font).
Distributable: `python make_patcher.py` → regenerates `../DrakkhenQOL/install.ps1` from the current
build (run it after every mod change so the patcher stays in sync).

Restore: `powershell -ExecutionPolicy Bypass -File restore.ps1 good` (last build confirmed working in
game) or `... restore.ps1 stock` (pristine). Saves are never touched by either. The
`-ExecutionPolicy Bypass` is needed because scripts are disabled by policy on this machine.

| Folder | Contents |
|---|---|
| `_backup/original/` | pristine stock files |
| `_backup/good/` | last known-good modded build + `MANIFEST.txt` of SHA256s |
| `_backup/saves/` | copy of `PERSO/OBJET/ACTIV.SAV` — the game rewrites `PERSO.SAV` on exit |

**Snapshot `_backup/good/` whenever the user confirms a build works**, before starting the next mod.



## Adding a mod



```python

# mod_example.py

def apply(b):

    import drakmod

    code = drakmod.assemble(source, off)     # 16-bit asm

    seg, off, lin = b.alloc(len(code))       # reserve verified-dead space

    b.put(lin, code)

    b.splice_call(seg_to_patch, off_to_patch, seg, off, expect=original_bytes)

    b.add_reloc(seg, off + 1)                # any segment word inside your code

```

Then add it to the list in `drakmod.py`'s `build([...])`.



The framework asserts the invariants below, so a mistake fails at build time instead of producing a

game that crashes in a way that takes a day to diagnose.



## Hard-won constraints — read before writing a mod



These each cost a long debugging cycle. They are enforced in code, but understanding them matters.



**1. The unpacked image size must never change.**

DOS gives the program 640 KB and the VGA build already needs ~563 KB. Growing the image shrinks the

graphics heap; a texture load then fails and the game's fallback is to assume the wrong floppy is

inserted — you get **"Please insert DRAKKHEN Disk 3"**. The container may grow (it's stored

uncompressed), but the *unpacked* image and MZ header must be identical.



**2. Never place code in BSS (`DS:4960..70E2`).**

The C startup zero-fills exactly that range at launch (`0000:00C4`), so anything there is wiped

before it runs. This also rules out appending code after the image.



**3. Zero-filled runs inside code segments are NOT free.**

They are `cs:`-relative variable storage for hand-written assembly modules. Segment `1AC6`, for

example, reads and writes `cs:[0x1a]` — the exact spot that looked like an empty 513-byte cave.

Overwriting one gives **"Divide error"**. A region is only safe if nothing references it; live

memory sampling alone is not proof, because a read-only table of zeros looks identical to free space.



**4a. The orphan filename tables carry STALE RELOCATIONS.**

The dead-space TABLE region (DS:1958..1A30) is far pointers, so the loader's relocation table has an
entry every 4 bytes pointing into it. Code placed there gets silently corrupted at load time as the
loader "relocates" words inside the instructions. `alloc()` now drops every stale relocation inside a
region it hands out and `save()` rebuilds the relocation table from scratch. (The string region has
no relocations, which is why the first three mods never hit this.)

**4. A splice site that was already a far call already has a relocation.**

Adding a second one relocates the segment word twice and sends the call into garbage. `splice_call()`

detects this and does the right thing automatically.



**5. Splicing over `mov ax,DGROUP / mov ds,ax` requires *repointing* its relocation.**

That immediate is relocated; if left alone it corrupts the new call's offset word. Handled by

`splice_call()`.



**6. keystone emits 32-bit forms in 16-bit mode.**

`ret`→`66 C3`, `retf`→`66 CB`, `call`→`66 E8 rel32`. These corrupt the stack. Use no `call`/`ret`

inside a hook and emit the far return as a raw `.byte 0xcb`. `drakmod.assemble()` rejects any

instruction carrying a `66`/`67` prefix.



## Compressed files that don't look compressed

`.?C0` files (e.g. `RESI_VGA.6C0`) are a **bare BPE chunk**: `[u32be packed][u32be unpacked][blocks]`,
no container header. They are compressed even though bitmaps and strings are plainly readable in the
raw bytes — those are literals in a block whose pair table happens not to code them.

**Patching such a file in place silently destroys it.** Some of the new byte values *are* pair codes,
each expands to two bytes, and every byte after that point shifts. The file keeps its exact length and
the diff looks small and clean, so nothing warns you; the game boots normally and then dies when it
loads that file. Cost a full debugging round on the spell font.

Always: `bpe_decode` → patch the decoded buffer → `bpe_encode_raw` → rewrite the 8-byte header. Assert
the **decoded** length is unchanged (that is the load footprint); the file on disk may grow.

## Keeping mods small



Space is the binding constraint, so it is worth compressing before adding code. What worked for the

compass (256 B -> 180 B, no visual change):



* **Exploit symmetry in shape data.** The ring was a 90-byte list of (x,y) points; because it is

  symmetric left-right it became a 17-byte table of one half-width per row, plotting `CX+/-w`. That

  alone saved 76 bytes - shape tables dominate small mods, not instructions.

* Quarter-symmetry (mirroring vertically too) would cut it to 9 bytes if ever needed.

* `pusha`/`popa` would save a further 12 bytes over seven `push`/`pop` pairs, but they are 286+

  instructions. Fine under DOSBox, wrong for real 8086 hardware - not used.

* Bitmaps beat coordinate lists once a shape has more than ~40 pixels.
* **Drop decoration that carries no information.** The compass ring cost 53 bytes (a 17-byte table
  plus its loop); a bare needle and north tick read just as clearly. 170 B -> 117 B.
* `pusha`/`popa` replace long push/pop runs (~10 bytes saved per hook). They are 286+ instructions -
  fine under DOSBox, wrong for real 8086 hardware.
* **Choose power-of-two sizes for tile grids.** With 8x4 tiles, tile-to-pixel is `shr`+`and`
  instead of `mul`, and the map still fits the viewport exactly.



## Where mod code lives



The engine ships four filename tables for different build configurations, but the selector at
`03AD:1918/1924` only ever installs table 3 (`0x1A30`) or table 4 (`0x1A9C`). Tables 1-2 and the
string sets only they point at are unreachable, and being *initialised* data they survive the BSS wipe.



| Region | Size | Status |

|---|---|---|

| `DS:2050..226E` orphan filename strings, sets 1-2 | 542 B | in use |
| `DS:1958..1A30` orphan filename tables 1-2 | 216 B | in use |

**758 B total, 347 B used (compass 117 + map 230), 400 B free.** This is the main constraint on
future *code* mods; data-only mods like the spell font cost none of it.

These tables are safe to reuse: `[0x60D8]` (the active filename table pointer) is written in exactly
two places, both at `03AD:1918/1924` during startup, and read-only everywhere else - so the choice is
never revisited mid-game. Sets 1-2 are byte-identical duplicates of the sets tables 3-4 point at, so
no unique data is lost. They are **not** unloaded disk configurations.



### If more space is needed

1. **External data files** — the route the map took (`MAP.DRK`) and the spell font takes
   (`RESI_VGA.6C0`). Bulk data should never live in code space. Read straight to its destination with
   `INT 21h`; the engine's own loader allocates from a heap with <5 KB headroom.
2. **Overwrite unused engine features**, proven dead the same way the filename tables were.
3. ~~Reclaim the copy-protection code~~ — **dead end**. Its strings (`DS:07A9` "Wrong code, sorry!",
   `DS:07C0` "Bad CheckSum") sit in a handler nothing reaches; the GOG build already bypasses the check,
   so there is nothing live to reclaim.

## Drawing overlays and full-screen modes — read this first

* **The viewport repaints every frame; the side and bottom panels do not.** The panels are only
  redrawn when their contents change (e.g. deploying the party). Anything drawn over them persists
  indefinitely, and no combination of the engine's own redraw routines reliably restores them.
  **Draw inside the viewport only** — `(64,3)` to `(319,130)`, 256x128 — which is also exactly what
  the game's own character sheet does. The map is sized to fit it precisely, so closing the map
  needs no restore at all.
* **Do not draw overlays into the frame buffer** (`DS:[3DF6]`). The engine keeps presenting that
  frame, so the overlay comes back every time and only the regions it actively redraws recover.
  Write to video memory (`A000`) instead and leave the frame holding the real scene.
* **A modal screen can simply block.** Main-loop hooks may spin waiting for a key; the timer
  interrupt keeps running, so music and timing are unaffected.

## Choosing a hook site

| Site | Runs |
|---|---|
| `19F7:09A9` (tail of the scene routine) | **every frame**, both modes — the main loop calls the scene routine at `0055:0E84`. Best general-purpose hook. |
| `070E:1F77` (input/click dispatcher) | only while the characters are deployed |
| `1B27:02B6` (engine "callback") | **an INT 8 handler** — installed at `1BC6:004F`. Never call DOS or block here. |

Only one mod can splice a given site, so mods **chain**: `mod_compass` publishes its entry as
`b.compass_entry`, and `mod_map` takes over the splice and far-calls the compass first.

## The keyboard is remapped

Scancodes pass through an AZERTY layout table at `DS:3D07` whenever `DS:3E06` is set — and it is
(`0x2000`). Physical **M arrives as `0x27`**, not `0x32`. Read the key from `DS:3DCE` (0 when no key
is down) and accept both values. This cost several rounds of "the hook runs but the key never
matches"; check the table before assuming a scancode.

## Rendering — how the world view is drawn



Established by instrumenting the running game; this is what the compass mod depends on.



* `19F7:08F8` draws the 3D scene **and presents it** at its own end:

  ```

  19F7:09A9   mov ax,DGROUP / mov ds,ax     <- compass spliced here

  19F7:09AE   cmp [bp+6], 0

  19F7:09B4   lcall 1998:000E               <- presents the frame

  ```

  Anything drawn *after* `08F8` returns is too late — the frame is already on screen. That is why

  hooking its callers produced either an invisible compass (drawn into a buffer never shown again)

  or a flickering one (drawn onto an already-displayed frame, wiped by the next).

* Draw target is `DS:[3DF6]`, a full **320×200** buffer — plain screen coordinates, stride 320.

  (Row-coherence measurement: mean row-to-row difference 5.3 at stride 320 vs 44.0 at 256.)

* `19F7:0046` is **not** the renderer — it computes a view code and only triggers a redraw when it

  changes. `19F7:0180` handles movement, `19F7:01A0` handles turning; both then call `19F7:0046`.

* The world view only redraws when the party moves or turns — a frozen frame counter while standing

  still is correct, not a bug.



## Useful engine addresses (DGROUP = seg `0x1FD4`)



| Address | Meaning |

|---|---|

| `DS:02E3` | heading byte, 0–255 = full circle |

| `DS:02EC` / `DS:02EE` | `16384·cos θ` / `−16384·sin θ` (kept updated by the engine) |

| `DS:02F0` / `DS:02F2` | party X / Y (int16). Tile = 512 units; tile index = (Y/512)·32 + X/512 |

| `DS:0300` | 0 in world view, 2 in inventory/character screen |

| `DS:3DF6` | far pointer to the frame being drawn |

| `DS:3DFA` | far pointer to the visible page (`A000:0000`) |

| `DS:3DD0` | direction bits from the keyboard ISR: 1 up, 2 down, 4 left, 8 right, 0x80 button |

| `DS:3DD4` / `DS:3DD6` | emulated pointer X / Y (arrow keys drive this, not the party directly) |

| `DS:3DCE` | last raw scancode; key table at `DS:3D87` |



Palette indices (`GAME.7AL`): 16 white, 38 red, 220 yellow, 0 black, 21 grey.



## Verification workflow



Test on a *separate* DOSBox instance, never the player's:



```bash

python drakmod.py                                   # build

powershell -File launch.ps1                         # windowed instance (dev.conf)

powershell -File dbx.ps1 "{F2}"                     # send keys, capture screen

```

`dbx.ps1` writes a screenshot to `shot.png` (or `$env:DBX_OUT`), which can be checked

programmatically — count pixels of the mod's colours in the expected region across several frames to

prove it is solid rather than flickering.

