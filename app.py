#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, session, redirect, url_for, request, flash, g, jsonify, make_response, send_from_directory, abort
import time
from werkzeug import secure_filename, check_password_hash
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.security import generate_password_hash
import os
import sys
from playerInfo import playerInfo
from farmInfo import getFarmInfo
from bigbase import dec2big
import generateSavegame
import json
import hashlib
from imageDrone import process_queue
from createdb import database_structure_dict, database_fields
import defusedxml
import operator
import random
import sqlite3
import psycopg2
import io
from xml.etree.ElementTree import ParseError
import datetime
from flask_recaptcha import ReCaptcha
import uuid
from google_measurement_protocol import Event, report
import imgur
import shutil
from savefile import savefile

if sys.version_info >= (3,0):
    unicode = str
else:
    str = unicode

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)



app = Flask(__name__)
app.config.from_object(os.environ['SDV_APP_SETTINGS'].strip('"'))
recaptcha = ReCaptcha(app=app)
app.secret_key = app.config['SECRET_KEY']
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.wsgi_app = ProxyFix(app.wsgi_app)
if app.config['USE_SQLITE'] == True:
    app.database = app.config['DB_SQLITE']
    app.sqlesc = '?'
    def connect_db():
        return sqlite3.connect(app.database)
else:
    app.database = 'dbname='+app.config['DB_NAME']+' user='+app.config['DB_USER']+' password='+app.config['DB_PASSWORD']
    app.sqlesc = '%s'
    def connect_db():
        return psycopg2.connect(app.database)

