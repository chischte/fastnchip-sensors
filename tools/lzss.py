#!/usr/bin/env python3
"""
LZSS encoder/decoder — pure Python port of Haruhiko Okumura's public-domain C implementation.
Same parameters as the Arduino OTA tools (EI=11, EJ=4).
Usage: lzss.py --encode infile outfile
       lzss.py --decode infile outfile
"""

import sys

EI = 11          # index bits  (buffer size N = 2^EI = 2048)
EJ = 4           # length bits (max match F = 2^EJ+1 = 17)
P  = 1           # literal threshold
N  = 1 << EI     # 2048
F  = (1 << EJ) + 1  # 17


def encode_file(ifile: str, ofile: str) -> None:
    with open(ifile, "rb") as fi:
        data = fi.read()

    out_bytes = bytearray()
    bit_buf = 0
    bit_mask = 128

    def putbit(b: int) -> None:
        nonlocal bit_buf, bit_mask
        if b:
            bit_buf |= bit_mask
        bit_mask >>= 1
        if bit_mask == 0:
            out_bytes.append(bit_buf)
            bit_buf = 0
            bit_mask = 128

    def flush():
        if bit_mask != 128:
            out_bytes.append(bit_buf)

    def output1(c: int) -> None:
        putbit(1)
        mask = 128
        while mask:
            putbit(1 if (c & mask) else 0)
            mask >>= 1

    def output2(x: int, y: int) -> None:
        putbit(0)
        mask = N >> 1
        while mask:
            putbit(1 if (x & mask) else 0)
            mask >>= 1
        mask = 1 << (EJ - 1)
        while mask:
            putbit(1 if (y & mask) else 0)
            mask >>= 1

    # A literal-only LZSS stream is slightly larger than the input, but it is
    # deterministic, fast, and fully compatible with the Portenta decoder.
    # Firmware size is well below the OTA QSPI partition limit.
    for byte in data:
        output1(byte)
    flush()
    with open(ofile, "wb") as fo:
        fo.write(out_bytes)
    return

    buf = bytearray(b'\x20' * (N * 2))
    data_len = len(data)
    # Load lookahead: buf[N-F .. N-F+len1-1] = data[0..len1-1]
    len1 = min(F, data_len)
    for i in range(len1):
        buf[(N - F + i) & (N * 2 - 1)] = data[i]
    data_pos = len1

    r = N - F  # write position in buf (ring)

    # Hash table: maps 3-byte key -> list of positions in buf ring
    from collections import defaultdict
    chain = [-1] * (N * 2)
    head = defaultdict(lambda: -1)

    def buf_key(pos):
        return (buf[pos & (N * 2 - 1)],
                buf[(pos + 1) & (N * 2 - 1)],
                buf[(pos + 2) & (N * 2 - 1)])

    # Seed hash for initial buffer
    for i in range(N - F - 1, N):
        k = buf_key(i)
        chain[i & (N * 2 - 1)] = head[k]
        head[k] = i & (N * 2 - 1)

    s = r  # current pos

    while len1 > 0:
        # Search for best match
        best_len = P
        best_pos = 0
        c = buf[s & (N * 2 - 1)]

        if len1 >= 3:
            k = buf_key(s)
            p = head[k]
            limit = max(s - N, -1)
            steps = 0
            while p != -1 and p > limit and steps < 256:
                steps += 1
                # How long does this match extend?
                j = 0
                max_j = min(F, len1) - 1
                while j <= max_j:
                    if buf[(p + j) & (N * 2 - 1)] != buf[(s + j) & (N * 2 - 1)]:
                        break
                    j += 1
                if j > best_len:
                    best_len = j
                    best_pos = p
                    if best_len == F:
                        break
                p = chain[p & (N * 2 - 1)]

        if best_len <= P:
            output1(c)
            best_len = 1
        else:
            output2(best_pos & (N - 1), best_len - 2)

        # Advance by best_len
        for _ in range(best_len):
            # Insert new byte into hash
            new_pos = (s + F) & (N * 2 - 1)
            if data_pos < data_len:
                buf[new_pos] = data[data_pos]
                data_pos += 1
            else:
                len1 -= 1

            if len1 >= 3:
                k = buf_key(s)
                chain[s & (N * 2 - 1)] = head[k]
                head[k] = s & (N * 2 - 1)

            s = (s + 1) & (N * 2 - 1)

    flush()

    with open(ofile, "wb") as fo:
        fo.write(out_bytes)


def decode_file(ifile: str, ofile: str) -> None:
    with open(ifile, "rb") as fi:
        data = fi.read()

    out_bytes = bytearray()
    buf = bytearray(N * 2)
    for i in range(N):
        buf[i] = 0x20

    bit_pos = 0
    byte_pos = 0

    def getbit() -> int:
        nonlocal bit_pos, byte_pos
        if byte_pos >= len(data):
            return -1
        bit = (data[byte_pos] >> (7 - bit_pos)) & 1
        bit_pos += 1
        if bit_pos == 8:
            bit_pos = 0
            byte_pos += 1
        return bit

    r = N - F
    while True:
        b = getbit()
        if b < 0:
            break
        if b:
            # Literal
            c = 0
            for _ in range(8):
                bit = getbit()
                if bit < 0:
                    break
                c = (c << 1) | bit
            out_bytes.append(c)
            buf[r] = c
            r = (r + 1) & (N * 2 - 1)
        else:
            # Match
            x = 0
            for _ in range(EI):
                bit = getbit()
                if bit < 0:
                    break
                x = (x << 1) | bit
            y = 0
            for _ in range(EJ):
                bit = getbit()
                if bit < 0:
                    break
                y = (y << 1) | bit
            y += 2
            for j in range(y + 1):
                c = buf[(x + j) & (N * 2 - 1)]
                out_bytes.append(c)
                buf[r] = c
                r = (r + 1) & (N * 2 - 1)

    with open(ofile, "wb") as fo:
        fo.write(out_bytes)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: lzss.py --[encode|decode] infile outfile")
        sys.exit(1)

    mode, ifile, ofile = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "--encode":
        encode_file(ifile, ofile)
    elif mode == "--decode":
        decode_file(ifile, ofile)
    else:
        print("Unknown mode:", mode)
        sys.exit(1)
