import requests
import os
import glob
import hashlib
import time
import json
import getpass
import webbrowser
import sqlite3

TIME_BETWEEN_CHECKS = 5

def find_directories_to_monitor(**kwargs):
    #look in registry? or just at appdata?
    lookin = os.path.join(os.getenv('APPDATA'),'StardewValley\\Saves\\*')
    if 'debug' in kwargs and kwargs['debug']==True:
        lookin = os.path.join(os.getcwd(),'*')
    watches = {}
    for row in [i for i in glob.glob(lookin) if os.path.isdir(i)]:
        savefolder = os.path.join(row,'*')
        dircontents = [[os.path.split(os.path.split(j)[0])[1],os.path.split(j)[1]] for j in glob.glob(savefolder)]
        if any([k[0]==k[1] for k in dircontents]) and any([k[1]=='SaveGameInfo' for k in dircontents]):
            name = [k[0] for k in dircontents if k[0]==k[1]]
            savegameinfoname = [os.path.join(row,k[1]) for k in dircontents if k[1]=='SaveGameInfo']
            watches[name[0]] = {'savefile':os.path.join(row,name[0]),'SaveGameInfo':savegameinfoname[0]}
    return watches

def md5(filename):
    # start_time=time.time()
    h = hashlib.md5()
    with open(filename,'rb') as md5file:
        for chunk in iter(lambda: md5file.read(4096), b""):
            h.update(chunk)
    # print 'md5 took:',time.time()-start_time
    return h.hexdigest()

def watch_files(watches):
    for key in watches.keys():
        if 'previous_md5' not in watches[key].keys():
            watches[key]['previous_md5'] = md5(watches[key]['SaveGameInfo'])
        watches[key]['changed']=False
    flag = False
    while True:
        time.sleep(TIME_BETWEEN_CHECKS)
        for key in watches.keys():
            try:
                checksum = md5(watches[key]['SaveGameInfo'])
            except:
                checksum = None
            if checksum != watches[key]['previous_md5']:
                watches[key]['previous_md5']=checksum
                watches[key]['changed']=True
                flag = True
        if flag == True:
            return watches

def submit_file(filename, api_key, api_secret):
    api_stuff = {'api_key':api_key,'api_secret':api_secret}
    files = {'file':open(filename,'rb')}
    r = requests.post('http://upload.farm/_uploader',files=files,data=api_stuff)
    return (r.status_code,r.text)

def check_settings():
    db = connect_db()
    c = db.cursor()
    try:
        c.execute('SELECT email,api_key,api_secret,settings_json FROM settings')
        result = c.fetchall()
    except sqlite3.OperationalError:
        create_db()
        result = []
    if len(result) == 0:
        email, api_key, api_secret = setup_uploader()
    else:
        email, api_key, api_secret = load_settings(result)
    return email, api_key, api_secret


def setup_uploader():
    print 'Welcome to upload.farm uploader version alpha: commandline edition!'
    print 'To use this you need to sign in (you only need do this the first time).'
    a = raw_input('Do you already have an account? (y/n): ')
    if a.lower() == 'n':
        webbrowser.open('http://upload.farm/su')
        print 'Please register at http://upload.farm/su (opened in browser)'
    while True:
        print 'Please log in:'
        email = raw_input('Email: ')
        password = getpass.getpass()
        result = login_api(email, password)
        if result[0] == 200:
            api_response = json.loads(result[1])
            api_key = api_response['api_key']
            api_secret = api_response['api_secret']
            break
        else:
            print 'Bad email or password! Try again...'
    db = connect_db()
    c = db.cursor()
    c.execute('INSERT INTO settings (email,api_key,api_secret) VALUES (?,?,?)',(email,api_key,api_secret))
    db.commit()
    print 'API keys retrieved and stored!'
    return email, api_key, api_secret

def load_settings(result):
    email = result[0][0]
    api_key = result[0][1]
    api_secret = result[0][2]
    return email, api_key, api_secret

def login_api(email, password):
    api_stuff = {'email':email,'password':password}
    r = requests.post('http://upload.farm/_register-api',data=api_stuff)
    return (r.status_code,r.text)

def create_db():
    try:
        idcode='INTEGER PRIMARY KEY AUTOINCREMENT'
        structure_dict = {'id':idcode,
        'email':'TEXT',
        'api_key':'TEXT',
        'api_secret':'TEXT',
        'settings_json':'TEXT'}
        log_dict = {'id':idcode,
        'time':'TEXT',
        'action':'TEXT',
        'outcome':'TEXT'}

        structure = ''
        for key in sorted(structure_dict.keys()):
            structure += key + ' ' +structure_dict[key] + ',\n'
        structure = structure[:-2]

        log = ''
        for key in sorted(log_dict.keys()):
            log += key + ' ' +log_dict[key] + ',\n'
        log = log[:-2]

        connection=connect_db()
        c=connection.cursor()
        c.execute('CREATE TABLE settings('+structure+')')
        c.execute('CREATE TABLE log('+log+')')
        connection.commit()
        connection.close()
        return True
    except:
        return False

def connect_db():
    connection = sqlite3.connect('uploader.db')
    return connection


if __name__=='__main__':
    email, api_key, api_secret = check_settings()
    watches = find_directories_to_monitor()
    print 'Logged in as',email
    print 'Watching these folders for changes:'
    for key in watches.keys():
        print '\t',key
    while True:
        watches = watch_files(watches)
        # this following code only triggers when watch_files resolves!
        for key in watches.keys():
            if watches[key]['changed']==True:
                print('noticed '+str(key)+' changed, uploading... '),
                result = submit_file(watches[key]['savefile'],api_key,api_secret)
                if result[0] == 200:
                    print('succesfully')
                else:
                    print('but it failed, returned '+str(result[1]))