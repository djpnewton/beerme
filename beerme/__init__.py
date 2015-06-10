# coding: utf-8

import os
from datetime import datetime, timedelta
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_kvsession import KVSessionExtension
from simplekv.db.sql import SQLAlchemyStore
from sqlalchemy import create_engine, MetaData
from flask_seasurf import SeaSurf
from flask_limiter import Limiter
import time
import random
import decimal
import uuid
import requests
import json

import config

# create global config
config = config.Config(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.cfg'))
# create flask wsgi app
app = Flask(__name__, template_folder='templates')
app.debug = False
app.config.update({
    'SQLALCHEMY_DATABASE_URI': config.main.db_connection,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SECURE': config.main.secure_cookie,
    'PERMANENT_SESSION_LIFETIME': timedelta(minutes=config.main.session_lifetime),
    'SECRET_KEY': config.main.secret_key
})
# mandrill middlelware
if config.email.use_mandrill:
    app.config['MANDRILL_API_KEY'] = config.email.mandrill_api_key
    app.config['MANDRILL_DEFAULT_FROM'] = config.email.from_
# add sqlalchemy middleware
db = SQLAlchemy(app)
# add flask_kvsession middleware
app.config['SESSION_KEY_BITS'] = 128
engine = create_engine('sqlite:///beerme/sessions.sqlite')
metadata = MetaData(bind=engine)
store = SQLAlchemyStore(engine, metadata, 'kvstore')
metadata.create_all()
KVSessionExtension(store, app)
# add flask csrf middleware
csrf = SeaSurf(app)
# add rate limiting middleware
limiter = Limiter(app)
auth_limit = limiter.shared_limit("5/minute;1/second", scope="auth")

# app constants
SATOSHIS = 1e8

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)

class Beer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brew = db.Column(db.String)
    table = db.Column(db.String)
    name = db.Column(db.String)
    price_satoshis = db.Column(db.Integer)
    address = db.Column(db.String)
    guid = db.Column(db.String, unique=True)
    txid = db.Column(db.String, unique=True)
    paid = db.Column(db.Boolean)
    processed = db.Column(db.Boolean)

def init_db():
    db.create_all()

@app.before_first_request
def init_all_on_first_request():
    init_db()

@app.before_request
def refresh_session():
    if session.has_key('gen_time'):
        gen_time = session['gen_time']
        lifetime = app.config['PERMANENT_SESSION_LIFETIME'].seconds
        if time.time() > gen_time + lifetime / 2:
            session.regenerate()
            session['gen_time'] = time.time()
    else:
        session['gen_time'] = time.time()

def user_create(email):
    user = User(email=email)
    db.session.add(user)
    db.session.commit()
    return user

def beer_callback_url(guid):
    callback_url = "http://beerme.djpsoft.com/payment?beer_guid=%s&secret=%s" % (guid, config.main.payment_secret)
    return callback_url

def beer_new_address(guid):
    callback_url = beer_callback_url(guid)
    bc_payment_url = 'https://api.blockcypher.com/v1/btc/main/payments'
    payload = {'token': config.main.blockcypher_token, 'destination': config.main.payment_address, 'callback_url': callback_url}
    print 'callback_url:', callback_url
    print 'bc_payment_url:', bc_payment_url
    r = requests.post(bc_payment_url, data=json.dumps(payload))
    if r.status_code == 200:
        data = r.json()
        print 'returned callback_url:', data['callback_url']
        if data['callback_url'] != callback_url or data['destination'] != config.main.payment_address:
            return None
        return data['input_address']

def beer_price():
    bbb_url = 'https://bitpay.com/api/rates/nzd'
    r = requests.get(bbb_url)
    if r.status_code == 200:
        rate = r.json()['rate']
        beer_price_nzd = config.main.beer_price
        # convert to satoshis
        return int(beer_price_nzd / rate * SATOSHIS)

def beer_add(brew, table, name, price_satoshis):
    # get input address
    guid = uuid.uuid4()
    address = beer_new_address(guid)
    if not address:
        return None
    # create new entry
    beer = Beer(brew=brew, table=table, name=name, price_satoshis=price_satoshis, address=address, guid=str(guid), paid=False, processed=False)
    db.session.add(beer)
    db.session.commit()
    return beer

def beer_payment(req):
    json = req.get_json(force=True)
    satoshis = json['value']
    address = json['destination_address']
    txid = json['input_transaction_hash']
    guid = req.args.get('beer_guid')
    secret = req.args.get('secret')
    print 'satoshis:', satoshis
    print 'txid:', txid
    print 'guid:', guid
    print 'secret:', secret
    if secret != config.main.payment_secret:
        print 'secret (%s) does not match payment_secret' % secret
        return
    beer = Beer.query.filter_by(guid=guid).first()
    if not beer:
        print 'invalid beer guid'
        return
    if address != beer.address:
        print 'invalid address'
        return
    if satoshis < beer.price_satoshis:
        print 'payment insufficient'
        return
    beer.txid = txid
    beer.paid = True
    db.session.add(beer)
    db.session.commit()
    # send email
    utils.send_email_beer_alert(config, beer)

import beerme.views
