from PIL import Image
from collections import namedtuple

# from sdv.playerInfo import getPartners
from sdv.playerinfo2 import get_partner
from sdv.savefile import get_location

map_types = [
    "Default",
    "Fishing",
    "Foraging",
    "Mining",
    "Combat",
    "FourCorners",
    "Island",
]


# Check adj. tiles for all tiles on map to determine orientation. Uses bit mask to  select correct tile from spritesheet
def checkSurrounding(tiles):
    floor_map = [[None for a in range(80)] for b in range(65)]
    for tile in tiles:
        try:
            floor_map[tile.y][tile.x] = tile
        except IndexError:
            pass

    temp = []
    m = []

    if tiles[0].name == "Fence":
        m = [5, 3, 10, 6, 5, 3, 0, 6, 9, 8, 7, 7, 2, 8, 4, 4]
        m_gate = [17, 17, 17, 17, 17, 15, 17, 17, 17, 17, 12, 17, 17, 17, 17, 17]
    elif tiles[0].name == "HoeDirt":
        m = [0, 24, 25, 17, 8, 16, 1, 9, 27, 19, 26, 18, 3, 11, 2, 10]
    else:
        m = [0, 12, 13, 9, 4, 8, 1, 5, 15, 11, 14, 10, 3, 7, 2, 6]

    for y, tile_row in enumerate(floor_map):
        for x, tile in enumerate(tile_row):
            a = 0
            if tile is not None:
                for dx, dy, b in [(0, -1, 1), (1, 0, 2), (0, 1, 4), (-1, 0, 8)]:
                    try:
                        current_tile = floor_map[y + dy][x + dx]
                    except IndexError:
                        current_tile = None
                    try:
                        if floor_map[y + dy][x + dx] is not None:
                            if tile.name == "Flooring" or (
                                tile.name == "Fence" and not tile.growth
                            ):
                                if floor_map[y + dy][x + dx].type == tile.type:
                                    a += b
                            else:
                                a += b
                    except Exception as e:
                        pass
                if tile.growth and tile.name == "Fence":
                    orientation = m_gate[a]
                    t = 1
                else:
                    orientation = m[a]
                    t = tile.type
                temp.append(tile._replace(orientation=orientation, type=t))
    return temp


# This is a test method for returning the position location and the name of objects
# located on the players farm.
# returns a dict with an array of tuples of the form: (name, x, y)

sprite = namedtuple(
    "Sprite",
    ["name", "x", "y", "w", "h", "index", "type", "growth", "flipped", "orientation"],
)


