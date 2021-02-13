# creates db for SDV-Summary
from flask import Flask
import os
import sys
import getpass
from werkzeug import check_password_hash
from config import config

config_name = os.environ.get("SDV_APP_SETTINGS", 'development')
configobj = config[config_name]

database_structure_dict = {
    "md5": "TEXT",
    "url": "TEXT",
    "isMale": "TEXT",
    "pantsColor0": "BIGINT",
    "pantsColor1": "BIGINT",
    "pantsColor2": "BIGINT",
    "pantsColor3": "BIGINT",
    "combatLevel": "BIGINT",
    "maxHealth": "BIGINT",
    "hair": "BIGINT",
    "favoriteThing": "TEXT",
    "maxItems": "BIGINT",
    "skin": "BIGINT",
    "friendshipsWilly": "BIGINT",
    "friendshipsClint": "BIGINT",
    "friendshipsJodi": "BIGINT",
    "friendshipsHarvey": "BIGINT",
    "friendshipsLeah": "BIGINT",
    "friendshipsWizard": "BIGINT",
    "friendshipsJas": "BIGINT",
    "friendshipsAbigail": "BIGINT",
    "friendshipsMaru": "BIGINT",
    "friendshipsElliott": "BIGINT",
    "friendshipsCaroline": "BIGINT",
    "friendshipsPam": "BIGINT",
    "friendshipsDwarf": "BIGINT",
    "friendshipsShane": "BIGINT",
    "friendshipsDemetrius": "BIGINT",
    "friendshipsAlex": "BIGINT",
    "friendshipsGus": "BIGINT",
    "friendshipsVincent": "BIGINT",
    "friendshipsSebastian": "BIGINT",
    "friendshipsRobin": "BIGINT",
    "friendshipsSam": "BIGINT",
    "friendshipsLewis": "BIGINT",
    "friendshipsMarnie": "BIGINT",
    "friendshipsPenny": "BIGINT",
    "friendshipsHaley": "BIGINT",
    "friendshipsPierre": "BIGINT",
    "friendshipsEvelyn": "BIGINT",
    "friendshipsLinus": "BIGINT",
    "friendshipsGeorge": "BIGINT",
    "friendshipsEmily": "BIGINT",
    "friendshipsKent": "BIGINT",
    "friendshipsKrobus": "BIGINT",
    "friendshipsSandy": "BIGINT",
    "friendshipsHenchman": "BIGINT",
    # 'friendshipsBouncer':'BIGINT',
    # 'friendshipsGil':'BIGINT',
    # 'friendshipsGovernor':'BIGINT',
    # 'friendshipsGrandpa':'BIGINT',
    # 'friendshipsGunther':'BIGINT',
    # 'friendshipsMarlon':'BIGINT',
    # 'friendshipsMorris':'BIGINT',
    # 'friendshipsMr_Qi':'BIGINT',
    "farmingLevel": "BIGINT",
    "statsRocksCrushed": "BIGINT",
    "statsDaysPlayed": "BIGINT",
    "statsStepsTaken": "BIGINT",
    "statsSpecificMonstersKilledFly": "BIGINT",
    "statsSpecificMonstersKilledGhost": "BIGINT",
    "statsSpecificMonstersKilledBat": "BIGINT",
    "statsSpecificMonstersKilledSkeleton": "BIGINT",
    "statsSpecificMonstersKilledGrub": "BIGINT",
    "statsSpecificMonstersKilledDust_Spirit": "BIGINT",
    "statsSpecificMonstersKilledStone_Golem": "BIGINT",
    "statsSpecificMonstersKilledFrost_Bat": "BIGINT",
    "statsSpecificMonstersKilledDuggy": "BIGINT",
    "statsSpecificMonstersKilledRock_Crab": "BIGINT",
    "statsSpecificMonstersKilledBig_Slime": "BIGINT",
    "statsSpecificMonstersKilledSludge": "BIGINT",
    "statsSpecificMonstersKilledFrost_Jelly": "BIGINT",
    "statsSpecificMonstersKilledBug": "BIGINT",
    "statsSpecificMonstersKilledGreen_Slime": "BIGINT",
    "statsSpecificMonstersKilledLava_Crab": "BIGINT",
    "statsSpecificMonstersKilledLava_Bat": "BIGINT",
    "statsSpecificMonstersKilledMetal_Head": "BIGINT",
    "statsSpecificMonstersKilledShadow_Brute": "BIGINT",
    "statsSpecificMonstersKilledShadow_Shaman": "BIGINT",
    "statsSpecificMonstersKilledMummy": "BIGINT",
    "statsSpecificMonstersKilledSerpent": "BIGINT",
    "statsSpecificMonstersKilledArmored_Bug": "BIGINT",
    "statsSpecificMonstersKilledVoid_Spirit": "BIGINT",
    "statsSpecificMonstersKilledSquid_Kid": "BIGINT",
    "statsSpecificMonstersKilledPurple_Slime": "BIGINT",
    "statsSpecificMonstersKilledRed_Slime": "BIGINT",
    "statsSpecificMonstersKilledTransparent_Slime": "BIGINT",
    "statsSlimesKilled": "BIGINT",
    "statsPreservesMade": "BIGINT",
    "statsGeodesCracked": "BIGINT",
    "statsSeedsSown": "BIGINT",
    "statsNotesFound": "BIGINT",
    "statsMonstersKilled": "BIGINT",
    "statsStumpsChopped": "BIGINT",
    "statsCropsShipped": "BIGINT",
    "statsCowMilkProduced": "BIGINT",
    "statsFishCaught": "BIGINT",
    "statsPiecesOfTrashRecycled": "BIGINT",
    "statsTrufflesFound": "BIGINT",
    "statsIridiumFound": "BIGINT",
    "statsTimesFished": "BIGINT",
    "statsStarLevelCropsShipped": "BIGINT",
    "statsCopperFound": "BIGINT",
    "statsBarsSmelted": "BIGINT",
    "statsBouldersCracked": "BIGINT",
    "statsCoinsFound": "BIGINT",
    "statsCaveCarrotsFound": "BIGINT",
    "statsStoneGathered": "BIGINT",
    "statsQuestsCompleted": "BIGINT",
    "statsGoatMilkProduced": "BIGINT",
    "statsCoalFound": "BIGINT",
    "statsIronFound": "BIGINT",
    "statsCheeseMade": "BIGINT",
    "statsItemsCooked": "BIGINT",
    "statsWeedsEliminated": "BIGINT",
    "statsTimesUnconscious": "BIGINT",
    "statsChickenEggsLayed": "BIGINT",
    "statsSheepWoolProduced": "BIGINT",
    "statsDiamondsFound": "BIGINT",
    "statsRabbitWoolProduced": "BIGINT",
    "statsAverageBedtime": "BIGINT",
    "statsBeveragesMade": "BIGINT",
    "statsOtherPreciousGemsFound": "BIGINT",
    "statsDuckEggsLayed": "BIGINT",
    "statsItemsCrafted": "BIGINT",
    "statsGiftsGiven": "BIGINT",
    "statsSticksChopped": "BIGINT",
    "statsPrismaticShardsFound": "BIGINT",
    "statsDirtHoed": "BIGINT",
    "statsGoldFound": "BIGINT",
    "statsMysticStonesCrushed": "BIGINT",
    "statsItemsShipped": "BIGINT",
    "statsGoatCheeseMade": "BIGINT",
    "shirt": "BIGINT",
    "uniqueIDForThisGame": "BIGINT",
    "miningLevel": "BIGINT",
    "facialHair": "BIGINT",
    "money": "BIGINT",
    "newEyeColor0": "BIGINT",
    "newEyeColor1": "BIGINT",
    "newEyeColor2": "BIGINT",
    "newEyeColor3": "BIGINT",
    "maxStamina": "BIGINT",
    "farmName": "TEXT",
    "foragingLevel": "BIGINT",
    "fishingLevel": "BIGINT",
    "deepestMineLevel": "BIGINT",
    "accessory": "BIGINT",
    "catPerson": "TEXT",
    "totalMoneyEarned": "BIGINT",
    "millisecondsPlayed": "BIGINT",
    "hairstyleColor0": "BIGINT",
    "hairstyleColor1": "BIGINT",
    "hairstyleColor2": "BIGINT",
    "hairstyleColor3": "BIGINT",
    "name": "TEXT",
    "professions0": "TEXT",
    "professions1": "TEXT",
    "professions2": "TEXT",
    "professions3": "TEXT",
    "professions4": "TEXT",
    "professions5": "TEXT",
    "professions6": "TEXT",
    "professions7": "TEXT",
    "professions8": "TEXT",
    "professions9": "TEXT",
    "farm_info": "TEXT",
    "farm_url": "TEXT",
    "avatar_url": "TEXT",
    "added_time": "FLOAT",
    "ip": "TEXT",
    "del_token": "BIGINT",
    "views": "BIGINT",
    # 'date':'TEXT',
    "savefileLocation": "TEXT",
    "petName": "TEXT",
    "portrait_info": "TEXT",
    "portrait_url": "TEXT",
    "animals": "TEXT",
    "download_enabled": "BOOLEAN",
    "download_url": "TEXT",
    "owner_id": "BIGINT",
    "series_id": "BIGINT",
    "map_url": "TEXT",
    "currentSeason": "TEXT",
    "failed_processing": "BOOLEAN",
    "imgur_json": "TEXT",
    "positive_votes": "BIGINT DEFAULT 1",
    "negative_votes": "BIGINT DEFAULT 1",
    "base_path": "TEXT",
    "thumb_url": "TEXT",
    "private": "BOOLEAN",
    "planner_url": "TEXT",
    "statsGoodFriends": "BIGINT",
    "statsItemsForaged": "BIGINT",
    "dayOfMonthForSaveGame": "TEXT",
    "seasonForSaveGame": "TEXT",
    "yearForSaveGame": "TEXT",
    "farmhands": "JSONB",
}