def md5(md5file):
    h = hashlib.md5()
    if type(md5file) == io.BytesIO:
        h.update(md5file.getvalue())
    else:
        for chunk in iter(lambda: md5file.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

@app.route('/_get_recents')
def jsonifyRecents():
    return jsonify(recents=get_recents()['posts'])

@app.route('/login', methods=['GET','POST'])
def login():
    start_time=time.time()
    error=None
    session.permanent = True
    if 'logged_in_user' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        if 'email' not in request.form or 'password' not in request.form or request.form['email']=='':
            error = 'Missing email or password for login!'
        else:
            time.sleep(0.2)
            g.db = connect_db()
            cur = g.db.cursor()
            cur.execute('SELECT id,password,auth_key FROM users WHERE email='+app.sqlesc,(request.form['email'],))
            result = cur.fetchall()
            assert len(result) <= 1
            if len(result) == 0:
                error = 'Username not found!'
            else:
                if check_password_hash(result[0][1],request.form['password']) == True:
                    if result[0][2] == None:
                        auth_key = dec2big(random.randint(0,(2**128)))
                        cur.execute('UPDATE users SET auth_key='+app.sqlesc+', login_time='+app.sqlesc+' WHERE id='+app.sqlesc,(auth_key,time.time(),result[0][0]))
                        g.db.commit()
                    else:
                        auth_key = result[0][2]
                    session['logged_in_user']=(result[0][0],auth_key)
                    return redirect(url_for('home'))
                else:
                    error = 'Incorrect password!'
    return render_template("login.html",error=error,processtime=round(time.time()-start_time,5))

@app.route('/su',methods=['GET','POST'])
def signup():
    start_time = time.time()
    error=None
    if 'logged_in_user' in session:
        error = 'You are already logged in!'
    elif request.method == 'POST':
        if 'email' not in request.form or 'password' not in request.form or request.form['email']=='':
            error = 'Missing email or password!'
        elif len(request.form['password'])<app.config['PASSWORD_MIN_LENGTH']:
            error = 'Password too short!'
        else:
            if recaptcha.verify():
                g.db = connect_db()
                cur = g.db.cursor()
                cur.execute('SELECT id FROM users WHERE email='+app.sqlesc,(request.form['email'],))
                result = cur.fetchall()
                if len(result) == 0:
                    if len(request.form['email'].split('@')) == 2 and len(request.form['email'].split('@')[1].split('.'))>= 2:
                        cur.execute('INSERT INTO users (email,password) VALUES ('+app.sqlesc+','+app.sqlesc+')',(request.form['email'],generate_password_hash(request.form['password'])))
                        g.db.commit()
                        flash('You have successfully registered. Now, please sign in!')
                        return redirect(url_for('login'))
                    else:
                        error = 'Invalid email address!'
                else:
                    error = 'This email address has already registered'
            else:
                error = 'Captcha failed! If you are human, please try again!'
    return render_template("signup.html",error=error,processtime=round(time.time()-start_time,5))

@app.route('/acc',methods=['GET','POST'])
def account_page():
    start_time=time.time()
    error = None
    if not logged_in():
        error = 'You must be signed in to view your profile!'
        return render_template("login.html",error=error,processtime=round(time.time()-start_time,5))
    else:
        user = get_logged_in_user()
        claimables = find_claimables()
        g.db = connect_db()
        c = g.db.cursor()
        c.execute('SELECT id,auto_key_json FROM series WHERE owner='+app.sqlesc,(user,))
        r = c.fetchall()
        claimed_ids = {}
        for row in r:
            c.execute('SELECT url,date,imgur_json FROM playerinfo WHERE series_id='+app.sqlesc+' AND owner_id='+app.sqlesc,(row[0],user))
            s = c.fetchall()
            # print s
            s = [list(part[:2])+[json.loads(part[2]) if part[2] != None else None] + list(part[3:]) for part in s]
            claimed_ids[row[0]] = {'auto_key_json':json.loads(row[1]),'data':s}
        claimable_ids = {}
        for row in claimables:
            c.execute('SELECT date FROM playerinfo WHERE id='+app.sqlesc,(row[0],))
            d = c.fetchone()[0]
            c.execute('SELECT auto_key_json FROM series WHERE id=(SELECT series_id FROM playerinfo WHERE id='+app.sqlesc+')',(row[0],))
            a = json.loads(c.fetchone()[0])
            claimable_ids[row[0]] = {'auto_key_json':a,'data':(row[1],d)}
        c.execute('SELECT email,imgur_json FROM users WHERE id='+app.sqlesc,(user,))
        e = c.fetchone()
        g.db.close()
        acc_info = {'email':e[0],'imgur':json.loads(e[1]) if e[1] != None else None}
        return render_template('account.html',error=error,claimed=claimed_ids,claimable=claimable_ids, acc_info=acc_info,processtime=round(time.time()-start_time,5))



def logged_in():
    # designed to prevent repeated db requests
    if not hasattr(g,'logged_in_user'):
        if 'logged_in_user' in session:
            g.db = connect_db()
            cur = g.db.cursor()
            cur.execute('SELECT auth_key FROM users WHERE id='+app.sqlesc,(session['logged_in_user'][0],))
            result = cur.fetchall()
            if len(result) == 0:
                session.pop('logged_in_user',None)
                g.logged_in_user = False
            elif result[0][0] == session['logged_in_user'][1]:
                g.logged_in_user = True
            else:
                session.pop('logged_in_user',None)
                g.logged_in_user = False
        else:
            g.logged_in_user = False
    return g.logged_in_user

app.jinja_env.globals.update(logged_in=logged_in)
app.jinja_env.globals.update(list=list)

def add_to_series(rowid,uniqueIDForThisGame,name,farmName):
    current_auto_key = json.dumps([uniqueIDForThisGame,name,farmName])
    db = connect_db()
    cur = db.cursor()
    if logged_in():
        logged_in_userid = session['logged_in_user'][0]
        cur.execute('SELECT id, owner, members_json FROM series WHERE auto_key_json='+app.sqlesc+' AND owner='+app.sqlesc,(current_auto_key,logged_in_userid))
        result = cur.fetchall()
        db.commit()
        assert len(result)<= 1
        if len(result)==0:
            cur.execute('INSERT INTO series (owner, members_json, auto_key_json) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+') RETURNING id',(logged_in_userid,json.dumps([rowid]),current_auto_key))
            series_id = cur.fetchall()[0][0]
        elif len(result)==1:
            series_id = result[0][0]
            new_members_json = json.dumps(json.loads(result[0][2])+[rowid])
            cur.execute('UPDATE series SET members_json='+app.sqlesc+' WHERE id='+app.sqlesc,(new_members_json,result[0][0]))
    else:
        cur.execute('INSERT INTO series (members_json, auto_key_json) VALUES ('+app.sqlesc+','+app.sqlesc+') RETURNING id',(json.dumps([rowid]),current_auto_key))
        series_id = cur.fetchall()[0][0]
    db.commit()
    db.close()
    return series_id

def get_logged_in_user():
    if logged_in():
        return session['logged_in_user'][0]
    else:
        return None

def file_uploaded(inputfile):
    memfile = io.BytesIO()
    inputfile.save(memfile)
    md5_info = md5(memfile)
    try:
        save = savefile(memfile.getvalue(), True)
        player_info = playerInfo(save)
    except defusedxml.common.EntitiesForbidden:
        error = "I don't think that's very funny"
        return {'type':'render','target':'index.html','parameters':{"error":error}}
    except IOError:
        error = "Savegame failed sanity check (if you think this is in error please let us know)"
        g.db = connect_db()
        cur = g.db.cursor()
        cur.execute('INSERT INTO errors (ip, time, notes) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+')',(request.environ['REMOTE_ADDR'],time.time(),'failed sanity check '+str(secure_filename(inputfile.filename))))
        g.db.commit()
        g.db.close()
        return {'type': 'render', 'target': 'index.html', 'parameters': {"error": error}}
    except AttributeError as e:
        error = "Not valid save file - did you select file 'SaveGameInfo' instead of 'playername_number'?"
        print(e)
        return {'type': 'render', 'target': 'index.html', 'parameters': {"error": error}}
    except ParseError as e:
        error = "Not well-formed xml"
        return {'type':'render','target':'index.html','parameters':{"error":error}}
    dupe = is_duplicate(md5_info,player_info)
    if dupe != False:
        session[dupe[0]] = md5_info
        session[dupe[0]+'del_token'] = dupe[1]
        return {'type':'redirect','target':'display_data','parameters':{"url":dupe[0]}}
        return redirect(url_for('display_data',url=dupe[0]))
    else:
        farm_info = getFarmInfo(save)
        outcome, del_token, rowid, error = insert_info(player_info,farm_info,md5_info)
        if outcome != False:
            filename = os.path.join(app.config['UPLOAD_FOLDER'],outcome)
            with open(filename,'wb') as f:
                f.write(memfile.getvalue())
            series_id = add_to_series(rowid,player_info['uniqueIDForThisGame'],player_info['name'],player_info['farmName'])
            owner_id = get_logged_in_user()
            g.db = connect_db()
            cur = g.db.cursor()
            cur.execute('UPDATE playerinfo SET savefileLocation='+app.sqlesc+', series_id='+app.sqlesc+', owner_id='+app.sqlesc+' WHERE url='+app.sqlesc+';',(filename,series_id,owner_id,outcome))
            g.db.commit()
            g.db.close()
        else:
            if error == None:
                error = "Error occurred inserting information into the database!"
            return {'type':'render','target':'index.html','parameters':{"error":error}}
        process_queue()
        memfile.close()
    if outcome != False:
        session.permanent = True
        session[outcome] = md5_info
        session[outcome+'del_token'] = del_token
        return {'type':'redirect','target':'display_data','parameters':{"url":outcome}}

@app.route('/',methods=['GET','POST'])
def home():
    start_time = time.time()
    error = None
    if request.method == 'POST':
        inputfile = request.files['file']
        if inputfile:
            result = file_uploaded(inputfile)
            if result['type'] == 'redirect':
                return redirect(url_for(result['target'],**result['parameters']))
            elif result['type'] == 'render':
                params = {'error':error,'blogposts':get_blogposts(5),'recents':get_recents(),'processtime':round(time.time()-start_time,5)}
                if 'parameters' in result:
                    for key in result['parameters'].keys():
                        params[key] = result['parameters'][key]
                return render_template(result['target'], **params)
    return render_template("index.html", recents=get_recents(), error=error,blogposts=get_blogposts(5), processtime=round(time.time()-start_time,5))

@app.route('/_uploader',methods=['GET','POST'])
def api_upload():
    if request.method=='POST':
        if verify_api_auth(request.form):
            inputfile = request.files['file']
            result = file_uploaded(inputfile)
            analyticsEvent(uuid.uuid4(),'upload','automaticFileUpload')
            return jsonify(result)
        else:
            return abort(401)

def analyticsEvent(userid, category, action):
    event = Event(category,action)
    r = report(app.config['ANALYTICS_ID'],userid,event)
    return r

def verify_api_auth(form):
    if 'api_key' not in form or 'api_secret' not in form or form['api_key']=='':
        return False
    else:
        g.db = connect_db()
        cur = g.db.cursor()
        cur.execute('SELECT id,api_secret,auth_key FROM users WHERE api_key='+app.sqlesc,(form['api_key'],))
        result = cur.fetchall()
        try:
            assert len(result) == 1
        except AssertionError:
            return False
        #if check_password_hash(result[0][1],form['api_secret']) == True:
        print('need to do proper storage of api keys (in another db table)...')
        if check_password_hash(form['api_secret'],result[0][1]) == True:
            if result[0][2] == None:
                auth_key = dec2big(random.randint(0,(2**128)))
                cur.execute('UPDATE users SET auth_key='+app.sqlesc+', login_time='+app.sqlesc+' WHERE id='+app.sqlesc,(auth_key,time.time(),result[0][0]))
                g.db.commit()
            else:
                auth_key = result[0][2]
            session['logged_in_user']=(result[0][0],auth_key)
            print('returning true')
            return True
        else:
            return False

@app.route('/_register-api',methods=['GET','POST'])
def api_register():
    if request.method=='POST':
        api_data = login_to_api(request.form)
        if api_data != False:
            analyticsEvent(uuid.uuid4(),'login','apiLogin')
            return api_data
        else:
            return abort(401)

def login_to_api(form):
    # takes username password, verifies they're in the db, if so, returns api key and hashed and salted password
    # either from db if exists, or generates them if not
    if 'email' not in form or 'password' not in form or form['email']=='':
        return False
    else:
        g.db = connect_db()
        cur = g.db.cursor()
        cur.execute('SELECT id,password,api_key,api_secret FROM users WHERE email='+app.sqlesc,(form['email'],))
        result = cur.fetchall()
        try:
            assert len(result) == 1
        except AssertionError:
            return False
        #if check_password_hash(result[0][1],form['api_secret']) == True:
        if check_password_hash(result[0][1],form['password']) == True:
            if result[0][2] == None or result[0][3] == None:
                api_key = dec2big(random.randint(0,(2**128)))
                api_secret = dec2big(random.randint(0,(2**128)))
                cur.execute('UPDATE users SET api_key='+app.sqlesc+', api_secret='+app.sqlesc+' WHERE id='+app.sqlesc,(api_key,api_secret,result[0][0]))
                g.db.commit()
            else:
                api_key = result[0][2]
                api_secret = result[0][3]
            return jsonify({'api_key':api_key,'api_secret':generate_password_hash(api_secret)})
        else:
            return False

def get_recents(n=6,**kwargs):
    g.db = connect_db()
    cur = g.db.cursor()
    recents = {}
    where = 'WHERE failed_processing IS NOT TRUE '
    if 'include_failed' in kwargs:
        if kwargs['include_failed']==True:
            where = ''
    query = 'SELECT url, name, farmName, date, avatar_url, farm_url FROM playerinfo '+where+'ORDER BY id DESC LIMIT '+app.sqlesc
    offset = 0
    if 'offset' in kwargs:
        offset = kwargs['offset']
        query += " OFFSET "+app.sqlesc
    if 'offset' in kwargs:
        cur.execute(query,(n,offset))
    else:
        cur.execute(query,(n,))
    recents['posts'] = cur.fetchall()
    cur.execute('SELECT count(*) FROM playerinfo')
    recents['total'] = cur.fetchone()[0]
    if len(recents)==0:
        recents == None
    g.db.close()
    return recents

def is_duplicate(md5_info,player_info):
    db = connect_db()
    cur = db.cursor()
    cur.execute('SELECT id, md5, name, uniqueIDForThisGame, url, del_token FROM playerinfo WHERE md5='+app.sqlesc,(md5_info,))
    matches = cur.fetchall()
    if len(matches) > 0:
        for match in matches:
            if str(player_info['name'])==str(match[2]) and str(player_info['uniqueIDForThisGame'])==str(match[3]):
                db.close()
                return (match[4],match[5])
        db.close()
        return False
    else:
        db.close()
        return False

def insert_info(player_info,farm_info,md5_info):
    columns = []
    values = []
    # player_info['date'] = ['Spring','Summer','Autumn','Winter'][int(((player_info['stats']['DaysPlayed']%(28*4))-((player_info['stats']['DaysPlayed']%(28*4))%(28)))/28)]+' '+str((player_info['stats']['DaysPlayed']%(28*4))%(28))+', Year '+str(((player_info['stats']['DaysPlayed']-player_info['stats']['DaysPlayed']%(28*4))/(28*4))+1)
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
    columns.append('added_time')
    values.append(time.time())
    columns.append('md5')
    values.append(md5_info)
    columns.append('ip')
    values.append(request.environ['REMOTE_ADDR'])
    columns.append('del_token')
    del_token = random.randint(-(2**63)-1,(2**63)-1)
    values.append(del_token)
    columns.append('views')
    values.append('0')
    default_images = [['avatar_url','static/placeholders/avatar.png'],
                      ['farm_url','static/placeholders/minimap.png'],
                      ['map_url','static/placeholders/'+str(player_info['currentSeason'])+'.png'],
                      ['portrait_url','static/placeholders/portrait.png']]
    for default in default_images:
        columns.append(default[0])
        values.append(default[1])

    colstring = ''
    for c in columns:
        colstring += c+', '
    colstring = colstring[:-2]
    questionmarks = ((app.sqlesc+',')*len(values))[:-1]
    g.db = connect_db()
    cur = g.db.cursor()
    try:
        cur.execute('INSERT INTO playerinfo ('+colstring+') VALUES ('+questionmarks+') RETURNING id,added_time',tuple(values))
        row = cur.fetchone()
        url = dec2big(int(row[0])+int(row[1]))
        rowid = row[0]
        cur.execute('UPDATE playerinfo SET url='+app.sqlesc+' WHERE id='+app.sqlesc+'',(url,rowid))
        cur.execute('INSERT INTO todo (task, playerid) VALUES ('+app.sqlesc+','+app.sqlesc+')',('process_image',rowid))
        g.db.commit()
        return url, del_token, rowid, None
    except (sqlite3.OperationalError, psycopg2.ProgrammingError) as e:
        g.db.rollback()
        cur.execute('INSERT INTO errors (ip, time, notes) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+')',(request.environ['REMOTE_ADDR'], time.time(),str(e)+' '+json.dumps([columns,values])))
        g.db.commit()
        return False, del_token, False, "Save file incompatible with current database: error is "+str(e)

@app.route('/<url>')
def display_data(url):
    error = None
    deletable = None
    start_time = time.time()
    g.db = connect_db()
    cur = g.db.cursor()
    cur.execute('SELECT '+database_fields+' FROM playerinfo WHERE url='+app.sqlesc+'',(url,))
    data = cur.fetchall()
    if len(data) != 1:
        error = 'There is nothing here... is this URL correct?'
        cur.execute('INSERT INTO errors (ip, time, notes) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+')',(request.environ['REMOTE_ADDR'],time.time(),str(len(data))+' cur.fetchall() for url:'+str(url)))
        g.db.commit()
        return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))
    else:
        cur.execute('UPDATE playerinfo SET views=views+1 WHERE url='+app.sqlesc+'',(url,))
        g.db.commit()
        datadict = {}
        for k, key in enumerate(sorted(database_structure_dict.keys())):
            if key != 'farm_info':
                datadict[key] = data[0][k]
        claimable = False
        deletable = False
        if datadict['owner_id'] == None:
            if url in session and url+'del_token' in session and session[url] == datadict['md5'] and session[url+'del_token'] == datadict['del_token']:
                if logged_in():
                    claimable = True
                else:
                    deletable = True
        elif logged_in() and str(datadict['owner_id']) == str(get_logged_in_user()):
            deletable = True

        for item in ['money','totalMoneyEarned','statsStepsTaken','millisecondsPlayed']:
            if item == 'millisecondsPlayed':
                datadict[item] = "{:,}".format(round(float((int(datadict[item])/1000)/3600.0),1))
            else:
                datadict[item] = "{:,}".format(datadict[item])

        datadict['animals'] = None if datadict['animals']=='{}' else json.loads(datadict['animals'])
        datadict['portrait_info'] = json.loads(datadict['portrait_info'])
        friendships = sorted([[friendship[11:],datadict[friendship]] for friendship in sorted(database_structure_dict.keys()) if friendship.startswith('friendships') and datadict[friendship]!=None],key=lambda x: x[1])[::-1]
        kills = sorted([[kill[27:].replace('_',' '),datadict[kill]] for kill in sorted(database_structure_dict.keys()) if kill.startswith('statsSpecificMonstersKilled') and datadict[kill]!=None],key=lambda x: x[1])[::-1]
        cur.execute('SELECT url, date FROM playerinfo WHERE series_id='+app.sqlesc,(datadict['series_id'],))
        other_saves = cur.fetchall()
        if datadict['imgur_json']!=None:
            datadict['imgur_json'] = json.loads(datadict['imgur_json'])
        # passworded = True if datadict['del_password'] != None else False
        # passworded=passworded, removed from next line
        claimables = find_claimables()
        if logged_in() == False and len(claimables) > 1 and request.cookies.get('no_signup')!='true':
            flash({'message':"<p>It looks like you have uploaded multiple files, but are not logged in: if you <a href='{}'>sign up</a> or <a href='{}'>sign in</a> you can link these uploads, enable savegame sharing, and one-click-post farm renders to imgur!</p>".format(url_for('signup'),url_for('login')),'cookie_controlled':'no_signup'})
        return render_template("profile.html", deletable=deletable, claimable=claimable, claimables=claimables, data=datadict, kills=kills, friendships=friendships, others=other_saves, error=error, processtime=round(time.time()-start_time,5))

