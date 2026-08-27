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
  **+0x52 = highest level reached, +0x53 = CURRENT LEVEL** (earlier "class-group" label was wrong -
  the 2/2 vs 4/4 pairs were simply levels; regen periods scale with LEVEL),
  **+0x37 (&0x1F) -> DS:1BAE -> the TRUE class index 0..3** (0 fighter/amazon, 1 scout,
  2 magician/sorceress, 3 priest/priestess - verified via the MP formula below),
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

## Leveling (research 2026-08-25, mod_levelup.py adds stat growth)
- Level-up routine img 0xCBB0..0xCD25 (called from the XP-award path). Level from a geometric XP
  threshold loop, **max level 0x18 = 24**.
- **Max MP = DS:1BB7[class*2] + DS:1BB7[class*2+1] * level, engine clamp 254.** Verified exactly on
  the user's party: fighter (3,2), scout (5,1), mage (16,11), priest (24,9).
- **Max HP += maxHP/16 per level, engine clamp 250.** Current HP untouched here.
- **Stock stats NEVER grow on level-up** - only the IMPROV spell handler (070E:0EB0, img 0x7F90,
  reached via the spell-effect far-ptr table at DS:0B96) gives +1 to a rand(6) stat, unclamped.
- mod_levelup splices the 7 bytes at img 0xCCD8 (les bx,[bp+6] / mov es:[bx+0x53],al) and applies a
  4-class x 6-stat gain table x level-delta, clamp 99. Emulation-verified (unicorn): single level,
  multi-level jump, clamp, no-op.

## Copy protection (SOLVED - mod_noprotect.py)
- Prompt strings are message-table entries: DS:2B36 "DRAKKHEN CODES", DS:2B3A "Line:", DS:2B3E "Word:".
  They are NOT reachable by any static index - that is why an index scan finds nothing.
- Dialog draw **0D7E:18B0** (pushes those three far ptrs). Protection routine **0D7E:19B1**
  (random line/word via `div 0x19`, letter input loop, compare). Single caller = gate **0D7E:1B79**:
  a 32-bit counter at **DS:1B1A/1B1C** increments once per call and fires the prompt when it equals
  exactly **0x4C1 (1217)**; leading `ja/jae` tests make it a one-shot per session.
  Companion flag DS:1B18 is written and never read.
- **Fix: set the counter HIGH word (DS:1B1C) to 1.** First `ja done` then skips forever. Data only,
  no code removed, 0 dead-space bytes. Counter is referenced by nothing else.

## Video-card menu (SOLVED - mod_novideomenu.py, patches CONFIG.TAT not the game)
- DRAKKHEN.COM is a menu shell shared with Infogrames' HOSTAGE (its strings are still inside).
  It reads CONFIG.TAT to 0x1A50, then `cmp word cs:[0x1a5a],-1 / jne skip / call show_menu`.
- **CONFIG.TAT+0x0A = chosen card** (0xFFFF = ask). Value is the MENU INDEX into the 5-word
  availability list at CONFIG.TAT+0x0E = {0x0018 CGA, 0x00DA EGA, 0x013B Tandy, 0x0079 Hercules,
  0x019C VGA} - each a byte offset to a driver/engine record. **VGA = 4.**
  (Record indices 8/9 are NOT valid here: they give "insert disk 1" and an instant exit.)

## Character creation / class templates
- Creation routine img 0x10E70..0x10FCB builds a character from a **6-byte per-class template at
  DS:1BBF** (`tmpl = 0x1BBF + (class & 0x7F)*6`):
  cls0 Fighter 9,6,7,3,2,5 | cls1 Scout 10,8,7,3,2,7 | cls2 Magician 12,10,10,6,5,12 |
  cls3 Priest 16,13,12,12,9,13 | cls4 Amazon 20,16,16,18,16,18 | cls5 Scout(f) 23,19,20,22,20,20 |
  cls6 Sorceress 54,48,45,44,39,33 | cls7 Priestess 30,20,15,11,7,3
  Each of the six stats (+0x42..+0x47) = template byte + rand(0..3); max HP (+0x4F) = 4*T + rand(4*T).
  NOTE: these numbers do not look like plain "starting stats" - verify against a fresh character
  before treating the table as authoritative class balance.
- **Level-up stat growth: img 0x7F90 - `rand(6)` picks ONE of the six stats and `inc`s it**
  (`mov ax,6; call rand; add bx,ax; inc es:[bx+0x42]`), then sets +0x51. There is NO per-class
  growth table and no class branch at this site: growth is flat +1 to a RANDOM stat for everyone.
  That is the hook point for class-dependent growth (weight the roll, or add +1 by class).

## Quest / event progress (research 2026-08-24)
Two counter arrays, both saved inside PERSO.SAV, both INCREMENTED (not set) as the party advances -
so they are progress step counters, not booleans:
- **DS:700C**, 0x40 bytes (save +0x6BC). Indexed `si*16 + di` -> si 0..3, di 0..15. Written at
  img 0x17D31 `inc byte [bx+0x700C]`, taken when a context word `[bp-0x68] == 0x80`.
  si is most likely the party-member index (4 of them); currently all zero in the user's save.
- **DS:6F38**, 0xCC bytes (save +0x6FC) = **51 entries x 4 bytes**, values observed 0..4. Indexed
  `si*4 + di`, written at img 0x17D66 `inc byte [bx+0x6F38]`. A far pointer to it is published to the
  global at DS:704C (img 0x17F9E). si here ranges far wider than 4, so si = location/NPC id.
- Both increments live in the **conversation/interaction handler** (img ~0x17CC0..0x17D8B): it builds
  a string from the message table at [0x6D90], calls the dialogue routine (img 0x177E1), and on
  result 1 credits the party (adds to [0x59B8]+0x10 dword) and bumps one of the two counters.
- Consequence for a quest log: the game does NOT store objective text or a quest list. It stores
  "how far along entity N is". A quest log would have to MAP counter values -> our own text.

