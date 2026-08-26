"""Render ../QUEST.DRK - the HINT page shown by mod_journal.py on the H key.

Reframed from a "journal" to an opt-in hint system: a header line tells the player SPACE reveals
the next hint, so spoilers are their choice. The header is part of the image and always visible.

Same trick as the map: a pre-rendered 256x128 raw image (game palette indices) that the engine-side
mod blits straight into the viewport with INT 21h row reads.  The text costs ZERO engine bytes
because it is baked into the image here, offline.

Progressive reveal: each quest step occupies exactly LINE_H rows, so showing "steps 1..N" is just
"read the first N*LINE_H rows and stop".  Hiding future steps costs no code at all - the mod simply
stops reading.  Step 4 carries a two-line hint, so a per-step row count is emitted to journal.json
for the mod to embed.

Font: the same 5x5 Latin glyphs mod_spellfont.py installs in the game, so the journal matches the
in-game spell text.  6px advance, 40 chars max per line (the engine's dialogue width).
"""
import json, os
import mod_spellfont

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
W, H = 256, 128
LINE_H = 7               # 5px glyph + 2px leading
C_BG, C_DONE, C_CUR, C_TITLE = 0, 103, 219, 16   # black, grey, gold, white

# Each entry: (text, extra_hint_lines).  Wrapped to <=40 chars - the engine's dialogue width.
STEPS = [
    ("TALK TO PRINCE HORDTKHEN",        []),
    ("VISIT PRINCESS HORDTKHA",         []),
    ("RETURN TO PRINCE HORDTKHEN",      []),
    ("FIND PRINCE HAAGGKHEN",           ["WALL SWITCH BY THE DOOR,",
                                         "THEN THE ? TO FREE THE PRISONER"]),
    ("ASSIST PRINCE NAAKHTKHEN",        []),
    ("STOP PRINCESS NAKHATKA",          []),
    ("FOLLOW PRINCESS HAAGGKHA'S TRAIL", []),
    ("KILL PRINCE HORDTKHEN",           []),
    ("RETURN TO PRINCESS HAAGGKHA",     []),
    ("TAKE THE TEAR OF HAZHULKHA",      []),
    ("KILL PRINCESS NAKHTKHA",          []),
    ("KILL PRINCE HAAGGKHEN",           []),
    ("KILL PRINCE HAZHULKHEN",          []),
    ("READ THE SEPULCHER MESSAGE",      []),
    ("GIVE THE 8 TEARS TO THE DRAGONS", []),
]


def glyph(ch):
    """5x5 rows for A-Z, 0-9 and a few marks, reusing the installed Latin font."""
    if ch in mod_spellfont.FONT:
        return mod_spellfont.FONT[ch]
    extra = {
        # The GAME's font has no 'Z' (glyph 26 spills past the packed row), but this image is
        # rendered offline, so the journal can have one.
        'Z': (0x1F, 0x02, 0x04, 0x08, 0x1F),
        ' ': (0, 0, 0, 0, 0),
        '.': (0, 0, 0, 0, 0x04),
        ',': (0, 0, 0, 0x04, 0x08),
        "'": (0x04, 0x04, 0, 0, 0),
        '?': (0x0E, 0x11, 0x02, 0, 0x04),
        '-': (0, 0, 0x0E, 0, 0),
        '0': (0x0E, 0x11, 0x11, 0x11, 0x0E), '1': (0x04, 0x0C, 0x04, 0x04, 0x0E),
        '2': (0x0E, 0x11, 0x02, 0x04, 0x1F), '3': (0x1E, 0x01, 0x0E, 0x01, 0x1E),
        '4': (0x02, 0x06, 0x0A, 0x1F, 0x02), '5': (0x1F, 0x10, 0x1E, 0x01, 0x1E),
        '6': (0x0E, 0x10, 0x1E, 0x11, 0x0E), '7': (0x1F, 0x01, 0x02, 0x04, 0x04),
        '8': (0x0E, 0x11, 0x0E, 0x11, 0x0E), '9': (0x0E, 0x11, 0x0F, 0x01, 0x0E),
    }
    return extra.get(ch, (0, 0, 0, 0, 0))


def main():
    img = bytearray([C_BG]) * (W * H)

    def text(x, y, s, col):
        for ch in s.upper():
            rows = glyph(ch)
            for r in range(5):
                for c in range(5):
                    if rows[r] & (1 << (4 - c)):
                        px, py = x + c, y + r
                        if 0 <= px < W and 0 <= py < H:
                            img[py * W + px] = col
            x += 6
        return x

    rows_per_step = []
    # header: always visible (baked into step 1's row count via HEADER_ROWS)
    text(2, 1, 'QUEST HINTS', C_CUR)
    text(80, 1, 'SPACE=NEXT HINT  B=BACK', C_TITLE)
    y = 9
    for i, (label, hints) in enumerate(STEPS, 1):
        start = y
        # colour: the LAST revealed step is the current objective (gold); earlier ones are done.
        # The mod reveals steps progressively, so we bake both states by drawing the step twice is
        # impossible in one image - instead every step is drawn in "done" grey and the mod tints
        # nothing; the CURRENT one is simply the last line visible. Gold is used for its number so
        # the eye lands on the newest line.
        x = text(2, y, '%2d' % i, C_CUR)
        text(x + 4, y, label, C_DONE)
        y += LINE_H
        for h in hints:
            text(14, y, h, C_TITLE)
            y += LINE_H
        rows_per_step.append(y - start)

    assert y <= H, 'journal overflows the viewport: %d rows > %d' % (y, H)
    out = os.path.join(GAME, 'QUEST.DRK')
    open(out, 'wb').write(bytes(img))
    rows_per_step[0] += 0   # header rows are included via the y offset baked into step 1
    json.dump({'line_h': LINE_H, 'header_rows': 9, 'rows_per_step': rows_per_step, 'total_rows': y},
              open(os.path.join(HERE, 'journal.json'), 'w'), indent=1)
    print('wrote %s (%d bytes), %d steps, %d rows used of %d'
          % (out, len(img), len(STEPS), y, H))
    print('rows per step:', rows_per_step)


if __name__ == '__main__':
    main()
