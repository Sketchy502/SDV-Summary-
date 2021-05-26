#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import (
    Flask,
    render_template,
    session,
    redirect,
    url_for,
    request,
    flash,
    g,
    jsonify,
    make_response,
    send_from_directory,
    abort,
)
from flask_babel import Babel, _, Locale
from flask_recaptcha import ReCaptcha
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from werkzeug import secure_filename, check_password_hash
from werkzeug.contrib.fixers import ProxyFix
import time
import os
import sys
import json
import hashlib
from xml.etree.ElementTree import ParseError
import random
import sqlite3
import datetime
import uuid
import io
import sdv.imgur
import patreon
import defusedxml
import psycopg2
import psycopg2.extras

from sdv.asset_bundles import assets

psycopg2.extras.register_json(oid=3802, array_oid=3807, globally=True)
import requests

from sdv.utils.log import app_logger
from sdv.utils.helpers import random_id
from sdv.utils.postgres import get_db_connection_string

# from sdv.playerInfo import playerInfo
from sdv.playerinfo2 import GameInfo
from sdv.farmInfo import getFarmInfo
from sdv.bigbase import dec2big
from sdv.parsers.json import parse_json, json_layout_map
from sdv.parsers.wordfilter import Censor

from config import config

from sdv.createdb import database_structure_dict, database_fields
from sdv.savefile import savefile
from sdv.zipuploads import zopen, zwrite, unzip_request_file
from sdv.getDate import get_date
import sdv.validate

logger = app_logger.getChild("init")

if sys.version_info >= (3, 0):
    unicode = str
    from urllib.parse import urlparse, urlencode
    from urllib.parse import quote_plus, unquote_plus
else:
    str = unicode
    from urllib import quote_plus, unquote_plus, urlencode
    from urlparse import urlparse

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

recaptcha = ReCaptcha()
bcrypt = Bcrypt()
mail = Mail()
censor = Censor()

random.seed()


def create_app(config_name=None):
    logger.info("Creating flask app...")
    app = Flask(__name__)

    if config_name is None:
        logger.info("Config name not supplied, searching environment")
        config_name = os.environ.get("SDV_APP_SETTINGS", "development")
        logger.info("Config name set to: {}".format(config_name))

    logger.info("Initialising extensions")
    app.config.from_object(config[config_name])

    recaptcha.init_app(app=app)
    bcrypt.init_app(app)
    mail.init_app(app)
    censor.init_app(app=app)
    assets.init_app(app)

    app.secret_key = app.config["SECRET_KEY"]
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.wsgi_app = ProxyFix(app.wsgi_app)

    if app.config["USE_SQLITE"]:
        logger.info("Application set to use SQLite")
        app.database = app.config["DB_SQLITE"]
        app.sqlesc = "?"

        def connect_db():
            return sqlite3.connect(app.database)

    else:
        logger.info("Application set to use Postgres")

        connstr = get_db_connection_string(app.config)
        app.database = (connstr)
        app.sqlesc = "%s"

    return app


app = create_app()
babel = Babel(app)


@babel.localeselector
def get_locale():
    default = request.accept_languages.best_match(app.config["LANGUAGES"])
    if "_language" in session and session.get("_language") in app.config["LANGUAGES"]:
        language = (
            session["_language"]
            if session["_language"] in app.config["LANGUAGES"]
            else default
        )
    else:
        language = default
        if language == None:
            language = "en"
        session["_language"] = language
    return language


@babel.timezoneselector
def get_timezone():
    return None


app.jinja_env.globals.update(Locale=Locale)


@app.route("/lang/<code>")
def set_lang(code):
    if code in app.config["LANGUAGES"]:
        session["_language"] = code
    else:
        session["_language"] = request.accept_languages.best_match(
            app.config["LANGUAGES"]
        )
    return redirect(request.referrer)


def connect_db():
    return psycopg2.connect(app.database)


def legacy_location(location):
    """
    this allows for the move from flat-file app to modular app. it's really hacky.
    it should be used ONLY on READ and WRITE commands, NEVER to modify a filename before saving to db - or it'll be
    reapplied later when that filename is read, and you'll end up with LEGACY_ROOT_FOLDER being prepended twice...
    """
    return os.path.join(app.config["LEGACY_ROOT_FOLDER"], location)


app.jinja_env.globals.update(legacy_location=legacy_location)
app.jinja_env.globals.update(get_locale=get_locale)
app.jinja_env.filters["quote_plus"] = lambda u: quote_plus(u)

import sdv.imageDrone  # noqa
import sdv.emailDrone  # noqa
import sdv.generateSavegame  # noqa


def get_db():
    # designed to prevent repeated db connections
    db = getattr(g, "db", None)
    if db is None:
        db = g.db = connect_db()
    return db


@app.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, "db", None)
    if db is not None:
        db.close()


def page_init():
    if not hasattr(g, "start_time"):
        g.start_time = time.time()
    if not hasattr(g, "error"):
        g.error = None


def page_args():
    advert = get_advert()
    return {
        "processtime": round(time.time() - g.start_time, 5),
        "error": g.error,
        "advert": advert,
    }


def get_advert():
    random.seed()
    if request.path == "/":
        if not logged_in() or check_api_eligibility() != True:
            try:
                fpads = app.config["FRONT_PAGE_ADVERTS"]
                result = None if fpads == None else random.choice(fpads)
            except KeyError:
                result = None
        else:
            result = None
    else:
        if not logged_in() or check_api_eligibility() != True:
            try:
                ads = app.config["ADVERTS"]
                result = None if ads == None else random.choice(ads)
            except KeyError:
                result = None
        else:
            result = None
    return result


@app.route("/out/<url>")
def route_out(url):
    url = unquote_plus(url)
    log_ad_click(url, request.args.get("id"), request.args.get("place"))
    return redirect(url)


def log_ad_click(ad_url, ad_id, ad_place):
    db = get_db()
    cur = db.cursor()
    ip = request.environ["REMOTE_ADDR"]
    referral_time = time.time()
    ad_file = None
    cur.execute(
        "INSERT INTO ad_log (time, ip_address, ad_id, ad_place, ad_file, ad_url) VALUES ("
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ")",
        (referral_time, ip, ad_id, ad_place, ad_file, ad_url),
    )
    db.commit()
    return


def md5(md5file):
    h = hashlib.md5()
    if type(md5file) == io.BytesIO:
        h.update(md5file.getvalue())
    else:
        for chunk in iter(lambda: md5file.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


@app.route("/_ver")
def theversion():
    return sys.version


@app.route("/_mini_recents")
def jsonifyRecents():
    mini_recents = [
        str(post[0])
        + str(post[5])
        + str(post[6])
        + str(post[8])
        + str(get_votes(post[0]))
        for post in get_recents()["posts"]
    ]
    return jsonify(mini_recents)


@app.route("/_full_recents")
def get_formatted_recents():
    recents = get_recents()
    vote = None
    votes = None
    if logged_in():
        vote = json.dumps({entry[0]: get_votes(entry[0]) for entry in recents["posts"]})
        votes = {}
        for recent in recents["posts"]:
            votes[recent[0]] = get_votes(recent[0])
    text = render_template("recents.html", recents=recents, vote=vote)
    return jsonify(text=text, votes=votes)


def generate_bcrypt_password_hash(word):
    word = bcrypt.generate_password_hash(word)
    try:
        word = word.decode("utf-8")
    except:
        pass
    return word


def check_bcrypt_password_hash(passwordhash, attempt):
    try:
        result = bcrypt.check_password_hash(passwordhash, attempt)
    except AssertionError:
        return None
    return result


def check_user_pw(email, password_attempt):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id,password,auth_key FROM users WHERE email=" + app.sqlesc, (email,)
    )
    result = cur.fetchall()
    assert len(result) <= 1
    if len(result) == 0:
        return {"result": False, "error": _("Username not found!")}
    else:
        hash_type = _get_hash_type(result[0][1])
        if hash_type == "sha1":
            password_valid = check_password_hash(result[0][1], password_attempt)
            if password_valid:
                new_hash = generate_bcrypt_password_hash(password_attempt)
                cur.execute(
                    "UPDATE users SET password="
                    + app.sqlesc
                    + " WHERE email="
                    + app.sqlesc,
                    (new_hash, email),
                )
                db.commit()
        elif hash_type == "bcrypt":
            password_valid = check_bcrypt_password_hash(result[0][1], password_attempt)
        else:
            return {"result": None}
        if password_valid == True:
            if result[0][2] == None:
                auth_key = dec2big(random.randint(0, (2 ** 128)))
                cur.execute(
                    "UPDATE users SET auth_key="
                    + app.sqlesc
                    + ", login_time="
                    + app.sqlesc
                    + " WHERE id="
                    + app.sqlesc,
                    (auth_key, time.time(), result[0][0]),
                )
                db.commit()
            else:
                auth_key = result[0][2]
            session["logged_in_user"] = (result[0][0], auth_key)
            return {"result": True}
        elif password_valid == None:
            return {"result": None}
        else:
            return {"result": False, "error": _("Incorrect password!")}


def _get_hash_type(hashed_pw):
    # print(hashed_pw)
    split_hash = hashed_pw.split("$")
    # print(split_hash)
    try:
        if split_hash[0] == "pbkdf2:sha1:1000":
            return "sha1"
        elif split_hash[1] == "2b" and split_hash[0] == "":
            return "bcrypt"
        else:
            raise TypeError
    except IndexError:
        return None


@app.route("/login", methods=["GET", "POST"])
def login():
    page_init()
    session.permanent = True
    if logged_in():
        return redirect(url_for("home"))
    if request.method == "POST":
        if (
            "email" not in request.form
            or "password" not in request.form
            or request.form["email"] == ""
        ):
            g.error = _("Missing email or password for login!")
        else:
            pw = check_user_pw(request.form["email"], request.form["password"])
            if pw["result"] == False:
                g.error = pw["error"]
            elif pw["result"] == None:
                flash(
                    {
                        "message": "<p>"
                        + _("Please reset your password to log in!")
                        + "</p>"
                    }
                )
                return redirect(url_for("reset_password"))
            else:
                flash({"message": "<p>" + _("Logged in successfully!") + "</p>"})
                redirect_url = session.get("login_redir")
                if redirect_url:
                    session.pop("login_redir")
                    return redirect(redirect_url)
                else:
                    return redirect(url_for("home"))
    return render_template("login.html", **page_args())


