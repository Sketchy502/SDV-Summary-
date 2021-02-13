import os
import json
import pytest

from sdv.savefile import savefile
from sdv.farmInfo import (
    regenerateFarmInfo,
    getFarmInfo,
    sprite,
)

current_directory = os.path.dirname(os.path.realpath(__file__))
data_directory = os.path.join(current_directory, '__data__')
sample_savefile = os.path.join(data_directory, 'Eliza_123456789')
sample_infofile = os.path.join(data_directory, 'Eliza_123456789_info.json')


def test_regenerateFarmInfo():
    json_from_db = dict(
        data=dict(
            sprite1=[
                ('name11', 111, 112, 113, 114, 'i11', 't11', 'g11', 'f11', 'o11'),
                ('name12', 121, 122, 123, 124, 'i12', 't12', 'g12', 'f12', 'o12'),
            ],
            sprite2=[
                ('name21', 211, 212, 213, 214, 'i21', 't21', 'g21', 'f21', 'o21'),
                ('name22', 221, 222, 223, 224, 'i22', 't22', 'g22', 'f22', 'o22'),
            ],
        )
    )
    data = regenerateFarmInfo(json_from_db)
    for i in range(2):
        for j in range(2):
            n = str(i + 1)
            m = n + str(j + 1)
            sprite = data['data']['sprite' + n][j] 
            assert sprite.name == "name" + m
            assert sprite.x == 1 + int(m) * 10
            assert sprite.y == 2 + int(m) * 10
            assert sprite.w == 3 + int(m) * 10
            assert sprite.h == 4 + int(m) * 10
            assert sprite.index == "i" + m
            assert sprite.type == "t" + m
            assert sprite.growth == "g" + m
            assert sprite.flipped == "f" + m
            assert sprite.orientation == "o" + m

class EncoderForNamedtuple(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, sprite):
            return list(o)

def test_getFarmInfo():
    with open(sample_savefile, 'r') as f:
        file = savefile(f)

    info = getFarmInfo(file)
    # Uncomment this to overwrite test file
    # with open(sample_infofile, 'w') as f:
    #     json.dump(info, f, indent=4, cls=EncoderForNamedtuple)

    with open(sample_infofile) as f:
        expected_info = json.load(f)
        assert info == expected_info
