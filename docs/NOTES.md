# Drakkhen PC (GOG) — reverse-engineering notes

## Files
- `DRAKKHEN.COM` loader: menu, reads CONFIG.TAT, BPE-decompresses driver + engine, jumps. Decoder @0x0a8d.
- Engine per video mode: CGA=DRAKC, EGA=DRAKE, **VGA=DRAKM.CC1** (+ DRDRIVER.6C1 sound driver). GOG default = VGA.
- `.?C1` container: u16be nchunks, nchunks*u32be offsets, chunks = [u32be packed][u32be unpacked][BPE blocks].
  BPE block: u8 npairs, u8 more, u16le len, tables code/left/right, data. npairs=0 → raw copy (used by our repacker).
- **`.?C0` files are a BARE BPE chunk** — no container header, just [u32be packed][u32be unpacked][BPE blocks].
  They are compressed even though they don't look it: readable ASCII/bitmaps appear in the raw file because
  those bytes are literals in a block whose pair table doesn't code them. **Never patch a `.C0` in place** —
  see MODDING.md "Compressed files that don't look compressed".
- `_tools/drakpack.py` unpack/repack; `_tools/drakdis.py` recursive disassembler; `_tools/memscan.py` + `record.py` live DOSBox memory.
- `_tools/launch.ps1` (windowed dev DOSBox via dev.conf), `_tools/dbx.ps1` (send keys + screenshot).
- Backups of all originals: `_backup/original/`.

## Engine (DRAKM.CC1 chunk 1 = `_tools/DRAKM_CC1/01.bin`, Turbo C 2.0 large model)
- DGROUP = seg 0x1FD4 (file image linear 0x1FD40). Live (DOSBox): load seg 0x04A4 → DS linear 0x24780.
- Keyboard ISR seg 1B24 (installed by 1B27:0124). Key table DS:3D87 (scancode, flags). Arrows → dir bits DS:3DD0 (1 U,2 D,4 L,8 R), Space=0x80.
  Buttons DS:3DD2/3DD8. Last scancode DS:3DCE. Timer poll 1B27:02B6 turns dir bits into pointer motion.
- Pointer X/Y = DS:3DD4 / DS:3DD6 (0..310, 0..190). Keyboard = pointer emulation; party turns when pointer at L/R edge, walks when at top edge (back when at bottom).
- Main-screen zone table DS:1DEC (9 zones, x0,y0,x1,y1), click dispatcher 070E:1F77 (jump table 070E:1FD9). Zone 1 = 3D view (64,3)-(319,130).
- Inventory/char screen = seg 1743 (enter: 0A4A:00B2 save, exit: 0A4A:0091 restore) — template for a full-screen map mode.

## Party world state (also saved, see below)
- DS:02E3 heading byte 0..255 (full circle). Angle θ = (hdg-64)*360/256 deg.
- DS:02EC = 16384*cos θ, DS:02EE = -16384*sin θ.
- DS:02F0 = X (int16), DS:02F2 = Y (int16). Forward walking vector = (-cos θ, -sin θ).
- Tile = 512 units. tile index = (Y/512)*32 + X/512. Island X 0x800..0x3800 → 25 tiles; DATAEXT.6IN = 25x25x2 bytes (encoded).
- New game start: X=6441 Y=9971 hdg=60.
- Clocks: DS:02FC (~0.6s tick), DS:02FA.

## Character record (0x19A bytes, 4 records at DS:5A2E; also in PERSO.SAV at +4)
- +0 name (ASCII), **+0x14 dword = experience** (awarded at img 0xCFD2/0xD075: kill XP =
  damage * victim_XP_pool / victim_maxHP; monsters share the layout family - victim +0x18 dword =
  remaining XP pool, +0x51 = HP), +0x24/+0x25 sprite screen x/y (deployed), +0x36 HP-regen countdown,
  +0x42..+0x47 six stat bytes, **+0x4F max HP, +0x51 current HP** (also the alive check),
  +0x52/+0x53 class-group pair (casters 2/2, others 4/4; +0x53 scales regen periods),
  **+0x56 class/portrait id** — user's party: sorceress=4, amazon=5, priestess=6, scout=7, so
  **even id = caster** holds for this party. CAVEAT: the class-NAME table order (Fighter, Scout,
  Magician, Priest, Amazon, Scout, Sorceress, Priestess = ids 0..7 via ptr [0x6986]) does NOT match
  those ids, so +0x56 may be a portrait/sprite index with a separate class field, or the sheet uses
  another mapping. Re-verify before shipping anything class-dependent to other players.
  +0x58 MP-regen countdown, **+0x5B current MP, +0x5C max MP**, +0xC4 8 spell-effect slots (0x1A each).
- Regen: **only the two characters-DEPLOYED loops** far-call 0C82:146C (sites 0x2DE0 outdoor,
  0x4C7D indoor - both once per iteration, ~33 ticks/s measured). **The packed world view never
  calls it: stock Drakkhen regenerates nothing while traveling** (memprobe-verified). The routine
  decrements HP countdown +0x36 and MP countdown +0x58; at 0 grants +1 (MP add+clamp = 0A4A:06F8)
  and resets to 0x78 - 4*[+0x53] (MP) / 0xDC - 4*[+0x53] (HP). A char effect flag halves a countdown
  (0x4000 HP, 0x8000 MP) - engine's own "fast regen" mechanism. mod_regen adds caster MP regen to
  the packed world view (19F7:09A9 chain, reset 75 = ~1.5x deployed rate) when standing still.
- **19F7:09A9 fires ONLY in the packed world view** (the deployed loops never reach the scene
  routine - same reason the compass vanishes and the map needed the dispatcher hook there). It is
  therefore also a free mode gate.