@app.route("/reset", methods=["GET", "POST"])
def reset_password():
    page_init()
    if request.method == "POST":
        if "email" in request.form and request.form["email"] != "":
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT id, email_confirmed FROM users WHERE email=" + app.sqlesc,
                (request.form["email"],),
            )
            result = cur.fetchall()
            if len(result) == 0:
                g.error = _("Username not found!")
            elif result[0][1] != True:
                g.show_verify_button = True
                g.error = _(
                    "Email address not verified; please verify your account using the verification email sent when you registered before attempting to reset password!"
                )
            else:
                cur.execute(
                    "SELECT users.id FROM users WHERE email="
                    + app.sqlesc
                    + " AND NOT EXISTS (SELECT todo.id FROM todo WHERE todo.playerid=CAST(users.id AS text))",
                    (request.form["email"],),
                )
                user_id = cur.fetchone()
                if user_id != None:
                    # cur.execute('INSERT INTO todo (task, playerid) VALUES ('+app.sqlesc+','+app.sqlesc+')',('email_passwordreset',user_id[0]))
                    # db.commit()
                    add_task(user_id[0], "email_passwordreset")
                    emailDrone.process_email()
                    flash({"message": "<p>" + _("Password reset email sent!") + "</p>"})
                else:
                    flash(
                        {
                            "message": "<p>"
                            + _(
                                "Previous password reset email still waiting to be sent... (sorry)"
                            )
                            + "</p>"
                        }
                    )
                return redirect(url_for("home"))
        elif (
            "password" in request.form
            and len(request.form["password"]) >= app.config["PASSWORD_MIN_LENGTH"]
            and "id" in request.form
            and "pw_reset_token" in request.form
        ):
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT pw_reset_token, id FROM users WHERE id=" + app.sqlesc,
                (request.form["id"],),
            )
            t = cur.fetchall()
            if len(t) == 0:
                g.error = _("Cannot reset password: account does not exist")
                return render_template("error.html", **page_args())
            elif t[0][0] == None:
                flash(
                    {
                        "message": "<p>"
                        + _("This reset link has already been used!</p>")
                        + "</p>"
                    }
                )
                return redirect(url_for("home"))
            else:
                if t[0][0] == request.args.get("t"):
                    new_hash = generate_bcrypt_password_hash(request.form["password"])
                    cur.execute(
                        "UPDATE users SET password="
                        + app.sqlesc
                        + ", pw_reset_token=NULL WHERE id="
                        + app.sqlesc,
                        (new_hash, request.form["id"]),
                    )
                    db.commit()
                    flash(
                        {
                            "message": "<p>"
                            + _("Password reset, please log in!")
                            + "</p>"
                        }
                    )
                    return redirect(url_for("login"))
            g.error = _("Malformed verification string!")
            return render_template("error.html", **page_args())
        elif (
            "password" in request.form
            and len(request.form["password"]) < app.config["PASSWORD_MIN_LENGTH"]
        ):
            g.error = _("Password insufficiently long, please try again")
        elif "resend" in request.form:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT id, email_confirmed FROM users WHERE email=" + app.sqlesc,
                (request.form["resend"],),
            )
            result = cur.fetchall()
            if len(result) == 0:
                g.error = _("Username not found!")
            elif result[0][1] != True:
                user_id = result[0][0]
                add_task(user_id, "old_email_confirmation")
                emailDrone.process_email()
                flash(
                    {
                        "message": "<p>"
                        + _("A new verification email has been sent to you")
                        + "</p>"
                    }
                )
        else:
            g.error = _("Please enter the email address you used to register")
    if "i" in request.args and "t" in request.args:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT pw_reset_token, email, id FROM users WHERE id=" + app.sqlesc,
            (request.args.get("i"),),
        )
        t = cur.fetchall()
        if len(t) == 0:
            g.error = _("Cannot reset password: account does not exist")
            return render_template("error.html", **page_args())
        elif t[0][0] == None:
            flash(
                {
                    "message": "<p>"
                    + _("This reset link has already been used!")
                    + "</p>"
                }
            )
            return redirect(url_for("home"))
        else:
            if t[0][0] == request.args.get("t"):
                return render_template("reset.html", details=t[0], **page_args())
        g.error = _("Malformed verification string!")
        return render_template("error.html", **page_args())
    elif logged_in():
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT email FROM users WHERE id=" + app.sqlesc, (get_logged_in_user(),)
        )
        result = cur.fetchall()
        if len(result) > 0:
            g.logged_in_address = result[0][0]
    show_verify_button = getattr(g, "show_verify_button", None)
    logged_in_address = getattr(g, "logged_in_address", None)
    return render_template(
        "reset.html",
        logged_in_address=logged_in_address,
        show_verify_button=show_verify_button,
        **page_args()
    )


@app.route("/su", methods=["GET", "POST"])
def signup():
    page_init()
    if "logged_in_user" in session:
        g.error = _("You are already logged in!")
    elif request.method == "POST":
        if (
            "email" not in request.form
            or "password" not in request.form
            or request.form["email"] == ""
        ):
            g.error = _("Missing email or password!")
        elif len(request.form["password"]) < app.config["PASSWORD_MIN_LENGTH"]:
            g.error = _("Password too short!")
        else:
            if recaptcha.verify():
                db = get_db()
                cur = db.cursor()
                cur.execute(
                    "SELECT id FROM users WHERE email=" + app.sqlesc,
                    (request.form["email"],),
                )
                result = cur.fetchall()
                if len(result) == 0:
                    if (
                        len(request.form["email"].split("@")) == 2
                        and len(request.form["email"].split("@")[1].split(".")) >= 2
                    ):
                        cur.execute(
                            "INSERT INTO users (email,password) VALUES ("
                            + app.sqlesc
                            + ","
                            + app.sqlesc
                            + ") RETURNING id",
                            (
                                request.form["email"],
                                generate_bcrypt_password_hash(request.form["password"]),
                            ),
                        )
                        user_id = cur.fetchall()[0][0]
                        # cur.execute('INSERT INTO todo (task, playerid) VALUES ('+app.sqlesc+','+app.sqlesc+')',('email_confirmation',user_id))
                        # db.commit()
                        add_task(user_id, "email_confirmation")
                        emailDrone.process_email()
                        flash(
                            {
                                "message": "<p>"
                                + _(
                                    "You have successfully registered. A verification email has been sent to you. Now, please sign in!"
                                )
                                + "</p>"
                            }
                        )
                        return redirect(url_for("login"))
                    else:
                        g.error = _("Invalid email address!")
                else:
                    g.error = _("This email address has already registered")
            else:
                g.error = _("Captcha failed! If you are human, please try again!")
    return render_template("signup.html", **page_args())


@app.route("/acc", methods=["GET", "POST"])
def account_page():
    page_init()
    if not logged_in():
        g.error = _("You must be signed in to view your profile!")
        return render_template("login.html", **page_args())
    else:
        user = get_logged_in_user()
        claimables = find_claimables()
        db = get_db()
        c = db.cursor()
        if request.method == "POST":
            if "privacy_default" in request.form and request.form.get(
                "privacy_default"
            ) in ["True", "False"]:
                # print c.mogrify('UPDATE users SET privacy_default='+app.sqlesc+' WHERE id='+app.sqlesc,(True if request.form.get('privacy_default') == 'True' else False,user)).decode('utf-8')
                c.execute(
                    "UPDATE users SET privacy_default="
                    + app.sqlesc
                    + " WHERE id="
                    + app.sqlesc,
                    (
                        True
                        if request.form.get("privacy_default") == "True"
                        else False,
                        user,
                    ),
                )
                db.commit()
        c.execute(
            "SELECT id,auto_key_json FROM series WHERE owner=" + app.sqlesc, (user,)
        )
        r = c.fetchall()
        claimed_ids = {}
        for row in r:
            c.execute(
                "SELECT url,statsDaysPlayed,dayOfMonthForSaveGame,seasonForSaveGame,yearForSaveGame,imgur_json FROM playerinfo WHERE series_id="
                + app.sqlesc
                + " AND owner_id="
                + app.sqlesc
                + " ORDER BY statsDaysPlayed ASC",
                (row[0], user),
            )
            s = c.fetchall()
            for i, entry in enumerate(s):
                s[i] = (
                    list(entry[:1])
                    + [
                        get_date(
                            {
                                "statsDaysPlayed": entry[1],
                                "dayOfMonthForSaveGame": entry[2],
                                "seasonForSaveGame": entry[3],
                                "yearForSaveGame": entry[4],
                            }
                        )
                    ]
                    + list(entry[5:])
                )
            s = [
                list(part[:2])
                + [json.loads(part[2]) if part[2] != None else None]
                + list(part[3:])
                for part in s
            ]
            claimed_ids[row[0]] = {"auto_key_json": json.loads(row[1]), "data": s}
        claimable_ids = {}
        for row in claimables:
            c.execute(
                "SELECT statsDaysPlayed,dayOfMonthForSaveGame,seasonForSaveGame,yearForSaveGame FROM playerinfo WHERE id="
                + app.sqlesc,
                (row[0],),
            )
            d_data = c.fetchone()
            d = get_date(
                {
                    "statsDaysPlayed": d_data[0],
                    "dayOfMonthForSaveGame": d_data[1],
                    "seasonForSaveGame": d_data[2],
                    "yearForSaveGame": d_data[3],
                }
            )
            c.execute(
                "SELECT auto_key_json FROM series WHERE id=(SELECT series_id FROM playerinfo WHERE id="
                + app.sqlesc
                + ")",
                (row[0],),
            )
            a = json.loads(c.fetchone()[0])
            claimable_ids[row[0]] = {"auto_key_json": a, "data": (row[1], d)}
        c.execute(
            "SELECT email,imgur_json,privacy_default,patreon_info FROM users WHERE id="
            + app.sqlesc,
            (user,),
        )
        e = c.fetchone()
        acc_info = {
            "email": e[0],
            "imgur": json.loads(e[1]) if e[1] != None else None,
            "privacy_default": e[2],
            "patreon": json.loads(e[3]) if e[3] != None else None,
        }
        has_liked = True if True in has_votes(user).values() else False
        return render_template(
            "account.html",
            claimed=claimed_ids,
            claimable=claimable_ids,
            has_liked=has_liked,
            acc_info=acc_info,
            **page_args()
        )


def logged_in():
    # designed to prevent repeated db requests
    if not hasattr(g, "logged_in_user"):
        if "logged_in_user" in session:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT auth_key FROM users WHERE id=" + app.sqlesc,
                (session["logged_in_user"][0],),
            )
            result = cur.fetchall()
            if len(result) == 0:
                session.pop("logged_in_user", None)
                g.logged_in_user = False
            elif result[0][0] == session["logged_in_user"][1]:
                g.logged_in_user = True
            else:
                session.pop("logged_in_user", None)
                g.logged_in_user = False
        else:
            g.logged_in_user = False
    return g.logged_in_user


def set_api_user(api_user_id):
    g.api_user_id = api_user_id
    set_privacy_for_api(api_user_id)


def api_user():
    if hasattr(g, "api_user_id"):
        return True
    else:
        return False


app.jinja_env.globals.update(logged_in=logged_in)
app.jinja_env.globals.update(list=list)
app.jinja_env.add_extension("jinja2.ext.do")


def add_to_series(rowid, uniqueIDForThisGame, name, farmName):
    current_auto_key = json.dumps([uniqueIDForThisGame, name, farmName])
    db = get_db()
    cur = db.cursor()
    if logged_in() or api_user():
        logged_in_userid = get_logged_in_user()
        cur.execute(
            "SELECT id, owner, members_json FROM series WHERE auto_key_json="
            + app.sqlesc
            + " AND owner="
            + app.sqlesc,
            (current_auto_key, logged_in_userid),
        )
        result = cur.fetchall()
        db.commit()
        assert len(result) <= 1
        if len(result) == 0:
            cur.execute(
                "INSERT INTO series (owner, members_json, auto_key_json) VALUES ("
                + app.sqlesc
                + ","
                + app.sqlesc
                + ","
                + app.sqlesc
                + ") RETURNING id",
                (logged_in_userid, json.dumps([rowid]), current_auto_key),
            )
            series_id = cur.fetchall()[0][0]
        elif len(result) == 1:
            series_id = result[0][0]
            new_members_json = json.dumps(json.loads(result[0][2]) + [rowid])
            cur.execute(
                "UPDATE series SET members_json="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (new_members_json, result[0][0]),
            )
    else:
        cur.execute(
            "INSERT INTO series (members_json, auto_key_json) VALUES ("
            + app.sqlesc
            + ","
            + app.sqlesc
            + ") RETURNING id",
            (json.dumps([rowid]), current_auto_key),
        )
        series_id = cur.fetchall()[0][0]
    db.commit()
    return series_id


def get_logged_in_user():
    if logged_in():
        return session["logged_in_user"][0]
    elif api_user():
        return g.api_user_id
    else:
        return None


