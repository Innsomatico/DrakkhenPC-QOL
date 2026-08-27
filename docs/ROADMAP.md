# Drakkhen mod roadmap

Feature backlog with feasibility. **Keep this file current — edit sections in place, don't append
duplicates.** Engine facts belong in `NOTES.md`; how-to-write-a-mod belongs in `MODDING.md`.

Effort scale: **S** = under an hour, **M** = a few hours, **L** = a day+, **XL** = open-ended research.
Confidence = how sure the approach is, before the research is done.

---

## Done

| # | Feature | Cost |
|---|---|---|
| 1 | Compass in the viewport, needle tracks heading | 117 B engine |
| 2 | World map on `M`, flashing party marker | 230 B engine + `MAP.DRK` |
| 3a | Spell/phial runes → readable Latin letters | **0 B engine** (data patch, verified in game) |

Engine dead space: 758 B total, 347 B used, **400 B free**. Data patches cost none of it.

---

## Dropped

### 3b. Mana cost shown next to each spell — **dropped** (user's call, 2026-08-23)
Not worth a custom renderer. The cost data is found and recorded in `NOTES.md` (byte +8 of the
14-byte record at `DS:08C4`) if this is ever revisited.

Cheap fallback if it comes back: the font covers A..Y, and **I, V, X are all in it**, so a roman
numeral needs no new glyphs and no renderer. Each record's name is a far pointer at +0, so repointing
it at a new string in dead space gives "HEALMIN I" / "IMPROV XV" for ~200 of our 400 bytes. Unverified
risk: the HUD slot may truncate names at 7 characters — check the draw routine before committing.

---

## Requested — not started

### 4. Music replacement (SNES tracks) — **not recommended**, effort XL, confidence low
**Correction:** an earlier note here claimed the game emits MIDI. It does not. `MIDI:Opened
device:win32` in DOSBox's log is DOSBox initialising its own MIDI subsystem at startup, whether or
not the game uses it. All three `DRDRIVER.?C1` sound drivers reference **port 388h (AdLib/OPL2)** and
**220h (Sound Blaster)**, and the engine itself drives ports 61h/42h/43h (PC speaker). No MPU-401
(330h) reference exists anywhere.

Consequences:
- A SoundFont / VirtualMIDISynth does **nothing** — there is no MIDI stream to re-synthesise.
- MP3/FLAC are impossible: a 1990 DOS game with <5 KB heap headroom cannot stream audio.
- Replacing the score means authoring **OPL2 FM register data in Drakkhen's own sequence format**
  (`MUSIC.8C1`, 20 chunks, unreversed). And 2-operator FM cannot reproduce SNES sample-based music
  in any case, so even full success sounds nothing like the source.
- Only marginal option: a DOSBox build with better OPL emulation (Staging/ECE, nuked OPL3) instead of
  GOG's 0.74. Small gain, may upset the GOG launcher.