def find_claimables():
    if not hasattr(g,'claimables'):
        sessionids = list(session.keys())
        removals = ['admin','logged_in_user']
        for key in removals:
            try:
                sessionids.remove(key)
            except ValueError:
                pass
        urls = tuple([key for key in sessionids if not key.endswith('del_token')])
        if len(urls) > 0:
            db = connect_db()
            cur = db.cursor()
            cur.execute('SELECT id, md5, del_token, url FROM playerinfo WHERE owner_id IS NULL AND url IN '+app.sqlesc,(urls,))
            result = cur.fetchall()
            checked_results = []
            for row in result:
                if row[1] == session[row[3]] and row[2] == session[row[3]+'del_token']:
                    checked_results.append((row[0],row[3]))
            g.claimables = checked_results
            db.close()
        else:
            g.claimables = []
    return g.claimables

@app.route('/<url>/<instruction>',methods=['GET','POST'])
def operate_on_url(url,instruction):
    error = None
    start_time = time.time()
    if request.method == 'POST':
        if (url in session and url+'del_token' in session) or logged_in():
            g.db = connect_db()
            cur = g.db.cursor()
            if logged_in():
                cur.execute('SELECT url,md5,del_token FROM playerinfo WHERE owner_id='+app.sqlesc,(get_logged_in_user(),))
                result = cur.fetchall()
                for row in result:
                    if not row[0] in session:
                        session[row[0]]=row[1]
                    if not row[0]+'del_token' in session:
                        session[row[0]+'del_token']=row[2]
            if instruction == 'del':
                cur.execute('SELECT owner_id FROM playerinfo WHERE url='+app.sqlesc,(url,))
                data = cur.fetchone()
                if str(data[0]) == str(get_logged_in_user()):
                    outcome = delete_playerinfo_entry(url,session[url],session[url+'del_token'])
                    if outcome == True:
                        return redirect(url_for('home'))
                    else:
                        error = outcome
                else:
                    error = 'You do not own this farm'
                return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))

            elif instruction == 'delall':
                cur.execute('SELECT url,owner_id FROM playerinfo WHERE series_id=(SELECT series_id FROM playerinfo WHERE url='+app.sqlesc+')',(url,))
                data = cur.fetchall()
                for row in data:
                    if str(row[1]) != str(get_logged_in_user()):
                        error = 'You do not own at least one of the farms'
                        return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))
                # verified logged_in_user owns all farms
                for row in data:
                    outcome = delete_playerinfo_entry(row[0],session[row[0]],session[row[0]+'del_token'])
                    if outcome != True:
                        error = outcome
                        return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))
                return redirect(url_for('home'))

            elif instruction == 'claim':
                if url in [url for rowid, url in find_claimables()]:
                    outcome = claim_playerinfo_entry(url,session[url],session[url+'del_token'])
                    if outcome == True:
                        return redirect(url_for('display_data',url=url))
                    else:
                        error = outcome
                else:
                    error = 'You do not have sufficient credentials to claim this page'
                return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))

            elif instruction == 'claimall':
                for rowid, claim_url in find_claimables():
                    outcome = claim_playerinfo_entry(claim_url,session[claim_url],session[claim_url+'del_token'])
                    if outcome != True:
                        error = 'You do not have sufficient credentials to claim one of these pages'
                return redirect(url_for('display_data',url=url))

            elif instruction == 'enable-dl':
                cur.execute('SELECT owner_id,id FROM playerinfo WHERE url='+app.sqlesc,(url,))
                data = cur.fetchone()
                if str(data[0]) == str(get_logged_in_user()):
                    cur = g.db.cursor()
                    cur.execute('UPDATE playerinfo SET download_enabled=TRUE WHERE id='+app.sqlesc,(data[1],))
                    g.db.commit()
                    return redirect(url_for('display_data',url=url))
                else:
                    error = 'You do not have sufficient credentials to perform this action'
                    return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))

            elif instruction == 'disable-dl':
                cur.execute('SELECT owner_id,id FROM playerinfo WHERE url='+app.sqlesc,(url,))
                data = cur.fetchone()
                if str(data[0]) == str(get_logged_in_user()):
                    cur = g.db.cursor()
                    cur.execute('UPDATE playerinfo SET download_enabled=FALSE WHERE id='+app.sqlesc,(data[1],))
                    g.db.commit()
                    return redirect(url_for('display_data',url=url))
                else:
                    error = 'You do not have sufficient credentials to perform this action'
                    return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))

            elif instruction == 'imgur':
                if logged_in():
                    check_access = imgur.checkApiAccess(get_logged_in_user())
                    if check_access == True:
                        result = imgur.uploadToImgur(get_logged_in_user(),url)
                        if 'success' in result:
                            return redirect(result['link'])
                        elif 'error' in result:
                            if result['error'] == 'too_soon':
                                error = 'You have uploaded this page to imgur in the last 2 hours: please wait to upload again'
                            elif result['error'] == 'upload_issue':
                                error = 'There was an issue with uploading the file to imgur. Please try again later!'
                        else:
                            error = 'There was an unknown error!'
                        return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))
                    elif check_access == False:
                        return redirect(imgur.getAuthUrl(get_logged_in_user(),target=request.path))
                    elif check_access == None:
                        error = 'Either you or upload.farm are out of imgur credits for the day! Sorry :( Try again tomorrow'
                        return render_template("error.html", error=error, processtime=round(time.time()-start_time,5))
                else:
                    error = "You must be logged in to post your farm to imgur!"
                    return render_template("signup.html", error=error, processtime=round(time.time()-start_time,5))
        else:
            return render_template("error.html", error="Unknown instruction or insufficient credentials", processtime=round(time.time()-start_time,5))
    else:
        return redirect(url_for('display_data',url=url))

