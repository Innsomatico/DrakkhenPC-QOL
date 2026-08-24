"""Extract the 32x32 world grid from map_src.png and render an 8x6-px-per-tile preview.
Outputs: mapgrid.json (terrain/lake/road/river per tile + icons), map_preview.png (4x zoom)."""
from PIL import Image; import numpy as np, json
im = np.array(Image.open('map_src.png').convert('RGB')).astype(int)
P = 64
SNOW, FOREST, PLAIN, DESERT, WATER = (255,255,255), (16,77,48), (48,109,16), (215,182,150), (16,77,231)
ROAD = {'S': (48,109,16), 'F': (199,170,138), 'P': (144,160,176), 'D': (20,85,52)}
TCOL = {'S': SNOW, 'F': FOREST, 'P': PLAIN, 'D': DESERT}
def near(px, c, tol=40): return abs(px - np.array(c)).sum(-1) < tol

# hand-labelled icons from the map's own captions (tile x, tile y)
ICONS = {
 'castle':  [(9,3), (5,10), (25,12), (12,19), (22,28), (6,31)],
 'ruin':    [(26,3), (30,19)],
 'shrine':  [(2,2), (16,11), (21,18), (0,29)],
 'tele':    [(0,0), (0,11), (31,11), (0,17), (31,20), (31,31)],
 'inn':     [(8,20)],
 'village': [(22,0),(24,0),(28,0),(19,1), (7,13),(27,13),(29,13),(31,13), (1,21),(4,21),(6,21),(10,21), (3,27),(9,30),(20,30),(23,30)],
 'ring':    [(17,0),(23,1),(28,1),(3,4),(19,5),(29,5),(24,6), (1,9),(8,10),(4,13),(6,13),(16,13),(22,13),
             (9,19),(14,18),(12,20),(18,19),(20,20),(21,21),(26,20), (0,24),(5,25),(25,25),(10,27),(15,27),(7,30),(11,30),(13,30),(27,30),(30,30)],
 'star':    [(2,28)],
 'furrow':  [(16,17),(16,18),(16,19),(16,20),(16,21),(16,22)],
}
ICON_AT = {xy: k for k, v in ICONS.items() for xy in v}

# plains road colour: sample from a known plains road cell
c = im[(19+1)*P+3:(19+2)*P-3, (1+1)*P+3:(1+2)*P-3].reshape(-1,3)
from collections import Counter
for col, n in Counter(map(tuple, c)).most_common(4):
    if not near(np.array(col), PLAIN, 30) and not (col[0]>150 and col[1]>180 and col[2]<120): ROAD['P'] = col; break
print('plains road colour', ROAD['P'])

grid = {}
for ty in range(32):
    for tx in range(32):
        cx, cy = tx+1, ty+1
        full = im[cy*P+3:cy*P+P-3, cx*P+3:cx*P+P-3]
        flat = full.reshape(-1, 3)
        land = {k: near(flat, v, 30).sum() for k, v in TCOL.items()}
        t = max(land, key=land.get)
        water = near(flat, WATER, 30)
        wfrac = water.mean()
        # river = horizontal/vertical band crossing the cell; lake = blob
        wm = water.reshape(full.shape[:2])
        rowsfull = (wm.mean(1) > 0.9).sum(); colsfull = (wm.mean(0) > 0.9).sum()
        river = 0
        if rowsfull >= 8: river |= 0b1010   # E|W band
        if colsfull >= 8: river |= 0b0101   # N|S band
        lake = wfrac > 0.15 and river == 0 and (tx, ty) not in ICON_AT
        road = 0
        def band(side):
            y0, x0 = cy*P, cx*P
            if side == 'N': return im[y0+2:y0+9, x0+22:x0+42]
            if side == 'S': return im[y0+P-9:y0+P-2, x0+22:x0+42]
            if side == 'W': return im[y0+22:y0+42, x0+2:x0+9]
            if side == 'E': return im[y0+22:y0+42, x0+P-9:x0+P-2]
        for i, s in enumerate('NESW'):
            b = band(s).reshape(-1, 3)
            if near(b, ROAD[t], 35).mean() > 0.25: road |= 8 >> i
        if (tx,ty) in ICON_AT:
            if road & 0b1010 and (road & 0b1010) != 0b1010: road |= 0b1010
            if road & 0b0101 and (road & 0b0101) != 0b0101: road |= 0b0101
        grid['%d,%d' % (tx, ty)] = dict(t=t, lake=bool(lake), road=road, river=river, icon=ICON_AT.get((tx, ty), ''))
