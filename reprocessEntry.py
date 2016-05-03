import psycopg2
import sqlite3
from playerInfo import playerInfo
from farmInfo import getFarmInfo
import json
import hashlib
from imageDrone import process_queue
from createdb import database_structure_dict, database_fields
import io
from xml.etree.ElementTree import ParseError
from app import connect_db, md5, app

sqlesc = app.sqlesc

def processFile(filename,old_md5,rowid,url):
    with open(filename,'rb') as f:
        md5_info = md5(f)
    player_info = playerInfo(filename)
    farm_info = getFarmInfo(filename)
    try:
        assert md5_info == old_md5
    except AssertionError:
        return False
        print filename,'failed md5'
    columns = []
    values = []
    for key in player_info.keys():
        if type(player_info[key]) == list:
            for i,item in enumerate(player_info[key]):
                columns.append(key.replace(' ','_') + str(i))
                values.append(str(item))
        elif type(player_info[key]) == dict:
            for subkey in player_info[key]:
                if type(player_info[key][subkey]) == dict:
                    for subsubkey in player_info[key][subkey]:
                        columns.append((key+subkey+subsubkey).replace(' ','_'))
                        values.append((player_info[key][subkey][subsubkey]))
                else:
                    columns.append((key + subkey).replace(' ','_'))
                    values.append(str(player_info[key][subkey]))
        else:
            columns.append(key)
            values.append(str(player_info[key]))
    columns.append('farm_info')
    values.append(json.dumps(farm_info))
    columns.append('failed_processing')
    values.append(None)

    colstring = ''
    for c in columns:
        colstring += c+', '
    colstring = colstring[:-2]
    questionmarks = ((sqlesc+',')*len(values))[:-1]
    try:
        connection = connect_db()
        cur = connection.cursor()
        cur.execute('UPDATE playerinfo SET ('+colstring+') = ('+questionmarks+') WHERE id='+sqlesc,(tuple(values+[rowid])))
        cur.execute('INSERT INTO todo (task, playerid) VALUES ('+sqlesc+','+sqlesc+')',('process_image',rowid))
        connection.commit()
        connection.close()
        return True
    except (sqlite3.OperationalError, psycopg2.ProgrammingError) as e:
        cur.execute('INSERT INTO errors (ip, time, notes) VALUES ('+sqlesc+','+sqlesc+','+sqlesc+')',('reprocessEntry.py', time.time(),str(e)+' '+str([columns,values])))
        connection.commit()
        return False

def getEntries(where=None):
    connection = connect_db()
    c = connection.cursor()
    if where==None:
        where=''
    c.execute('SELECT id,md5,url,savefileLocation FROM playerinfo '+where)
    entries = c.fetchall()
    connection.close()
    return entries



if __name__ == "__main__":
    entries = getEntries()
    for eno, entry in enumerate(entries):
        print entry
        success = processFile(entry[3],entry[1],entry[0],entry[2])
        print eno+1,'of',len(entries)
        if not success:
            print 'FAIL:',entry
