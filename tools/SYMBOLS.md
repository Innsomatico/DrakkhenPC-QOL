# Drakkhen engine symbol map

Named addresses recovered by reverse engineering. `img` = linear offset into the decoded
DRAKM.CC1 chunk-1 image (MZ header 0x2A00 stripped; DGROUP = 0x1FD4, data base img 0x1FD40).
`com:` = DRAKKHEN.COM address (file offset + 0x100). See NOTES.md for the deep dives.

## Character record  (party: 4 x 0x19A bytes at DS:5A2E; monsters/NPCs: DS:60E6)

| offset | symbol | notes |
|--------|--------|-------|
| +0x00  | name | 6 chars + NUL |
| +0x0C..+0x0F | effect_flags | passive-effect bits (mod_ring writes these) |
| +0x10/+0x12 | **jades** | money, 32-bit little-endian per character |
| +0x37  | class_mask | 1 fighter, 2 scout, 4 mage, 8 priest (bitmask, not index) |
| +0x38  | class_group | fighter 6, scout 6, mage 1, priest 1 |
| +0x3B  | class_mask_monster | used by monster records; 0 for party |
| +0x46..+0x4B | stats | STR CON INT nnn nnn nnn (6 bytes, mod_levelup grows) |
| +0x4F/+0x51 | HP_max / HP_cur | **HP_cur == 0 means dead** |
| +0x53  | level | temple fee = level^3 x5 heal / x20 revive |
| +0x56  | held_weapon_slot | item-slot index of wielded weapon; 0x7F = empty-handed |
| +0x57  | held_other? | stays 0x7F even with shield worn |
| +0x5B/+0x5C | MP_max / MP_cur | |
| +0x64  | items[8] | 6-byte records; slots 0/1 = monster innate atk/def, players start slot 2 |
| +0x94  | magic_items[8] | rings/sceptres/phials live HERE, not in items |
| +0xC4  | third_array[8] | |

Item record: `[0]flags (bit7=worn, bit5=weapon, low nibble=class mask) [1]variant/spell
[2]power [3]id [4..5]price`. Magic item: id from DS:1BF9[type], byte2 = (type<<5)|arg, price 0.

## Engine data  (DS:xxxx, add 0x1FD40 for img)

| DS | symbol | notes |
|----|--------|-------|
| 02DC..032B | save_globals | PERSO.SAV file+0x66C..0x6BB (XOR i&0xFF); position, zone state |
| 08C4 | spell_table | 23 x 14B: name-ptr, +4 ?, +5 MP cost?, +9 class/level?, +13 effect id |
| 1958/19C4 | filename_tables_orphan | provably unreachable - the mod dead-space pool |
| 1A30/1A9C | filename_tables_live | selected by DRK1[0]==5 -> 1A30 (img 0x53E8) |
| 1BF9 | magictype_to_id | 04 05 06 07 42 43 |
| 1C0F / 1C3F | loot_tiers_armour / _weapons | 8x6 catalog indices; loot only, NOT starting gear |
| 1CBB | id_to_nameindex | item id-4 -> name ordinal |
| 1F34 | item_catalog | 47 x 6B, bow last (#46); item code = index+4, weapons code 0x2B+ via 201E |
| 2A46.. | item_name_block | packed NUL-separated, ordinal-walked ('jade coins' 2E48, names 3042..) |
| 5A2E | party | see record above |
| 53F4 | save_marshal_bufptr | far ptr to save staging heap |
| 60D8 | filename_table_ptr | far ptr, -> 1A30 |
| 67D0/67D2 | current_char_ptr | far ptr = 5A2E + i*0x19A |
| 679E | zone_id | 0x0F outdoors -> 0x0E inside temple (observed live) |
| 67A0 | zone_sub | save byte & 0xF |
| 6CF0 | current_char_index | |
| 6D7C | ui_char_flag | |

## Engine functions  (chunk 1)

| img | seg:off | symbol | notes |
|-----|---------|--------|-------|
| 0x02A98 | - | **temple_service(char_idx)** | fee = lvl^3 x5/x20 (imm at 0x2ADA/0x2AF1, mod_freetemple zeroes); fail -> text 0x5F |
| 0x039xx | - | priest_dialogue | pays info-donation via pay_richest from table [0x50A+zone*2] |
| 0x0AC9B | 0A4A:07FB | fee_scale(a,b) | level-scaled cost helper (4 callers) |
| 0x0ACC1 | 0A4A:0821 | **pay_richest(amount32)** | richest pays; 0xFFFF if unaffordable; only temple+donation call it |
| 0x0B373 | 0B20:0173 | find_free_magic_slot | scans +0x97 ids |
| 0x0B3AA | 0B20:01AA | find_free_item_slot | scans +0x67 ids, 8 slots |
| 0x0B6xx | - | equip_toggle | xor worn bit; if weapon (bit5) sets held_weapon_slot +0x56 |
| 0x14AB8 | - | make_magic_item(type,variant,arg) | builds ring/phial record into +0x94 |
| 0x14B65 | 1435:0815 | **give_item(charptr,src,qty)** | memcpy 6B into free item slot; 4 callers (loot/shop) |
| 0x0CA20 | - | loot_gear_roll | tier tables 1C0F/1C3F -> give_item |
| 0x181A2-ish | - | shop_buy | subtracts price from current char |
| 0x04384.. | - | save_load(PERSO.SAV) | XOR, 0x7CA size check, maps file->DS (see NOTES) |
| 0x0580A | - | party_zero_init | 4 records, clears +0x3B |
| 0x19FFC | - | fkey_handler | F1..F6 -> cs:[60AE/60AF] pairs (consumed by driver) |
| 0x0F191..0xF359 | 0D7E:19B1 | copyprotect_carcass | dead once mod_noprotect; code-mod pool |

## Character creator  (DRAKM.CC1 chunk 0; MZ header 0xA00, DGROUP 0x06B8)

| addr | symbol | notes |
|------|--------|-------|
| img 0x00B7B | class_select_jumptable | stores mask 1/2/4/8 to [char+0x37] |
| img 0x02DB9/2E3C/2EA4/2F0C | gear_fighter/scout/priest/mage | 27B memcpy blocks; source imm = catalog rec |
| img 0x02C34/2CAE/2D2B/2DA8 | held_weapon_init x4 | unrolled loop over PARTY SLOTS; imm 0x7F (startworn -> 4) |
| DS:0DA4 | creator_catalog | private 47-rec copy, price byte = 01; 37 recs provably dead (mod pool) |
| DS:217C | edited_char_ptr | |

## Launcher  (DRAKKHEN.COM - see NOTES "The launcher")

| com | symbol | notes |
|-----|--------|-------|
| 0x01C3 | menu_jump_table | 5 words (menu4 renumbers) |
| 0x040A | menu_text_block | drawer language: 0D nl, 24/00 end, 03 skip, 04 attr, 05 reset, 02 RLE |
| 0x1466 | stipple_fill | mov cx,780/mov ax,07B1/rep stosw (attr byte = menucolor field) |
| 0x148E | block_drawer | row stride 0xA0; default attr imm at 0x14BB (menucolor text) |
| 0x1193 | config_load | Config.tat -> 0x1A50 whole; [0x151]=end -> SELF-SHRINK int21/4A at 0x1215 |
| 0x0FB6 | startup entry | via jmp at 0x100 |