def delete_playerinfo_entry(url, md5, del_token):
    # takes url, md5, and del_token (from session); if verified, deletes
    g.db = connect_db()
    cur = g.db.cursor()
    cur.execute('SELECT id,md5,del_token,url,savefileLocation,avatar_url,farm_url,download_url,owner_id,series_id FROM playerinfo WHERE url='+app.sqlesc,(url,))
    result = cur.fetchone()
    if result[1] == md5 and result[2] == del_token and str(result[8]) == str(get_logged_in_user()):
        if remove_series_link(result[0], result[9]) is False:
            pass  # return 'Problem removing series link!'
        cur.execute('DELETE FROM playerinfo WHERE id=('+app.sqlesc+')', (result[0],))
        shutil.rmtree(os.path.join(app.config.get('IMAGE_FOLDER'), result[3]))
        g.db.commit()
        session.pop(url, None)
        session.pop(url+'del_token', None)
        return True
    else:
        return 'You do not have the correct session information to perform this action!'

def remove_series_link(rowid, series_id):
    # removes a link to playerinfo id (rowid) from id in series (series_id)
    if not hasattr(g,'db'):
        g.db = connect_db()
    cur = g.db.cursor()
    cur.execute('SELECT members_json FROM series WHERE id='+app.sqlesc,(series_id,))
    a = cur.fetchone()
    result = json.loads(a[0]) if a != None else None
    try:
        result.remove(int(rowid))
    except (ValueError,AttributeError):
        return False
    if len(result) == 0:
        cur.execute('DELETE FROM series WHERE id='+app.sqlesc,(series_id,))
        cur.execute('UPDATE playerinfo SET series_id=NULL WHERE id='+app.sqlesc,(rowid,))
    else:
        cur.execute('UPDATE series SET members_json='+app.sqlesc+' WHERE id='+app.sqlesc,(json.dumps(result),series_id))
        cur.execute('UPDATE playerinfo SET series_id=NULL WHERE id='+app.sqlesc,(rowid,))
    g.db.commit()
    return True