def getFarmInfo(saveFile):
    ns = "{http://www.w3.org/2001/XMLSchema-instance}"

    farm = {}

    root = saveFile.getRoot()

    # This is a crude flag to prevent two greenhouses from being registered in version 1.5
    seen_greenhouse = False

    # Farm Objects

    s = []
    farm_location = get_location(root, "Farm")
    farm_age = int(root.find("player").find("stats").find("DaysPlayed").text)
    day_of_season = int(root.find("player").find("dayOfMonthForSaveGame").text)
    is_last_week_of_season = day_of_season > 21
    for item in farm_location.find("objects").iter("item"):
        f = False
        obj = item.find("value").find("Object")
        name = obj.find("name").text
        x = int(item.find("key").find("Vector2").find("X").text)
        y = int(item.find("key").find("Vector2").find("Y").text)
        i = int(obj.find("parentSheetIndex").text)
        try:
            t = obj.find("type").text
        except:
            continue
        a = False
        other = obj.find("name").text
        if name == "Chest":
            colours = obj.find("playerChoiceColor")
            try:
                red = int(colours.find("R").text)
                green = int(colours.find("G").text)
                blue = int(colours.find("B").text)
                tint = (red, green, blue)
                other = [other, tint]
            except Exception as e:
                print("Error getting chest colours. Possibly old save file")

        if obj.find("flipped").text == "true":
            f = True
        if "Fence" in name or name == "Gate":
            t = int(obj.find("whichType").text)
            a = False
            if name == "Gate":
                a = True
            name = "Fence"
        else:
            name = "Object"
        s.append(sprite(name, x, y, 0, 0, i, t, a, f, other))

    d = {k[0]: [a for a in s if a[0] == k[0]] for k in s}

    try:
        farm["Fences"] = checkSurrounding(d["Fence"])
    except Exception as e:
        pass

    farm["objects"] = [a for a in s if a.name != "Fence"]

    # Terrain Features

    tf = []
    crops = []
    for item in farm_location.find("terrainFeatures").iter("item"):
        s = None
        loc = None
        f = False
        name = item.find("value").find("TerrainFeature").get(ns + "type")
        if name == "Tree":
            t = int(item.find("value").find("TerrainFeature").find("treeType").text)
            s = int(item.find("value").find("TerrainFeature").find("growthStage").text)
            if item.find("value").find("TerrainFeature").find("flipped").text == "true":
                f = True
        if name == "Flooring":
            t = int(item.find("value").find("TerrainFeature").find("whichFloor").text)

            # simple fix to correct missing whichView node in some save files
            s = item.find("value").find("TerrainFeature").find("whichView")
            if s is None:
                s = 0
            else:
                s = int(s.text)
        if name == "HoeDirt":
            crop = item.find("value").find("TerrainFeature").find("crop")
            if crop is not None:
                crop_x = int(item.find("key").find("Vector2").find("X").text)
                crop_y = int(item.find("key").find("Vector2").find("Y").text)
                crop_phase = int(crop.find("currentPhase").text)
                crop_location = int(crop.find("rowInSpriteSheet").text)
                if crop_location in [26, 27, 28, 29, 31]:
                    r = int(crop.find("tintColor").find("R").text)
                    g = int(crop.find("tintColor").find("G").text)
                    b = int(crop.find("tintColor").find("B").text)
                    days = int(crop.find("dayOfCurrentPhase").text)
                    o = ((r, g, b), days)
                else:
                    o = None
                crop_flip = False
                if crop.find("flip").text == "true":
                    crop_flip = True
                crop_dead = False
                if crop.find("dead").text == "true":
                    crop_dead = True
                crops.append(
                    sprite(
                        "HoeDirtCrop",
                        crop_x,
                        crop_y,
                        1,
                        1,
                        crop_dead,
                        crop_location,
                        crop_phase,
                        crop_flip,
                        o,
                    )
                )
        if name == "FruitTree":
            t = int(item.find("value").find("TerrainFeature").find("treeType").text)
            s = int(item.find("value").find("TerrainFeature").find("growthStage").text)
            if item.find("value").find("TerrainFeature").find("flipped").text == "true":
                f = True
        if name == "Grass":
            t = int(item.find("value").find("TerrainFeature").find("grassType").text)
            s = int(
                item.find("value").find("TerrainFeature").find("numberOfWeeds").text
            )
            loc = int(
                item.find("value").find("TerrainFeature").find("grassSourceOffset").text
            )
        if name == "Bush":
            name = "Tea_Bush"
            node = item.find("value").find("TerrainFeature")
            f = node.find("flipped").text.lower() == "true"
            t = int(node.find("size").text)

            # Calculate growth stage
            date_planted = int(node.find("datePlanted").text)
            age = farm_age - date_planted
            if age < 10:
                s = 0
            elif age < 20:
                s = 1
            else:
                s = 2

            if s == 2 and is_last_week_of_season:
                s = 3

        x = int(item.find("key").find("Vector2").find("X").text)
        y = int(item.find("key").find("Vector2").find("Y").text)
        tf.append(sprite(name, x, y, 1, 1, loc, t, s, f, None))

    d = {k[0]: [a for a in tf if a[0] == k[0]] for k in tf}
    excludes = ["Flooring", "HoeDirt", "Crop"]
    farm["terrainFeatures"] = [a for a in tf if a.name not in excludes]
    farm["Crops"] = crops

    try:
        farm["Flooring"] = checkSurrounding(d["Flooring"])
    except Exception as e:
        pass

    try:
        farm["HoeDirt"] = checkSurrounding(d["HoeDirt"])
    except:
        pass

    # Large Terrain Features

    large_terrain_features = []
    for ltf in farm_location.find("largeTerrainFeatures"):
        name = ltf.get(ns + "type")
        flipped = ltf.find("flipped").text == "true"
        size = int(ltf.find("size").text)
        x = int(ltf.find("tilePosition").find("X").text)
        y = int(ltf.find("tilePosition").find("Y").text)
        tile_sheet_offset = int(ltf.find("tileSheetOffset").text)

        large_terrain_features.append(
            sprite(name, x, y, 1, 1, tile_sheet_offset, None, size, flipped, None)
        )

    farm["largeTerrainFeatures"] = large_terrain_features

    # Resource Clumps
    s = []

    for item in farm_location.find("resourceClumps").iter("ResourceClump"):
        name = item.get(ns + "type")
        if name is None:
            name = "ResourceClump"
        t = int(item.find("parentSheetIndex").text)
        x = int(item.find("tile").find("X").text)
        y = int(item.find("tile").find("Y").text)
        w = int(item.find("width").text)
        h = int(item.find("height").text)
        s.append(sprite(name, x, y, w, h, None, t, None, None, None))

    farm["resourceClumps"] = s

    s = []
    for item in farm_location.find("buildings").iter("Building"):
        name = "Building"
        x = int(item.find("tileX").text)
        y = int(item.find("tileY").text)
        w = int(item.find("tilesWide").text)
        h = int(item.find("tilesHigh").text)
        t = item.find("buildingType").text
        o = None
        index = 0
        if "cabin" in t.lower():
            try:
                o = min(
                    int(
                        item.find("indoors")
                        .find("farmhand")
                        .find("houseUpgradeLevel")
                        .text
                    ),
                    2,
                )
            except AttributeError:
                o = 0
        if t.lower() == "fish pond":
            netting_style = int(item.find("nettingStyle").find("int").text)

            # Handle water tint, default (25, 155, 178)
            water_color_element = item.find("overrideWaterColor").find("Color")
            red = int(water_color_element.find("R").text)
            green = int(water_color_element.find("G").text)
            blue = int(water_color_element.find("B").text)
            if red == 255 and green == 255 and blue == 255:
                tint = (25, 155, 178)
            else:
                tint = (red, green, blue)

            has_output = item.find("output") is not None

            o = {
                "netting_style": netting_style,
                "water_color": tint,
                "has_output": has_output,
            }

        if t.lower() == "greenhouse":
            seen_greenhouse = True
            hasGreenhouse = False
            try:
                community_center = get_location(root, "CommunityCenter")
                cats = community_center.find("areasComplete").findall("boolean")
                if cats[0].text == "true":
                    hasGreenhouse = True
            except AttributeError:
                pass

            # Check for letter to confirm player has unlocked greenhouse, thanks /u/BumbleBHE
            for letter in root.find("player").find("mailReceived").iter("string"):
                if letter.text == "ccPantry":
                    hasGreenhouse = True

            hasGreenhouse |= farm_location.find("greenhouseUnlocked") == "true"

            index = 1 if hasGreenhouse else 0
            # Offset of greenhouse is 4 not 6
            h -= 2


        s.append(sprite(name, x, y, w, h, index, t, None, None, o))

    farm["buildings"] = s

    house = sprite(
        "House",
        58,
        14,
        10,
        6,
        int(root.find("player").find("houseUpgradeLevel").text),
        None,
        None,
        None,
        None,
    )

    try:
        mapType = int(root.find("whichFarm").text)
    except Exception as e:
        mapType = 0


    farm["misc"] = [house]

    if not seen_greenhouse:
        hasGreenhouse = False
        try:
            community_center = get_location(root, "CommunityCenter")
            cats = community_center.find("areasComplete").findall("boolean")
            if cats[0].text == "true":
                hasGreenhouse = True
        except AttributeError:
            pass

        # Check for letter to confirm player has unlocked greenhouse, thanks /u/BumbleBHE
        for letter in root.find("player").find("mailReceived").iter("string"):
            if letter.text == "ccPantry":
                hasGreenhouse = True

        if mapType == 5:  # Four Corners
            greenhouse_x = 36
            greenhouse_y = 31
        elif mapType == 6:  # Island
            greenhouse_x = 14
            greenhouse_y = 16
        else:
            greenhouse_x = 25
            greenhouse_y = 12

        greenhouse = sprite(
            "Greenhouse", greenhouse_x, greenhouse_y, 0, 6, 1 if hasGreenhouse else 0, None, None, None, None
        )

        farm['misc'].append(greenhouse)


    spouse = get_partner(root.find("player"))
    spouse = spouse.lower() if spouse else None
    return {"type": map_types[mapType], "data": farm, "spouse": spouse}


def colourBox(x, y, colour, pixels, scale=8):
    for i in range(scale):
        for j in range(scale):
            try:
                pixels[x * scale + i, y * scale + j] = colour
            except IndexError:
                pass
    return pixels


# Renders a PNG of the players farm where one 8x8 pixel square is equivalent to one in game tile.
# Legend:   Shades of green - Trees, Weeds, Grass
#      Shades of brown - Twigs, Logs
#      Shades of grey - Stones, Boulders, Fences
#      Dark red - Static buildings
#      Light red - Player placed objects (Scarecrows, etc)
#      Blue - Water
#      Off Tan - Tilled Soil
def generateImage(data):
    type = data["type"]
    farm = data["data"]

    image = Image.open("./sdv/assets/base/minimap/{}.png".format(type))
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


def regenerateFarmInfo(json_from_db):
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

    for key in json_from_db["data"].keys():
        for i, item in enumerate(json_from_db["data"][key]):
            json_from_db["data"][key][i] = sprite(*item)
    return json_from_db