json.dump(grid, open('mapgrid.json', 'w'), indent=0)

# ---------- preview render at 8x6 per tile, then zoom 4x ----------
TW, TH = 8, 6
PAL = {'S': (236,236,236), 'F': (24,84,48), 'P': (64,128,32), 'D': (214,180,140), 'W': (24,72,200)}
ROADC = {'S': (120,120,120), 'F': (190,160,120), 'P': (170,170,170), 'D': (90,80,60)}
img = Image.new('RGB', (32*TW, 32*TH))
px = img.load()
def put(x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height: px[x, y] = c
for ty in range(32):
    for tx in range(32):
        g = grid['%d,%d' % (tx, ty)]
        base = PAL[g['t']]
        for y in range(TH):
            for x in range(TW): put(tx*TW+x, ty*TH+y, base)
        if g['lake']:
            for y in range(1, TH-1):
                for x in range(1, TW-1): put(tx*TW+x, ty*TH+y, PAL['W'])
        rv = g['river']
        if rv & 0b1010:
            for x in range(TW):
                for y in (2, 3): put(tx*TW+x, ty*TH+y, PAL['W'])
        if rv & 0b0101:
            for y in range(TH):
                for x in (3, 4): put(tx*TW+x, ty*TH+y, PAL['W'])
        rd = g['road']; rc = ROADC[g['t']]
        cxp, cyp = tx*TW+4, ty*TH+3
        if rd:
            put(cxp, cyp, rc)
            if rd & 8:
                for y in range(0, 3): put(cxp, ty*TH+y, rc)
            if rd & 2:
                for y in range(3, TH): put(cxp, ty*TH+y, rc)
            if rd & 4:
                for x in range(4, TW): put(tx*TW+x, cyp, rc)
            if rd & 1:
                for x in range(0, 5): put(tx*TW+x, cyp, rc)
        ic = g['icon']
        GL = {
         'castle': ["..#..#..", ".######.", ".#.##.#.", ".######.", ".##..##.", "........"],
         'ruin':   ["..#.....", ".#.#..#.", ".#.##.#.", ".##...#.", ".#..#.#.", "........"],
         'village':["...##...", "..####..", ".######.", "..#..#..", "..#..#..", "........"],
         'shrine': ["...#....", "..###...", "...#....", "..###...", ".#####..", "........"],
         'tele':   ["...#....", "..#.#...", ".#...#..", "..#.#...", "...#....", "........"],
         'inn':    [".######.", ".#....#.", ".#.##.#.", ".#.##.#.", ".######.", "........"],
         'ring':   ["...##...", "....#...", "..####..", ".######.", ".######.", "..####.."],
         'star':   ["...#....", ".#####..", "..###...", ".#...#..", "........", "........"],
         'furrow': ["...#....", "........", "...#....", "........", "...#....", "........"],
        }
        IC = {'castle': (255,255,255), 'ruin': (200,200,200), 'village': (0,0,0), 'shrine': (255,240,80),
              'tele': (0,255,255), 'inn': (255,200,0), 'ring': (255,200,0), 'star': (255,40,40), 'furrow': (255,255,255)}
        if ic:
            for y, row in enumerate(GL[ic]):
                for x, ch in enumerate(row):
                    if ch == '#': put(tx*TW+x, ty*TH+y, IC[ic])
img.resize((img.width*4, img.height*4), Image.NEAREST).save('map_preview.png')
print('wrote map_preview.png', img.size)