if configobj.USE_SQLITE == True:
    database_structure_dict["id"] = "INTEGER PRIMARY KEY AUTOINCREMENT"
    sqlesc = "?"
    idcode = "INTEGER PRIMARY KEY AUTOINCREMENT"
else:
    sqlesc = "%s"
    idcode = "SERIAL PRIMARY KEY"
    database_structure_dict["id"] = "SERIAL PRIMARY KEY"

users_structure_dict = {
    "id": idcode,
    "email": "TEXT",
    "email_confirmed": "BOOLEAN",
    "email_conf_token": "TEXT",
    "pw_reset_token": "TEXT",
    "password": "TEXT",
    "imgur_json": "TEXT",
    "imgur_id": "TEXT",
    "patreon_info": "TEXT",
    "patreon_token": "TEXT",
    "patreon_refresh_token": "TEXT",
    "patreon_expiry": "BIGINT",
    "unconditional_api_access": "BOOLEAN",  # designed to allow discretionary
    # awarding of API usage; should not be used when API access is required:
    # update check_api_availability() instead!
    "auth_key": "TEXT",
    "login_time": "BIGINT",
    "api_key": "TEXT",
    "api_secret": "TEXT",
    "votes": "TEXT",
    "privacy_default": "BOOLEAN DEFAULT FALSE",
}