## Dialogue text files (0/1/2.7XT)
- Text is stored with the HIGH BIT SET; `b & 0x7F` makes it plain English. Lines NUL-separated.
- The prose is fully readable and quest-bearing, e.g. "The Master of Water is the Master of Tears",
  "it will take you to NAKHTKHA. Hurry on!", "Gems are tears". So a quest log could quote the game's
  own words rather than invent text.

## Main quest (user-supplied walkthrough, 2026-08-24 - authoritative)
Journal wording, wrapped to the 40-char dialogue width:
   1. Talk to Prince Hordtkhen
   2. Visit Princess Hordtkha
   3. Return to Prince Hordtkhen
   4. Find Prince Haaggkhen
      (wall switch by the door, THEN the ?)
   5. Assist Prince Naakhtkhen
   6. Stop Princess Nakhatka
   7. Follow Princess Haaggkha's trail
   8. Kill Prince Hordtkhen
   9. Return to Princess Haaggkha
  10. Take the Tear of Hazhulkha
  11. Kill Princess Nakhtkha
  12. Kill Prince Haaggkhen
  13. Kill Prince Hazhulkhen
  14. Read the message in the sepulchers
  15. Give the 8 tears to the dragons
The list is LINEAR, so a journal only needs a CURRENT STEP number - it does not have to derive
objectives from engine state.

## Quest / event progress counters (research 2026-08-24)
Two arrays, both inside PERSO.SAV, both INCREMENTED as the party advances (progress counters, not
booleans):
- **DS:700C**, 0x40 B (save +0x6BC), indexed `si*16 + di`, si 0..3 - likely per party member.
  Written img 0x17D31 when a context word `[bp-0x68] == 0x80`. All zero in the user's save.
- **DS:6F38**, 0xCC B (save +0x6FC) = 51 entries x 4 B, indexed `si*4 + di`; written img 0x17D66.
  Far pointer published to DS:704C (img 0x17F9E). **Only byte 0 of each entry is ever non-zero** in
  a real save, and non-zero entries come in CONSECUTIVE CLUSTERS (observed: 4-8, 17/18/20, 29-31,
  34-36/38, 43-45, 48-50; values 1..4) - consistent with one cluster per location, one counter per
  NPC/topic within it.
- Both increments live in the conversation/interaction handler (img ~0x17CC0..0x17D8B): build the
  line from the [0x6D90] message table, call the dialogue routine (img 0x177E1), and on result 1
  credit XP and bump a counter.
- **GAP**: counter index -> quest step is NOT established and cannot be derived statically. Closing
  it needs snapshots of DS:6F38 at known walkthrough points (memprobe.py while the user plays).

## Dialogue text (0/1/2.7XT) - editable
- LOOSE, UNCOMPRESSED files. Chars stored with the HIGH BIT SET (`b & 0x7F` decodes), NUL-separated.
- Text may be rewritten in place at the SAME length freely; changing a line's length also requires
  rebuilding the file's offset table.
- **Wrap limit 40 chars**: the line builder 0A4A:033D fills DS:5426 with stride 0x28, ~4-5 lines.
- Engine string draw: `lcall 0A4A:0241 (far ptr, x, y)`.

