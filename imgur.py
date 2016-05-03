from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError
from app import app, connect_db
from flask import url_for
import uuid
import json
import time
import sys

if sys.version_info >= (3,0):
    unicode = str
else:
    str = unicode

def checkApiAccess(userid):
    # something that checks whether we have api keys and whether they work;
    # if not, return False
    db = connect_db()
    c = db.cursor()
    c.execute('SELECT imgur_json FROM users WHERE id='+app.sqlesc,(userid,))
    r = c.fetchone()
    if len(r) > 0:
        try:
            r = json.loads(r[0])
            access_token = r['access_token']
            refresh_token = r['refresh_token']
        except TypeError:
            return False
    else:
        return False
    client = ImgurClient(app.config['IMGUR_CLIENTID'],app.config['IMGUR_SECRET'])
    client.set_user_auth(access_token,refresh_token)
    try:
        client.get_account('me').url
        credits = client.credits
        # print(credits)
        if credits['ClientRemaining'] > 10 and credits['UserRemaining'] > 10:
            return True
        else:
            return None
    except ImgurClientError:
        return False

def getAuthUrl(userid,target=None):
    db = connect_db()
    c = db.cursor()
    iuid = unicode(uuid.uuid4())
    imgur_id = json.dumps({'id':iuid,'redir':target})
    c.execute('UPDATE users SET imgur_id='+app.sqlesc+' WHERE id='+app.sqlesc,(iuid,userid))
    db.commit()
    db.close()
    client = ImgurClient(app.config['IMGUR_CLIENTID'],app.config['IMGUR_SECRET'])
    authorization_url = client.get_auth_url('code')+'&state='+unicode(imgur_id)
    return authorization_url

def swapCodeForTokens(response):
    # takes dict of response parameters as input, like {'error':'blah blah'} or {'code':'blah blah','state':'blah blah'}
    db = connect_db()
    c=db.cursor()
    state = json.loads(response['state'])
    user_identifier = state['id']
    redir = state['redir']
    if 'error' in response:
        c.execute('UPDATE users SET imgur_json=NULL WHERE imgur_id='+app.sqlesc,(user_identifier,))
        db.commit()
        return {'success':False}
    # called at the server redirect when imgur returns the code
    client = ImgurClient(app.config['IMGUR_CLIENTID'],app.config['IMGUR_SECRET'])
    credentials = client.authorize(response['code'],'authorization_code')
    # print credentials
    if 'access_token' in credentials.keys() and 'refresh_token' in credentials.keys():
        db = connect_db()
        c = db.cursor()
        c.execute('UPDATE users SET imgur_json='+app.sqlesc+' WHERE imgur_id='+app.sqlesc,(json.dumps(credentials),user_identifier))
        db.commit()
        db.close()
        return {'success':True,'redir':redir}
    else:
        c.execute('UPDATE users SET imgur_json=NULL WHERE imgur_id='+app.sqlesc,(user_identifier,))
        db.commit()
        return {'success':False}

def uploadToImgur(userid,url):
    db = connect_db()
    c = db.cursor()
    c.execute('SELECT map_url,name,farmname,date,imgur_json FROM playerinfo WHERE url='+app.sqlesc,(url,))
    result = c.fetchone()
    if result[4] != None:
        previous_upload_properties = json.loads(result[4])
        if time.time() < previous_upload_properties['upload_time']+(2*3600):
            return {'error':'too_soon','link':previous_upload_properties['imgur_url']}
    map_url = result[0]
    titlestring = u"{} Farm, {} by {}".format(result[2],result[3],result[1])
    descriptionstring = u"Stardew Valley game progress, full summary at http://upload.farm/{}".format(url)
    # try:
    c.execute('SELECT imgur_json FROM users WHERE id='+app.sqlesc,(userid,))
    r = json.loads(c.fetchone()[0])
    access_token = r['access_token']
    refresh_token = r['refresh_token']
    client = ImgurClient(app.config['IMGUR_CLIENTID'],app.config['IMGUR_SECRET'])
    client.set_user_auth(access_token,refresh_token)
    # file = url_for('home',filename=map_url,_external=True)
    # print 'uploaded to',file
    # client.upload_from_url(file,config={'title':'uploaded from','description':'upload.farm'},anon=False)
    if app.config['IMGUR_DIRECT_UPLOAD'] == True:
        result = client.upload_from_path(map_url,config={'title':titlestring,'description':descriptionstring},anon=False)
    else:
        map_url = u"http://upload.farm/{}".format(map_url)
        result = client.upload_from_url(map_url,config={'title':titlestring,'description':descriptionstring},anon=False)
    print(result)
    imgur_json = json.dumps({'imgur_url':'http://imgur.com/'+result['id'],'upload_time':time.time()})
    c.execute('UPDATE playerinfo SET imgur_json='+app.sqlesc+' WHERE url='+app.sqlesc,(imgur_json,url))
    db.commit()
    try:
        return {'success':None,'link':result['link']}
    except:
        return {'error':'upload_issue','link':None}


if __name__ == '__main__':
    code = ''
    if code == '':
        user_id = 1
        check_auth = checkApiAccess(user_id)
        exit()
        if check_auth == False:
            print(getAuthUrl(user_id))
        else:
            print(check_auth)
    else:
        codedict = {'code':code,'state':state}
        swapCodeForTokens(codedict)


    file = './static/images/1AFQF1p.png'
    # print client.upload_from_path(file,config={'title':'uploaded from','description':'python'},anon=False)

    print(client.get_account('me').id)

    response_looks_like = {u'datetime': 1460205330, u'bandwidth': 0, u'nsfw': None,
    u'vote': None, u'id': u'68htuuP', u'account_id': 33971158, u'in_gallery': False,
    u'title': u'The Title', u'section': None, u'width': 80, u'size': 1638, u'type': u'image/png',
    u'deletehash': u'yHKPz1regUue88y', u'description': u'The Description', u'views': 0,
    u'link': u'http://i.imgur.com/68htuuP.png', u'height': 152, u'name': u'', u'favorite': False,
    u'account_url': None, u'comment_preview': None, u'animated': False}