def file_uploaded(inputfile):
    memfile = io.BytesIO()
    inputfile.save(memfile)
    md5_info = md5(memfile)
    try:
        save = savefile(memfile.getvalue(), True)
        player_info = GameInfo(save).get_info()
    except defusedxml.common.EntitiesForbidden:
        g.error = _("I don't think that's very funny")
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }
    except IOError:
        g.error = _(
            "Savegame failed sanity check (if you think this is in error please let us know)"
        )
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO errors (ip, time, notes) VALUES ("
            + app.sqlesc
            + ","
            + app.sqlesc
            + ","
            + app.sqlesc
            + ")",
            (
                request.environ["REMOTE_ADDR"],
                time.time(),
                "failed sanity check " + str(secure_filename(inputfile.filename)),
            ),
        )
        db.commit()
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }
    except AttributeError as e:
        g.error = _(
            "Not valid save file - did you select file 'SaveGameInfo' instead of 'playername_number'?"
        )
        # print(e)
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }
    except ParseError as e:
        g.error = _("Not well-formed xml")
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }
    except AssertionError as e:
        g.error = _("Savegame failed an internal check (often caused by mods) sorry :(")
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }
    except Exception as e:
        logger.error("An unexpected error occoured: {}".format(e))
        g.error = _("An unexpected error has occoured.")
        return {
            "type": "render",
            "target": "index.html",
            "parameters": {"error": g.error},
        }

    dupe = is_duplicate(md5_info, player_info)
    if dupe != False:
        session[dupe[0]] = md5_info
        session[dupe[0] + "del_token"] = dupe[1]
        return {
            "type": "redirect",
            "target": "display_data",
            "parameters": {"url": dupe[0]},
        }
    else:
        farm_info = getFarmInfo(save)
        outcome, del_token, rowid, g.error = insert_info(
            player_info, farm_info, md5_info
        )
        if outcome != False:
            filename = os.path.join(app.config["UPLOAD_FOLDER"], outcome)
            # with open(filename,'wb') as f:
            # 	f.write(memfile.getvalue())
            # REPLACED WITH ZIPUPLOADS
            zwrite(memfile.getvalue(), legacy_location(filename))
            series_id = add_to_series(
                rowid,
                player_info["uniqueIDForThisGame"],
                player_info["name"],
                player_info["farmName"],
            )
            owner_id = get_logged_in_user()
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "UPDATE playerinfo SET savefileLocation="
                + app.sqlesc
                + ", series_id="
                + app.sqlesc
                + ", owner_id="
                + app.sqlesc
                + " WHERE url="
                + app.sqlesc
                + ";",
                (filename, series_id, owner_id, outcome),
            )
            db.commit()
        else:
            user_error = _("An error occurred whilst processing the save file.")
            if g.error is None:
                g.error = _("Error occurred inserting information into the database!")
            logger.error(
                "An error occurred when inserting save to database: {}".format(g.error)
            )
            return {
                "type": "render",
                "target": "index.html",
                "parameters": {"error": user_error},
            }
        imageDrone.process_queue()
        memfile.close()
    if outcome != False:
        session.permanent = True
        session[outcome] = md5_info
        session[outcome + "del_token"] = del_token
        return {
            "type": "redirect",
            "target": "display_data",
            "parameters": {"url": outcome},
        }


@app.route("/", methods=["GET", "POST"])
def home():
    page_init()
    if request.method == "POST":
        inputfile = request.files["file"]
        if inputfile:
            result = file_uploaded(inputfile)
            if result["type"] == "redirect":
                return redirect(url_for(result["target"], **result["parameters"]))
            elif result["type"] == "render":
                params = {
                    "blogposts": get_blogposts(5),
                    "recents": get_recents(),
                    "vote": json.dumps(
                        {
                            entry[0]: get_votes(entry[0])
                            for entry in get_recents()["posts"]
                        }
                    ),
                }
                if "parameters" in result:
                    for key in result["parameters"].keys():
                        params[key] = result["parameters"][key]
                return render_template(result["target"], **params)
    recents = get_recents()
    vote = json.dumps({entry[0]: get_votes(entry[0]) for entry in recents["posts"]})
    return render_template(
        "index.html",
        recents=recents,
        vote=vote,
        blogposts=get_blogposts(5),
        **page_args()
    )


@app.route("/auth", methods=["POST", "GET"])
def api_auth():
    page_init()
    if request.args.get("client_id"):
        if logged_in():
            db = get_db()
            cur = db.cursor()
            if request.method == "POST":
                # should probably have some kind of csrf protection! perhaps hidden form field in GET request which is POSTed back? [answer: yes]
                cur.execute(
                    "DELETE FROM api_users WHERE userid = "
                    + app.sqlesc
                    + " AND clientid = (SELECT id FROM api_clients WHERE key = "
                    + app.sqlesc
                    + ")",
                    (get_logged_in_user(), request.args.get("client_id")),
                )
                db.commit()
                for i in range(100):
                    # try 100 times to insert new uuids; if fails 100 times, something is seriously wrong!
                    try:
                        token = str(uuid.uuid4())
                        refresh_token = str(uuid.uuid4())
                        expires_in = 3600
                        expiry = int(time.time()) + expires_in
                        cur.execute(
                            "INSERT INTO api_users(clientid,userid,token,refresh_token,expiry) VALUES ((SELECT id FROM api_clients WHERE key = "
                            + app.sqlesc
                            + "),"
                            + app.sqlesc
                            + ","
                            + app.sqlesc
                            + ","
                            + app.sqlesc
                            + ","
                            + app.sqlesc
                            + ")",
                            (
                                request.args.get("client_id"),
                                get_logged_in_user(),
                                token,
                                refresh_token,
                                expiry,
                            ),
                        )
                        db.commit()
                        cur.execute(
                            "SELECT redirect, name FROM api_clients WHERE key = "
                            + app.sqlesc,
                            (request.args.get("client_id"),),
                        )
                        results = cur.fetchall()
                        try:
                            assert len(results) < 2
                        except AssertionError:
                            g.error = _(
                                "Multiple entries for this client_id! Please contact the site administrator!"
                            )
                            return render_template("error.html", **page_args())
                        # try:
                        flash(
                            {
                                "message": "<p>"
                                + _(
                                    "You have granted access to %(client)s, you may now close this tab",
                                    client=results[0][1],
                                )
                                + "</p>"
                            }
                        )
                        return redirect(
                            results[0][0]
                            + "?"
                            + urlencode(
                                {
                                    "token": token,
                                    "refresh_token": refresh_token,
                                    "expiry": expires_in,
                                }
                            )
                        )
                        # except:
                        #     g.error = "An unexpected error occurred returning the token to {}! Please try again later.".format(results[0][1])
                        #     return render_template("error.html", **page_args())
                    except psycopg2.IntegrityError:
                        db.rollback()
                g.error = _(
                    "Unable to generate unique key! Something bad has happened, report to site administrator!"
                )
                return render_template("error.html", **page_args())
            else:
                eligible = check_api_eligibility()
                if eligible:
                    cur.execute(
                        "SELECT name, id FROM api_clients WHERE key = " + app.sqlesc,
                        (request.args.get("client_id"),),
                    )
                    results = cur.fetchall()
                    try:
                        assert len(results) < 2
                    except AssertionError:
                        g.error = _(
                            "Multiple entries for this client_id! Please contact the site administrator!"
                        )
                        return render_template("error.html", **page_args())
                    if len(results) == 0:
                        g.error = _("Referrer client_id is invalid!")
                        return render_template("error.html", **page_args())
                    else:
                        cur.execute(
                            "SELECT COUNT(*) FROM api_users WHERE userid = "
                            + app.sqlesc
                            + " AND clientid = (SELECT id FROM api_clients WHERE key = "
                            + app.sqlesc
                            + ")",
                            (get_logged_in_user(), request.args.get("client_id")),
                        )
                        entries = cur.fetchone()
                        # print(entries)
                        api_client_name = results[0][0]
                        if entries[0] != 0:
                            flash(
                                {
                                    "message": "<p>"
                                    + _(
                                        "You have previously approved %(client)s to access your account - reauthorising will generate a new API key",
                                        client=api_client_name,
                                    )
                                    + "</p>"
                                }
                            )
                        return render_template(
                            "api_auth.html",
                            api_client_name=api_client_name,
                            **page_args()
                        )
                else:
                    g.error = _(
                        "At this time, the upload.farm API and uploader are for upload.farm supporters only. If you are already a supporter, please connect your Patreon account on your account panel. If your Patreon account is already linked, please check you have active pledges. If you think this is in error, please contact us via the About page!"
                    )
                    return render_template("error.html", **page_args())
        else:
            flash({"message": "<p>" + _("Please log in first") + "</p>"})
            session["login_redir"] = url_for(
                "api_auth", client_id=request.args.get("client_id")
            )
            return redirect(url_for("login"))
    else:
        g.error = _(
            "Referrer didn't include client_id in request! Please contact whoever linked you here."
        )
        return render_template("error.html", **page_args())


@app.route("/api/v1/get_user_info", methods=["POST"])
def api_v1_get_user_info():
    if request.method == "POST":
        credential_check = check_api_credentials(request.form)
        if "user" in credential_check:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT email FROM users WHERE id = " + app.sqlesc,
                (credential_check.get("user"),),
            )
            result = cur.fetchone()
            return make_response(jsonify({"email": result[0]}))
        else:
            return make_response(
                jsonify(
                    {
                        key: value
                        for key, value in credential_check.items()
                        if key in ["error", "error_description"]
                    }
                ),
                400,
            )


@app.route("/api/v1/get_series_info", methods=["POST"])
def api_v1_get_series_info():
    if request.method == "POST":
        if "url" in request.form:
            credential_check = check_api_credentials(request.form)
            if "user" in credential_check:
                db = get_db()
                cur = db.cursor()
                set_api_user(credential_check["user"])
                entries = get_entries(
                    n=10000,
                    series=request.form.get("url"),
                    sort_by="chronological",
                    include_failed=False,
                )
                entries["posts"] = entries["posts"][::-1]
                return make_response(jsonify(entries))
            else:
                return make_response(
                    jsonify(
                        {
                            key: value
                            for key, value in credential_check.items()
                            if key in ["error", "error_description"]
                        }
                    ),
                    400,
                )
    else:
        return make_response(jsonify({"error": "no_url_error"}), 400)


@app.route("/api/v1/get_user_uploads", methods=["POST"])
def api_v1_get_user_uploads():
    if request.method == "POST":
        credential_check = check_api_credentials(request.form)
        if "user" in credential_check:
            db = get_db()
            cur = db.cursor()
            set_api_user(credential_check["user"])

            user = get_logged_in_user()
            cur.execute(
                "SELECT id,auto_key_json FROM series WHERE owner="
                + app.sqlesc
                + " ORDER BY id ASC",
                (user,),
            )
            r = cur.fetchall()
            claimed_ids = []
            for row in r:
                cur.execute(
                    "SELECT url,statsDaysPlayed,dayOfMonthForSaveGame,seasonForSaveGame,yearForSaveGame FROM playerinfo WHERE series_id="
                    + app.sqlesc
                    + " AND owner_id="
                    + app.sqlesc
                    + " ORDER BY millisecondsPlayed DESC LIMIT 1",
                    (row[0], user),
                )
                s = cur.fetchall()
                for i, entry in enumerate(s):
                    url = entry[0]
                    date = get_date(
                        {
                            "statsDaysPlayed": entry[1],
                            "dayOfMonthForSaveGame": entry[2],
                            "seasonForSaveGame": entry[3],
                            "yearForSaveGame": entry[4],
                        }
                    )
                cur.execute(
                    "SELECT count(*) FROM playerinfo WHERE series_id="
                    + app.sqlesc
                    + " AND owner_id="
                    + app.sqlesc,
                    (row[0], user),
                )
                total = cur.fetchone()[0]
                claimed_ids.append(json.loads(row[1])[1:] + [url, date, total])

            return make_response(jsonify(claimed_ids))
        else:
            return make_response(
                jsonify(
                    {
                        key: value
                        for key, value in credential_check.items()
                        if key in ["error", "error_description"]
                    }
                ),
                400,
            )


@app.route("/api/v1/upload_zipped", methods=["POST"])
def api_v1_upload_zipped():
    if request.method == "POST":
        if "zip" in request.files:
            credential_check = check_api_credentials(request.form)
            if "user" in credential_check:
                rate_limited = check_upload_zip_rate_limiter(credential_check["user"])
                if rate_limited != None:
                    return make_response(
                        jsonify(
                            {"error": "over_rate_limit", "retry-next": rate_limited}
                        ),
                        429,
                    )
                set_api_user(credential_check["user"])
                try:
                    inputfile = unzip_request_file(request.files["zip"])
                except zipfile.BadZipfile:
                    return make_response(jsonify({"error": "bad_zip_error"}), 400)
                return make_response(jsonify(_api_zip_uploaded(inputfile)))
            else:
                return make_response(
                    jsonify(
                        {
                            key: value
                            for key, value in credential_check.items()
                            if key in ["error", "error_description"]
                        }
                    ),
                    400,
                )
        else:
            return make_response(jsonify({"error": "no_file_error"}), 400)


@app.route("/api/v1/uploader_version", methods=["GET"])
def api_v1_uploader_version():
    return make_response(jsonify({"version": "2.0"}))


def set_privacy_for_api(userid):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT privacy_default FROM users WHERE id=" + app.sqlesc, (userid,))
    g.logged_in_privacy_default = cur.fetchone()[0]