## DRAKTJ.CC1 - the character-creation program (research for the starting-gear mod)
GOAL (user's explicit spec): SCOUT class starts with the bow, MAGICIAN/SORCERESS with a RESTORE
ring - patched into the CREATION CODE so every new character gets them. NOT a save edit.
- Container: 2 chunks (159656 MZ + 614). Analysis copies: `_tools/../_backup/... none` - unpack
  fresh via drakpack from ../DRAKTJ.CC1. Scratch copy used: scratchpad/unpacked/DRAKTJ.CC1.00.bin.
  All img offsets below are into that decoded chunk 0.
- **DGROUP file base = 0x22DF0** (NOT the same layout as DRAKM: stat templates at DS:1A73 here,
  vs DRAKM's 1BBF; derive any DS:x as file 0x22DF0+x).
- Character records live at **DS:4BBE** (4 x 0x19A, same record layout as DRAKM's DS:5A2E).
  PERSO.SAV writer/loader ~img 0x6A00-0x6DB5 (same XOR i&0xFF + u16 sum-of-encoded checksum).
- **Creation record-init**: img ~0x13290-0x1348C. Reads a 0x1C-stride per-class spec at **DS:0D00**
  (`spec = 0xD00 + class*0x1C`, loaded at img 0x1330B). Writes stats (template DS:1A73 + rand(4)),
  maxHP/level like DRAKM, and inventory slots 0/1 as spell-book entries (img 0x13414-0x13443) -
  NOTE these slots end up EMPTY in a fresh save, so something later clears/overwrites them.
- **Spec DS:0D00 does NOT hold gear**: fields identified = +0 name prefix (Ara/Sco/Doi/War/Kni/
  Lor/Por/Dan), +4 stat-template idx, +8&0xF (class group, cmp 7 at img 0x134FD), +0xB/+0x11
  (spell-book byte2 values), +0xE (XP pool), +0x10 (MP class), +0x12/+0x13 (sprite ids).
- **Give-item helpers**: img 0x0DB12 (memcpy 6 bytes into first free WEAPON slot, record+0x64
  scan) and img 0x0DB9C (ITEM area, record+0x94). Take (char_far, item_far) cdecl.
- **NEXT STEP - the untraced part**: the per-class wearable-gear grant (slots 2-4: shoes/armor/
  weapon, catalog-record copies) is in the branch chain from **img 0x134F2** (starts by reading
  spec[+8]&0xF and comparing to 7, then class-specific paths; shl al,3 / add al,0x14 at 0x13502
  suggests a computed table index). Trace where it fetches the catalog entries (DRAKTJ has the
  same catalog data - 'fighter-shoes' record found at file 0x24BD8 = DS:1DE8-ish region), then
  either patch the per-class selection bytes (if table-driven) or splice the give-item calls.
- Patch delivery once found: new mod file patches DRAKTJ.CC1 (decode chunk0, edit, repack container
  like DRAKM), add as 4th file to installers with its own stock/steam SHA gates (Steam's
  DRAKTJ.CC1 hash must be checked - its .BAKs exist for DRAKC/DRAKE/DRAKM but DRAKTJ was NOT
  in Steam's .BAK set, so verify whether Steam's DRAKTJ matches GOG's before assuming).

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

---

## Character creation and starting equipment  (solved 2026-08-26)

### DRAKM.CC1 has TWO executables

`drakpack.unpack_container(DRAKM.CC1)` yields **two chunks, both MZ images**:

| chunk | size | header | DGROUP | what it is |
|-------|------|--------|--------|------------|
| 0 | 34378 B image (36938 raw) | 0x0A00 | **0x06B8** (linear 0x6B80) | **the character creator** |
| 1 | 149152 B image | 0x2A00 | 0x1FD4 (linear 0x1FD40) | the game engine |

`drakmod.Builder` only ever loaded `chunks[1]`, so every mod and every probe so far has
touched the engine alone.  That is why two rounds of patching the engine's weapon tables
produced no change to starting gear: **the creator is a different binary.**

Chunk 0 is confirmed as the creator by its class-mask writes - a jump table on the chosen
class (0..3) at img 0x00B7B storing 1 / 2 / 4 / 8 into `es:[bx+0x37]` through the
"character being edited" pointer at DS:217C.

### Character record layout (both binaries, DS:5A2E in the engine)

Party array = **4 records of 0x19A bytes at DS:5A2E** (ends 0x6096; the engine's own init
loop at img 0x0580A walks exactly that range).  A second identical-stride array for
monsters/NPCs lives at DS:60E6.

| offset | field |
|--------|-------|
| +0x00 | name, 6 chars + NUL |
| +0x37 | **class mask** - 1 fighter, 2 scout, 4 mage, 8 priest (a BITMASK, not an index) |
| +0x38 | class group |
| +0x46..+0x4B | the six stats |
| +0x53 / +0x55 | HP max / current |
| +0x5F / +0x60 | MP max / current |
| **+0x64** | **item array: 8 slots x 6 bytes** (ends +0x93) |
| +0x94 | spell array: 8 slots x 6 bytes |
| +0xC4 | third 8 x 6 array |

`find_free_slot` (0B20:01AA, img 0xB3AA) scans `es:[bx + slot*6 + 0x67]` for a zero over 8
slots - +0x67 is `0x64 + 3`, i.e. the item **id** byte, so a slot is free iff its id is 0.

Item record = 6 bytes: `[0] flags (low nibble = class mask allowed to use it), [1] ?,
[2] power, [3] item id, [4..5] price word`.

**Slots 0 and 1 are the innate attack / innate defence slots.**  The monster spawner at
img 0x10F02 fills them (`[0x64]=0x21`, `[0x67]=4`; `[0x6a]=0xC0`, `[0x6d]=4`) - natural
weapon and hide.  Player characters leave them empty, which is why party gear starts at
slot 2 and why `find_free_slot` was a red herring.

### PERSO.SAV format

1994 bytes = 0x7CA.  Load path is img 0x04500..0x0460A:

```
buf[i] ^= (i & 0xFF)      for i < 0x7C8       ; checksum word stored at buf[0x7C8]
buf[0], buf[1]  -> two locals
buf[2..3]       -> DS:6CF0   (current character index)
buf[4..0x66B]   -> DS:5A2E   (0x668 = 4 x 0x19A, the whole party array)
```

So **file offset 4 is character 0's record base**; add 4 to every record offset above to
get a file offset.  The save is marshalled through a heap buffer at `[0x53F4]`, not
memcpy'd directly, which is what made the offsets look shifted at first.

### The starting-gear grant  -  DRAKM.CC1 chunk 0, img 0x02DBC..0x02F60

The creator has **its own copy of the item catalog** at chunk-0 img 0x07924 = **DS:0DA4**,
47 records of 6 bytes, same order as the engine's catalog at DS:1F34.  In the creator's
copy the price word is `01 00` for *every* record - that, not any code, is why every
starting item in a save has byte 4 = 01.

Gear is granted as four/three identical 27-byte blocks, one per item, no tables and no
`give_item` call - a straight 6-byte memcpy per item:

```
mov ax,6                ; count
push ax
mov dx,[bp+8]           ; character record, seg
mov ax,[bp+6]           ; character record, off
add ax,0x70             ; DESTINATION  0x70/0x76/0x7C/0x82 = item slots 2,3,4,5
push dx / push ax
push ds
mov ax,0x0DA4           ; SOURCE  = creator catalog record
push ax
lcall 02AD:00D8         ; memcpy(src, dst, 6)
mov sp,bp
```

The source operand is the only thing that varies.  Patch the `mov ax,imm16` at these
addresses to change what a class starts with:

| class | slot 2 (shoes) | slot 3 (armour) | slot 4 (weapon) | slot 5 |
|-------|----------------|-----------------|-----------------|--------|
| Fighter | 0x02DCD `0DA4` | 0x02DE8 `0DBC` jacket | 0x02E03 `0E58` buckler | 0x02E1E `0E94` sword |
| Scout   | 0x02E50 `0DA4` | 0x02E6B `0DC2` leather | 0x02E86 `0E8E` dagger  | - |
| Priest  | 0x02EB8 `0DA4` | 0x02ED3 `0DF2` robe    | 0x02EEE `0EB2` bludgeon| - |
| Mage    | 0x02F20 `0DA4` | 0x02F3B `0E04` robe    | 0x02F56 `0EAC` rod     | - |

(addresses are the imm16 operand itself - the `b8` opcode is one byte earlier.  Shoes are
the same record for all four, the invariant that confirms the read.)  The fighter block also sets +0x5B=3,
+0x5C=3, +0x38=6 before returning.

Creator catalog record address = `0x0DA4 + catalog_index * 6`.  Useful ones:

| item | idx | DS addr | record |
|------|-----|---------|--------|
| shoes | 0 | 0DA4 | `4f0100080100` |
| jacket | 4 | 0DBC | `4f02000e0100` |
| leather | 5 | 0DC2 | `4f04000f0100` |
| priest robe | 13 | 0DF2 | `48041e170100` |
| mage robe | 16 | 0E04 | `44041e1a0100` |
| buckler | 30 | 0E58 | `4f05142d0100` |
| dagger | 39 | 0E8E | `2f0205360100` |
| sword | 40 | 0E94 | `2f0208380100` |
| rod | 44 | 0EAC | `2f02083e0100` |
| bludgeon | 45 | 0EB2 | `2f02063f0100` |
| **bow** | 46 | **0EB8** | `2f0106410100` (last record; zeros follow) |

Note the creator's catalog is independent of the engine's, so `mod_bow`'s power change to
the engine catalog does NOT reach a bow handed out at creation - patch chunk 0's copy too.

### Engine-side item facts (chunk 1) found on the way

* Engine catalog: **DS:1F34**, 47 records, index 0..46, bow last.  Orphan filename strings
  begin immediately after at DS:204E.
* `item code = catalog index + 4` (armour codes 4..0x2A read `code-4` from DS:1F34;
  weapon codes 0x2B+ read `code-0x2B` from DS:201E, which is catalog record 39).  The bow
  is item code 50 = 0x32.
* Loot tier tables: **DS:1C0F armour**, **DS:1C3F weapons**, 8 rows x 6 columns of catalog
  indices.  Weapon row 3 is already all-bow.  These drive random drops (`give_item` callers
  at img 0x0CA6A / 0x0CB0F), NOT starting gear.
* `give_item` = **1435:0815, img 0x14B65**: finds a free slot, memcpy 6 bytes from a catalog
  record to `charptr + slot*6 + 0x64`, sets `[+5] = qty`, refreshes.  Only 4 callers, all
  loot/shop - none in the creation path.

### Magic items (rings / sceptres / phials) and the starting ring  (2026-08-26)

**Rings are not catalog items.**  The catalog covers ids 0x08..0x41.  Rings, sceptres, phials and
two unnamed kinds live in a separate id space produced by the engine's magic-item creator at
img 0x14AB8, which BUILDS a record instead of copying one:

```
slot = find_free(charptr)          ; 0B20:0173 - scans es:[bx + slot*6 + 0x97], 8 slots
dst  = charptr + slot*6 + 0x94     ; the MAGIC-ITEM array, not the +0x64 item array
dst[0] = 0x0F                      ; flags
dst[1] = variant                   ; spell index  (0xFF forced when type == 4)
dst[2] = (type << 5) | arg
dst[3] = DS:1BF9[type]             ; type -> id
dst[4] = dst[5] = 0                ; price
```

`DS:1BF9 = 04 05 06 07 42 43`, so **type 3 -> id 0x07 = ring**.  Verified against a real save: a
phial reads `1f 00 40 06 00 00` (type 2, byte2 = 2<<5) and the 0x42 / 0x43 items read byte2 =
0x80 / 0xA0 - all three agree with `(type << 5)`.

So a character record holds **three** 8-slot x 6-byte arrays: **+0x64 items**, **+0x94 magic
items**, **+0xC4** (third kind).  `mod_ring` scans +0x64 for 14 slots, which happens to run to
+0xB7 and therefore covers the magic array too - that is why a worn ring at +0x94 is picked up.

A worn RESTORE ring is therefore `8f 12 60 07 00 00` (bit 7 = worn, variant 18 = RESTORE,
(3<<5)|0, id 7, price 0).

**Dead space in chunk 0.**  The creator's copy of the catalog at DS:0DA4 is private to it, and
chunk 0 contains **no `mov dx,6 / mul dx` anywhere** - there is no computed indexing into that
table at all.  The only way any code there can reach a record is a direct `mov ax,imm16`, and all
twelve of those are the gear-grant blocks.  Exactly **10 of the 47 records are referenced**; the
remaining **37 (222 bytes) are unreachable** - a complete proof, not a heuristic.  That is the
only proven dead space in chunk 0.

Do NOT use the 422-byte zero run after the catalog (DS:0EBE): it is a **10 x 42-byte string
table** filled at runtime, indexed by `(idx - 0xF1) * 0x2A + 0x0EBE` at img 0x03052 and passed to
a string-width routine.  The other zero runs in chunk 0 (ds:034d, ds:005b, ds:10db, ds:0507) are
all referenced too.  There is no padding between functions - the magician's routine ends with
`retf` at 0x02F73 and the next `push bp` is at 0x02F74 - so a grant block cannot be appended.

**Granting the ring with no new code** (`mod_startring`): a grant block's byte COUNT is an
immediate as well.  The magician's last block copies 6 bytes to +0x7C.  Pointing it at 30
contiguous dead catalog bytes laid out as `[rod][zeros][zeros][zeros][ring]` and raising the
count to 30 makes the single memcpy fill +0x7C (rod, unchanged), +0x82/+0x88/+0x8E (zeros, which
are already zero at creation) and **+0x94** - magic-item slot 0.  The magician keeps every item
it had and no code is added or moved.

Rule of thumb that falls out of all this: giving any class any **catalog** item is a two-byte
edit of one source operand.  Anything outside the catalog needs a synthesised record, and the
count/destination operands are the levers for placing it.

### Equipping the starting gear  (mod_startworn, 2026-08-26)

Stock creation sends the party out **naked with the gear sitting in the inventory** - it never
equipped anything, so there was no existing mechanism to copy.

Two separate things make a character actually equipped:

**1. Bit 7 of the item's flags byte = worn.**  Confirmed against a played save: worn items read
0xDF / 0xD4 / 0xBF and the same items unworn read 0x5F / 0x54 / 0x3F, with several worn at once
(tunic + jacket + shield + sword), so there is no single equip slot to conflict with.  Since a
granted item is a verbatim copy of a creator catalog record, this is set at the source: OR 0x80
into the flags byte of every record a grant block can copy from.

**2. Record +0x56 = the item-slot index of the HELD WEAPON** (0x7F = empty handed).  Bit 7 alone
only lights the item up in the inventory list - this is what puts a weapon in the character's
hands.  The engine's own equip handler maintains it (img 0x0B6D4):

```
xor es:[bx], 0x80          ; toggle worn on the item
test es:[bx], 0x20         ; bit 5 marks the item as a weapon
   charptr[+0x56] = 0x7F   ;   nothing held
   if now worn: charptr[+0x56] = that item's slot index
```

Proven live with a read-only probe of the running game (`probe_equip.py`): a character the player
had re-equipped by hand read **+0x56 = 02** with its weapon in slot 2, while characters given gear
by this mod read **+0x56 = 0x7F** and held nothing - exactly the reported symptom.  Armour needs
nothing extra; only weapons (flags bit 5 = 0x20) have an index field, and +0x57 stays 0x7F even
for a character wearing a shield.

The creator writes +0x56 = 0x7F in four `mov byte es:[bx+0x56], 0x7F` instructions at chunk-0 img
0x02C34 / 0x02CAE / 0x02D2B / 0x02DA8.  Those are one **unrolled loop over the four PARTY SLOTS**
(each is followed by `add [bp-4], 0x19A`), not per class, so they cannot carry a per-class value.
The fix is therefore to give every class its weapon in the SAME slot and write that one index:
the fighter's buckler and sword destinations are swapped so its sword lands in slot 4 like every
other class's weapon, then all four writes become 4.  Both halves are immediate edits.

Bit 4 (0x10) is deliberately NOT set.  It means "revealed in the inventory list": the list draw
skips items without it (img 0x0BA39) and the game bulk-sets it across every slot when the
inventory opens (img 0x0B2F0).  That is why played saves carry it everywhere and fresh ones do
not - the game does it itself.

The equipped-record list is the **union** of every record any grant block can point at under any
mod selection - the ten stock sources, the bow (live only with mod_startgear) and the
mod_startring pool (live only with that mod).  It is spelled out rather than scanned so the
recorded fragment does not depend on which other mods were in the reference build; setting the
bit on a record the current selection does not use is harmless, since those records are
unreachable dead space.  `mod_startworn` runs LAST in the build, and `mod_startring` copies the
rod out of the catalog as it stands so the equipped bit carries into its pool.

`verify_startgear.py --matrix` emulates the creator for every combination of the three start*
mods and reports, per class, the weapon's slot and the held-weapon field.  Without `startworn`
every class must still read "naked" (stock behaviour); with it, every class must hold its weapon.

### Game text: the .XT files  (2026-08-26)

Format is trivially editable: a big-endian u16 offset table (the first entry doubles as the
header length, so `count = offs[0] / 2`), then the entries, each a run of NUL-separated display
lines.  Entry n spans `offs[n] .. offs[n+1]`.

Three distinct text files ship, NOT three copies of one:

| file | entries | content |
|------|---------|---------|
| `0.?XT` | 96 | NPC / villager chatter |
| `1.?XT` | 16 | letters and scrolls |
| `2.?XT` | 32 | signposts, directions, quest text |

Each is then duplicated **once per video mode**, and the suffix is what selects it:

| binary | mode | text set opened |
|--------|------|-----------------|
| **DRAKM.CC1** | **VGA - the one this project patches** | **`.7xt`** |
| DRAKE.CC1 | EGA | `.3xt` |
| DRAKC.CC1 | CGA | `.1xt` |
| DRAKTJ / DRAKTC | Tandy / Hercules | `.3xt` |

`0.1XT == 0.3XT == 0.7XT` byte for byte (and likewise for 1 and 2) - 9 files, 3 distinct
contents.  **A text mod therefore only needs to patch `0.7XT`, `1.7XT`, `2.7XT`.**

Each binary also carries a SECOND live filename table naming an alternate set (`.4xt` for
DRAKM/DRAKE/DRAKT*, `.2xt` for DRAKC) whose files are **not shipped in this release** - selected
at 03AD:1918/1924, the same selector that leaves filename tables 1 and 2 orphaned.  So the
engine's own dead space and this text redundancy come from the same cause: a 1990 multi-format
release built from one tree, shipping the union of every configuration's asset set rather than
pruning per SKU.  That redundancy is precisely why this project has room to work in.

Translation quality is BETTER than expected - the scrolls and NPC dialogue are competent British
English, not the mangled port people assume.  What actually reads as a translation is:

* **French typography, 46 instances** across the three files: 28 x `space !`, 7 x `space :`,
  5 x `space ?`, 5 x `space ;`, 1 x `space ,`.  French spaces before those marks; English does
  not.  Also present in the engine's own UI strings ("Do you want to buy this object ?").
* **Two typos**: `cemetary` (x2) and `Beware of it's children`.
* **Item names squeezed to a display-width budget** (engine strings, not .XT): `arch` = bow
  (French *arc*, fixed by mod_bow), `sword lg` = long sword, **`drags` = dragon sword** - the
  strongest weapon in the game at power 55 / price 100 - and `greave` for greaves.

Fixing the typography is pure deletion, so the files SHRINK and the offset table just gets
rebuilt; no engine risk at all.  Item names are harder: they live in a packed NUL-separated block
at **DS:2A46** (pointer installed at img 0x03BCC: `mov word [6CE8], 0x2A46`), located by ORDINAL
via the index table at DS:1CBB, so lengthening one name has to be paid for by shortening another,
and the inventory column is only ~7-8 characters wide before the suffix mod_itemname draws.

### Reclaiming the alternate asset set: 382 more bytes  (analysed 2026-08-26, NOT yet used)

The four filename tables are two PAIRS, not four variants.  Tables 1/3 name the `.6c1/.7c1/.8c1/
.7xt` set (the files this release actually ships); tables 2/4 name an alternate `.2c1/.4c1/.4xt`
set.  Within a pair the filenames are identical but the tables are NOT byte-identical - each
points at its own copy of the strings, exactly 0x220 apart:

    t1 tbl DS:1958  strings DS:204E      t3 tbl DS:1A30  strings DS:226E
    t2 tbl DS:19C4  strings DS:215E      t4 tbl DS:1A9C  strings DS:237E

Each table is 108 B = **27 far pointers** (offset + DGROUP segment), which is why every odd word
reads 0x1FD4.

**Which are live.**  The selector at img 0x053DF reads byte 0 of the file **DRK1** (fallback
DRK2, opened at img 0x03E31) and does:

```
cmp ax, 5
je  -> [60D8] = 0x1A30    ; table 3
jne -> [60D8] = 0x1A9C    ; table 4
```

`DRK1` = `05 01 01 01`, so byte 0 is 5 and **table 3 is always chosen**.  A raw little-endian
word scan of the whole image finds tables 1 and 2 referenced **zero** times in code or data, and
tables 3/4 exactly once each - here.  (The only operands that fall inside the orphan string range
are `cmp [0x2F0], 8392` / `cmp [0x2F0], 8492` at img 0x02086 - a 100-wide numeric window, not
pointers; they land mid-string.)

**Table 4 is already non-functional**: 15 of its 27 files do not exist in this release
(`pers_vga.4c1`, `exte_vga.4c0`, `inte_vga.4c0`, `game_vga.4c1`, `mons_vga.4c1`, `reg.4c1`,
`drk4`, `0/1/2.4xt`, `music.4c1`, `gamebvga.4c1`, `game.4AL`, `end.4AL`, `drksv`).  If that
branch were ever taken the game would fail to load regardless.

**So it can be reclaimed.**  Patch the `jne` at img 0x053E2 (`75 0C`) to two NOPs so the selector
always installs table 3.  Table 4 and its string set then become provably unreachable:

    table 4 pointers  DS:1A9C..1B08   108 B
    table 4 strings   DS:237E..2490   274 B
    TOTAL                             382 B      (vs 758 B in the existing data pool)

This is strictly MORE robust than stock - the branch it removes leads to a guaranteed load
failure.  Not implemented yet: there is no queued mod that needs the room, and capacity with no
consumer is speculative.  When something needs it, add the two ranges to `drakmod.SPACE` behind
the selector patch, exactly as `alloc_code` is gated on `mod_noprotect`.

**The video mode IS user-switchable at any time - via DRAKKHEN.COM, not DRAKM.**  (An earlier
revision of this file claimed otherwise; that was wrong, and was written without opening
DRAKKHEN.COM.)  The launcher draws:

```
Main Menu                      Select Video Card
  F1  Creation                   F1  CGA      4   colors
  F2  Game                       F2  EGA      16  colors
  F3  Select video card          F3  Tandy    16  colors
  F4  Joystick calibration       F4  VGA      256 colors
  F5  Return to DOS              F5  HERCULES Monochrome
```

F1/F2 being separate entries is independent confirmation of the two-executable finding: F1 runs
the creator (chunk 0), F2 the game (chunk 1).

Choosing a non-VGA card rewrites `Config.tat` (string at com:0x01D5) and the next launch loads a
DIFFERENT executable - DRAKE (EGA), DRAKC (CGA), DRAKTC/DRAKTJ (Tandy/Hercules) - none of which
this project patches.  **Consequence: every QOL mod silently disappears and the CONFIG.TAT video
byte mod_novideomenu set is overwritten.**  It is not a crash, it is a "where did my mods go"
bug, and it is reachable from the main menu at any time.

This does NOT endanger reclaiming table 4: that table lives inside DRAKM, and if the player
selects EGA then DRAKM is not loaded at all.

**The launcher already has a hide mechanism**, so suppressing F3 is tractable.  Main-menu key
loop at com:0x116A:

```
mov ah,0 / int 16h
cmp ah,0x3B / jl loop          ; below F1
cmp ah,0x45 / jg loop          ; above F10
sub ah,0x3B                    ; F1..F5 -> 0..4
cmp ah,5   / jae redraw
mov al,ah
lea bx,[0x1ED] / xlatb         ; 5-byte dispatch table
cmp al,0xFF / je loop          ; 0xFF = no such visible entry
mov cs:[0x1A5A],ax             ; accept
```

The table at com:0x01ED is built at runtime (com:0x1109): filled with 0xFF, then walked against a
5-word descriptor array at `cs:[0x01CD]` - a zero word hides that entry, and only VISIBLE entries
consume a slot (`mov cs:[di],cl / inc di`), so hiding one renumbers the rest exactly as the game
would.  Zeroing the F3 descriptor word would therefore give a clean four-item menu.  NOT yet
implemented: `cs:[0x01CD]` is itself assigned at runtime and that assignment has not been traced.

The engine's own F-key handler (img 0x19FFC in DRAKM) is unrelated: F7 makes a call and F1..F6
store byte pairs - (1,0x0C) (2,0x0B) (3,0x0A) (4,9) (3,8) (3,7) - to `cs:[0x60AE]`/`cs:[0x60AF]`,
which are written in six places and read nowhere in the engine, so they are consumed by the
separately loaded driver.  Those are not a video selector.

### The launcher, DRAKKHEN.COM: menu surgery and the art post-mortem  (2026-08-27)

**mod_menu4 (SHIPPED)** removes "F3 Select video card" from the main menu - with the card pinned
to VGA it was the one in-game path that silently unloads every mod (picking another card rewrites
Config.tat and the next Play loads DRAKE/DRAKC/DRAKT*, which we do not patch).  The menu is a
static text block plus a parallel jump table, so both halves are edited:

  * lines com:04D1/04FA/0523 (36 chars, inside the block drawn from com:040A): F3 becomes
    Joystick calibration, F4 becomes Return to DOS, F5 blank.
  * jump table com:01C3 (5 words, dispatched by `jmp word cs:[bx+0x1C3]` at com:104E):
    {Creation, Game, video, joystick, exit} -> {Creation, Game, joystick, exit, redraw}.
    The key filter (com:1041) accepts F1..F5 before dispatch, so slot 4 must stay valid -
    it now points at the redraw loop (com:103B) and a stray F5 does nothing.

Verified by memory probe of the live launcher: Main Menu / Creation / Game / Joystick /
Return to DOS, no fifth entry.  GOG and Steam ship byte-identical DRAKKHEN.COM
(sha256 32060c0f...), so one hash covers both.  Requires mod_novideomenu: it preempts the
first-boot card prompt, so together no card selection is reachable at all.

**Launcher facts** (hard-won, reusable):
  * Entry jmp -> com:0FB6.  `mov sp,0x1A4E`; Config.tat is read WHOLE to com:0x1A50
    (`cx=0xFFFF`), then `[0x151] = 0x1A50 + bytes_read` and the program SHRINKS its own
    memory block to that boundary (int 21/4A at com:1215) - anything appended to the COM
    file is deallocated, and Config.tat is size-sensitive (enlarging it kills the launcher:
    something consumes bytes_read as a length).  The '(c) Infogrames' title block, the
    5-word video-card availability table (config+0x0E), and the text-block pointers all
    live inside the loaded config.
  * The block-drawer (com:148E) is a mini-language: 0x0D newline, 0x24/0x00 end, 0x03 skip-N,
    0x04 attr-follows, 0x02 RLE-run, row stride 0xA0.
  * The card-menu lines (com:0646..0712, via pointer table com:063C) are STAMPED at runtime
    (digit written at line+5) even when the card menu never shows.  The "memory required"
    text at com:0x225 OVERLAPS live variables (startup stores a far pointer at 0x26C/0x26E;
    the EXEC parameter block lives around 0x25C).  The SSSSSSSS card-mismatch text at
    com:038B is a template the mismatch path stamps the card name into (writer at com:1399).
    **Practically none of the launcher's "dead-looking" text is safe to overwrite.**

**Menu background art - WIP, NOT shipped.**  The plan (replace the 0xB1 stipple fill at
com:1466 with an RLE-decoded 80x24 char/attr image; Blazej Kozlowski's "-bug" wolf, initials
kept per the Respect ASCII Artists Campaign, menu box moved to column 1) is built and the
pieces are proven separately: encoder + decoder verified byte-exact under Unicorn both with
art present and with the fallback path, `_tools`/scratch has the composed 973-byte RLE.
Every in-place hosting attempt died on the constraints above (COM append -> deallocated;
config append -> size-sensitive; card lines -> stamped; 0x225 -> live variables), and the
final variant still hangs before the first fill call for an untraced reason.  Next session
should run dosbox_with_debugger.exe (in the Steam folder) and trace com:1466's caller chain
at startup rather than bisecting blind.  A memory-probe harness exists
(scratch vgaprobe.py/markprobe.py): PrintWindow screenshots of Staging are UNRELIABLE
(black frames) - probe the text page in process RAM instead, or CopyFromScreen the
foregrounded window.

### Launcher menu color  (mod_menucolor, 2026-08-27)

User-picked palette from live-probed mockups: **deep blue stipple field, gold text and borders.**
Three immediate bytes: com:146C (fill attr 07->01), com:14BB (drawer default 07->0E), com:14DD
(the code-5 attr-reset, kept in lockstep).  The drawer's block language supports per-element
color (<ATTR:XX> = 04 XX), so finer schemes are possible later by recomposing blocks in place -
same total length, padding with the ignored 0x01 code.  The 'Loading ......' blink is <ATTR:87>
in the strip block and resets through com:14DD.

Installer note: menu4 and menucolor both patch DRAKKHEN.COM, so the installers apply COM mods as
a PIPELINE - stock source (the backup on re-runs), selected mods applied in canonical order, and
the result verified against a per-combination hash table.  Verified live for all three
selections: both, color-only (stock 5-item menu, colored), and menu4-on-top-of-color via backup.

### The Anak temple: fees, the softlock, and mod_freetemple  (2026-08-27)

**Money is per-character and 32-bit**: record +0x10/+0x12.  Found live (four values matched the
user's in-game jade readout), and **+0x53 is LEVEL** (the earlier read of it as HP was wrong; HP
is +0x4F max / +0x51 cur, dead == HP_cur 0).

**temple_service (img 0x2A98)**, reached inside temples (zone id DS:679E flips 0x0F -> 0x0E on
entry, observed live):

```
fee_base = level^3                 ; byte [bx+0x53] cubed
dead  (HP_cur==0): amount = fee_base * 20     ; imm at img 0x2ADA
alive:             amount = fee_base * 5      ; imm at img 0x2AF1
pay_richest(amount32)              ; 0A4A:0821, img 0x0ACC1
  -> scans all 4 records, the FATTEST purse pays; 0xFFFF if even that cannot afford
on failure: dialogue 0x5F = "Riches cannot win your head. Die and without jade stay dead!"
on success: +5 HP (img 0x2B70, clamped to max), sets Recuperation flags 0x6000, clears +0x2C,
            then a 75-step restore animation
```

Verified live before patching: healing a level-2 character billed exactly 40 jade (2^3 x 5), and
two consecutive heals were paid by two DIFFERENT characters - the richest at each moment.  The
softlock: revive = level^3 x 20 (level 5 = 2500 jade), and a first-fight corpse's own pocket
cannot pay for itself.

**mod_freetemple** (key `freetemple`): both multiplier immediates -> 0 (free and ungated - the
taunt is unreachable), and the +5-HP add+clamp (23 bytes at img 0x2B70) rewritten to
`HP_cur = HP_max` + NOPs, so ONE visit fully heals and a revive returns at full HP.  The
Recuperation grant and status clear are preserved.  pay_richest itself is untouched: its only
other caller is the priest's pay-for-information donation (img 0x39C3, fail -> text 0x5E),
deliberately left as a paid flavor service.  User-verified at multiple temples.

### The IFGM sound-driver interface  (music spike, 2026-08-27)

Drakkhen's sound is a PLUGGABLE DRIVER STANDARD - exactly the seam needed to replace the music
without touching the engine.

* DRDRIVER.xC1 is a BPE-packed flat binary, loaded resident by the launcher (CONFIG.TAT pairs a
  drdriver with each executable).  Decoded 6C1 = 3942 B: `jmp init` at offset 0, OPL instrument
  patch records, init at CS:0xFE1 (file offset - 0x100: loaded COM-style at PSP:0x100).
* Install: reads INT 0xF0's vector (0000:03C0); if handler+2 already reads "IFGM" it exits,
  else installs its handler (CS:0xF5D) and TSRs (int 21/31).  Handler+2 carries the tag and a
  variant name: **"IFGM ADLIB"**.
* Handler: `BX=AH; call word cs:[BX+0xF41]` - AH is an EVEN function code into a word table.
* Engine side (wrappers img 0x1AA4D..0x1AC60, presence flag cs:[6], 14 `int 0xF0` sites):
  AH=00 detect, 02 init (after loading a file via 1BC6:0202/0255), 06+08 music-data segment
  handoff (DX=seg, SI=ofs), 04 start, 0A music cmd (DX,CX,SI), 0C sfx cmd (one caller feeds a
  table at DS:4D2), 0E stop, 10 enable.
* The engine's own sound-event layer: sound_event(id) img 0x1E4F0 - ids 0..0x58 and negatives
  to -0x23, priority byte table DS:4668, handler queue DS:7062 (4-byte far ptrs, count
  DS:46CE), fixed vectors DS:46C2/46C6/46CA (engine default 07:xx installed img 0x1EC49).
* MUSIC.8C1 = 20 BPE chunks, 60457 B decoded - song data in the AdLib driver's own format;
  ~60 KB of OPL event streams.  Chip: AdLib OPL2 (YM3812), 2-op FM - the sound quality
  ceiling of the ORIGINAL driver, not of the interface.

REPLACEMENT PLAN (music project, phase 2+): write an "IFGM MIDI" TSR implementing the same
INT F0 contract, translating music/sfx commands into MPU-401 UART writes (port 0x330) - DOSBox
renders them via a modern synth/SoundFont OUTSIDE the 640K box (Staging: mididevice, fluidsynth).
Accept and ignore the engine's music-data handoff; our tunes live in our own files.  Remaining
unknowns before implementation: exact AH=0A/0C argument semantics (song numbering), and whether
SFX should stay on OPL (probably yes - keep AH=0C forwarding to a minimal OPL voice, or chain to
the original driver for SFX only).

### Merchants & the tavern economy (spike, 2026-08-27, live-verified with the user)
- **Taverns are RUMOR VENDORS**: the "?" click buys information for 100-200 jade. When the party
  cannot afford it, the keeper says XT text 0x5E "Come back later. A little richer, if possible!"
  (0.7XT index 0x5E, adjacent to the temple taunt 0x5F). User-verified live: with injected jade the
  "?" purchases deducted 100-200 each; with the stock 8-32 jade purses the refusal is permanent -
  which is why merchants seemed absent for ~100 hours.
- **A full item BUY/SELL shop exists in code** (seg 1743, ~0x0700-0x0960): haggle formula with a
  -10%/point modifier from [0x7008], prints shop strings ("I will buy it for N Jades", YES/NO via
  the picker at 1743:03B1), pays into char +0x10 money, increments a per-item counter at
  [0x700C+...] feeding the "important customer" line. WHICH building type reaches it: unknown.
- Building doors carry kind 1-4 -> interior scene 0xD/0xC/0xB/0xA (dispatch img 0x101F0-0x10225,
  table cs:[0x85A]); kind 3 plays song 0x17 (houses), kind 4 song 0x12 (temple). Scene id is
  stored at door-entity +0x22.
- Shop message table: [0x6D90] = DS:2ACE = entry 51 of the 88-entry far-ptr table at DS:2A02
  (verified live: 2477:2ACE -> "Do you want to buy this object ?" at DS:30DC).
- CAUTION for future readers: args to string-draw 0A4A:0241 are (farptr,x,y) - small constants
  near it are COORDINATES, not text indexes (a 0x5E coordinate cost an hour of wrong turns).
- [0x675C] is set to 1 at boot (img 0x05404) and was 1 during the refusal - the ==3 checks in
  seg 1743 are NOT the tavern gate. Meaning of 3: unknown.
- Char money display may cap at 100 visually; the memory dword holds larger values fine.
- NEXT: find the building-kind source in map data -> identify item-shop buildings (if any exist
  on the map) -> highlight taverns/temples/shops on the M-key map.

### The item shop - FOUND and user-verified working (2026-08-27 live session)
- Interior type comes from TWO tables: per-building descriptors DS:0456 (4 zones x 8 buildings,
  byte = speech<<4 | kind, 0xFF = no building) and the TYPE TABLE DS:0476 (4 zones x 4 kinds,
  signed byte). Type -2 (0xFE) = ITEM SHOP, routed at 01dc:0f6c -> 1743:1319 ([0x7052]=1).
  Derivation at 0055:079f: kind=[desc]&0xF -> [0x30C]; speech=[desc]>>4 -> [0x30E];
  [0x310] = typetable[zone*4+kind]. Zone var = [0x2E0].
- **Engine zone order is NOT element order: engine zone 2 = EARTH (the starting zone)**, probed
  live. The single vanilla shop is typetable row 0 kind 3 - i.e. NOT in Earth. Which element
  engine-zone 0 is: unverified (probe [0x2E0] after a Transference).
- User-verified live (type-table byte flipped in memory): the shop interior WORKS - selling pays
  real jade; BUYING works via a click-region on his goods (stock = what he has acquired,
  a buy-back economy); the merchant has no dialogue BY DESIGN (speech nibble 15 on shop
  buildings, including the vanilla one).
- Planned mod (user-approved concept, awaiting go): **zonemerchants** - every zone already has
  exactly one kind-3 building; setting typetable[z][3]=0xFE for the three shopless zones gives
  one merchant per zone. 3 data bytes in DGROUP init (img 0x1FD40+0x476+z*4+3).
- Found jewelry is BLANK: world drops roll variant 0 (no spell) for rings/sceptres - probed a
  live party: found ring/sceptre variant 0, creation RESTORE ring variant 18. The loot
  generator never enchants; candidate future mod at the drop-creation site (tier tables
  DS:1C0F/1C3F per mod_startgear notes).
