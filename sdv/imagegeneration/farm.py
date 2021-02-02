import random

from PIL import Image
from itertools import chain
from collections import namedtuple

from sdv.imagegeneration.buildings.fish_pond import render_fish_pond
from .tools import colourBox, tintImage, cropImg
from .assets import loadFarmAssets


def loadTree(ss_tree, loc=0):
    tree = Image.new("RGBA", (3 * 16, 6 * 16))
    body = cropImg(ss_tree, loc, objectSize=(48, 96))
    stump = cropImg(ss_tree, 20, objectSize=(16, 32))
    tree.paste(stump, (1 * 16, 4 * 16), stump)
    tree.paste(body, (0, 0), body)
    return tree


def getPlant(img, growth, colour, days, T, defaultSize=(16, 16), objectSize=(16, 16)):
    if growth < 4:
        return cropImg(img, growth, defaultSize, objectSize)
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


def generateFarm(season, data, assets=None):
    type = data["type"]
    farm = data["data"]
    sprite = namedtuple(
        "Sprite",
        [
            "name",
            "x",
            "y",
            "w",
            "h",
            "index",
            "type",
            "growth",
            "flipped",
            "orientation",
        ],
    )
    craftable_blacklist = [
        "Twig",
        "Stone",
        "Weeds",
        "Torch",
        "Sprinkler",
        "Quality Sprinkler",
        "Iridium Sprinkler",
        "Note Block",
        "Jack-O-Lantern",
    ]

    if assets is None:
        print("\tLoading Assets...")
        assets = loadFarmAssets(season, type)

    farm_heights = {"FourCorners": 1280, "Island": 1760}
    farm_height = farm_heights.get(type, 1040)

    farm_widths = {"Island": 1760}
    farm_width = farm_widths.get(type, 1280)

    farm_base = Image.new("RGBA", (farm_width, farm_height))
    farm_base.paste(assets["base"][type][season], (0, 0))

    # seed the random number generator so we render the same way every time
    random.seed(0)

    spouse = data.get("spouse")
    if spouse:
        farm["buildings"].append(
            sprite("spouse_area", 69, 8, 4 * 16, 4 * 16, 0, 0, 0, 0, 0)
        )

    farm = sorted(chain.from_iterable(farm.values()), key=lambda x: x.y)
    floor_types = ["Flooring", "HoeDirt"]
    floor = [i for i in farm if i.name in floor_types]
    gates = []
    farm_tile_height = farm_height // 16
    other_things = {
        y: [i for i in farm if (i not in floor and i.y == y)]
        for y in range(farm_tile_height)
    }

    for i in range(farm_tile_height):
        strip_back = assets["overlays"][type][season]["Buildings"][i]
        farm_base.paste(strip_back, (0, i * 16), strip_back)

    print("\tRendering Sprites...")
    for item in floor:
        if item.name == "Flooring":
            floor_type = cropImg(assets["flooring"], item.type, (64, 64), (64, 64))
            floor_view = cropImg(floor_type, item.orientation)
            farm_base.paste(floor_view, (item.x * 16, item.y * 16), floor_view)

        if item.name == "HoeDirt":
            if season != "winter":
                hoe_sheet = assets["hoe dirt"]["normal"]
            else:
                hoe_sheet = assets["hoe dirt"]["winter"]
            hoe_tile = cropImg(hoe_sheet, item.orientation)
            farm_base.paste(hoe_tile, (item.x * 16, item.y * 16), hoe_tile)

    for y, items in other_things.items():

        for item in items:
            if "Crop" in item.name:
                if item.name != "GiantCrop":
                    crop_sprites = cropImg(
                        assets["crops"], item.type, (128, 32), (128, 32)
                    )
                    if item.orientation is None:
                        crop_img = cropImg(
                            crop_sprites, item.growth, (16, 32), (16, 32)
                        )
                    else:
                        crop_img = getPlant(
                            crop_sprites,
                            item.growth,
                            item.orientation[0],
                            item.orientation[1],
                            item.type,
                            (16, 32),
                            (16, 32),
                        )
                else:
                    if item.type == 190:
                        crop_img = cropImg(
                            assets["crops"],
                            263,
                            objectSize=(48, 64),
                            defaultSize=(16, 32),
                        )
                    if item.type == 254:
                        crop_img = cropImg(
                            assets["crops"],
                            266,
                            objectSize=(48, 64),
                            defaultSize=(16, 32),
                        )
                    if item.type == 276:
                        crop_img = cropImg(
                            assets["crops"],
                            269,
                            objectSize=(48, 64),
                            defaultSize=(16, 32),
                        )
                if item.flipped:
                    crop_img = crop_img.transpose(Image.FLIP_LEFT_RIGHT)
                farm_base.paste(crop_img, (item.x * 16, item.y * 16 - 16), crop_img)

            if item.name == "Object":
                if (
                    item.type == "Crafting"
                    and item.orientation not in craftable_blacklist
                ):
                    obj_img = cropImg(
                        assets["craftables"], item.index, (16, 32), (16, 32)
                    )
                    offset = 16
                else:
                    obj_img = cropImg(assets["objects"], item.index)
                    offset = 0
                if item.orientation and len(item.orientation[1]) == 3:
                    # Seriously need to get reworking how images are rendered
                    obj_img = cropImg(assets["craftables"], 168, (16, 32), (16, 32))

                    is_chest = item.orientation[0] == "Chest"
                    tint = item.orientation[1]
                    if is_chest and tint == [0, 0, 0]:
                        tint = [211, 139, 71]

                    obj_img = tintImage(obj_img, tint)
                    overlay = cropImg(assets["craftables"], 176, (16, 32), (16, 32))
                    obj_img.paste(overlay, box=(0, 0), mask=overlay)

                if item.flipped:
                    obj_img = obj_img.transpose(Image.FLIP_LEFT_RIGHT)
                farm_base.paste(obj_img, (item.x * 16, item.y * 16 - offset), obj_img)

            if item.name == "Fence":
                try:
                    offsetx = 0
                    offsety = 0
                    if item.type == 1:
                        material = "wood"
                    elif item.type == 2:
                        material = "stone"
                    elif item.type == 3:
                        material = "iron"
                    elif item.type == 5:
                        material = "hardwood"

                    if item.orientation == 12 and item.growth:
                        gates.append(item)
                        continue
                    elif item.orientation == 15 and item.growth:
                        fence_img = cropImg(
                            assets["fences"][material],
                            item.orientation,
                            defaultSize=(16, 32),
                            objectSize=(8, 16),
                        )
                        offsetx = 5
                        offsety = 22
                    else:
                        fence_img = cropImg(
                            assets["fences"][material],
                            item.orientation,
                            defaultSize=(16, 32),
                            objectSize=(16, 32),
                        )
                    offsety = 16
                    farm_base.paste(
                        fence_img,
                        (item.x * 16 + offsetx, item.y * 16 - offsety),
                        fence_img,
                    )
                except Exception as e:
                    print(e)

            if item.name == "Tea_Bush":
                season_offset_x = 64 if season in {"summer", "winter"} else 0
                season_offset_y = 32 if season in {"fall", "winter"} else 0
                tile_sheet_x = 0 + season_offset_x
                tile_sheet_y = 256 + season_offset_y

                sprite_index_x = tile_sheet_x + item.growth * 16
                sprite_index = int((sprite_index_x / 16) + ((tile_sheet_y / 32) * 8))

                obj_img = cropImg(
                    assets["bushes"],
                    sprite_index,
                    objectSize=(16, 32),
                    defaultSize=(16, 32),
                )

                if item.flipped:
                    obj_img = obj_img.transpose(Image.FLIP_LEFT_RIGHT)

                farm_base.paste(obj_img, (item.x * 16, item.y * 16), obj_img)

            if item.name == "Bush":

                sprite_sizes = [(16, 32), (32, 48), (48, 48)]

                sprite_size = sprite_sizes[item.growth]
                season_offset = 0
                if item.growth == 0:
                    if season == "spring":
                        season_offset = 0
                    elif season == "summer":
                        season_offset = 2
                    elif season == "fall":
                        season_offset = 4
                    elif season == "winter":
                        season_offset = 6
                elif item.growth == 1:
                    if season == "spring":
                        season_offset = 0
                    elif season == "summer":
                        season_offset = 4 + item.index * 2
                    elif season == "fall":
                        season_offset = 8 * 3
                    elif season == "winter":
                        season_offset = 8 * 3 + 4
                elif item.growth == 2:
                    if season == "spring":
                        season_offset = 0
                    elif season == "summer":
                        season_offset = 0
                    elif season == "fall":
                        season_offset = 3
                    elif season == "winter":
                        season_offset = 8 * 3

                sprite_index = [8 * 14, 8 * 0, 8 * 8][item.growth] + season_offset

                obj_img = cropImg(
                    assets["bushes"], sprite_index, objectSize=sprite_size
                )

                if item.flipped:
                    obj_img = obj_img.transpose(Image.FLIP_LEFT_RIGHT)

                farm_base.paste(
                    obj_img, (item.x * 16, item.y * 16 - (sprite_size[1]) + 16), obj_img
                )

            if item.name == "ResourceClump":
                obj_img = cropImg(assets["objects"], item.type, objectSize=(32, 32))
                farm_base.paste(obj_img, (item.x * 16, item.y * 16), obj_img)

            if item.name == "Tree":
                try:
                    if item.type == 1:
                        tree_img = assets["trees"]["oak"][season]
                    elif item.type == 2:
                        tree_img = assets["trees"]["maple"][season]
                    elif item.type == 3:
                        tree_img = assets["trees"]["pine"][season]
                    elif item.type == 7:
                        tree_img = assets["trees"]["mushroom"]

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
                        offsety = 5 * 16
                        offsetx = 1 * 16
                    if item.flipped:
                        tree_crop = tree_crop.transpose(Image.FLIP_LEFT_RIGHT)
                    farm_base.paste(
                        tree_crop,
                        (item.x * 16 - offsetx, item.y * 16 - offsety),
                        tree_crop,
                    )
                except Exception as e:
                    print(e)

            if item.name == "FruitTree":
                seasons = {"spring": 0, "summer": 1, "fall": 2, "winter": 3}
                try:
                    if item.growth <= 3:
                        tree_crop = cropImg(
                            assets["trees"]["fruit"],
                            item.growth + 1 + 9 * item.type,
                            defaultSize=(48, 80),
                            objectSize=(48, 80),
                        )
                    else:
                        tree_crop = cropImg(
                            assets["trees"]["fruit"],
                            4 + seasons[season] + 9 * item.type,
                            defaultSize=(48, 80),
                            objectSize=(48, 80),
                        )
                    offsety = 4 * 16
                    offsetx = 1 * 16
                    if item.flipped:
                        tree_crop = tree_crop.transpose(Image.FLIP_LEFT_RIGHT)
                    farm_base.paste(
                        tree_crop,
                        (item.x * 16 - offsetx, item.y * 16 - offsety),
                        tree_crop,
                    )
                except Exception as e:
                    print(e)

            if item.name == "Building":
                if item.type != "Greenhouse":
                    try:
                        if item.type.lower() == "junimo hut":
                            offsety = (
                                assets["buildings"][item.type.lower()][season].height
                                - (item.h) * 16
                            )
                            farm_base.paste(
                                assets["buildings"][item.type.lower()][season],
                                (item.x * 16, item.y * 16 - offsety),
                                assets["buildings"][item.type.lower()][season],
                            )
                        elif item.type.lower() == "fish pond":
                            pond_image = render_fish_pond(item, assets)
                            pond_offset_y = 2 * 16
                            farm_base.paste(
                                pond_image,
                                (item.x * 16, item.y * 16 - pond_offset_y),
                                pond_image,
                            )
                        else:
                            offsety = (
                                assets["buildings"][item.type.lower()].height
                                - (item.h) * 16
                            )
                            asset = assets["buildings"][item.type.lower()]
                            if "cabin" in item.type.lower():
                                asset = cropImg(
                                    asset,
                                    item.orientation,
                                    (item.w * 16, asset.height),
                                    (item.w * 16, asset.height),
                                )
                            farm_base.paste(
                                asset, (item.x * 16, item.y * 16 - offsety), asset
                            )
                    except Exception as e:
                        print(e)

            if item.name == "spouse_area":
                sprite = assets["spouseArea"][spouse][season]
                farm_base.paste(sprite, (item.x * 16, item.y * 16 - 16 * 2), sprite)

            if item.name == "Grass":
                try:
                    xmask = 0b01
                    ymask = 0b10
                    s = {"spring": 0, "summer": 4, "fall": 8}
                    for i in range(item.growth):
                        grass_img = cropImg(
                            assets["grass"],
                            s[season] + random.randint(0, 2),
                            (16, 20),
                            (16, 20),
                        )
                        offsety = 8 + (ymask & i) * 4 - 16 + random.randint(-2, 2)
                        offsetx = 12 + (xmask & i) * 8 - 16 + random.randint(-2, 2)
                        farm_base.paste(
                            grass_img,
                            (item.x * 16 + offsetx, item.y * 16 + offsety),
                            grass_img,
                        )
                except Exception as e:
                    print(e)

            if item.name == "House":
                house_index = 2 if item.index == 3 else item.index
                try:
                    house_img = cropImg(
                        assets["buildings"]["house"],
                        house_index,
                        defaultSize=(160, 144),
                        objectSize=(160, 144),
                    )
                    farm_base.paste(
                        house_img, (item.x * 16, item.y * 16 - 16 * item.h), house_img
                    )
                except Exception as e:
                    print(e)

            if item.name == "Greenhouse" or item.type == "Greenhouse":
                try:
                    greenhouse_img = cropImg(
                        assets["buildings"]["greenhouse"],
                        item.index,
                        defaultSize=(112, 160),
                        objectSize=(112, 160),
                    )
                    farm_base.paste(
                        greenhouse_img,
                        (item.x * 16, item.y * 16 - 16 * item.h),
                        greenhouse_img,
                    )
                except Exception as e:
                    print(e)

        strip_back = assets["overlays"][type][season]["Front"][y]
        farm_base.paste(strip_back, (0, y * 16), strip_back)

        strip_back = assets["overlays"][type][season]["AlwaysFront"][y]
        farm_base.paste(strip_back, (0, y * 16), strip_back)

    for item in gates:
        try:
            offsetx = 0
            offsety = 0
            if item.type == 1:
                material = "wood"
            elif item.type == 1:
                material = "stone"
            elif item.type == 1:
                material = "iron"
            elif item.type == 1:
                material = "hardwood"
            gate_img = cropImg(
                assets["fences"][material],
                item.orientation,
                defaultSize=(16, 32),
                objectSize=(24, 32),
            )
            offsetx = -4
            offsety = 16
            farm_base.paste(
                gate_img, (item.x * 16 + offsetx, item.y * 16 - offsety), gate_img
            )
        except Exception as e:
            print(e)

    try:
        farm_base.paste(assets["binLid"], (1136, 210), mask=assets["binLid"])
    except Exception as e:
        print(e)

    for i in range(55, farm_tile_height):
        strip_back = assets["overlays"][type][season]["AlwaysFront"][i]
        farm_base.paste(strip_back, (0, i * 16), strip_back)

    farm_base = farm_base.convert("RGBA").convert(
        "P", palette=Image.ADAPTIVE, colors=255
    )
    return farm_base