def claim_playerinfo_entry(url,md5,del_token):
    # verify ability to be owner, then remove_series_link (checking ownership!), then add_to_series
    if logged_in():
        if not hasattr(g,'db'):
            g.db = connect_db()
        cur = g.db.cursor()
        cur.execute('SELECT id,series_id,md5,del_token,owner_id,uniqueIDForThisGame,name,farmName FROM playerinfo WHERE url='+app.sqlesc,(url,))
        result = cur.fetchone()
        if result[2] == md5 and result[3] == del_token and result[4] == None:
            remove_series_link(result[0], result[1])
            series_id = add_to_series(result[0],result[5],result[6],result[7])
            cur.execute('UPDATE playerinfo SET series_id='+app.sqlesc+', owner_id='+app.sqlesc+' WHERE id='+app.sqlesc,(series_id,get_logged_in_user(),result[0]))
            g.db.commit()
            return True
        else:
            return 'Problem authenticating!'
    else:
        return 'You are not logged in!'

@app.route('/admin',methods=['GET','POST'])
def admin_panel():
    start_time = time.time()
    error = None
    if 'admin' in session:
        #trusted
        returned_blog_data = None
        g.db = connect_db()
        cur = g.db.cursor()
        if request.method == 'POST':
            if request.form['blog'] == 'Post':
                live = False
                if 'live' in request.form:
                    if request.form['live']=='on':
                        live = True
                if request.form['content'] == '' or request.form['blogtitle'] == '':
                    error = 'Failed to post blog entry, title or body was empty!'
                    returned_blog_data = {'blogtitle':request.form['blogtitle'],
                                            'content':request.form['content'],
                                            'checked': live}
                else:
                    cur.execute('INSERT INTO blog (time, author, title, post, live) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+','+app.sqlesc+','+app.sqlesc+')',(int(time.time()),session['admin'],request.form['blogtitle'],request.form['content'],live))
                    g.db.commit()
                    if live == True:
                        flash('Posted blog entry "'+str(request.form['blogtitle']+'"'))
                    else:
                        flash('Saved unposted blog entry "'+str(request.form['blogtitle']+'"'))
            elif request.form['blog'] == 'update':
                state = request.form['live'] == 'true'
                cur.execute('UPDATE blog SET live='+app.sqlesc+' WHERE id='+app.sqlesc,(state,request.form['id']))
                g.db.commit()
                return 'Success'
            elif request.form['blog'] == 'delete':
                cur.execute('DELETE FROM blog WHERE id='+app.sqlesc,(request.form['id'],))
                g.db.commit()
                return 'Success'
        cur.execute('SELECT url,name,farmName,date FROM playerinfo')
        entries = cur.fetchall()
        return render_template('adminpanel.html',returned_blog_data=returned_blog_data,blogposts=get_blogposts(include_hidden=True),entries=entries,error=error, processtime=round(time.time()-start_time,5))
    else:
        if request.method == 'POST':
            if 'blog' in request.form:
                return 'Failure'
            else:
                try:
                    g.db = connect_db()
                    cur = g.db.cursor()
                    cur.execute('SELECT password FROM admin WHERE username='+app.sqlesc+' ORDER BY id',(request.form['username'],))
                    r = cur.fetchone()
                    if r != None:
                        if check_password_hash(r[0],request.form['password']) == True:
                            session['admin']=request.form['username']
                            return redirect(url_for('admin_panel'))
                    cur.execute('INSERT INTO errors (ip, time, notes) VALUES ('+app.sqlesc+','+app.sqlesc+','+app.sqlesc+')',(request.environ['REMOTE_ADDR'], time.time(),'failed login: '+request.form['username']))
                    g.db.commit()
                    g.db.close()
                    error = 'Incorrect username or password'
                except:
                    pass
        return render_template('admin.html',error=error,processtime=round(time.time()-start_time,5))