### 5. Extend leveling past the cap — effort **L**, confidence medium
Research so far: XP = dword at char+0x14; award formula found (damage-proportional share of the
victim's XP pool). Still missing: the level field, the threshold table/formula, and what the cap
actually is. Stats are the six bytes at +0x42..+0x47 (8..16 observed) — byte-wide, so 255 hard cap.
Level-up UI strings are messages 0-3 of the DS:2A02 table; tracing their reader finds the level code.

### 6. Regen mode — **DROPPED** (user's call, 2026-08-23)
Three versions deep, each fixing a real layer, and it still crashed on the deploy->pack transition:
v1 spliced what proved to be the outdoor-DEPLOYED loop (boosted the wrong mode; stock regen never
runs in the packed world view at all — memprobe-verified). v2 chained the 19F7:09A9 world-view hook
and provably regenerated (live counters showed the mod's reset value) — but silently: nothing in the
packed view repaints the MP gauges, so the UI stayed stale. v3 granted through the engine's gain-MP
fn (0A4A:06F8) and force-called the per-char gauge redraw (near fn 0A4A:08D6 via a retf-trampoline);
the user's session crashed when packing characters and the interaction was judged not worth further
cycles. `mod_regen.py` (excluded from the build) and the research below survive if ever revisited:
regen internals fully mapped in NOTES.md (countdowns, rates, gain fn, gauge-redraw chain, dirty
flags). The unexplained part is only the pack-transition crash.

### 7. Item names — **built, awaiting user confirmation** (2026-08-23)
`mod_itemname.py`, 125 B. Wraps the inventory name draw: after the generic name, items of type
sceptre/phial/ring/rod with variant byte 1..23 get the matching SPELL NAME drawn beside them (reuses
the spell-name strings already in DS - zero new string data). Variant 0 (e.g. empty phial) or out of
range draws nothing. The variant=spell-index hypothesis is unconfirmed until the user sees a real
ring/staff labeled; if the labels are wrong, the mapping (not the mechanism) needs adjusting.

### 8. Bigger spell target area (~2×) — **parked** (user's call, 2026-08-23), effort L, confidence medium
Research so far (2026-08-23): the spell record is now fully decoded — +8 MP, **+9 damage/heal
amount** (user's warning was right that damage lives here; it is now identified and will not be
touched), +11 status-effect ID, +13 animation. **The record holds no geometry**, so the target size
is hard-coded in the hit test. Damage application found (img 0x7B05 applier); the geometric gate
that decides whether a cast hits is upstream of it and not yet located. Candidates eliminated:
01DC:0756 (sprite blit), the 0055 seg `cmp ax,0xF` (party-member hit window), 02DE world handler
`cmp ax,0x7A` (scripted-location heading check). Next: trace callers of the applier wrappers
(img 0x7BA9..0x7C3E) backwards to the collision compare.

### 9. Numeric HP/MP on character portraits, red at <=20% — effort **L**, confidence low
Original goal #4, never started. User already flagged it as the riskiest of the first four and
accepted it may never ship. Needs the same digit renderer that got MP display (3b) dropped, plus
per-character HP/MP field offsets and four more draw sites. Shares all its research with 5, 6 and 9.
Reconsider only after the character record layout is mapped.

### 10. Patcher / distributable — **DONE** (2026-08-23)
`../DrakkhenQOL/` = `install.ps1` + `README.txt`, generated by `make_patcher.py` from
`patcher_template.ps1`. Single self-contained PowerShell file (~61 KB): verifies the customer's
files are stock US GOG by SHA256, backs them up, REBUILDS the modded files from the customer's own
data (embedded C# port of the BPE codec + a 4.3 KB sparse diff + the 80 B font block + MAP.DRK,
which is our artwork) and verifies the result byte-for-byte before committing. No Infogrames data
distributed. `-Restore` uninstalls. Tested: fresh install (byte-identical to reference), re-run
no-op, restore, wrong-version abort. **Regenerate after every mod change:**
`python drakmod.py && python make_patcher.py`.

### 11. Party-shared XP — **built, awaiting user confirmation** (2026-08-23)
`mod_partyxp.py`, 61 B. Both kill-award sites spliced; every living member gets amount/4, the killer
also gets the /4 remainder (no XP lost with a full living party), dead members' shares are lost.
Scripted/event rewards (third site, img 0x15916) intentionally stay personal.

### 12. Bow buff (was: "Longbow") — **DONE** (2026-08-23)
User wanted a second, stronger ranged weapon. Research found the full item catalog (6-byte records:
flags, tier, power, id, price - NOTES.md) and that the bow ships as the weakest weapon in the game
(power 6 = bludgeon, vs sword 8 / sabre 32 / drags 55). A true new "Longbow" id is architecturally
possible (spare ids 0x45/0x46, catalog row fits at DS:204E, pair-emission mechanism exists) but the
id-indexed tables at DS:1B38..1CFD are PACKED edge-to-edge, so a new id means relocating tables and
patching every reader, plus unresearched drop tables - user chose the fallback: `mod_bow.py` patches
the bow's own catalog record to power 8, price 12 (v2 - 12 was too strong in play). Every bow
bought or dropped from now on uses it;
bows already sitting in a save keep their old copied stats (drop/rebuy to upgrade).

### 13. Quest journal — researched, DESIGN READY, effort M (v1) / L (v2)
User supplied the authoritative 15-step walkthrough (see NOTES.md) and wants a journal that shows
completed + current steps and HIDES future ones (no spoilers).

**Design (v1, cheap):** the map mod already proves the pattern - a pre-rendered 256x128 image blitted
into the viewport from an external file, one INT 21h row-read at a time, no heap. So render the 15
journal lines OFFLINE into `QUEST.DRK` (our own text, our own font, laid out exactly as we want), and
at runtime **read only the first N rows** - stopping early is what hides unseen steps. Reuses
mod_map's proven loop almost verbatim; ~80-120 B of engine code, and the text costs zero engine space.

**Blocker for auto-progress (v2):** N must come from somewhere. The DS:6F38 counters are the right
shape (per-location, incremented on story interactions) but the index->step mapping cannot be derived
statically. Closing it needs memprobe snapshots at known walkthrough points during a real playthrough.
**Ship v1 with a manual/heuristic step first; add auto-detection once the mapping is observed.**

### 14. Clearer dialogue English — effort M, confidence high, NOT started
User's point: the original prose is cryptic even in-game ("Gems are tears"), so a journal that quotes
it faithfully just relocates the confusion. The .7XT files are loose, uncompressed and directly
editable (high-bit ASCII, NUL-separated). Same-length rewrites are trivial; different lengths need
the offset table rebuilt. Hard limit: **40 chars per line** (DS:5426 stride 0x28). Highest-value
targets are the lines that name a destination or a required action.

### 15. Ring/sceptre effects wired — **DONE, user-verified** (2026-08-25)
Research: worn rings were INERT in stock (live-probed: no flag changes). The engine ships seven
passive-effect flags its sheet lister names (Power/Invisibility/Acceleration/Understanding/
Recuperation/Protection/Impalpability) and its regen code honors - nothing ever set them.
`mod_ring.py` (170 B): both regen call sites wrapped; equipped rings/sceptres (variant = spell idx)
map to effects: INVISIB->Invisibility, STRENGH->Power, LANGUAG->Understanding, SHIELD->Protection,
SPEED->Acceleration, RESTORE->Recuperation (2x regen), TELEPOR->Impalpability. Stateless per tick.
User confirmed Recuperation (regen doubles, shows in ability list after sheet reopen) and
Invisibility in play. Sheet refresh on equip is a known cosmetic lag. Stat+2 rings from the SNES
guide: judged not worth the code (user's call).

### 16. Starting equipment — **SOLVED, bow shipped** (2026-08-26)
GOAL (user): new characters born with gear - SCOUT +bow, MAGICIAN +RESTORE ring. NOT a save edit.

**Root cause of every earlier dead end: DRAKM.CC1 contains TWO MZ executables.**
`chunks[0]` (34 KB, DGROUP 0x06B8) is the **character creator**; `chunks[1]` (149 KB,
DGROUP 0x1FD4) is the game engine. `drakmod.Builder` only ever loaded chunk 1, so the two
rounds spent patching the engine's weapon tables (DS:1AF3 in DRAKTJ, then DS:1C3F in DRAKM)
could never have worked - those tables drive random loot, and the creator is a different
binary that carries its own copy of the item catalog.

Full map of the record layout, the save format, the creator's catalog and the grant code is in
**NOTES.md, "Character creation and starting equipment"**. Short version:

- Party = 4 records x 0x19A at DS:5A2E. Item array at record **+0x64**, 8 slots x 6 bytes.
  Slots 0/1 are the innate attack/defence slots the monster spawner fills; player gear starts
  at slot 2, which is why `find_free_slot` was a red herring.
- PERSO.SAV: `buf[i] ^= i & 0xFF`, then `buf[4..0x66B]` -> DS:5A2E, so **file offset 4 is
  character 0**.
- The grant is four/three 27-byte blocks in chunk 0 at img 0x02DBC..0x02F60, each a plain
  6-byte `memcpy(creator_catalog_record, record + slot_offset)`. Changing a class's starting
  item is a two-byte edit of one `mov ax,imm16` operand. Entry points: fighter 0x02DB9,
  scout 0x02E3C, priest 0x02EA4, mage 0x02F0C.
- The creator catalog (chunk-0 DS:0DA4) stores price `01 00` on every record - that, not any
  code, is why every starting item in a save has byte 4 = 01.

SHIPPED: `mod_startgear.py` repoints the scout's weapon from the dagger (DS:0E8E) to the bow
(DS:0EB8) and raises the bow's power 6->8 in the creator's catalog so it agrees with `mod_bow`
(the creator has its own catalog; mod_bow's edit to the engine copy does not reach a starting
item). Installer key `startgear`, depends on `bow` for the "arch" -> "bow" rename.

PROOF (`verify_startgear.py`): loads chunk 0, applies its relocations and **executes** each
class's gear routine under unicorn against a blank record. On the STOCK binary the emulated
output reproduces a real PERSO.SAV byte-for-byte for all four characters - and independently
recovers the creation order. On the patched binary the scout's slot 4 becomes
`2f0108410100` (bow, power 8) with every other class untouched and shoes still shared by all
four. The generated installer, run on stock files, reproduces the reference build exactly.

TOOLING: `Builder.img0` now exposes chunk 0; chunk-0 edits journal to fragments.json as
`writes0` and are applied by `fragsim.apply_writes0`, `install.py apply_creator_fragments`
and `install.ps1 Apply-CreatorFragments`. No relocation bookkeeping is needed there because
these edits are immediate operands. `probe_startgear.py` was deleted - it targeted chunk 1.

ALSO DONE - the MAGICIAN's RESTORE ring (`mod_startring`, installer key `startring`, depends on
`ring`). Rings are not catalog items, so this needed a synthesised record plus somewhere to put
it. Both problems solved without adding code: the creator's catalog is private and chunk 0 has no
computed indexing into it, so 37 of its 47 records are provably unreachable (222 B of dead space),
and a grant block's byte COUNT is an immediate - widening the magician's last block to 30 bytes
over `[rod][zeros x3][ring]` lands the rod where it already went and the ring in the magic-item
array at +0x94. Emulation confirms the magician keeps shoes/robe/rod and gains a worn
`8f 12 60 07 00 00` RESTORE ring. Full detail in NOTES.md, "Magic items".

ALSO DONE - gear is EQUIPPED at creation (`mod_startworn`, installer key `startworn`, no deps).
Stock creation sends the party out naked with the gear in the inventory. TWO fields are needed:
bit 7 of an item's flags byte (worn - lights it up in the inventory), AND record +0x56, the slot
index of the HELD WEAPON (0x7F = empty handed), which is what actually puts a weapon in someone's
hands. v1 set only bit 7 and the user correctly reported "inventory looks on, but no one is
holding their weapons"; confirmed live with probe_equip.py against a hand-re-equipped character.
The creator's four +0x56 writes are an unrolled loop over PARTY SLOTS, not classes, so the
fighter's buckler/sword destinations are swapped to put every class's weapon in slot 4 and all
four writes become 4. Runs last in the build so it also catches the bow and the
startring pool. `verify_startgear.py --matrix` proves all 7 combinations of the start* mods.

### 17. Steam version support — **DONE** (2026-08-25)
The Steam release = GOG stock with exactly ONE byte changed per engine (.CC1): Steam's own
copy-protection skip (jne->jmp at decoded offset 0x11D87 in DRAKM), with .BAK files = untouched GOG
stock. Both installers now: auto-detect the Steam `game/` subfolder layout, recognize the Steam
DRAKM hash, normalize that byte back to stock before applying the diff (output byte-identical to
the GOG reference), and restore returns the STEAM original. Unknown-hash failures now print the
found vs known hashes and where to report them. Verified on the user's real Steam install.

### 18. Mod-selection installer — **DONE** (2026-08-25)
Both installers now install a user-chosen SUBSET of mods. Build side: drakmod.build() journals each
mod's exact contribution (image write-runs, relocation adds/drops/repoints) to fragments.json;
make_patcher embeds it plus a moddef list (key, label, deps). Install side: fragment applicator +
runtime relocation-table rebuild (stock entries minus drops, with repoints, plus adds in canonical
order). Full selection is verified byte-identical to the reference build; partial selections are
structurally verified (hash check inherently unavailable for 2^n combos). Deps auto-enabled:
map->compass, hints->map+noprotect, ring->noprotect. UI: PowerShell = WinForms checkbox dialog with
Check-all (plus -All / -Mods key,list); Python = numbered console checklist (plus --all / --mods /
--list). Verified: full --all == reference on both; PS and PY partial builds byte-identical; a
partial build (compass,map,bow,vga) boot-tested in game - and the user independently confirmed the
unselected itemname mod was absent, i.e. selection observably works.

---

## Suggested order

0. **User confirmations pending**: item names (7) — needs a ring/staff in inventory.
1. Regen (6) dropped; party XP (11) confirmed working by the user.
2. **Leveling** (5) / **item names** (7) / **portrait HP/MP** (9) — record research is now largely done
   for characters (see NOTES.md); item records still unmapped.
3. **Party-shared XP** (11) — ready to build on the user's go-ahead.
4. **Spell target size** (8) — parked; resume from the applier callers.
3. **Leveling** (5), **item names** (7), **portrait HP/MP** (9) — all gated on record-layout
   research; do that research once, since they need the same character/item structures.
4. **Patcher** (10) — last, once the feature set is settled.

Music (4) is not recommended. MP display (3b) is dropped.
