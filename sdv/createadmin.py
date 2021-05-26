# creates db for SDV-Summary
from config import config
from flask import Flask
import os
import sys
from werkzeug.security import generate_password_hash
from sdv.utils.postgres import get_db_connection_string

app = Flask(__name__)
config_name = os.environ.get("SDV_APP_SETTINGS", "development")
app.config.from_object(config[config_name])

if sys.version_info >= (3, 0):
    raw_input = input

if app.config["USE_SQLITE"] == True:
    sqlesc = "?"
    idcode = "INTEGER PRIMARY KEY AUTOINCREMENT"
else:
    sqlesc = "%s"
    idcode = "SERIAL PRIMARY KEY"


def connect_db():
    if app.config["USE_SQLITE"] == True:
        import sqlite3

        connection = sqlite3.connect(app.config["DB_SQLITE"])
    else:
        import psycopg2
        connstr = get_db_connection_string(app.config)
        connection = psycopg2.connect(connstr)
    return connection


def generate_admin():
    connection = connect_db()
    c = connection.cursor()
    c.execute("CREATE TABLE admin (id " + idcode + ", username TEXT, password TEXT)")
    connection.commit()


def init_admin():
    a = raw_input("Generate database? (y/n): ")
    if a == "y":
        generate_admin()
        print("done")
    b = raw_input("Add user? (y/n): ")
    if b == "y":
        connection = connect_db()
        c = connection.cursor()
        user = raw_input("Username: ")
        password = raw_input("Password: ")
        d = raw_input(
            'Username: "'
            + str(user)
            + '", password: "'
            + str(password)
            + '", correct? (y/n): '
        )
        if d == "y":
            c.execute(
                "INSERT INTO admin (username, password) VALUES ("
                + sqlesc
                + ","
                + sqlesc
                + ")",
                (user, generate_password_hash(password)),
            )
            connection.commit()


if __name__ == "__main__":
    init_admin()
