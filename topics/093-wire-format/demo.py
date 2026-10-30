"""Multi-record wire example. Python 3, standard library only."""
import struct

def decode(buf):
    b = memoryview(buf).cast('B')
    if len(b) < 8 or b[:4] != b'W093':
        raise ValueError('header')
    n, = struct.unpack_from('<I', b, 4)
    if n > (len(b) - 8) // 12:
        raise ValueError('count')
    end = 8 + 12 * n
    records = []
    for i in range(n):
        ident, off, size = struct.unpack_from('<III', b, 8 + 12 * i)
        if off != end or off > len(b) or size > len(b) - off:
            raise ValueError('extent')
        records.append((ident, b[off:off + size]))
        end = off + size
    if end != len(b):
        raise ValueError('trailing bytes')
    return records

if __name__ == '__main__':
    packet = b'W093' + struct.pack('<IIII', 1, 7, 20, 3) + b'abc'
    ident, payload = decode(packet)[0]
    print(ident, bytes(payload), payload.obj is packet)
    try:
        decode(packet[:-1])
    except ValueError as error:
        print('rejected:', error)
