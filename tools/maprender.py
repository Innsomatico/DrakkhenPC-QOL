"""Render ../MAP.DRK (v2) from mapgrid.json - the image the M-key map blits into the viewport.

Output: raw 256x128, one byte per pixel, game palette (GAME.7AL) indices.  32x32 tiles at 8x4 px.

v2 changes over v1 (all to make landmarks readable against every terrain band):
  * every icon is drawn with an automatic 1px DARK HALO (outline = dilate(shape) - shape).  v1 drew
    flat single-colour glyphs, so black houses vanished on the dark forest band and white castles
    vanished on snow.  With a halo, one glyph works on snow, forest, plain and desert alike.
  * icon colours re-chosen for separation: castle white, temple/shrine gold, village orange,
    ruin grey, teleport cyan, inn magenta - shapes differ too, so they read even at 8x4.
  * the "old drakkhen" money-bags (v1: big bold yellow, which dominated the map) are now a small
    GREY '?' as requested - present but quiet.
  * terrain/road/river/lake rendering is unchanged.

Run:  python maprender.py       (writes ../MAP.DRK and maprender_preview.png)
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
TW, TH, N = 8, 4, 32
W, H = N * TW, N * TH

# --- game palette indices (verified against a live 320x200 capture) -------------------
C = dict(snow=17, forest=210, plain=71, desert=56, water=93,
         dark=0,                     # halo colour
         light=16,                   # light halo, used on dark terrain
         castle=86,                  # (109,48,207) violet - white blended into the snow band
         temple=219,                 # (231,211,77)  gold
         village=53,                 # (207,134,65)  orange
         ruin=103,                   # (150,154,146) grey
         tele=120,                   # (16,207,207)  cyan
         inn=16,                     # (207,207,207) white (single tile, sits on plains)
         bag=103,                    # grey '?' - deliberately low-key
         star=38, furrow=16)
TERR = {'S': C['snow'], 'F': C['forest'], 'P': C['plain'], 'D': C['desert']}
ROADC = {'S': 104, 'F': 104, 'P': 104, 'D': 104}

# --- 8x4 glyphs. '#' = body, '.' = empty. Halo is generated, not drawn. --------------
GLYPH = {
 # castle: full-width crenellated keep - the biggest silhouette on the map
 'castle':  ["#.#.#.#.",
             "########",
             "#.####.#",
             "########"],
 # ruin: same keep, collapsed on the right
 'ruin':    ["#.#.....",
             "###.....",
             "####....",
             "#####..."],
 # village: small peaked house with a door
 'village': ["...##...",
             "..####..",
             "..#..#..",
             "..####.."],
 # temple: stepped ziggurat, widest at the base - distinct from the house
 'temple':  ["...##...",
             "..####..",
             ".######.",
             "########"],
 'tele':    ["...#....",
             "..###...",
             ".#####..",
             "..###..."],
 'inn':     [".####...",
             ".####.#.",
             ".####.#.",
             ".####..."],
 # the 32 fixed old-drakkhen sites: a quiet '?', no halo
 'bag':     [".###....",
             "...#....",
             "..#.....",
             "..#....."],
 'star':    ["..#.....",
             "#####...",
             ".###....",
             "#...#..."],
 'furrow':  ["...#....",
             "........",
             "...#....",
             "........"],
}
# icons that stay flat (no dark halo) so they read as background detail
NO_HALO = {'bag', 'furrow', 'star'}
# mapgrid.json uses 'shrine' for temples; keep the old key working
GLYPH['shrine'] = GLYPH['temple']
ICOL = dict(castle='castle', ruin='ruin', village='village', temple='temple', shrine='temple',
            tele='tele', inn='inn', ring='bag', bag='bag', star='star', furrow='furrow')


def halo(rows):
    """Return the set of cells forming a 1px border around the glyph body."""
    body = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == '#'}
    out = set()
    for (x, y) in body:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                if p not in body and 0 <= p[0] < TW and 0 <= p[1] < TH:
                    out.add(p)
    return body, out


def main():
    grid = json.load(open(os.path.join(HERE, 'mapgrid.json')))
    img = bytearray(W * H)

    def put(x, y, c):
        if 0 <= x < W and 0 <= y < H:
            img[y * W + x] = c

    for ty in range(N):
        for tx in range(N):
            g = grid['%d,%d' % (tx, ty)]
            ox, oy = tx * TW, ty * TH
            base = TERR[g['t']]
            for y in range(TH):
                for x in range(TW):
                    put(ox + x, oy + y, base)
            if g['lake']:
                for y in range(TH):
                    for x in range(1, TW - 1):
                        put(ox + x, oy + y, C['water'])
            rv = g['river']
            if rv & 0b1010:
                for x in range(TW):
                    put(ox + x, oy + 1, C['water']); put(ox + x, oy + 2, C['water'])
            if rv & 0b0101:
                for y in range(TH):
                    put(ox + 3, oy + y, C['water']); put(ox + 4, oy + y, C['water'])
            rd, rc = g['road'], ROADC[g['t']]
            if rd:
                put(ox + 4, oy + 2, rc)
                if rd & 8:
                    for y in range(0, 3):
                        put(ox + 4, oy + y, rc)
                if rd & 2:
                    for y in range(2, TH):
                        put(ox + 4, oy + y, rc)
                if rd & 4:
                    for x in range(4, TW):
                        put(ox + x, oy + 2, rc)
                if rd & 1:
                    for x in range(0, 5):
                        put(ox + x, oy + 2, rc)
            ic = g['icon']
            if ic:
                key = ICOL.get(ic, 'bag')
                rows = GLYPH.get(ic) or GLYPH[key]
                body, ring = halo(rows)
                if key not in NO_HALO:
                    # outline colour flips with the terrain so one glyph reads on every band
                    hc = C['light'] if (g['t'] == 'F' or g['lake']) else C['dark']
                    for (x, y) in ring:
                        put(ox + x, oy + y, hc)
                for (x, y) in body:
                    put(ox + x, oy + y, C[key])

    # 1px ocean frame - the source art surrounds the island with water, and without it the
    # bottom/edges read as though the map were clipped.
    for x in range(W):
        img[x] = C['water']; img[(H - 1) * W + x] = C['water']
    for y in range(H):
        img[y * W] = C['water']; img[y * W + W - 1] = C['water']

    out = os.path.join(GAME, 'MAP.DRK')
    open(out, 'wb').write(bytes(img))
    print('wrote %s (%d bytes, %dx%d)' % (out, len(img), W, H))

    # preview PNG in the real game palette, 3x zoom
    try:
        from PIL import Image
        pal = Image.open(os.path.join(HERE, 'map_palette_ref.png')).getpalette() if os.path.exists(
            os.path.join(HERE, 'map_palette_ref.png')) else None
        p = Image.frombytes('P', (W, H), bytes(img))
        if pal:
            p.putpalette(pal)
        p.convert('RGB').resize((W * 3, H * 3), Image.NEAREST).save(
            os.path.join(HERE, 'maprender_preview.png'))
        print('wrote maprender_preview.png')
    except Exception as e:
        print('(preview skipped: %s)' % e)


if __name__ == '__main__':
    main()