def get_blogposts(n=False,**kwargs):
    g.db = connect_db()
    cur = g.db.cursor()
    blogposts = None
    query = "SELECT id,time,author,title,post,live FROM blog"
    metaquery = "SELECT count(*) FROM blog"
    try:
        if kwargs['include_hidden'] == False:
            query += " WHERE live='1'"
            metaquery += " WHERE live='1'"
    except KeyError:
        query += " WHERE live='1'"
        metaquery += " WHERE live='1'"
    query += " ORDER BY id DESC"
    if app.config['USE_SQLITE'] == True:
        if n==False:
            n=-1
    if n!=False:
        query += " LIMIT "+app.sqlesc
    offset = 0
    if 'offset' in kwargs:
        offset = kwargs['offset']
    query += " OFFSET "+app.sqlesc
    if n==False:
        cur.execute(query,(offset,))
    else:
        cur.execute(query,(n,offset))
    blogposts = list(cur.fetchall())
    for b,blogentry in enumerate(blogposts):
        blogposts[b] = list(blogentry)
        blogposts[b][1] = datetime.datetime.fromtimestamp(blogentry[1])
    cur.execute(metaquery)
    metadata = cur.fetchone()
    blogdict = {'total':metadata[0],
                'posts':blogposts}
    return blogdict

