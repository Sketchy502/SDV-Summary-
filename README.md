# SDV-Summary

A Flask webapp using Python Image Library to reconstruct and display a summary of the player and farm from a Stardew Valley save file. A deployed instance is hosted at [upload.farm](http://upload.farm).

## config.py

`config.py` goes in the `sdv` subfolder. The `SDV_APP_SETTINGS` environment variable is used in order to specify which Python object to load for configuration from config.py as per Flask's config.from_object. In that file the following settings can be used:

### Mandatory Settings

`UPLOAD_FOLDER` where uploaded files are stored

`SECRET_KEY` for Flask's sessions etc.

`MAX_CONTENT_LENGTH` in bytes for uploads

`PASSWORD_ATTEMPTS_LIMIT` (currently unused)

`PASSWORD_MIN_LENGTH` used to determine minimum password length for registering users

`IMGUR_CLIENTID` for imgur integration

`IMGUR_SECRET` for imgur integration

`IMGUR_DIRECT_UPLOAD` to upload directly to imgur by sending file rather than by directing imgur to url (can't redirect imgur to localhost, for example, when testing)

`RECAPTCHA_ENABLED` for the ReCaptcha on the signup form

`RECAPTCHA_SITE_KEY` as above

`RECAPTCHA_SECRET_KEY` as above

`ANALYTICS_ID` to report interactions server-side to Google Analytics using google-measurement-protocol

`DEBUG` set to True for helpful debugging; never set to True in production environment

`ASSET_PATH` a path to a directory for assets for the app

#### Database

`USE_SQLITE` NOTE: in testing we've moved to Postgres, so this probably doesn't work any more

##### SQLite

`DB_SQLITE`

##### PostgreSQL

`DB_NAME`

`DB_USER`

`DB_PASSWORD`

##### Flask-mail

As per flask-mail docs and your email server

## Initialization

Install prerequisites using a tool like [pip](https://pypi.org/project/pip/) by running the following command from the root directory:

```bash
pip install -r requirements.txt
# Or, for Python 3: pip3 install -r requirements.txt
```

You need PostgreSQL installed and running. Then create a database:

```bash
createdb sdv_summary_development
```

To create a config file for SDV-Summary:

```bash
cp sdv/config.py.sample sdv/config.py
```

Modify sdv/config.py to specify the user name and password for the PostgreSQL database you created.

Once the config file has been written, run createadmin.py and createdb.py and follow the prompts to create the database structure:

```bash
SDV_APP_SETTINGS=development python sdv/createadmin.py
# Or, for Python 3: SDV_APP_SETTINGS=development python3 sdv/createadmin.py
SDV_APP_SETTINGS=development python sdv/createdb.py
# Or, for Python 3: SDV_APP_SETTINGS=development python3 sdv/createdb.py
```

To run, the templating engine jinja2 needs `sdv\templates\analytics.html` to exist.

You need a copy of Stardew Valley so you can extract its asset files using a tool
like [LeonBlade/xnbcli](https://github.com/LeonBlade/xnbcli). See also
[the Stardew Valley wiki](https://stardewvalleywiki.com/Modding:Editing_XNB_files#Unpack_.26_pack_game_files)
for information about unpacking xnb files to access the png images.

Assets for image generation go in `sdv\assets\[subfolder]`. Assets used as-is go in `sdv\static\assets\[subfolder]`.

Using LeonBlade/xnbcli, you can unpack Stardew Valley xnbs by copying them from the
game's installation directory to the packed/ directory from xnbcli. For example,
on macOS with Stardew Valley installed via Steam, your xnb files are here:

```bash
cd ~/Library/Application\ Support/Steam/steamapps/common/Stardew\ Valley/Contents/Resources/Content
open . # to open this location in a Finder window
```

Copy everything from the Content/ directory into xnbcli's packed/ directory. Then,
to run xnbcli:

```bash
# From the xnbcli directory:
npm install
npm run unpack
```

This process will take a while but should hopefully end with a bunch of new pngs and
JSON files in xnbcli's unpacked/ directory. The script should finish with output like
this:

```
[INFO] Reading file "packed/Animals/horse.xnb" ...
[INFO] XNB file validated successfully!
[INFO] File has been successfully decompressed!
[INFO] Successfuly read XNB file!
[INFO] Exporting Texture2D ...
[INFO] Output file saved: unpacked/Animals/horse.json
Success 2039
Fail 0
```

You can generate SDV-Summary's expected asset directory structure via:

```bash
SDV_APP_SETTINGS=development python sdv/makeAssetDirectories.py
# Or, for Python 3: SDV_APP_SETTINGS=development python3 sdv/makeAssetDirectories.py
```

Once you have the right directory structure for assets, you can start copying unpacked
assets into the right SDV-Summary locations:

```bash
# SDV_APP_SETTINGS=development python sdv/copyUnpackedAssets.py <path to xnbcli's unpacked directory>
# Or, for Python 3: SDV_APP_SETTINGS=development python3 sdv/copyUnpackedAssets.py <path to xnbcli's unpacked directory>
# Example:
SDV_APP_SETTINGS=development python sdv/copyUnpackedAssets.py ~/xnbcli-master/unpacked
```

**Note:** the copyUnpackedAssets.py script isn't finished yet, so it will only copy
a few of the asset files to the location SDV-Summary expects. Pull requests welcome!

Once you have all the asset files in place, run the app using Flask:

```bash
SDV_APP_SETTINGS=development FLASK_APP=runserver.py flask run
```

## Acknowledgements

Thank you to our translators, specifically:

* Leonardo Francisco (icantbewrong@outlook.com) for Brazilian Portuguese
* Yiming Wang (yimingw@umich.edu) for Chinese
* Jhordi Rodriguez (jhordi.rs@gmail.com) for Spanish
* Federico Grandi (fgrandi30@gmail.com) for Italian
