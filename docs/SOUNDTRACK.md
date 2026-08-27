# Definitive Soundtrack — hunt list & slot plan

## PC side: the replacement list (fingerprinted from engine code, 2026-08-27)

MUSIC.8C1 = 20 chunks: 0-7 are instrument/SFX banks, 8-19 are MUSIC BANKS.
Banks 16-19 = the four AREA banks (Earth/Water/Air/Fire), loaded on zone entry
(selector: play_area(i) -> chunk 16+i; also chunk [DS:0310]+8 on interior transitions).
Within the loaded bank, SEQUENCE IDs pick the tune (engine: play_song(N) -> driver AH=0C).

PC track slots found in code (img = call site; * = high-confidence context label):

  seq  1  combat, monster class A        (combat picker img 0x0C8C6)
  seq  4  defeat / death jingle*         (img 0x0818F, after combat resolution w/ flag 0x40)
  seq  7  priest / interior theme*       (imgs 0x030DA 0x0344C 0x0769F; dialog region)
  seq 10  combat class B + night event   (imgs 0x0C8CA, 0x0E5D2 gated on [0xCD6])
  seq 11  common wander default*         (imgs 0x076AC 0x0EF34 0x13B5D + fallback 0x19346)
  seq 12  combat class C                 (img 0x0C8DB)
  seq 14  combat class D / special foe   (imgs 0x0C8E0, 0x08EA0 setting effect flag 0x400)
  seq 15  ?                              (img 0x0353E)
  seq 17  intro / title*                 (img 0x01617, startup-sequence region)
  seq 18  TEMPLE theme*                  (imgs 0x025D7 temple-restore loop, 0x10256)
  seq 19  post-load resume               (img 0x048D8, right after save load)
  seq 20  temple ritual A*               (img 0x022EE, temple region)
  seq 23  houses / generic indoor*       (imgs 0x0241B 0x08CF1 0x10244 0x10771; building
                                          jump table img 0x10225)
  seq 26  temple ritual B*               (imgs 0x023F4 0x0299F)
  + four AREA WANDER themes as banks 16-19 (PC has NO day/night variants)
  + computed picks: combat-by-monster-class (4 tracks), building-type table

Confirmation pass: one wander session with the instrumented driver (sndlog shows CX=seq id
live) turns every * into certainty.

REPLACEMENT MAPPING (PC slot -> SNES track): area banks -> #4/13/17/23 (+night via director),
combat family -> #9/27/28/29/31 princes + #B01 Shade of Doom, temple -> #11 ANAK,
houses -> #6/15/19/25, title -> #2, death -> #36, resume -> current area theme.

## SNES OST (36 + bonus) — the shopping list
[x] = blessed master in _music/library    [slot notes in brackets]

 1. Kemco Jingle                     (skip — Kemco logo)
 2. Title
 3. Character Making            [x]  Character Creation.mid  <- the wishlist item!
 4. Earth Area (Day)
 5. Earth Area (Night)          [x]  05 Earth Area (Night).mid
 6. House in Earth Area
 7. Lively Inn
 8. Hordkhen's Castle           [x]  Castle (Hordkhen).mid
 9. Hordkhen                         [boss fight — prince battle]
10. Bonhommes
11. ANAK                             [TEMPLE music — perfect for our free temples]
12. Transference                     [TELEPORT — the wishlist item!]
13. Water Area (Day)
14. Water Area (Night)
15. House in Water Area
16. Haaggkhen's Castle
17. Air Area (Day)
18. Air Area (Night)
19. House in Air Area
20. Naaktkha's Castle
21. Ninth Tear Allies
22. Haaggkha's Castle
23. Fire Area (Day)
24. Fire Area (Night)
25. House in Fire Area          [x]  Tent Master.mid (user: will be REPURPOSED, not used here)
26. Hazulkha's Castle
27. Hazhulkha                        [boss]
28. Naaktkha                         [boss]
29. Haaggkhen                        [boss]
30. Hazulkhen's Castle               [the FINAL castle — user wants heroic here]
31. Hazhulkhen                       [final boss?]
32. Eight Tears
33. Center of Island                 [endgame area]
34. Ending
35. Staff Roll                  [x]  Staff Roll (Ending).mid
36. Game Over
B01. Shade of Doom                   [the CONSTELLATION MONSTER — wishlist item!]

Day/night pairs per area (4/5, 13/14, 17/18, 23/24) = the day-night director feature.
Sources: snesmusic.org set (SPC), Flying Omelette transcriptions, KHInsider/VGMusic, own
conversions via the pipeline. Intake: py -3.12 _tools/normmidi.py in.mid "library/Name.mid"