@app.route('/lo')
def logout():
    if 'admin' in session:
        session.pop('admin',None)
    session.pop('logged_in_user',None)
    return redirect(url_for('home'))

@app.route('/blog')
def blogmain():
    error = None
    start_time = time.time()
    num_entries = 5
    #print(request.args.get('p'))
    try:
        offset = int(request.args.get('p')) * num_entries
    except:
        offset = 0
    if offset < 0:
        return redirect(url_for('blogmain'))
    blogposts = get_blogposts(num_entries,offset=offset)
    if blogposts['total']<=offset and blogposts['total']>0:
        return redirect(url_for('blogmain'))
    return render_template('blog.html',full=True,offset=offset,blogposts=blogposts,error=error, processtime=round(time.time()-start_time,5))

@app.route('/all')
def allmain():
    error = None
    start_time = time.time()
    num_entries = 18
    #print(request.args.get('p'))
    try:
        offset = int(request.args.get('p')) * num_entries
    except TypeError:
        offset = 0
    except:
        error = "No browse with that ID!"
        return render_template('error.html',error=error,processtime=round(time.time()-start_time,5))
    if offset < 0:
        return redirect(url_for('allmain'))
    recents = get_recents(num_entries,offset=offset,include_failed=True)
    if recents['total']<=offset and recents['total']>0:
        return redirect(url_for('allmain'))
    return render_template('all.html',full=True,offset=offset,recents=recents,error=error, processtime=round(time.time()-start_time,5))


