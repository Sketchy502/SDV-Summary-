import os

# os.chdir(os.path.join(os.path.dirname(__file__), "sdv"))

import sys

sys.path.insert(0, "./")
sys.path.insert(1, "./sdv/")

# for some reason on Python 3.4 on Linux Mint, using runserver.py crashes on first reload if os.chdir() is used
# so to avoid this (and break some of the site, but oh well...) remove os.chdir and add sdv to path
# Weirdly, after first launch, subsequent reloads work if you go back to including os.chdir...
# sys.path.insert(0, './sdv')
#

from sdv import app

app.run(host="0.0.0.0")
