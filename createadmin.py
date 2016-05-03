# creates db for SDV-Summary
import config
from flask import Flask
import os
import sys
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config.from_object(os.environ['SDV_APP_SETTINGS'].strip('"'))

if sys.version_info >= (3, 0):
    raw_input = input

if app.config['USE_SQLITE']==True:
    sqlesc = '?'
    idcode='INTEGER PRIMARY KEY AUTOINCREMENT'
else:
    sqlesc = '%s'
    idcode='SERIAL PRIMARY KEY'

def connect_db():
    if app.config['USE_SQLITE'] == True:
        import sqlite3
        connection = sqlite3.connect(app.config['DB_SQLITE'])
    else:
        import psycopg2
        connection = psycopg2.connect('dbname='+app.config['DB_NAME']+' user='+app.config['DB_USER']+' password='+app.config['DB_PASSWORD'])
    return connection

def generate_admin():
    connection = connect_db()
    c = connection.cursor()
    c.execute('CREATE TABLE admin (id '+idcode+', username TEXT, password TEXT)')
    connection.commit()

if __name__ == "__main__":
    a = raw_input('Generate database? (y/n): ')
    if a == 'y':
        generate_admin()
        print('done')
    b = raw_input('Add user? (y/n): ')
    if b == 'y':
        connection = connect_db()
        c = connection.cursor()
        user = raw_input('Username: ')
        password = raw_input('Password: ')
        d = raw_input('Username: "'+str(user)+'", password: "'+str(password)+'", correct? (y/n): ')
        if d == 'y':
            c.execute("INSERT INTO admin (username, password) VALUES ("+sqlesc+","+sqlesc+")",(user, generate_password_hash(password)))
            connection.commit()