def _api_zip_uploaded(inputfile):
    memfile = inputfile.read()
    md5_info = md5(io.BytesIO(memfile))
    error = None
    try:
        save = savefile(memfile, True)
        player_info = GameInfo(save).get_info()
    except (
        defusedxml.common.EntitiesForbidden,
        IOError,
        AttributeError,
        ParseError,
        AssertionError,
    ):
        return {"error": "invalid_file_error"}
    dupe = is_duplicate(md5_info, player_info)
    if dupe != False:
        return {"url": dupe[0]}
    else:
        farm_info = getFarmInfo(save)
        outcome, del_token, rowid, error = insert_info(player_info, farm_info, md5_info)
        if outcome != False:
            filename = os.path.join(app.config["UPLOAD_FOLDER"], outcome)
            zwrite(memfile, legacy_location(filename))
            owner_id = get_logged_in_user()
            series_id = add_to_series(
                rowid,
                player_info["uniqueIDForThisGame"],
                player_info["name"],
                player_info["farmName"],
            )
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "UPDATE playerinfo SET savefileLocation="
                + app.sqlesc
                + ", series_id="
                + app.sqlesc
                + ", owner_id="
                + app.sqlesc
                + " WHERE url="
                + app.sqlesc
                + ";",
                (filename, series_id, owner_id, outcome),
            )
            db.commit()
        else:
            return {"error": "internal_server_error"}
        imageDrone.process_queue()
    if outcome != False:
        return {"url": outcome}


def check_upload_zip_rate_limiter(owner_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT added_time FROM playerinfo WHERE owner_id="
        + app.sqlesc
        + " AND added_time>"
        + app.sqlesc
        + " ORDER BY added_time ASC",
        (owner_id, time.time() - app.config["API_V1_UPLOAD_ZIP_TIME_PER_USER"]),
    )
    results = cur.fetchall()
    if len(results) <= app.config["API_V1_UPLOAD_ZIP_LIMIT_PER_USER"]:
        return None
    else:
        return int(
            app.config["API_V1_UPLOAD_ZIP_TIME_PER_USER"]
            - (time.time() - results[0][0])
        )


@app.route("/api/v1/refresh_token", methods=["POST"])
def api_v1_refresh_token():
    if request.method == "POST":
        credential_check = refresh_api_credentials(request.form)
        # print(credential_check)
        if "token" in credential_check:
            return make_response(jsonify(credential_check))
        elif "error" in credential_check:
            return make_response(
                jsonify(
                    {
                        key: value
                        for key, value in credential_check.items()
                        if key in ["error", "error_description"]
                    }
                ),
                400,
            )
        else:
            return make_response(jsonify({"error": "internal_server_error"}), 500)


def refresh_api_credentials(formdata):
    """returns new expiry if refresh_token/client_id/client_secret correct and valid"""
    client_id = formdata.get("client_id")
    client_secret = formdata.get("client_secret")
    refresh_token = formdata.get("refresh_token")
    if None in [client_id, client_secret, refresh_token]:
        return {"error": "invalid_token"}
    else:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id,userid from api_users WHERE refresh_token = "
            + app.sqlesc
            + " AND clientid = (SELECT id FROM api_clients WHERE key = "
            + app.sqlesc
            + " AND secret = "
            + app.sqlesc
            + ")",
            (refresh_token, client_id, client_secret),
        )
        result = cur.fetchall()
        if len(result) == 0:
            return {"error": "bad_refresh_token"}
        elif len(result) != 1:
            return {"internal_error": "multiple_users_returned"}
        else:
            # perform the checking for API key eligibility...
            set_api_user(result[0][1])
            eligible = check_api_eligibility()
            if eligible:
                for i in range(100):
                    # try 100 times to insert new uuids; if fails 100 times, something is seriously wrong!
                    try:
                        token = str(uuid.uuid4())
                        refresh_token = str(uuid.uuid4())
                        expires_in = 3600
                        expiry = int(time.time()) + expires_in
                        cur.execute(
                            "UPDATE api_users SET token = "
                            + app.sqlesc
                            + ", refresh_token = "
                            + app.sqlesc
                            + ", expiry = "
                            + app.sqlesc
                            + " WHERE id = "
                            + app.sqlesc,
                            (token, refresh_token, expiry, result[0][0]),
                        )
                        db.commit()
                        return {
                            "token": token,
                            "refresh_token": refresh_token,
                            "expires_in": expires_in,
                        }
                    except psycopg2.IntegrityError:
                        db.rollback()
            else:
                return {"error": "no_api_access"}
            return {"internal_error": "unable_to_generate_new_unique_keys"}


def check_api_eligibility():
    """checks whether a user can use the upload.farm API; returns True if can, False if not"""
    # first check db field for unconditional API access
    if _user_has_unconditional_api_access() == True:
        return True
    # then check Patreon
    try:
        patreon_info = update_patreon_info_for_current_user()
        if patreon_info["num_pledges"] > 0:
            return True
    except:
        pass
    return False


def _user_has_unconditional_api_access():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT unconditional_api_access FROM users WHERE id =" + app.sqlesc,
        (get_logged_in_user(),),
    )
    result = cur.fetchone()
    if result[0] == True:
        return True
    else:
        return False


def check_api_credentials(formdata):
    """returns users id in {user:id} if token/client_id/client_secret/expiry correct and valid,
    else returns {error:type}"""
    client_id = formdata.get("client_id")
    client_secret = formdata.get("client_secret")
    token = formdata.get("token")
    if None in [client_id, client_secret, token]:
        return {"error": "invalid_request"}
    else:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT userid from api_users WHERE token = "
            + app.sqlesc
            + " AND expiry > "
            + app.sqlesc
            + " AND clientid = (SELECT id FROM api_clients WHERE key = "
            + app.sqlesc
            + " AND secret = "
            + app.sqlesc
            + ")",
            (token, time.time(), client_id, client_secret),
        )
        result = cur.fetchall()
        if len(result) == 0:
            cur.execute(
                "SELECT userid from api_users WHERE token = "
                + app.sqlesc
                + " AND expiry <= "
                + app.sqlesc
                + " AND clientid = (SELECT id FROM api_clients WHERE key = "
                + app.sqlesc
                + " AND secret = "
                + app.sqlesc
                + ")",
                (token, time.time(), client_id, client_secret),
            )
            result2 = cur.fetchall()
            if len(result2) == 1:
                return {"error": "invalid_token", "error_description": "token_expired"}
            else:
                return {"error": "bad_token"}
        try:
            assert len(result) == 1
        except AssertionError:
            return {"internal_error": "multiple_users_returned"}
        return {"user": result[0][0]}


@app.route("/api/v1/plan", methods=["POST"])
def api_v1_plan():
    if request.method == "POST":
        # check input json for validity (because if it's invalid, why hit db?)
        try:
            input_structure = request.get_json()
            if input_structure == None:
                return make_response(jsonify({"status": "no_json_header"}), 400)
            verify_json(input_structure)
        except AssertionError:
            return make_response(jsonify({"status": "bad_input"}), 400)

        # check rate limiter; if all good, continue, else return status:'overlimit'
        try:
            check_rate_limiter()
        except AssertionError:
            return make_response(jsonify({"status": "over_rate_limit"}), 429)

        # check conversion to upload.farm format & map type
        try:
            parsed = parse_json(input_structure["plan_json"])
            if parsed["type"] == "unsupported_map":
                return make_response(jsonify({"status": "unsupported_map"}), 400)
        except:
            return make_response(
                jsonify({"status": "failed_conversion_to_local_structure"}), 400
            )

        # insert it to the database, checking for duplicates(?)
        season = None if "season" not in input_structure else input_structure["season"]
        url, md5_value = check_for_duplicate(input_structure["plan_json"], season)
        if url == None:  # if no existing url
            # insert into db
            plan_id, url = add_plan(
                json.dumps(input_structure["plan_json"]),
                input_structure["source_url"],
                season,
                md5_value,
            )
            # queue a rendering job
            add_task(plan_id, "process_plan_image")
            # optional: run imageDrone
            imageDrone.process_plans()
            # check for number of entries; remove entry if over limit
            check_max_renders()
        # return status:'success'
        return make_response(
            jsonify(
                {
                    "status": "success",
                    "url": url_for("display_plan", url=url, _external=True),
                }
            ),
            200,
        )


@app.route("/api/v1/render_exists", methods=["GET"])
def api_v1_render_exists():
    if "url" in request.args:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT render_deleted FROM plans WHERE url=" + app.sqlesc,
            (request.args.get("url"),),
        )
        try:
            result = True if cur.fetchone()[0] != True else False
            return make_response(jsonify({"render_exists": result}))
        except:
            return make_response(jsonify({"render_exists": None}), 400)
    return make_response(jsonify(None), 400)


def check_rate_limiter():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT count(*) FROM plans WHERE added_time>" + app.sqlesc,
        (time.time() - app.config["API_V1_PLAN_TIME"],),
    )
    assert cur.fetchone()[0] <= app.config["API_V1_PLAN_LIMIT"]


def check_max_renders():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT count(*) FROM plans WHERE render_deleted IS NOT TRUE AND failed_render IS NOT TRUE"
    )
    if cur.fetchone()[0] > app.config["API_V1_PLAN_MAX_RENDERS"]:
        # print('over max render limit!')
        cur.execute(
            "SELECT url FROM plans WHERE render_deleted IS NOT TRUE AND failed_render IS NOT TRUE AND last_visited=(SELECT MIN(last_visited) FROM plans WHERE render_deleted IS NOT TRUE AND failed_render IS NOT TRUE);"
        )
        url = cur.fetchone()[0]
        remove_render_over_limit(url)


def remove_render_over_limit(url):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE plans SET render_deleted=TRUE WHERE url="
        + app.sqlesc
        + " RETURNING image_url, base_path",
        (url,),
    )
    image_url, base_path = cur.fetchone()
    if image_url != None and os.path.split(os.path.split(image_url)[0])[1] == url:
        # second condition ensures you're in a folder named after the URL which prevents accidentally deleting placeholders
        try:
            os.remove(legacy_location(image_url))
        except:
            pass
    try:
        os.rmdir(legacy_location(base_path))
    except:
        pass
    db.commit()


def verify_json(input_structure):
    assert "plan_json" in input_structure
    assert "source_url" in input_structure
    if "season" in input_structure:
        assert input_structure["season"] in sdv.validate.seasons


def add_plan(source_json, planner_url, season, md5_value):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO plans (added_time,source_json,planner_url,views,last_visited,season,md5) VALUES ("
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ","
        + app.sqlesc
        + ") RETURNING id, added_time;",
        (time.time(), source_json, planner_url, 0, time.time(), season, md5_value),
    )
    row = cur.fetchone()
    url = dec2big(int(row[0]) + int(row[1]))
    cur.execute(
        "UPDATE plans SET url=" + app.sqlesc + " WHERE id=" + app.sqlesc + "",
        (url, row[0]),
    )
    db.commit()
    return row[0], url


def add_task(id_number, task_type):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO todo (task, playerid) VALUES ("
        + app.sqlesc
        + ","
        + app.sqlesc
        + ")",
        (task_type, id_number),
    )
    db.commit()


def make_hashable(input_json):
    big_string = ""
    for key in sorted(input_json.keys()):
        sub_string = "{}: {{".format(key)
        if type(input_json[key]) == list:
            sub_string += "["
            for item in input_json[key]:
                sub_string += "{"
                for sub_key in sorted(item.keys()):
                    sub_string += "{}:{},".format(sub_key, item[sub_key])
                sub_string += "},"
            sub_string += "]"
        elif type(input_json[key]) == dict:
            sub_string += "{"
            for sub_key in sorted(input_json[key].keys()):
                if type(input_json[key][sub_key]) != dict:
                    sub_string += "{}:{},".format(sub_key, input_json[key][sub_key])
                else:
                    sub_string += "{"
                    for sub_sub_key in sorted(input_json[key][sub_key].keys()):
                        sub_string += "{}:{},".format(
                            sub_sub_key, input_json[key][sub_key][sub_sub_key]
                        )
                    sub_string += "},"
            sub_string += "},"
        sub_string += "}, "
        big_string += sub_string
    return big_string


