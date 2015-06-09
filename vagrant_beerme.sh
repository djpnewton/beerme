#!/bin/sh

set -e

cd /vagrant
export VENV_PATH=$HOME

echo setup python dependancies 
python setup_dependancies.py
export HOST=0.0.0.0
echo start beerme app
python run.py runserver.py debug
