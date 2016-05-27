import os
import random

from PIL import Image
from itertools import chain
from collections import namedtuple
from imagegeneration.tools import colourBox, tintImage, cropImg


def loadTree(ss_tree, loc=0):
    tree = Image.new('RGBA', (3*16, 6*16))
    body = cropImg(ss_tree, loc, objectSize=(48, 96))
    stump = cropImg(ss_tree, 20, objectSize=(16, 32))
    tree.paste(stump, (1*16, 4*16), stump)
    tree.paste(body, (0, 0), body)
    return tree


def getPlant(img, location, colour, days, T, defaultSize=(16, 16), objectSize=(16, 16)):
    if location < 4:
        return cropImg(img, location, defaultSize, objectSize)
    else:
        bloomed = False
        if T == 26 and days > 1:
            bloomed = True
        if T == 27 and days > 2:
            bloomed = True
        if T == 28 and days > 2:
            bloomed = True
        if T == 29 and days > 2:
            bloomed = True
        if T == 31 and days > 3:
            bloomed = True

        if bloomed:
            plant_body = cropImg(img, 5, defaultSize, objectSize)
            plant_head = cropImg(img, 6, defaultSize, objectSize)
            plant_head = tintImage(plant_head, colour)
            plant_body.paste(plant_head, (0, 0), plant_head)
        else:
            plant_body = cropImg(img, 4, defaultSize, objectSize)

        return plant_body


def loadAssets():
    assets = {
                'base': {
                            'spring': {
                                'Back': Image.open('./assets/bases/spring/Back.png'),
                                'Buildings': Image.open('./assets/bases/spring/Buildings.png'),
                                'Front': Image.open('./assets/bases/spring/Front.png'),
                                'AlwaysFront': Image.open('./assets/bases/spring/AlwaysFront.png'),
                            },
                            'summer': {
                                'Back': Image.open('./assets/bases/spring/Back.png'),
                                'Buildings': Image.open('./assets/bases/spring/Buildings.png'),
                                'Front': Image.open('./assets/bases/spring/Front.png'),
                                'AlwaysFront': Image.open('./assets/bases/spring/AlwaysFront.png'),
                            },
                            'fall': {
                                'Back': Image.open('./assets/bases/fall/Back.png'),
                                'Buildings': Image.open('./assets/bases/fall/Buildings.png'),
                                'Front': Image.open('./assets/bases/fall/Front.png'),
                                'AlwaysFront': Image.open('./assets/bases/fall/AlwaysFront.png'),
                            },
                            'winter': {
                                'Back': Image.open('./assets/bases/spring/Back.png'),
                                'Buildings': Image.open('./assets/bases/spring/Buildings.png'),
                                'Front': Image.open('./assets/bases/spring/Front.png'),
                                'AlwaysFront': Image.open('./assets/bases/spring/AlwaysFront.png'),
                            },
                          },
                'objects': Image.open('./assets/farm/objects.png'),
                'craftables': Image.open('./assets/farm/craftables.png'),
                'flooring': Image.open('./assets/farm/flooring.png'),
                'hoe dirt': {
                              'normal': Image.open('./assets/farm/hoeDirt.png'),
                              'winter': Image.open('./assets/farm/hoeDirtsnow.png')
                              },
                'crops': Image.open('./assets/farm/crops.png'),
                'fences': {
                                'wood': Image.open('./assets/farm/Fence1.png'),
                                'stone': Image.open('./assets/farm/Fence2.png'),
                                'iron': Image.open('./assets/farm/Fence3.png'),
                                'hardwood': Image.open('./assets/farm/Fence5.png')
                            },
                'trees': {
                            'oak': {
                                        'spring': Image.open('./assets/farm/trees/tree1_spring.png'),
                                        'summer': Image.open('./assets/farm/trees/tree1_summer.png'),
                                        'fall': Image.open('./assets/farm/trees/tree1_fall.png'),
                                        'winter': Image.open('./assets/farm/trees/tree1_winter.png')
                                    },
                            'maple': {
                                        'spring': Image.open('./assets/farm/trees/tree2_spring.png'),
                                        'summer': Image.open('./assets/farm/trees/tree2_summer.png'),
                                        'fall': Image.open('./assets/farm/trees/tree2_fall.png'),
                                        'winter': Image.open('./assets/farm/trees/tree2_winter.png')
                                        },
                            'pine': {
                                        'spring': Image.open('./assets/farm/trees/tree3_spring.png'),
                                        'summer': Image.open('./assets/farm/trees/tree3_summer.png'),
                                        'fall': Image.open('./assets/farm/trees/tree3_fall.png'),
                                        'winter': Image.open('./assets/farm/trees/tree3_winter.png')
                                     },
                            'mushroom': Image.open('./assets/farm/trees/mushroom_tree.png'),
                            'fruit': Image.open('./assets/farm/fruitTrees.png')
                            },
                'grass': Image.open('./assets/farm/grass/grass.png'),
                'buildings': {
                                    'barn': Image.open('./assets/farm/buildings/Barn.png'),
                                    'big barn': Image.open('./assets/farm/buildings/Big Barn.png'),
                                    'deluxe barn': Image.open('./assets/farm/buildings/Deluxe Barn.png'),
                                    'coop': Image.open('./assets/farm/buildings/Coop.png'),
                                    'big coop': Image.open('./assets/farm/buildings/Big Coop.png'),
                                    'deluxe coop': Image.open('./assets/farm/buildings/Deluxe Coop.png'),
                                    'greenhouse': Image.open('./assets/farm/buildings/Greenhouse.png'),
                                    'house': Image.open('./assets/farm/buildings/houses.png'),
                                    'silo': Image.open('./assets/farm/buildings/Silo.png'),
                                    'slime hutch': Image.open('./assets/farm/buildings/Slime Hutch.png'),
                                    'stable': Image.open('./assets/farm/buildings/Stable.png'),
                                    'well': Image.open('./assets/farm/buildings/Well.png'),
                                }
              }
    return assets


