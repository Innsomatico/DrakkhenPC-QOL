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
the bow's own catalog record to power 12, price 16. Every bow bought or dropped from now on uses it;
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

### 16. Starting equipment — STILL OPEN, large trace; findings + dead ends below
GOAL (user, unchanged): new characters born with gear - SCOUT +bow, MAGICIAN +RESTORE ring.
NOT a save edit. The user's own save already has them; this is for everyone else.

CONFIRMED FACTS
- Observed starting gear (from a real fresh save): fighter shoes/jacket/buckler/sword
  (catalog idx 4,8,0x22,0x2C), scout shoes/leather/dagger (4,9,0x2B), magician shoes/robe/rod
  (4,0x14,0x30), priestess shoes/robe/bludgeon (4,0x11,0x31). All are catalog records copied with
  the price byte replaced by quantity 1 - there is NO separate starting-gear record template
  anywhere in either binary (searched for every gear record with qty=1: no hits).
- Catalog bases: DRAKM DS:1F34 (idx 4..0x2A) + DS:201E (idx 0x2B..0x32);
  DRAKTJ DS:1DE8 + DS:1ED2. DRAKTJ DGROUP file base = 0x22DF0.
- **DRAKTJ (the creator) does NOT build inventory**: an exhaustive scan finds no 6-byte record copy
  anywhere in its creation region (0x12000-0x14000). So the grant happens in the GAME, not the
  creator - the earlier plan to patch DRAKTJ was based on a wrong premise.

RULED OUT (do not re-investigate)
- DS:0D00 (0x1C stride) - creation spec: names/stat-template/MP class/sprites, no gear.
- DS:1AC3 (DRAKTJ) / DS:1C0F (DRAKM), 8 rows x 6 - per-class ARMOUR/WEAPON TIER lists (helmet
  tiers etc., used by shops+loot), not starting gear.
- DS:187A - signed coordinate deltas. The 0x1AC3-indexing sites at DRAKTJ 0x0F110/0x1A670 and
  DRAKM 0xCA20 are all SHOP buy/sell paths.
- give-item 140D:0819 (DRAKTJ) / 1435:0815 (DRAKM): all 4 callers are shop code.

BREAKTHROUGH (2026-08-25, later): the grant IS in DRAKTJ after all - the earlier "no inventory
writes" conclusion was wrong because the copy goes through a helper, not literal offsets.
- **give-item helper = DRAKTJ img 0x170E9**: takes (char_far, item_record_far, qty); finds the
  first free slot via 0xB11:01AF, memcpy's 6 bytes to `record + 0x64 + slot*6`, then sets byte +5
  to the qty argument (which is why starting gear = catalog record with price replaced by qty 1).
  Four callers: 0x17361, 0x1744F (shop buy paths) and **0x17CAA, 0x17D64 (the auto-grant)**.
- **STARTING-WEAPON TABLE = DS:1AF3**, 8 rows x 6 bytes, values are indices into catalog2
  (DS:1ED2). Decoded:
    row0 dagger x6      row1 sword,sword,sword,swordlg,swordlg,sabre
    row2 bludgeon x6    **row3 BOW x6**      row4 rod x6
    row5 sword..sabre   row6 sword..drags    row7 dagger/sword mix
  Observed fresh-party weapons map to rows: fighter->1, scout->0, magician->4, priest->2, so the
  row is class-derived and **row 3 (all bow) already exists** - the mechanism we want is shipped.
- Armour/other gear uses the sibling site at img 0x17D35 with table **DS:1AC3** (also 8x6) into
  catalog1 (DS:1DE8).
- The column index is `rand(4) + [0x5F06]/2` (a stat), i.e. better stats -> better starting tier.

REMAINING UNKNOWN (do this first next time)
How the ROW is selected: it comes from the return of `lcall 161C:0342` at img 0x17C50, which
disassembles as drawing code - the disassembly is mis-aligned there, so re-disassemble that
function from a known-good entry. Once row<-class is proven, the feature is a ONE-BYTE-PER-ENTRY
data patch: set the scout's row to 07 (bow) - no code, no dead space.
CAUTION: do not guess the row mapping and ship it; if a row is shared between classes the wrong
class starts with a bow.

NOTE ON THE RING: rings are NOT catalog items (the catalog starts at shoes), so a starting RESTORE
ring cannot come from this table at all. Granting one needs a synthesised 6-byte record passed to
the give-item helper - a code hook, not a data edit. Split it from the bow half.

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
