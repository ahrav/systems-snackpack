"""Strict whole-batch decimal counter parser. Run with Python 3."""
import re


def parse(data: bytes) -> list[int]:
    values, value, digits = [], 0, 0
    for byte in data:
        if byte == 10:
            if digits == 0:
                raise ValueError('empty record')
            values.append(value)
            value = digits = 0
        elif 48 <= byte <= 57:
            if digits and value == 0:
                raise ValueError('leading zero')
            value = value * 10 + byte - 48
            digits += 1
            if value > 0xffffffff:
                raise ValueError('u32 overflow')
        else:
            raise ValueError('invalid byte')
    if digits:
        raise ValueError('missing final LF')
    return values


def oracle(data: bytes) -> list[int]:
    if not re.fullmatch(rb'(?:(?:0|[1-9][0-9]{0,9})\n)*', data):
        raise ValueError('grammar')
    values = [int(line) for line in data.splitlines()]
    if any(v > 0xffffffff for v in values):
        raise ValueError('range')
    return values


def accepted(function, data: bytes):
    """Return the values function produces for data, or None when it raises ValueError."""
    try:
        return function(data)
    except ValueError:
        return None


if __name__ == '__main__':
    for data in (b'12\n0\n4294967295\n', b'01\n', b'4294967296\n', b'12'):
        try:
            print(repr(data), '=>', parse(data))
        except ValueError as error:
            print(repr(data), '=> reject:', error)
        if accepted(parse, data) != accepted(oracle, data):
            raise SystemExit(f'parse and oracle disagree on {data!r}')