- `memprobe.py`: read-only live probe of the dev DOSBox (finds RAM by party-name signature, samples
  char fields). Use it instead of guessing which loop runs when.

## PERSO.SAV (1994 bytes, XOR byte i with i&0xFF, checksum u16 at +0x7C8)
- +0 flags, +1 ?, +2 u16 current char index (DS:6CF0)
- +4   4 x 0x19A character records → DS:5A2E (name at +4 of record)
- +0x66C 0x50 bytes world globals → DS:02DC..032C (position/heading at save +0x684 X, +0x686 Y, +0x677 heading)
- +0x6BC 0x40 bytes → DS:700C ; +0x6FC 0xCC bytes → DS:6F38
- Loader 03AD:09C7; reads into far buffer DS:[53F4]; decode loop 03AD:0AB1.

## Strings / data (DS offsets = file linear - 0x1FD40)
- "quete.fnt" = copy-protection code table (NOT a font); "Wrong code" at DS:07A9. Protection is unreachable in the GOG build.

## Spells
- Names: 23 NUL-terminated ASCII strings at **DS:0AA1** (HEALMIN, CURE, LIGHTNG, INVISIB, LIGHT, STRENGH,
  LANGUAG, SHIELD, HEALMAJ, UNLOCK, ANTIMAT, LOCK, PARALYS, DISPELL, CONFUSI, SPEED, ISOLATI, RESTORE,
  ANTIMAG, RESUREC, BLINDNE, TELEPOR, IMPROV).
- Records: **DS:08C4**, 14 bytes each, `rec = 0x08C4 + index*14` (indexer at 18A0:00DB). Layout:
  +0 far ptr to name, +4 word (unknown, 332..25800), +6 word (flags, 0x8000 seen), **+8 = MP cost**,
  **+9 = amount (damage or heal)** — applied at img 0x7B62 (`add [target+0x48], al`, heal path) and
  img 0x7B94 (`sub [target+0x48], al`, damage path); target byte **+0x48 = HP**. High bit of +9 seen
  set on some spells (0x82/0x85/0x86) — meaning unconfirmed.
  +10 = has-status flag, **+11 = status-effect type ID** (switches at img 0x7254/0x7634 compare it
  against 1,4,10,11,30,33,34 — the exact values in the table), +12 ?, +13 = animation/effect index.
  **No geometry in the record** — target size is code-side, in the hit test (not yet located).
- Live effect slots: 8 per character, stride 0x1A, at `char+0xC4`; built by 18A0:0043/0x96.
  Effect: +2/+4 x/y, +0xC/+0xE flag dword, +0x10 duration ctr, +0x12 spell idx, +0x13 fired-once,
  +0x16..+0x19 copied from record +10..+13. Applier at img 0x7B05.
  MP: HEALMIN/CURE/LIGHTNG/INVISIB 1; LIGHT/STRENGH/LANGUAG/SHIELD/UNLOCK/SPEED 2; HEALMAJ 3; ANTIMAT 4;
  LOCK/PARALYS 5; TELEPOR 6; DISPELL 7; CONFUSI/ISOLATI 8; RESTORE/ANTIMAG/RESUREC 10; BLINDNE 12; IMPROV 15.
- **Rune font** (spells and phials): the game draws those ASCII strings through a 5x5 glyph set — one rune
  per letter, no cipher. Lives in **RESI_VGA.6C0**, at **decoded** offset 36216: five 16-byte rows, each
  holding 25 glyph-rows of 5 bits end to end, so glyph N is bits [5N,5N+5) of every row (not 5 consecutive
  bytes). Glyph table at 36296: 25 x (width<<4|row, xoff) = (0x50, 0,5,10,...). Covers A..Y; 'Z' spills off
  the row and is garbage in the original. Replaced with Latin letters by `mod_spellfont.py`.
- Filename table: far ptrs at DS:1958 (index 16 = dataext.6in), VGA set; second set follows (floppy variant).
- Dialogue: 0/1/2.7XT, u16be offset table, 5-byte record header, NUL-separated lines.

## Message / name tables (all far-ptr tables in DGROUP; bases handed out at img 0x3BA1)
- **DS:2A02**: 88 entries. 0-3 level-up ('Ability', 'gets', ' Hit points'), 4-16 status msgs,
  **17-42 item type names** (spell book, sceptre, phial, ring, ... key), **43-50 class names**,
  51-60 shop, 61+ credits/disk prompts. Global base ptrs: [0x59C0]=DS:28DA, [0x678A]=DS:290E,
  [0x59CA]=DS:2942, **[0x6CE8]=DS:2A46 item names**, [0x6986]=DS:2AAE class names, [0x6D90]=DS:2ACE shop.
- String draw: `lcall 0A4A:0241 (farptr, x, y)`.

## Items
- Inventory: variable list of **6-byte records at char+0x64** (after 4 unknown bytes at +0x60):
  +0 flags (bit7 = equipped?), **+1 variant/content** (phial: 0 = empty -> 'empty phial'; suspected
  spell idx for filled phial / ring / sceptre), +2 param, **+3 item type id (0x04..0x44)**,
  +4 quantity, +5 zero.
- Name display (img 0xBA6F): name idx = `[DS:1CBB + id-4] & 0x7F`, then far ptr from [0x6CE8] table;
  draws qty at x+0x23. **DS:1CBB is the id->name map**: armor has real tiers (cuirass ids 0x11-0x16,
  helmet 0x23-0x2C...), but **ring is a single id 0x07** (also sceptre 0x05, rod 0x3E, phial 0x06) -
  ring identity must live in the variant byte +1, unconfirmed until a save containing a ring is read.
- OBJET.SAV / objet.6sr: 210-byte world-object pickup state, u32 header; NOT inventory, NOT XOR-coded.
- ACTIV.SAV: 360 activity flag bytes.
