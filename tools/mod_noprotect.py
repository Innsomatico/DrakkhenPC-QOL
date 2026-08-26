"""Mod: never show the "DRAKKHEN CODES / Line: / Word:" copy-protection prompt.

One word of initialised data - no code is patched, nothing is removed, and no dead space is used.

The prompt is drawn by 0D7E:18B0 (pushes the three far pointers at DS:2B36/2B3A/2B3E) from the
protection routine 0D7E:19B1 (picks a random line/word with `div 0x19`, reads letters, compares).
That routine has exactly one caller, a per-iteration gate at 0D7E:1B79:

    1b79  cmp  word [0x1b1c], 0        ; counter high word
    1b7e  ja   done                    ; already past -> never again
    1b80  jb   count
    1b82  cmp  word [0x1b1a], 0x4c1    ; counter low word
    1b88  jae  done                    ; already fired -> never again
    count:
    1b8a  mov  word [0x1b18], 1        ; (written, never read - leftover)
    1b90  add  word [0x1b1a], 1
    1b95  adc  word [0x1b1c], 0
    1b9a  cmp  word [0x1b1c], 0
    1b9f  jne  done
    1ba1  cmp  word [0x1b1a], 0x4c1
    1ba7  jne  done
    1ba9  call protection              ; fires on tick 1217 exactly, once per session
    done: retf

So it is a one-shot that trips 1217 iterations into a session - matching the reported "happens once,
a little while after starting, in the world view".  The counter (DS:1B1A/1B1C) is initialised data,
starts at 0, and is referenced ONLY by this gate.  Setting the high word to 1 makes the very first
`ja done` skip everything forever: the counter never advances and the prompt never appears.

Reverting the word to 0 restores stock behaviour exactly.
"""
COUNTER_HI = 0x1FD40 + 0x1B1C      # image-linear address of the counter's high word
OLD = b'\x00\x00'
NEW = b'\x01\x00'


def apply(b):
    cur = bytes(b.img[COUNTER_HI:COUNTER_HI + 2])
    assert cur == OLD, 'protection counter not as expected: %s' % cur.hex()
    b.img[COUNTER_HI:COUNTER_HI + 2] = NEW
    b.noprotect = True      # unlocks Builder.alloc_code(): the protection routine is now dead
    print('  noprotect: protection counter high word 0 -> 1 (prompt disabled, 0 code bytes)')