def check_for_duplicate(plan_json, season):
    h = hashlib.md5()
    h.update(make_hashable(plan_json).encode())
    md5_value = h.hexdigest()
    db = get_db()
    cur = db.cursor()
    if season == None:
        cur.execute(
            "SELECT source_json, url FROM plans WHERE md5="
            + app.sqlesc
            + " AND season IS NULL",
            (md5_value,),
        )
    else:
        cur.execute(
            "SELECT source_json, url FROM plans WHERE md5="
            + app.sqlesc
            + " AND season="
            + app.sqlesc,
            (md5_value, season),
        )
    result = cur.fetchone()
    if result != None and make_hashable(json.loads(result[0])) == make_hashable(
        plan_json
    ):
        return result[1], md5_value
    else:
        return None, md5_value


"""
# DEPRECATED 'API' CODE
# left in as reminder of how it worked; remove once new api complete

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
        db = get_db()
        cur = db.cursor()
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
                db.commit()
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
        db = get_db()
        cur = db.cursor()
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
                db.commit()
            else:
                api_key = result[0][2]
                api_secret = result[0][3]
            return jsonify({'api_key':api_key,'api_secret':generate_password_hash(api_secret)})
        else:
            return False
"""


def get_planner_link(url):
    # check for existing planner_url in db; if present return this
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT planner_url, savefileLocation, id FROM playerinfo WHERE url="
        + app.sqlesc,
        (url,),
    )
    result = cur.fetchone()
    if result[0] != None:
        return {"status": "success", "planner_url": result[0]}
    else:
        # check file exists; read file; raise error if problem!
        try:
            f = {"file": open(legacy_location(result[1]), "rb")}
        except IOError:
            # file is missing or not in the right place!
            return {"status": "missing_file"}
        # send to stardew.info
        r = requests.post(
            "https://stardew.info/api/import", files=f, verify=False
        )  # verify false as there was a strange SSLError when I ran this on the server
        response = r.json()
        status_code = r.status_code
        # check not error (r.json()['message'] I think)
        if "message" in response:
            return {"status": response["message"]}
        elif "absolutePath" in response:
            # add absolutePath to database & commit
            cur.execute(
                "UPDATE playerinfo SET planner_url="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (response["absolutePath"], result[2]),
            )
            db.commit()
            return {"status": "success", "planner_url": response["absolutePath"]}
        elif status_code == 429:
            return {"status": "over_rate_limit"}
        else:
            return {"status": "unknown_error"}


def get_recents(n=6, **kwargs):
    recents = get_entries(n, **kwargs)
    return recents


def is_duplicate(md5_info, player_info):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, md5, name, uniqueIDForThisGame, url, del_token FROM playerinfo WHERE md5="
        + app.sqlesc,
        (md5_info,),
    )
    matches = cur.fetchall()
    if len(matches) > 0:
        for match in matches:
            if str(player_info["name"]) == str(match[2]) and str(
                player_info["uniqueIDForThisGame"]
            ) == str(match[3]):
                return (match[4], match[5])
        return False
    else:
        return False


def get_privacy():
    if not hasattr(g, "logged_in_privacy_default"):
        if logged_in():
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT privacy_default FROM users WHERE id=" + app.sqlesc,
                (get_logged_in_user(),),
            )
            g.logged_in_privacy_default = cur.fetchone()[0]
        else:
            g.logged_in_privacy_default = None
    return g.logged_in_privacy_default


def key_in_database_structure(key):
    if key in database_structure_dict:
        return True
    else:
        return False


def insert_info(player_info, farm_info, md5_info):
    columns = []
    values = []
    # player_info['date'] = ['Spring','Summer','Autumn','Winter'][int(((player_info['stats']['DaysPlayed']%(28*4))-((player_info['stats']['DaysPlayed']%(28*4))%(28)))/28)]+' '+str((player_info['stats']['DaysPlayed']%(28*4))%(28))+', Year '+str(((player_info['stats']['DaysPlayed']-player_info['stats']['DaysPlayed']%(28*4))/(28*4))+1)
    for key in player_info.keys():
        if key == "UniqueMultiplayerID":
            continue
        if key == "farmhands":
            if key_in_database_structure(key):
                columns.append(key)
                values.append(json.dumps(player_info[key]))
        elif type(player_info[key]) == list:
            for i, item in enumerate(player_info[key]):
                if key_in_database_structure(key.replace(" ", "_") + str(i)):
                    columns.append(key.replace(" ", "_") + str(i))
                    values.append(str(item))
        elif type(player_info[key]) == dict:
            for subkey in player_info[key]:
                if type(player_info[key][subkey]) == dict:
                    for subsubkey in player_info[key][subkey]:
                        if key_in_database_structure(
                            (key + subkey + subsubkey).replace(" ", "_")
                        ):
                            columns.append((key + subkey + subsubkey).replace(" ", "_"))
                            values.append((player_info[key][subkey][subsubkey]))
                else:
                    if key_in_database_structure((key + subkey).replace(" ", "_")):
                        columns.append((key + subkey).replace(" ", "_"))
                        values.append(str(player_info[key][subkey]))
        else:
            columns.append(key)
            values.append(str(player_info[key]))
    columns.append("farm_info")
    values.append(json.dumps(farm_info))
    columns.append("added_time")
    values.append(time.time())
    columns.append("md5")
    values.append(md5_info)
    columns.append("ip")
    values.append(request.environ["REMOTE_ADDR"])
    columns.append("del_token")
    del_token = random.randint(-(2 ** 63) - 1, (2 ** 63) - 1)
    values.append(del_token)
    columns.append("views")
    values.append("0")
    if get_privacy() != None:
        columns.append("private")
        values.append(get_privacy())
    default_images = [
        ["avatar_url", "static/placeholders/avatar.png"],
        ["farm_url", "static/placeholders/minimap.png"],
        [
            "map_url",
            "static/placeholders/" + str(player_info["currentSeason"]) + ".png",
        ],
        ["portrait_url", "static/placeholders/portrait.png"],
    ]
    for default in default_images:
        columns.append(default[0])
        values.append(default[1])

    colstring = ""
    for c in columns:
        colstring += c + ", "
    colstring = colstring[:-2]
    questionmarks = ((app.sqlesc + ",") * len(values))[:-1]
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO playerinfo ("
            + colstring
            + ") VALUES ("
            + questionmarks
            + ") RETURNING id,added_time",
            tuple(values),
        )
        row = cur.fetchone()
        url = dec2big(int(row[0]) + int(row[1]))
        rowid = row[0]
        cur.execute(
            "UPDATE playerinfo SET url=" + app.sqlesc + " WHERE id=" + app.sqlesc + "",
            (url, rowid),
        )
        # cur.execute('INSERT INTO todo (task, playerid) VALUES ('+app.sqlesc+','+app.sqlesc+')',('process_image',rowid))
        add_task(rowid, "process_image")
        db.commit()
        return url, del_token, rowid, None
    except (sqlite3.OperationalError, psycopg2.ProgrammingError) as e:
        db.rollback()
        cur.execute(
            "INSERT INTO errors (ip, time, notes) VALUES ("
            + app.sqlesc
            + ","
            + app.sqlesc
            + ","
            + app.sqlesc
            + ")",
            (
                request.environ["REMOTE_ADDR"],
                time.time(),
                str(e) + " " + json.dumps([columns, values]),
            ),
        )
        db.commit()
        return (
            False,
            del_token,
            False,
            _("Save file incompatible with current database: error is ") + str(e),
        )


@app.route("/<url>")
def display_data(url):
    page_init()
    deletable = None
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT " + database_fields + " FROM playerinfo WHERE url=" + app.sqlesc + "",
        (url,),
    )
    data = cur.fetchall()
    if len(data) != 1:
        g.error = _("There is nothing here... is this URL correct?")
        if str(url) != "favicon.ico":
            cur.execute(
                "INSERT INTO errors (ip, time, notes) VALUES ("
                + app.sqlesc
                + ","
                + app.sqlesc
                + ","
                + app.sqlesc
                + ")",
                (
                    request.environ["REMOTE_ADDR"],
                    time.time(),
                    str(len(data)) + " cur.fetchall() for url:" + str(url),
                ),
            )
            db.commit()
        return render_template("error.html", **page_args())
    else:
        cur.execute(
            "UPDATE playerinfo SET views=views+1 WHERE url=" + app.sqlesc + "", (url,)
        )
        db.commit()
        datadict = {}
        for k, key in enumerate(sorted(database_structure_dict.keys())):
            if key != "farm_info":
                datadict[key] = data[0][k]
        claimable = False
        deletable = False
        if datadict["owner_id"] == None:
            if (
                url in session
                and url + "del_token" in session
                and session[url] == datadict["md5"]
                and session[url + "del_token"] == datadict["del_token"]
            ):
                if logged_in():
                    claimable = True
                else:
                    deletable = True
        elif logged_in() and str(datadict["owner_id"]) == str(get_logged_in_user()):
            deletable = True

        # other_saves, gallery_set = get_others(datadict['url'],datadict['date'],datadict['map_url'])
        other_saves, gallery_set = get_others(
            datadict["url"], get_date(datadict), datadict["map_url"]
        )
        for item in [
            "money",
            "totalMoneyEarned",
            "statsStepsTaken",
            "millisecondsPlayed",
        ]:
            if item == "millisecondsPlayed":
                datadict[item] = "{:,}".format(
                    round(float((int(datadict[item]) / 1000) / 3600.0), 1)
                )
            else:
                datadict[item] = "{:,}".format(datadict[item])

        datadict["animals"] = (
            None if datadict["animals"] == "{}" else json.loads(datadict["animals"])
        )
        datadict["portrait_info"] = json.loads(datadict["portrait_info"])
        friendships = sorted(
            [
                [friendship[11:], datadict[friendship]]
                for friendship in sorted(database_structure_dict.keys())
                if friendship.startswith("friendships") and datadict[friendship] != None
            ],
            key=lambda x: x[1],
        )[::-1]
        kills = sorted(
            [
                [kill[27:].replace("_", " "), datadict[kill]]
                for kill in sorted(database_structure_dict.keys())
                if kill.startswith("statsSpecificMonstersKilled")
                and datadict[kill] != None
            ],
            key=lambda x: x[1],
        )[::-1]
        if datadict["imgur_json"] != None:
            datadict["imgur_json"] = json.loads(datadict["imgur_json"])
        # passworded = True if datadict['del_password'] != None else False
        # passworded=passworded, removed from next line
        claimables = find_claimables()
        vote = json.dumps({url: get_votes(url)})
        if (
            logged_in() == False
            and len(claimables) > 1
            and request.cookies.get("no_signup") != "true"
        ):
            flash(
                {
                    "message": "<p>"
                    + _(
                        "It looks like you have uploaded multiple files, but are not logged in: if you <a href='{}'>sign up</a> or <a href='{}'>sign in</a> you can link these uploads, enable savegame sharing, and one-click-post farm renders to imgur!"
                    )
                    + "</p>".format(url_for("signup"), url_for("login")),
                    "cookie_controlled": "no_signup",
                }
            )

        datadict["uf_id"] = random_id()
        if datadict["farmhands"]:
            for fh in datadict["farmhands"]:
                # parse partner json
                fh["portrait_info"] = json.loads(fh.get("portrait_info", "{}"))
                fh["uf_id"] = random_id()
        return render_template(
            "profile/profile.html",
            deletable=deletable,
            claimable=claimable,
            claimables=claimables,
            vote=vote,
            data=datadict,
            kills=kills,
            friendships=friendships,
            others=other_saves,
            gallery_set=gallery_set,
            **page_args()
        )


@app.route("/plan/<url>")
def display_plan(url):
    page_init()
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, planner_url, image_url, render_deleted, season, failed_render FROM plans WHERE url="
        + app.sqlesc
        + "",
        (url,),
    )
    data = cur.fetchall()
    if len(data) != 1:
        g.error = _("There is nothing here... is this URL correct?")
        if str(url) != "favicon.ico":
            cur.execute(
                "INSERT INTO errors (ip, time, notes) VALUES ("
                + app.sqlesc
                + ","
                + app.sqlesc
                + ","
                + app.sqlesc
                + ")",
                (
                    request.environ["REMOTE_ADDR"],
                    time.time(),
                    str(len(data)) + " cur.fetchall() for planner url:" + str(url),
                ),
            )
            db.commit()
        return render_template("error.html", **page_args())
    else:
        plan_id, planner_url, image_url, render_deleted, season, failed_render = data[0]
        if failed_render != True:
            if render_deleted == True:
                check_max_renders()
                add_task(plan_id, "process_plan_image")
                imageDrone.process_plans()
            image_url = image_url[1:]
            if (
                urlparse(planner_url).netloc
                not in app.config["API_V1_PLAN_APPROVED_SOURCES"]
            ):
                planner_url = None
            season = season if season != None else "spring"
            cur.execute(
                "UPDATE plans SET views=views+1, last_visited="
                + app.sqlesc
                + " WHERE url="
                + app.sqlesc
                + "",
                (time.time(), url),
            )
            db.commit()
            return render_template(
                "plan.html",
                url=url,
                planner_url=planner_url,
                season=season,
                image_url=image_url,
                render_deleted=render_deleted,
                **page_args()
            )
        else:
            g.error = _(
                "This plan failed to render, probably because of a bug. It's logged and we'll look into it as soon as possible! Sorry!"
            )
            return render_template("error.html", **page_args())


