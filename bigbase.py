#
# converts base 10 to base 62 for purpose of small URL identifiers
#
import sys

CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

if sys.version_info > (3,):
    long = int

def dec2big(num):
    assert type(num) in [int,long]
    if num == 0:
        output = CHARS[0]
    elif num > 0:
        base = len(CHARS)
        output = ''
        while num > 0:
            rem = int(num%base)
            output = CHARS[rem] + output
            num = (num-rem)/base
    else:
        raise IOError
    return output

def big2dec(num):
    assert all([num[x] in CHARS for x in range(len(num))])
    base = len(CHARS)
    output = 0
    multiplier = 1
    for item in num[::-1]:
        output += multiplier * CHARS.index(item)
        multiplier *= base
    return output


if __name__ == "__main__":
    print(dec2big(9999999999999999999999999999999999999999999999999999999))
    print(big2dec('gUFRx61gTwUoLRUcYcoUr2SbzgUyBQz'))