database_fields = ""
database_fields_less_farminfo = ""
for key in sorted(database_structure_dict.keys()):
    database_fields += key + ","
    if key != "farm_info":
        database_fields_less_farminfo += key + ","
database_fields = database_fields[:-1]
database_fields_less_farminfo = database_fields_less_farminfo[:-1]

capitalization_map = {key.lower(): key for key in database_structure_dict.keys()}

if sys.version_info >= (3, 0):
    raw_input = input


def connect_db():
    if configobj.USE_SQLITE == True:
        import sqlite3

        connection = sqlite3.connect(configobj.DB_SQLITE)
    else:
        import psycopg2

        connection = psycopg2.connect(
            "dbname="
            + configobj.DB_NAME
            + " user="
            + configobj.DB_USER
            + " password="
            + configobj.DB_PASSWORD
        )
    return connection


def generate_db():
    database_structure = ""
    for key in sorted(database_structure_dict.keys()):
        database_structure += key + " " + database_structure_dict[key] + ",\n"
    database_structure = database_structure[:-2]
    connection = connect_db()
    c = connection.cursor()
    c.execute("CREATE TABLE playerinfo(" + database_structure + ")")
    connection.commit()
    print("done")


def generate_errors():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE errors (id " + idcode + ", ip TEXT, time BIGINT, notes TEXT);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_todo():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE todo (id "
        + idcode
        + ", task TEXT, playerid TEXT, currently_processing BOOLEAN);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_blog():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE blog(id "
        + idcode
        + ", time BIGINT, author TEXT, title TEXT, post TEXT, live BOOLEAN);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_users():
    users_structure = ""
    for key in sorted(users_structure_dict.keys()):
        users_structure += key + " " + users_structure_dict[key] + ",\n"
    users_structure = users_structure[:-2]
    connection = connect_db()
    c = connection.cursor()
    c.execute("CREATE TABLE users(" + users_structure + ")")
    connection.commit()
    connection.close()
    print("done")


def generate_serial():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE series(id "
        + idcode
        + ", owner INT, members_json TEXT, auto_key_json TEXT);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_plans():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE plans(id "
        + idcode
        + ", failed_render BOOLEAN, added_time BIGINT, source_json TEXT, url TEXT, image_url TEXT, base_path TEXT, planner_url TEXT, views INT, owner_id TEXT, last_visited BIGINT, season TEXT, md5 TEXT, render_deleted BOOL);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_ad_log():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE ad_log(id "
        + idcode
        + ", time BIGINT, ip_address TEXT, ad_id TEXT, ad_place TEXT, ad_file TEXT, ad_url TEXT);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_api_clients():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE api_clients(id "
        + idcode
        + ", name TEXT, key TEXT, secret TEXT, redirect TEXT, info TEXT);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def generate_api_users():
    connection = connect_db()
    c = connection.cursor()
    statement = (
        "CREATE TABLE api_users(id "
        + idcode
        + ", clientid INT, userid INT, token TEXT UNIQUE, refresh_token TEXT UNIQUE, expiry INT, scope TEXT);"
    )
    c.execute(statement)
    connection.commit()
    connection.close()
    print("done")


def set_indexes():
    connection = connect_db()
    c = connection.cursor()
    indexes = [
        "CREATE INDEX series_id_index ON playerinfo (series_id)",
        "CREATE INDEX url_index ON playerinfo (url)",
        "CREATE INDEX views_index ON playerinfo (views)",
        "CREATE INDEX positive_votes_index ON playerinfo (positive_votes)",
        "CREATE INDEX negative_votes_index ON playerinfo (negative_votes)",
        "CREATE INDEX millisecondsPlayed ON playerinfo (millisecondsPlayed)",
    ]
    for index in indexes:
        try:
            c.execute(index)
            connection.commit()
            print("{} successful".format(index))
        except:
            connection.rollback()
            print("{} failed (may already exist)".format(index))

    connection.close()
    print("done")


def delete_db():
    connection = connect_db()
    c = connection.cursor()
    print("you must log in as admin to delete the database")
    username = raw_input("username: ")
    password = getpass.getpass("password: ")
    c.execute("SELECT password FROM admin WHERE username=" + sqlesc, (username,))
    passhash = c.fetchone()
    if check_password_hash(passhash[0], password) == True:
        a = raw_input(
            "just to double check, you REALLY want to delete everything? (y/n): "
        )
        if a == "y":
            c.execute("DROP TABLE playerinfo")
            c.execute("DROP TABLE errors")
            c.execute("DROP TABLE todo")
            c.execute("DROP TABLE blog")
            c.execute("DROP TABLE users")
            c.execute("DROP TABLE series")
            c.execute("DROP TABLE plans")
            connection.commit()
            connection.close()
            print("all (except admin) deleted")
    else:
        print("incorrect credentials")


def update_playerinfo():
    if configobj.USE_SQLITE == True:
        print("This is only for Postgres databases")
        return
    connection = connect_db()
    c = connection.cursor()
    c.execute(
        "SELECT * FROM information_schema.columns WHERE table_schema='public' AND table_name='playerinfo'"
    )
    returned_database_structure = {
        row[3].lower(): row[7].upper() for row in c.fetchall()
    }
    current_design_structure = {
        key.lower(): database_structure_dict[key].upper()
        for key in database_structure_dict.keys()
    }
    redundant = {}
    incorrect_type = {}
    for key in returned_database_structure.keys():
        try:
            if current_design_structure[key] == returned_database_structure[key]:
                # print(key,'matches')
                pass
            else:
                # print(key,'by design:',current_design_structure[key],'db has:',returned_database_structure[key])
                incorrect_type[key] = {
                    "should be": current_design_structure[key],
                    "was": returned_database_structure[key],
                }
            del current_design_structure[key]
        except KeyError:
            # print(key,'in db but not in current design structure')
            redundant[key] = {"redundant": returned_database_structure[key]}
    not_implemented = current_design_structure
    print("not implemented in db:")
    for key in not_implemented.keys():
        print(key, not_implemented[key])
    print("redundant in db:")
    for key in redundant.keys():
        print(key, redundant[key])
    print("incorrect type in db:")
    for key in incorrect_type.keys():
        print(key, incorrect_type[key])
    a = raw_input("Alter database? (y/n): ")
    if a == "y":
        print("you must log in as admin to alter the database")
        username = raw_input("username: ")
        password = getpass.getpass("password: ")
        c.execute("SELECT password FROM admin WHERE username=" + sqlesc, (username,))
        passhash = c.fetchone()
        if check_password_hash(passhash[0], password) == True:
            print("implementing not-implemented keys (ADDing to database)")
            for key in not_implemented.keys():
                a = raw_input(
                    "Add column "
                    + str(key)
                    + " type "
                    + str(not_implemented[key])
                    + " to playerinfo? (y/n): "
                )
                if a == "y":
                    c.execute(
                        "ALTER TABLE playerinfo ADD COLUMN "
                        + str(key)
                        + " "
                        + str(not_implemented[key])
                    )
                    print("done")
            print("removing no-longer-necessary keys (DROPping from database)")
            for key in redundant.keys():
                a = raw_input("Remove column " + str(key) + " from playerinfo? (y/n): ")
                if a == "y":
                    c.execute("ALTER TABLE playerinfo DROP COLUMN " + str(key))
        else:
            print("incorrect credentials")
    connection.commit()
    connection.close()
    print("all modifications committed")


def update_users():
    if configobj.USE_SQLITE == True:
        print("This is only for Postgres databases")
        return
    connection = connect_db()
    c = connection.cursor()
    c.execute(
        "SELECT * FROM information_schema.columns WHERE table_schema='public' AND table_name='users'"
    )
    returned_database_structure = {
        row[3].lower(): row[7].upper() for row in c.fetchall()
    }
    current_design_structure = {
        key.lower(): users_structure_dict[key].upper()
        for key in users_structure_dict.keys()
    }
    redundant = {}
    incorrect_type = {}
    for key in returned_database_structure.keys():
        try:
            if current_design_structure[key] == returned_database_structure[key]:
                # print(key,'matches')
                pass
            else:
                # print(key,'by design:',current_design_structure[key],'db has:',returned_database_structure[key])
                incorrect_type[key] = {
                    "should be": current_design_structure[key],
                    "was": returned_database_structure[key],
                }
            del current_design_structure[key]
        except KeyError:
            # print(key,'in db but not in current design structure')
            redundant[key] = {"redundant": returned_database_structure[key]}
    not_implemented = current_design_structure
    print("not implemented in db:")
    for key in not_implemented.keys():
        print(key, not_implemented[key])
    print("redundant in db:")
    for key in redundant.keys():
        print(key, redundant[key])
    print("incorrect type in db:")
    for key in incorrect_type.keys():
        print(key, incorrect_type[key])
    a = raw_input("Alter database? (y/n): ")
    if a == "y":
        print("you must log in as admin to alter the database")
        username = raw_input("username: ")
        password = getpass.getpass("password: ")
        c.execute("SELECT password FROM admin WHERE username=" + sqlesc, (username,))
        passhash = c.fetchone()
        if check_password_hash(passhash[0], password) == True:
            print("implementing not-implemented keys (ADDing to database)")
            for key in not_implemented.keys():
                a = raw_input(
                    "Add column "
                    + str(key)
                    + " type "
                    + str(not_implemented[key])
                    + " to users? (y/n): "
                )
                if a == "y":
                    c.execute(
                        "ALTER TABLE users ADD COLUMN "
                        + str(key)
                        + " "
                        + str(not_implemented[key])
                    )
                    print("done")
            print("removing no-longer-necessary keys (DROPping from database)")
            for key in redundant.keys():
                a = raw_input("Remove column " + str(key) + " from users? (y/n): ")
                if a == "y":
                    c.execute("ALTER TABLE users DROP COLUMN " + str(key))
        else:
            print("incorrect credentials")
    connection.commit()
    connection.close()
    print("all modifications committed")


def init_db(drop_all=False):
    if drop_all:
        delete_db()
    print("---------")
    a = raw_input("Generate advertising log database? (y/n): ")
    if a == "y":
        generate_ad_log()
    a = raw_input("Generate playerinfo database? (y/n): ")
    if a == "y":
        generate_db()
    a = raw_input("Generate todo database? (y/n): ")
    if a == "y":
        generate_todo()
    a = raw_input("Generate errors database? (y/n): ")
    if a == "y":
        generate_errors()
    a = raw_input("Generate blog database? (y/n): ")
    if a == "y":
        generate_blog()
    a = raw_input("Generate user database? (y/n): ")
    if a == "y":
        generate_users()
    a = raw_input("Generate serial database? (y/n): ")
    if a == "y":
        generate_serial()
    a = raw_input("Generate api_clients database? (y/n): ")
    if a == "y":
        generate_api_clients()
    a = raw_input("Generate api_users database? (y/n): ")
    if a == "y":
        generate_api_users()
    a = raw_input("Generate plans database? (y/n): ")
    if a == "y":
        generate_plans()
    a = raw_input("Set indexes for optimized db access? (y/n): ")
    if a == "y":
        set_indexes()
    print("--------")
    a = raw_input("Update playerinfo database? (y/n): ")
    if a == "y":
        update_playerinfo()
    a = raw_input("Update users database? (y/n): ")
    if a == "y":
        update_users()


if __name__ == "__main__":
    init_db()