def get_others(url, date, map_url):
    return_data = {}
    gallery_set = {"order": [], "lookup": {}}
    try:
        arguments = {"series": url, "sort_by": "chronological"}
        results = get_entries(1000, **arguments)["posts"][::-1]
        current_index = list(zip(*results))[0].index(url)
        for j, i in enumerate(range(current_index - 1, current_index + 2)):
            if i >= 0 and i < len(results):
                return_data[["previous", "current", "next"][j]] = (
                    results[i][0],
                    results[i][3],
                )
        for row in results:
            gallery_set["order"].append(row[7])
            gallery_set["lookup"][row[7]] = [row[0], row[3]]
    except (ValueError, IndexError):
        # this would occur in the case of a private page being viewed by a non-logged-in user; get_entries() will return nothing
        return_data["current"] = (url, date, map_url)
        gallery_set["order"].append(map_url)
        gallery_set["lookup"][map_url] = [url, date]
    gallery_set = {"json": json.dumps(gallery_set), "dict": gallery_set}
    return return_data, gallery_set


def find_claimables():
    if not hasattr(g, "claimables"):
        sessionids = list(session.keys())
        removals = ["admin", "logged_in_user"]
        for key in removals:
            try:
                sessionids.remove(key)
            except ValueError:
                pass
        urls = tuple([key for key in sessionids if not key.endswith("del_token")])
        if len(urls) > 0:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT id, md5, del_token, url FROM playerinfo WHERE owner_id IS NULL AND url IN "
                + app.sqlesc,
                (urls,),
            )
            result = cur.fetchall()
            checked_results = []
            for row in result:
                if (
                    row[1] == session[row[3]]
                    and row[2] == session[row[3] + "del_token"]
                ):
                    checked_results.append((row[0], row[3]))
            g.claimables = checked_results
        else:
            g.claimables = []
    return g.claimables


@app.route("/<url>/<instruction>", methods=["GET", "POST"])
def operate_on_url(url, instruction):
    page_init()
    if request.method == "POST":
        if (url in session and url + "del_token" in session) or logged_in():
            db = get_db()
            cur = db.cursor()
            # first: if logged in, get the URL, MD5 and deletion token for all farms owned by user; set session cookies indicating this ownership for all
            _op_set_ownership_cookies()

            if instruction == "del":
                return _op_del(url)
            elif instruction == "delall":
                return _op_delall(url)

            elif instruction == "claim":
                return _op_claim(url)
            elif instruction == "claimall":
                return _op_claimall(url)

            elif instruction == "enable-dl":
                return _op_toggle_boolean_param(url, "download_enabled", True)
            elif instruction == "disable-dl":
                return _op_toggle_boolean_param(url, "download_enabled", False)

            elif instruction == "imgur":
                return _op_imgur_post(url)

            elif instruction == "plan":
                return _op_planner(url)

            elif instruction == "list":
                return _op_toggle_boolean_param(url, "private", False)
            elif instruction == "unlist":
                return _op_toggle_boolean_param(url, "private", True)
        g.error = _("Unknown or insufficient credentials")
        return render_template("error.html", **page_args())
    elif request.method == "GET" and url == ".well-known":
        return redirect(
            url_for("static", filename=".well-known/{}".format(instruction))
        )
    else:
        return redirect(url_for("display_data", url=url))


def _op_set_ownership_cookies():
    db = get_db()
    cur = db.cursor()
    if logged_in():
        cur.execute(
            "SELECT url,md5,del_token FROM playerinfo WHERE owner_id=" + app.sqlesc,
            (get_logged_in_user(),),
        )
        result = cur.fetchall()
        for row in result:
            if not row[0] in session:
                session[row[0]] = row[1]
            if not row[0] + "del_token" in session:
                session[row[0] + "del_token"] = row[2]


def _op_del(url):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT owner_id FROM playerinfo WHERE url=" + app.sqlesc, (url,))
    data = cur.fetchone()
    if str(data[0]) == str(get_logged_in_user()):
        outcome = delete_playerinfo_entry(url, session[url], session[url + "del_token"])
        if outcome == True:
            return redirect(url_for("home"))
        else:
            g.error = outcome
    else:
        g.error = _("You do not own this farm")
    return render_template("error.html", **page_args())


def _op_delall(url):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT url,owner_id FROM playerinfo WHERE series_id=(SELECT series_id FROM playerinfo WHERE url="
        + app.sqlesc
        + ")",
        (url,),
    )
    data = cur.fetchall()
    for row in data:
        if str(row[1]) != str(get_logged_in_user()):
            g.error = _("You do not own at least one of the farms")
            return render_template("error.html", **page_args())
    # verified logged_in_user owns all farms
    for row in data:
        outcome = delete_playerinfo_entry(
            row[0], session[row[0]], session[row[0] + "del_token"]
        )
        if outcome != True:
            g.error = outcome
            return render_template("error.html", **page_args())
    return redirect(url_for("home"))


def _op_claim(url):
    db = get_db()
    cur = db.cursor()
    if url in [url for rowid, url in find_claimables()]:
        outcome = claim_playerinfo_entry(url, session[url], session[url + "del_token"])
        if outcome == True:
            return redirect(url_for("display_data", url=url))
        else:
            g.error = outcome
    else:
        g.error = _("You do not have sufficient credentials to claim this page")
    return render_template("error.html", **page_args())


def _op_claimall(url):
    db = get_db()
    cur = db.cursor()
    for rowid, claim_url in find_claimables():
        outcome = claim_playerinfo_entry(
            claim_url, session[claim_url], session[claim_url + "del_token"]
        )
        if outcome != True:
            g.error = _(
                "You do not have sufficient credentials to claim one of these pages"
            )
    return redirect(url_for("display_data", url=url))


def _op_toggle_boolean_param(url, param, state):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT owner_id,id FROM playerinfo WHERE url=" + app.sqlesc, (url,))
    data = cur.fetchone()
    if str(data[0]) == str(get_logged_in_user()):
        cur = db.cursor()
        cur.execute(
            "UPDATE playerinfo SET "
            + param
            + "="
            + app.sqlesc
            + " WHERE id="
            + app.sqlesc,
            (
                state,
                data[1],
            ),
        )
        db.commit()
        return redirect(url_for("display_data", url=url))
    else:
        g.error = _("You do not have sufficient credentials to perform this action")
        return render_template("error.html", **page_args())


def _op_imgur_post(url):
    db = get_db()
    cur = db.cursor()
    if logged_in():
        check_access = imgur.checkApiAccess(get_logged_in_user())
        if check_access == True:
            result = imgur.uploadToImgur(get_logged_in_user(), url)
            if "success" in result:
                return redirect(result["link"])
            elif "error" in result:
                if result["error"] == "too_soon":
                    g.error = _(
                        "You have uploaded this page to imgur in the last 2 hours: please wait to upload again"
                    )
                elif result["error"] == "upload_issue":
                    g.error = _(
                        "There was an issue with uploading the file to imgur. Please try again later!"
                    )
            else:
                g.error = "There was an unknown error!"
            return render_template("error.html", **page_args())
        elif check_access == False:
            return redirect(imgur.getAuthUrl(get_logged_in_user(), target=request.path))
        elif check_access == None:
            g.error = _(
                "Either you or upload.farm are out of imgur credits for the day! Sorry :( Try again tomorrow"
            )
            return render_template("error.html", **page_args())
    else:
        g.error = _("You must be logged in to post your farm to imgur!")
        return render_template("signup.html", **page_args())


def _op_planner(url):
    result = get_planner_link(url)
    if result["status"] == "success":
        return redirect(result["planner_url"])
    elif result["status"] == "over_rate_limit":
        flash(
            {
                "message": "<p>"
                + _(
                    "Sorry, the stardew.info planner API is over its rate limit: please try again in a few minutes!"
                )
                + "</p>"
            }
        )
        return redirect(url_for("display_data", url=url))
        # return render_template("error.html",**page_args())
    else:
        flash(
            {
                "message": "<p>"
                + _("There was a problem accessing the planner. Error was: {}")
                + "</p>".format(result["status"])
            }
        )
        return redirect(url_for("display_data", url=url))


def delete_playerinfo_entry(url, md5, del_token):
    # takes url, md5, and del_token (from session); if verified, deletes
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id,md5,del_token,url,savefileLocation,avatar_url,portrait_url,map_url,farm_url,download_url,thumb_url,base_path,owner_id,series_id FROM playerinfo WHERE url="
        + app.sqlesc,
        (url,),
    )
    result = cur.fetchone()
    if (
        result[1] == md5
        and result[2] == del_token
        and str(result[12]) == str(get_logged_in_user())
    ):
        if remove_series_link(result[0], result[13]) == False:
            pass  # return 'Problem removing series link!'
        cur.execute(
            "DELETE FROM playerinfo WHERE id=(" + app.sqlesc + ")", (result[0],)
        )
        for filename in result[4:11]:
            if filename != None and (
                os.path.split(os.path.split(filename)[0])[1] == result[3]
                or os.path.split(os.path.split(filename)[0])[1] == "uploads"
            ):
                # second condition ensures you're in a folder named after the URL which prevents accidentally deleting placeholders
                try:
                    os.remove(legacy_location(filename))
                except:
                    pass
        try:
            os.rmdir(legacy_location(result[11]))
        except:
            pass
        db.commit()
        session.pop(url, None)
        session.pop(url + "del_token", None)
        return True
    else:
        return _(
            "You do not have the correct session information to perform this action!"
        )


def remove_series_link(rowid, series_id):
    # removes a link to playerinfo id (rowid) from id in series (series_id)
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT members_json FROM series WHERE id=" + app.sqlesc, (series_id,))
    a = cur.fetchone()
    result = json.loads(a[0]) if a != None else None
    try:
        result.remove(int(rowid))
    except (ValueError, AttributeError):
        return False
    if len(result) == 0:
        cur.execute("DELETE FROM series WHERE id=" + app.sqlesc, (series_id,))
        cur.execute(
            "UPDATE playerinfo SET series_id=NULL WHERE id=" + app.sqlesc, (rowid,)
        )
    else:
        cur.execute(
            "UPDATE series SET members_json=" + app.sqlesc + " WHERE id=" + app.sqlesc,
            (json.dumps(result), series_id),
        )
        cur.execute(
            "UPDATE playerinfo SET series_id=NULL WHERE id=" + app.sqlesc, (rowid,)
        )
    db.commit()
    return True


def claim_playerinfo_entry(url, md5, del_token):
    # verify ability to be owner, then remove_series_link (checking ownership!), then add_to_series
    if logged_in():
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id,series_id,md5,del_token,owner_id,uniqueIDForThisGame,name,farmName FROM playerinfo WHERE url="
            + app.sqlesc,
            (url,),
        )
        result = cur.fetchone()
        if result[2] == md5 and result[3] == del_token and result[4] == None:
            remove_series_link(result[0], result[1])
            series_id = add_to_series(result[0], result[5], result[6], result[7])
            cur.execute(
                "UPDATE playerinfo SET series_id="
                + app.sqlesc
                + ", owner_id="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (series_id, get_logged_in_user(), result[0]),
            )
            db.commit()
            return True
        else:
            return _("Problem authenticating!")
    else:
        return _("You are not logged in!")