@app.route('/blog/<id>')
def blogindividual(id):
    error = None
    start_time = time.time()
    try:
        blogid = int(id)
        g.db = connect_db()
        cur = g.db.cursor()
        cur.execute("SELECT id,time,author,title,post,live FROM blog WHERE id="+app.sqlesc+" AND live='1'",(blogid,))
        blogdata = cur.fetchone()
        if blogdata != None:
            blogdata = list(blogdata)
            blogdata[1] = datetime.datetime.fromtimestamp(blogdata[1])
            blogposts = {'posts':(blogdata,),'total':1}
            return render_template('blog.html',full=True,offset=0,recents=get_recents(),blogposts=blogposts,error=error, processtime=round(time.time()-start_time,5))
        else:
            error = "No blog with that ID!"
    except:
        error = "No blog with that ID!"
    return render_template('error.html',error=error,processtime=round(time.time()-start_time,5))

@app.route('/dl/<url>')
def retrieve_file(url):
    error=None
    start_time = time.time()
    g.db = connect_db()
    cur = g.db.cursor()
    cur.execute("SELECT savefileLocation,name,uniqueIDForThisGame,download_enabled,download_url,id FROM playerinfo WHERE url="+app.sqlesc,(url,))
    result = cur.fetchone()
    if result[3] == True:
        if result[4] == None:
            filename = generateSavegame.createZip(url,result[1],result[2],'static/saves',result[0])
            cur.execute('UPDATE playerinfo SET download_url='+app.sqlesc+' WHERE id='+app.sqlesc,(filename,result[5]))
            g.db.commit()
            return redirect(filename)
        else:
            return redirect(result[4])
    elif 'admin' in session:
        if result != None:
            with open(result[0],'rb') as f:
                response = make_response(f.read())
            response.headers["Content-Disposition"] = "attachment; filename="+str(result[1])+'_'+str(result[2])
            return response
        else:
            error = "URL does not exist"
    else:
        error = "You are unable to download this farm data at this time."
    return render_template('error.html',error=error,processtime=round(time.time()-start_time,5))

@app.route('/faq')
def faq():
    error = None
    start_time=time.time()
    return render_template('faq.html',error=error,processtime=round(time.time()-start_time,5))

@app.route('/imgur')
def get_imgur_auth_code():
    start_time = time.time()
    error = None
    if logged_in():
        if len(request.args)==0:
            return redirect(imgur.getAuthUrl(get_logged_in_user(),target=url_for('account_page')))
        else:
            result = imgur.swapCodeForTokens(request.args)
            if result['success']==True:
                return redirect(result['redir'])
            else:
                error = "Problem authenticating at imgur!"
                return render_template('error.html',error=error,processtime=round(time.time()-start_time,5))
    else:
        error = "Cannot connect to imgur if not logged in!"
        return render_template('error.html',error=error,processtime=round(time.time()-start_time,5))

@app.route('/_vote',methods=['POST'])
def submit_vote():
    if logged_in():
        if request.method == 'POST':
            if 'vote' in request.form:
                return json.dumps(handle_vote(get_logged_in_user(),request.form))
    else:
        return 'not logged in'

def handle_vote(logged_in_user,vote_info):
    # 1: check whether user has voted previously
    g.db = connect_db()
    cur = g.db.cursor()
    vote = json.loads(request.form['vote'])
    cur.execute('SELECT votes FROM users WHERE id='+app.sqlesc,(logged_in_user,))
    votes = cur.fetchone()[0]
    votes = json.loads(votes) if votes != None else {}
    # 2: if voted previously, modify user vote info to new vote, else add vote info to user vote
    previous = votes[request.form['url']] if request.form['url'] in votes else None
    if vote == previous:
        return True
    else:
        # subtract previous vote
        if previous != None:
            prev_col = 'positive_votes' if previous == True else 'negative_votes'
            cur.execute('UPDATE playerinfo SET '+prev_col+'='+prev_col+'-1 WHERE url='+app.sqlesc,(request.form['url'],))
            votes[request.form['url']] = None
        # 3: add vote to correct column in playerinfo
        if vote != None:
            vote_col = 'positive_votes' if vote == True else 'negative_votes'
            cur.execute('UPDATE playerinfo SET '+vote_col+'='+vote_col+'+1 WHERE url='+app.sqlesc,(request.form['url'],))
            votes[request.form['url']] = vote
        votes = json.dumps(votes)
        cur.execute('UPDATE users SET votes='+app.sqlesc+' WHERE id='+app.sqlesc,(votes,logged_in_user))
        g.db.commit()
        return True
        # 4: commit, return

if __name__ == "__main__":
    app.run()