def generateFarm(season, farm, assets=None):
    sprite = namedtuple('Sprite', ['name', 'x', 'y', 'w', 'h', 'index', 'type', 'growth', 'flipped', 'orientation'])
    craftable_blacklist = ['Twig', 'Torch', 'Sprinkler',
                           'Quality Sprinkler', 'Iridium Sprinkler']

    if assets is None:
        print('\tLoading Assets...')
        assets = loadAssets()

    farm_base = Image.new('RGBA', (1280, 1040))
    farm_base.paste(assets['base'][season]["Back"], (0, 0))
    farm_base = Image.alpha_composite(farm_base, assets['base'][season]["Buildings"])

    # seed the random number generator so we render the same way every time
    random.seed(0)

    farm = sorted(chain.from_iterable(farm.values()), key=lambda x: x.y)
    floor_types = ['Flooring', 'HoeDirt']
    floor = [i for i in farm if i.name in floor_types]
    gates = []
    other_things = [i for i in farm if i not in floor]

    print('\tRendering Sprites...')
    for item in floor:
        if item.name == 'Flooring':
            floor_type = cropImg(assets['flooring'], item.type,
                                 (64, 64), (64, 64))
            floor_view = cropImg(floor_type, item.orientation)
            farm_base.paste(floor_view, (item.x*16, item.y*16), floor_view)

        if item.name == 'HoeDirt':
            if season != 'winter':
                hoe_sheet = assets['hoe dirt']['normal']
            else:
                hoe_sheet = assets['hoe dirt']['winter']
            hoe_tile = cropImg(hoe_sheet, item.orientation)
            farm_base.paste(hoe_tile, (item.x*16, item.y*16), hoe_tile)

    for item in other_things:
        if 'Crop' in item.name:
            if item.name != "GiantCrop":
                crop_sprites = cropImg(assets['crops'], item.type,
                                       (128, 32), (128, 32))
                if item.orientation is None:
                    crop_img = cropImg(crop_sprites, item.growth,
                                       (16, 32), (16, 32))
                else:
                    crop_img = getPlant(crop_sprites, item.growth, item.orientation[0], item.orientation[1], item.type, (4, 8), (4, 8))
            else:
                if item.type == 190:
                    crop_img = cropImg(assets['crops'], 263, objectSize=(48, 64), defaultSize=(16, 32))
                if item.type == 254:
                    crop_img = cropImg(assets['crops'], 266, objectSize=(48, 64), defaultSize=(16, 32))
                if item.type == 276:
                    crop_img = cropImg(assets['crops'], 269, objectSize=(48, 64), defaultSize=(16, 32))
            if item.flipped:
                crop_img = crop_img.transpose(Image.FLIP_LEFT_RIGHT)
            farm_base.paste(crop_img, (item.x*16, item.y*16 - 16), crop_img)

        if item.name == 'Object':
            if item.type == "Crafting" and item.orientation not in craftable_blacklist:
                obj_img = cropImg(assets['craftables'], item.index,
                                  (16, 32), (16, 32))
                offset = 16
            else:
                obj_img = cropImg(assets['objects'], item.index)
                offset = 0
            farm_base.paste(obj_img, (item.x*16, item.y*16 - offset), obj_img)

        if item.name == 'Fence':
            try:
                offsetx = 0
                offsety = 0
                if item.type == 1:
                    material = 'wood'
                elif item.type == 2:
                    material = 'stone'
                elif item.type == 3:
                    material = 'iron'
                elif item.type == 5:
                    material = 'hardwood'

                if item.orientation == 12 and item.growth:
                    gates.append(item)
                    continue
                elif item.orientation == 15 and item.growth:
                    fence_img = cropImg(assets['fences'][material], item.orientation,
                                        defaultSize=(16, 32), objectSize=(8, 16))
                    offsetx = 5
                    offsety = 22
                else:
                    fence_img = cropImg(assets['fences'][material], item.orientation,
                                        defaultSize=(16, 32), objectSize=(16, 32))
                offsety = 16
                farm_base.paste(fence_img, (item.x * 16 + offsetx, item.y * 16 - offsety), fence_img)
            except Exception as e:
                print(e)

        if item.name == 'ResourceClump':
            obj_img = cropImg(assets['objects'], item.type, objectSize=(32, 32))
            farm_base.paste(obj_img, (item.x*16, item.y*16), obj_img)

        if item.name == 'Tree':
            try:
                if item.type == 1:
                    tree_img = assets['trees']['oak'][season]
                elif item.type == 2:
                    tree_img = assets['trees']['maple'][season]
                elif item.type == 3:
                    tree_img = assets['trees']['pine'][season]
                elif item.type == 7:
                    tree_img = assets['trees']['mushroom']

                if item.growth == 0:
                    tree_crop = cropImg(tree_img, 26)
                    offsetx = 0
                    offsety = 0
                elif item.growth == 1:
                    tree_crop = cropImg(tree_img, 24)
                    offsetx = 0
                    offsety = 0
                elif item.growth == 2:
                    tree_crop = cropImg(tree_img, 25)
                    offsetx = 0
                    offsety = 0
                elif item.growth == 3 or item.growth == 4:
                    tree_crop = cropImg(tree_img, 18, objectSize=(16, 32))
                    offsetx = 0
                    offsety = 16
                else:
                    tree_crop = loadTree(tree_img)
                    offsety = 5*16
                    offsetx = 1*16
                if item.flipped:
                    tree_crop = tree_crop.transpose(Image.FLIP_LEFT_RIGHT)
                farm_base.paste(tree_crop, (item.x*16 - offsetx, item.y*16 - offsety), tree_crop)
            except Exception as e:
                print(e)

        if item.name == 'FruitTree':
            seasons = {'spring': 0, 'summer': 1, 'fall': 2, 'winter': 3}
            try:
                    if item.growth <= 3:
                        tree_crop = cropImg(assets['trees']['fruit'], item.growth + 1+9*item.type,
                                            defaultSize=(48, 80), objectSize=(48, 80))
                    else:
                        tree_crop = cropImg(assets['trees']['fruit'], 4 + seasons[season] + 9*item.type,
                                            defaultSize=(48, 80), objectSize=(48, 80))
                    offsety = 4*16
                    offsetx = 1*16
                    if item.flipped:
                        tree_crop = tree_crop.transpose(Image.FLIP_LEFT_RIGHT)
                    farm_base.paste(tree_crop, (item.x*16 - offsetx, item.y*16 - offsety), tree_crop)
            except Exception as e:
                print(e)

        if item.name == "Building":
            try:
                offsety = assets['buildings'][item.type.lower()].height - (item.h)*16
                farm_base.paste(assets['buildings'][item.type.lower()], (item.x*16, item.y*16 - offsety), assets['buildings'][item.type.lower()])
            except Exception as e:
                print(e)

        if item.name == "Grass":
            try:
                xmask = 0b01
                ymask = 0b10
                s = {'spring': 0, 'summer': 4, 'fall': 8}
                for i in range(item.growth):
                    grass_img = cropImg(assets['grass'], s[season] + random.randint(0, 2),
                                        (16, 20), (16, 20))
                    offsety = 8 + (ymask & i)*4 - 16 + random.randint(-2, 2)
                    offsetx = 12 + (xmask & i)*8 - 16 + random.randint(-2, 2)
                    farm_base.paste(grass_img, (item.x*16 + offsetx, item.y*16 + offsety), grass_img)
            except Exception as e:
                print(e)

        if item.name == "House":
            try:
                house_img = cropImg(assets['buildings']['house'], item.index,
                                    defaultSize=(160, 144), objectSize=(160, 144))
                farm_base.paste(house_img, (item.x*16, item.y*16 - 16 * item.h), house_img)
            except Exception as e:
                print(e)

        if item.name == "Greenhouse":
            try:
                greenhouse_img = cropImg(assets['buildings']['greenhouse'], item.index,
                                         defaultSize=(112, 160), objectSize=(112, 160))
                farm_base.paste(greenhouse_img, (item.x*16, item.y*16 - 16 * item.h), greenhouse_img)
            except Exception as e:
                print(e)

    for item in gates:
        try:
                offsetx = 0
                offsety = 0
                if item.type == 1:
                    material = 'wood'
                elif item.type == 1:
                    material = 'stone'
                elif item.type == 1:
                    material = 'iron'
                elif item.type == 1:
                    material = 'hardwood'
                gate_img = cropImg(assets['fences'][material], item.orientation,
                                    defaultSize=(16, 32), objectSize=(24, 32))
                offsetx = -4
                offsety = 16
                farm_base.paste(gate_img, (item.x * 16 + offsetx, item.y * 16 - offsety), gate_img)
        except Exception as e:
                print(e)

    farm_base = Image.alpha_composite(farm_base, assets['base'][season]["Front"])
    farm_base = Image.alpha_composite(farm_base, assets['base'][season]["AlwaysFront"])

    farm_base = farm_base.convert('RGBA').convert('P', palette=Image.ADAPTIVE, colors=255)
    return farm_base