@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    page_init()
    if "admin" in session:
        # trusted
        returned_blog_data = None
        db = get_db()
        cur = db.cursor()
        if request.method == "POST":
            if request.form["blog"] == "Post":
                live = False
                if "live" in request.form:
                    if request.form["live"] == "on":
                        live = True
                if request.form["content"] == "" or request.form["blogtitle"] == "":
                    g.error = "Failed to post blog entry, title or body was empty!"
                    returned_blog_data = {
                        "blogtitle": request.form["blogtitle"],
                        "content": request.form["content"],
                        "checked": live,
                    }
                else:
                    cur.execute(
                        "INSERT INTO blog (time, author, title, post, live) VALUES ("
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ")",
                        (
                            int(time.time()),
                            session["admin"],
                            request.form["blogtitle"],
                            request.form["content"],
                            live,
                        ),
                    )
                    db.commit()
                    if live == True:
                        flash(
                            'Posted blog entry "' + str(request.form["blogtitle"] + '"')
                        )
                    else:
                        flash(
                            'Saved unposted blog entry "'
                            + str(request.form["blogtitle"] + '"')
                        )
            elif request.form["blog"] == "update":
                state = request.form["live"] == "true"
                cur.execute(
                    "UPDATE blog SET live=" + app.sqlesc + " WHERE id=" + app.sqlesc,
                    (state, request.form["id"]),
                )
                db.commit()
                return "Success"
            elif request.form["blog"] == "delete":
                cur.execute(
                    "DELETE FROM blog WHERE id=" + app.sqlesc, (request.form["id"],)
                )
                db.commit()
                return "Success"
        cur.execute(
            "SELECT url,name,farmName,statsDaysPlayed,dayOfMonthForSaveGame,seasonForSaveGame,yearForSaveGame FROM playerinfo"
        )
        entries = cur.fetchall()
        for i, entry in enumerate(entries):
            entries[i] = list(entry[:3]) + [
                get_date(
                    {
                        "statsDaysPlayed": entry[3],
                        "dayOfMonthForSaveGame": entry[4],
                        "seasonForSaveGame": entry[5],
                        "yearForSaveGame": entry[6],
                    }
                )
            ]
        return render_template(
            "adminpanel.html",
            returned_blog_data=returned_blog_data,
            blogposts=get_blogposts(include_hidden=True),
            entries=entries,
            **page_args()
        )
    else:
        if request.method == "POST":
            if "blog" in request.form:
                return "Failure"
            else:
                try:
                    db = get_db()
                    cur = db.cursor()
                    cur.execute(
                        "SELECT password FROM admin WHERE username="
                        + app.sqlesc
                        + " ORDER BY id",
                        (request.form["username"],),
                    )
                    r = cur.fetchone()
                    if r != None:
                        if check_password_hash(r[0], request.form["password"]) == True:
                            session["admin"] = request.form["username"]
                            return redirect(url_for("admin_panel"))
                    cur.execute(
                        "INSERT INTO errors (ip, time, notes) VALUES ("
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ","
                        + app.sqlesc
                        + ")",
                        (
                            request.environ["REMOTE_ADDR"],
                            time.time(),
                            "failed login: " + request.form["username"],
                        ),
                    )
                    db.commit()
                    g.error = "Incorrect username or password"
                except:
                    pass
        return render_template("admin.html", **page_args())


def get_blogposts(n=False, **kwargs):
    db = get_db()
    cur = db.cursor()
    blogposts = None
    query = "SELECT id,time,author,title,post,live FROM blog"
    metaquery = "SELECT count(*) FROM blog"
    try:
        if kwargs["include_hidden"] == False:
            query += " WHERE live='1'"
            metaquery += " WHERE live='1'"
    except KeyError:
        query += " WHERE live='1'"
        metaquery += " WHERE live='1'"
    query += " ORDER BY id DESC"
    if app.config["USE_SQLITE"] == True:
        if n == False:
            n = -1
    if n != False:
        query += " LIMIT " + app.sqlesc
    offset = 0
    if "offset" in kwargs:
        offset = kwargs["offset"]
    query += " OFFSET " + app.sqlesc
    if n == False:
        cur.execute(query, (offset,))
    else:
        cur.execute(query, (n, offset))
    blogposts = list(cur.fetchall())
    for b, blogentry in enumerate(blogposts):
        blogposts[b] = list(blogentry)
        blogposts[b][1] = datetime.datetime.fromtimestamp(blogentry[1])
    cur.execute(metaquery)
    metadata = cur.fetchone()
    blogdict = {"total": metadata[0], "posts": blogposts}
    return blogdict


@app.route("/lo")
def logout():
    if "admin" in session:
        session.pop("admin", None)
    session.pop("logged_in_user", None)
    return redirect(url_for("home"))


@app.route("/blog")
def blogmain():
    page_init()
    num_entries = 5
    # print(request.args.get('p'))
    try:
        offset = int(request.args.get("p")) * num_entries
    except:
        offset = 0
    if offset < 0:
        return redirect(url_for("blogmain"))
    blogposts = get_blogposts(num_entries, offset=offset)
    if blogposts["total"] <= offset and blogposts["total"] > 0:
        return redirect(url_for("blogmain"))
    return render_template(
        "blog.html", full=True, offset=offset, blogposts=blogposts, **page_args()
    )


@app.route("/all")
def allmain():
    page_init()
    num_entries = 18
    # print(request.args.get('p'))
    arguments = {"include_failed": True}
    try:
        arguments["offset"] = int(request.args.get("p")) * num_entries
    except TypeError:
        arguments["offset"] = 0
    except:
        g.error = _("No browse with that ID!")
        return render_template("error.html", **page_args())
    if arguments["offset"] < 0:
        return redirect(url_for("allmain"))
    # adapt get_recents() to take a kwarg for sort type; sort type can be GET value: /all&sort=popular
    arguments["sort_by"] = (
        request.args.get("sort") if request.args.get("sort") != None else "recent"
    )
    if "search" in request.args:
        arguments["search_terms"] = [
            item.encode("utf-8") for item in request.args.get("search").split(" ")[:10]
        ]
    if "series" in request.args:
        arguments["series"] = request.args.get("series")
    if "liked" in request.args:
        arguments["liked"] = True if request.args.get("liked") == "True" else False
    if "dl" in request.args:
        arguments["dl"] = True if request.args.get("dl") == "True" else False
    if "full_thumbnail" in request.args:
        arguments["full_thumbnail"] = (
            True if request.args.get("full_thumbnail") == "True" else False
        )
    try:
        entries = get_entries(num_entries, **arguments)
    except:
        g.error = _("Malformed request for entries!")
        return render_template("error.html", **page_args())
    if entries["total"] <= arguments["offset"] and entries["total"] > 0:
        return redirect(url_for("allmain"))
    vote = json.dumps({entry[0]: get_votes(entry[0]) for entry in entries["posts"]})
    return render_template(
        "all.html",
        full=True,
        offset=arguments["offset"],
        recents=entries,
        vote=vote,
        **page_args()
    )


def get_entries(n=6, **kwargs):
    '''
        Returns n entries; has kwargs:
            include_failed	bool	if True includes uploads which failed image generation
            search_terms	text	search string
            series 			text	takes 'url' as key; finds all matching in series
            liked 			bool	if True only show results user has upvoted
            offset 			int 	to allow for pagination
            dl 				bool	if True only show results with downloads enabled
            full_thumbnail	bool	if True, return *full* thumbnails, not maps
            sort_by			text	'rating', 'views', 'recent', 'chronological'; 'rating' defined according to snippet from http://www.evanmiller.org/how-not-to-sort-by-average-rating.html
            include_private bool	if True, return will check for admin status and include private farms (NOT FULLY IMPLEMENTED YET!)
    '''
    order_types = {
        "rating": "ORDER BY ((positive_votes + 1.9208) / (positive_votes + negative_votes) - 1.96 * SQRT((positive_votes*negative_votes)/(positive_votes+negative_votes)+0.9604) / (positive_votes+negative_votes)) / ( 1 + 3.8416 / (positive_votes + negative_votes)) ",
        "views": "ORDER BY views ",
        "recent": "ORDER BY id ",
        "chronological": "ORDER BY millisecondsPlayed ",
    }
    search_fields = (
        "name",
        "farmName",
    )  # removed 'date'; too complex at this point in time (and field is deprecated)
    db = get_db()
    cur = db.cursor()
    where_contents = []
    if (
        "include_failed" not in kwargs
        or "include_failed" in kwargs
        and kwargs["include_failed"] == False
    ):
        where_contents.append("failed_processing IS NOT TRUE")
    if "sort_by" in kwargs and kwargs["sort_by"] == "rating":
        where_contents.append("positive_votes + negative_votes > 0")
    if "search_terms" in kwargs and len(kwargs["search_terms"]) > 0:
        search = ""
        for i, item in enumerate(kwargs["search_terms"]):
            if i == 0:
                search += "("
            else:
                search += "AND "
            for f, field in enumerate(search_fields):
                if f == 0:
                    search += "("
                else:
                    search += "OR "
                search += cur.mogrify(
                    field + " ILIKE " + app.sqlesc + " ",
                    ("%%" + item.decode("utf-8") + "%%",),
                ).decode("utf-8")
                if f == len(search_fields) - 1:
                    search += ")"
            if i == len(kwargs["search_terms"]) - 1:
                search += ")"
        where_contents.append(search)
    if "series" in kwargs and kwargs["series"] != None:
        where_contents.append(
            cur.mogrify(
                "series_id=(SELECT series_id FROM playerinfo WHERE url="
                + app.sqlesc
                + ")",
                (kwargs["series"],),
            ).decode("utf-8")
        )
    if "liked" in kwargs and kwargs["liked"] == True and logged_in():
        likes = [
            url
            for url, value in has_votes(get_logged_in_user()).items()
            if value == True
        ]
        if len(likes) > 0:
            where_contents.append(
                cur.mogrify("url=ANY(" + app.sqlesc + ")", (likes,)).decode("utf-8")
            )
        else:
            where_contents.append("url=ANY(ARRAY[])")
    if "dl" in kwargs and kwargs["dl"] == True:
        where_contents.append("download_enabled=TRUE")
    if "include_private" in kwargs and kwargs["include_private"] == True:
        pass
    # do some checking to ensure the person getting the private data is an admin
    else:
        where_contents.append(
            cur.mogrify(
                "(private IS NOT TRUE OR (private IS TRUE AND owner_id="
                + app.sqlesc
                + "))",
                (get_logged_in_user(),),
            ).decode("utf-8")
        )
    where = ""
    for c, contents in enumerate(where_contents):
        if c == 0:
            where += "WHERE " + contents + " "
        if c != 0:
            where += "AND " + contents + " "
    order = (
        "ORDER BY id " if "sort_by" not in kwargs else order_types[kwargs["sort_by"]]
    )
    thumbtype = (
        "thumb_url"
        if "full_thumbnail" in kwargs and kwargs["full_thumbnail"] == True
        else "farm_url"
    )
    query = (
        "SELECT url, name, farmName, statsDaysPlayed,dayOfMonthForSaveGame,seasonForSaveGame,yearForSaveGame, avatar_url, "
        + thumbtype
        + ", download_enabled, map_url, private FROM playerinfo "
        + where
        + order
        + "DESC LIMIT "
        + app.sqlesc
    )  # removed 'date'
    # print('query:',query)
    offset = 0
    if "offset" in kwargs:
        offset = kwargs["offset"]
        query += " OFFSET " + app.sqlesc
    if "offset" in kwargs:
        cur.execute(query, (n, offset))
    else:
        cur.execute(query, (n,))
    entries = {}
    entries["posts"] = cur.fetchall()

    for i, entry in enumerate(entries["posts"]):
        entries["posts"][i] = (
            list(entry[:3])
            + [
                get_date(
                    {
                        "statsDaysPlayed": entry[3],
                        "dayOfMonthForSaveGame": entry[4],
                        "seasonForSaveGame": entry[5],
                        "yearForSaveGame": entry[6],
                    }
                )
            ]
            + list(entry[7:])
        )

    cur.execute("SELECT count(*) FROM playerinfo " + where)
    entries["total"] = cur.fetchone()[0]
    if len(entries) == 0:
        entries == None
    return entries