# Renders a PNG of the players farm where one 8x8 pixel square is equivalent to one in game tile.
# Legend:   Shades of green - Trees, Weeds, Grass
#      Shades of brown - Twigs, Logs
#      Shades of grey - Stones, Boulders, Fences
#      Dark red - Static buildings
#      Light red - Player placed objects (Scarecrows, etc)
#      Blue - Water
#      Off Tan - Tilled Soil
def generateMinimap(data):
    type = data["type"]
    farm = data["data"]
    image = Image.open("./sdv/assets/base/Minimap/{}.png".format(type))
    pixels = image.load()

    pixels[1, 1] = (255, 255, 255)

    for building in farm["buildings"]:
        for i in range(building[3]):
            for j in range(building[4]):
                colourBox(building[1] + i, building[2] + j, (255, 150, 150), pixels)

    if "terrainFeatures" in farm:
        for tile in farm["terrainFeatures"]:
            name = tile.name
            if name == "Tree":
                colourBox(tile.x, tile.y, (0, 175, 0), pixels)
            elif name == "Grass":
                colourBox(tile.x, tile.y, (0, 125, 0), pixels)
            elif name == "Flooring":
                colourBox(tile.x, tile.y, (50, 50, 50), pixels)
            else:
                colourBox(tile.x, tile.y, (0, 0, 0), pixels)

    if "HoeDirt" in farm:
        for tile in farm["HoeDirt"]:
            colourBox(tile.x, tile.y, (196, 196, 38), pixels)

    if "Flooring" in farm:
        for tile in farm["Flooring"]:
            colourBox(tile.x, tile.y, (50, 50, 50), pixels)

    if "Fences" in farm:
        for tile in farm["Fences"]:
            colourBox(tile.x, tile.y, (200, 200, 200), pixels)

    if "objects" in farm:
        for tile in farm["objects"]:
            name = tile.orientation
            if name == "Weeds":
                colourBox(tile.x, tile.y, (0, 255, 0), pixels)
            elif name == "Stone":
                colourBox(tile.x, tile.y, (125, 125, 125), pixels)
            elif name == "Twig":
                colourBox(tile.x, tile.y, (153, 102, 51), pixels)
            else:
                colourBox(tile.x, tile.y, (255, 0, 0), pixels)

    if "resourceClumps" in farm:
        for tile in farm["resourceClumps"]:
            if tile.type == 672:
                for i in range(tile[3]):
                    for j in range(tile[3]):
                        colourBox(tile.x + i, tile.y + j, (102, 51, 0), pixels)
            elif tile.type == 600:
                for i in range(tile[3]):
                    for j in range(tile[3]):
                        colourBox(tile.x + i, tile.y + j, (75, 75, 75), pixels)
    return image