# Renders a PNG of the players farm where one 8x8 pixel square is equivalent to one in game tile.
# Legend:   Shades of green - Trees, Weeds, Grass
#      Shades of brown - Twigs, Logs
#      Shades of grey - Stones, Boulders, Fences
#      Dark red - Static buildings
#      Light red - Player placed objects (Scarecrows, etc)
#      Blue - Water
#      Off Tan - Tilled Soil
def generateMinimap(farm):
    image = Image.open("./assets/bases/minimap_base.png")
    pixels = image.load()

    pixels[1, 1] = (255, 255, 255)

    for building in farm['buildings']:
        for i in range(building[3]):
            for j in range(building[4]):
                colourBox(building[1] + i, building[2] + j, (255, 150, 150), pixels)

    if 'terrainFeatures' in farm:
        for tile in farm['terrainFeatures']:
            name = tile.name
            if name == "Tree":
                colourBox(tile.x, tile.y, (0, 175, 0), pixels)
            elif name == "Grass":
                colourBox(tile.x, tile.y, (0, 125, 0), pixels)
            elif name == "Flooring":
                colourBox(tile.x, tile.y, (50, 50, 50), pixels)
            else:
                colourBox(tile.x, tile.y, (0, 0, 0), pixels)

    if 'HoeDirt' in farm:
        for tile in farm['HoeDirt']:
            colourBox(tile.x, tile.y, (196, 196, 38), pixels)

    if 'Flooring' in farm:
        for tile in farm['Flooring']:
            colourBox(tile.x, tile.y, (50, 50, 50), pixels)

    if 'Fences' in farm:
        for tile in farm['Fences']:
            colourBox(tile.x, tile.y, (200, 200, 200), pixels)

    if 'objects' in farm:
        for tile in farm['objects']:
            name = tile.orientation
            if name == "Weeds":
                colourBox(tile.x, tile.y, (0, 255, 0), pixels)
            elif name == "Stone":
                colourBox(tile.x, tile.y, (125, 125, 125), pixels)
            elif name == "Twig":
                colourBox(tile.x, tile.y, (153, 102, 51), pixels)
            else:
                colourBox(tile.x, tile.y, (255, 0, 0), pixels)

    if 'resourceClumps' in farm:
        for tile in farm['resourceClumps']:
            if tile.type == 672:
                for i in range(tile[3]):
                    for j in range(tile[3]):
                        colourBox(tile.x + i, tile.y + j, (102, 51, 0), pixels)
            elif tile.type == 600:
                for i in range(tile[3]):
                    for j in range(tile[3]):
                        colourBox(tile.x+i, tile.y + j, (75, 75, 75), pixels)
    return image