@app.route("/blog/<id>")
def blogindividual(id):
    page_init()
    try:
        blogid = int(id)
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id,time,author,title,post,live FROM blog WHERE id="
            + app.sqlesc
            + " AND live='1'",
            (blogid,),
        )
        blogdata = cur.fetchone()
        if blogdata != None:
            blogdata = list(blogdata)
            blogdata[1] = datetime.datetime.fromtimestamp(blogdata[1])
            blogposts = {"posts": (blogdata,), "total": 1}
            return render_template(
                "blog.html",
                full=True,
                offset=0,
                recents=get_recents(),
                blogposts=blogposts,
                **page_args()
            )
        else:
            g.error = _("No blog with that ID!")
    except:
        g.error = _("No blog with that ID!")
    return render_template("error.html", **page_args())


@app.route("/dl/<url>")
def retrieve_file(url):
    page_init()
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT savefileLocation,name,uniqueIDForThisGame,download_enabled,download_url,id FROM playerinfo WHERE url="
        + app.sqlesc,
        (url,),
    )
    result = cur.fetchone()
    if result[3] == True:
        if result[4] == None:
            filename = generateSavegame.createZip(
                url, result[1], result[2], "static/saves", result[0]
            )
            cur.execute(
                "UPDATE playerinfo SET download_url="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (filename, result[5]),
            )
            db.commit()
            return redirect(filename)
        else:
            return redirect(result[4])
    elif "admin" in session:
        if result != None:
            with open(legacy_location(result[0]), "rb") as f:
                response = make_response(f.read())
            response.headers["Content-Disposition"] = (
                "attachment; filename=" + str(result[1]) + "_" + str(result[2])
            )
            return response
        else:
            g.error = _("URL does not exist")
    else:
        g.error = _("You are unable to download this farm data at this time.")
    return render_template("error.html", **page_args())


@app.route("/faq")
def faq():
    page_init()
    return render_template("faq.html", **page_args())


@app.route("/about")
def about():
    page_init()
    return render_template("about.html", **page_args())


@app.route("/pp")
def privacy():
    page_init()
    return render_template("privacy.html", **page_args())


@app.route("/imgur")
def get_imgur_auth_code():
    page_init()
    if logged_in():
        if len(request.args) == 0:
            return redirect(
                imgur.getAuthUrl(get_logged_in_user(), target=url_for("account_page"))
            )
        else:
            result = imgur.swapCodeForTokens(request.args)
            if result["success"] == True:
                return redirect(result["redir"])
            else:
                g.error = _("Problem authenticating at imgur!")
                return render_template("error.html", **page_args())
    else:
        g.error = _("Cannot connect to imgur if not logged in!")
        return render_template("error.html", **page_args())


@app.route("/_patreon")
def get_patreon_auth_code():
    page_init()
    if logged_in():
        if len(request.args) == 0:
            db = get_db()
            cur = db.cursor()
            csrf = str(uuid.uuid4())
            cur.execute(
                "UPDATE users SET patreon_info="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (json.dumps({"csrf": csrf}), get_logged_in_user()),
            )
            db.commit()
            return redirect(
                "http://www.patreon.com/oauth2/authorize?"
                + urlencode(
                    {
                        "response_type": "code",
                        "client_id": app.config["PATREON_CLIENT_ID"],
                        "redirect_uri": app.config["PATREON_REDIRECT_URI"],
                        "state": csrf,
                    }
                )
            )
        else:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT patreon_info FROM users WHERE id=" + app.sqlesc,
                (get_logged_in_user(),),
            )
            result = cur.fetchall()
            if (
                len(result) == 1
                and request.args.get("state") == json.loads(result[0][0])["csrf"]
            ):
                # CSRF passed [thumbs up emoji]
                oauth_client = patreon.OAuth(
                    app.config["PATREON_CLIENT_ID"], app.config["PATREON_CLIENT_SECRET"]
                )
                tokens = oauth_client.get_tokens(
                    request.args.get("code"), app.config["PATREON_REDIRECT_URI"]
                )
                if (
                    "errors" in tokens
                    or "error" in tokens
                    or "token_type" not in tokens
                ):
                    g.error = _(
                        "Error authorising with Patreon. Please try again later!"
                    )
                    return render_template("error.html", **page_args())
                else:
                    # put tokens in db
                    at = tokens["access_token"]
                    rt = tokens["refresh_token"]
                    expiry = tokens["expires_in"] + time.time()
                    cur.execute(
                        "UPDATE users SET patreon_token="
                        + app.sqlesc
                        + ", patreon_refresh_token="
                        + app.sqlesc
                        + ", patreon_expiry="
                        + app.sqlesc
                        + " WHERE id="
                        + app.sqlesc,
                        (at, rt, expiry, get_logged_in_user()),
                    )
                    db.commit()
                    patreon_info = update_patreon_info(at, rt, expiry)
                    if (
                        patreon_info.get("num_pledges") != None
                        and patreon_info["num_pledges"] > 0
                    ):
                        flash(
                            {
                                "message": "<p>"
                                + _("Connected to Patreon. Thank you for your support!")
                                + "</p>"
                            }
                        )
                    else:
                        flash({"message": "<p>" + _("Connected to Patreon!") + "</p>"})
                    return redirect(url_for("account_page"))
            else:
                g.error = _("Cross-site request forgery check failed!")
                return render_template("error.html", **page_args())
    else:
        g.error = _("Cannot connect to Patreon if not logged in!")
        return render_template("error.html", **page_args())


def update_patreon_info_for_current_user():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT patreon_token,patreon_refresh_token,patreon_expiry FROM users WHERE id="
        + app.sqlesc,
        (get_logged_in_user(),),
    )
    result = cur.fetchone()
    return update_patreon_info(result[0], result[1], result[2])


def update_patreon_info(access_token, refresh_token, expiry):
    # if expired, refresh
    if time.time() >= expiry:
        result = refresh_patreon_token(refresh_token, expiry)
        access_token = result.get("new_access_token")
        # print(result)
        if access_token == None:
            return {"error": result}
    # get info
    try:
        # try to get new info
        api_client = patreon.API(access_token)
        user = api_client.fetch_user()
        try:
            if "errors" in user:
                # if not authorised, try a last-ditch attempt at refreshing token
                if user["errors"][0]["status"] == "401":
                    result = refresh_patreon_token(refresh_token, expiry)
                    access_token = result.get("new_access_token")
                    if access_token == None:
                        return {"error": result}
                    else:
                        # if it worked, try getting new user info
                        api_client = patreon.API(access_token)
                        user = api_client.fetch_user()
                        if "errors" in user:
                            # but if this failed, handle errors & return
                            return {"error": user}
        except TypeError:
            pass
        # otherwise continue
        patreon_info = {
            "json_data": user.json_data,
            "name": user.data().attributes()["full_name"],
            "num_pledges": len(user.data().relationships()["pledges"]["data"]),
        }
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET patreon_info=" + app.sqlesc + " WHERE id=" + app.sqlesc,
            (json.dumps(patreon_info), get_logged_in_user()),
        )
        db.commit()
        return patreon_info
    except:
        # except if you can't for some reason (server issue?), fall back on existing db info...
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT patreon_info FROM users WHERE id=" + app.sqlesc,
            (get_logged_in_user(),),
        )
        result = cur.fetchone()
        try:
            patreon_info = json.loads(result[0])
        except json.JSONDecodeError:
            patreon_info = {}
        return patreon_info


def handle_patreon_error(response):
    try:
        if response.get("errors"):
            if response["errors"][0]["status"] == "401":
                db = get_db()
                cur = db.cursor()
                cur.execute(
                    "UPDATE users SET patreon_info="
                    + app.sqlesc
                    + ", patreon_token="
                    + app.sqlesc
                    + ", patreon_refresh_token="
                    + app.sqlesc
                    + ", patreon_expiry="
                    + app.sqlesc
                    + " patreon WHERE id="
                    + app.sqlesc,
                    (
                        json.dumps({"error": "unauthorized"}),
                        None,
                        None,
                        None,
                        get_logged_in_user(),
                    ),
                )
                db.commit()
        if response.get("error") and response["error"] == "invalid_grant":
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "UPDATE users SET patreon_info="
                + app.sqlesc
                + ", patreon_token="
                + app.sqlesc
                + ", patreon_refresh_token="
                + app.sqlesc
                + ", patreon_expiry="
                + app.sqlesc
                + " WHERE id="
                + app.sqlesc,
                (
                    json.dumps({"error": "unauthorized"}),
                    None,
                    None,
                    None,
                    get_logged_in_user(),
                ),
            )
            db.commit()
    except:
        pass


def refresh_patreon_token(refresh_token, expiry):
    oauth_client = patreon.OAuth(
        app.config["PATREON_CLIENT_ID"], app.config["PATREON_CLIENT_SECRET"]
    )
    tokens = oauth_client.refresh_token(
        refresh_token, app.config["PATREON_REDIRECT_URI"]
    )
    if "token_type" not in tokens:
        handle_patreon_error(tokens)
        return tokens
    else:
        db = get_db()
        cur = db.cursor()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expiry = tokens["expires_in"] + time.time()
        cur.execute(
            "UPDATE users SET patreon_token="
            + app.sqlesc
            + ", patreon_refresh_token="
            + app.sqlesc
            + ", patreon_expiry="
            + app.sqlesc
            + " WHERE id="
            + app.sqlesc,
            (access_token, refresh_token, expiry, get_logged_in_user()),
        )
        db.commit()
        return {"new_access_token": access_token}


@app.route("/verify_email")
def verify_email():
    page_init()
    if "i" in request.args and "t" in request.args:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT email_conf_token, email_confirmed FROM users WHERE id="
            + app.sqlesc,
            (request.args.get("i"),),
        )
        t = cur.fetchall()
        if len(t) == 0:
            g.error = _("Account does not exist!")
            return render_template("error.html", **page_args())
        elif t[0][1] == True:
            flash({"message": "<p>" + _("Already confirmed email address!") + "</p>"})
            return redirect(url_for("home"))
        else:
            if t[0][0] == request.args.get("t"):
                cur.execute(
                    "UPDATE users SET email_confirmed="
                    + app.sqlesc
                    + " WHERE id="
                    + app.sqlesc,
                    (True, request.args.get("i")),
                )
                db.commit()
                flash(
                    {"message": "<p>" + _("Account email address confirmed!") + "</p>"}
                )
                return redirect(url_for("home"))
    g.error = _("Malformed verification string!")
    return render_template("error.html", **page_args())


@app.route("/_vote", methods=["POST"])
def submit_vote():
    if logged_in():
        if request.method == "POST":
            if "vote" in request.form:
                return json.dumps(handle_vote(get_logged_in_user(), request.form))
    else:
        return _("not logged in")


def handle_vote(logged_in_user, vote_info):
    # 1: check whether user has voted previously
    votes = has_votes(logged_in_user)
    vote = json.loads(request.form["vote"]) if request.form["vote"] != "" else None
    # 2: if voted previously, modify user vote info to new vote, else add vote info to user vote
    previous = votes[request.form["url"]] if request.form["url"] in votes else None
    if vote == previous:
        return True
    else:
        # subtract previous vote
        db = get_db()
        cur = db.cursor()
        if previous != None:
            prev_col = "positive_votes" if previous == True else "negative_votes"
            cur.execute(
                "UPDATE playerinfo SET "
                + prev_col
                + "="
                + prev_col
                + "-1 WHERE url="
                + app.sqlesc,
                (request.form["url"],),
            )
            votes[request.form["url"]] = None
        # 3: add vote to correct column in playerinfo
        if vote != None:
            vote_col = "positive_votes" if vote == True else "negative_votes"
            cur.execute(
                "UPDATE playerinfo SET "
                + vote_col
                + "="
                + vote_col
                + "+1 WHERE url="
                + app.sqlesc,
                (request.form["url"],),
            )
            votes[request.form["url"]] = vote
        votes = json.dumps(votes)
        cur.execute(
            "UPDATE users SET votes=" + app.sqlesc + " WHERE id=" + app.sqlesc,
            (votes, logged_in_user),
        )
        db.commit()
        return True
    # 4: commit, return


def has_votes(logged_in_user):
    if not hasattr(g, "logged_in_users_votes"):
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT votes FROM users WHERE id=" + app.sqlesc, (logged_in_user,))
        votes = cur.fetchone()[0]
        g.logged_in_users_votes = json.loads(votes) if votes != None else {}
    return g.logged_in_users_votes


def get_votes(url):
    if logged_in():
        result = has_votes(get_logged_in_user())
        return result[url] if url in result else None
    else:
        return None


if __name__ == "__main__":
    app.run()
