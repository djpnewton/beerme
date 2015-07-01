from flask import url_for, session, request, render_template, redirect, flash, jsonify
import decimal
import urllib

import beerme
from beerme import app, config, csrf
from beerme import User, Beer
import utils

def current_user(session_key_name='id'):
    if session_key_name in session:
        uid = session[session_key_name]
        return User.query.get(uid)
    return None

def clear_user():
    if 'id' in session:
        session.pop('id', None)

def paginate_pagenums(row_count):
    page = request.args.get('page')
    if not page:
        page = 1
    try:
        page = int(page)
    except:
        page = 1
    max_pages = (row_count - 1) / config.main.paginate_row_count + 1
    pagenums = []
    if max_pages > 1:
        if page != 1:
            pagenums.append(1)
        if page > 5:
            pagenums.append('.')
        if page > 4:
            pagenums.append(page-3)
        if page > 3:
            pagenums.append(page-2)
        if page > 2:
            pagenums.append(page-1)
        pagenums.append(page)
        if page < max_pages - 1:
            pagenums.append(page + 1)
        if page < max_pages - 2:
            pagenums.append(page + 2)
        if page < max_pages - 3:
            pagenums.append(page + 3)
        if page < max_pages - 4:
            pagenums.append('.')
        if page != max_pages:
            pagenums.append(max_pages)
    return pagenums, page

@app.route('/', methods=('GET',))
def landing():
    return render_template('landing.html', table=request.cookies.get('table'), name=request.cookies.get('name'))

@app.route('/beer')
def beer():
    brew = request.args.get('brew', '')
    table = request.args.get('table', 'n/a')
    name = request.args.get('name', 'n/a')
    price_satoshis = beerme.beer_price()
    if not price_satoshis:
        return 'error calculating price'
    beer = beerme.beer_add(brew, table, name, price_satoshis)
    if not beer:
        return 'error creating payment address'
    resp = redirect('/beer/%s' % beer.guid)
    resp.set_cookie('table', table)
    resp.set_cookie('name', name)
    return resp

@app.route('/beer/<guid>')
def beer_specific(guid):
    beer = Beer.query.filter_by(guid=guid).first()
    if not beer:
        return 'invalid order'
    # convert price to btc
    price_btc = decimal.Decimal(beer.price_satoshis) / decimal.Decimal(beerme.SATOSHIS)
    # create qr code
    bitcoin_uri = 'bitcoin:%s?%s' % (beer.address, urllib.urlencode({'amount': price_btc, 'message': beer.brew}))
    qr = utils.qrcode(bitcoin_uri)
    img_buf = utils.qrcode_png_buffer(qr)
    img_data = img_buf.getvalue()
    img_data_b64 = img_data.encode('base64').replace('\n', '')
    data_uri = 'data:image/png;base64,%s' % img_data_b64
    return render_template('beer.html', beer=beer, price_btc=price_btc, data_uri=data_uri, bitcoin_uri=bitcoin_uri)

@csrf.exempt
@app.route('/payment', methods=['POST'])
def payment():
    beerme.beer_payment(request)
    return '*ok*'

@app.route('/beers')
def beers():
    beers = Beer.query.all()
    return render_template('beers.html', beers=beers)
