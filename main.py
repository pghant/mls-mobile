import datetime
import json

from flask import Flask, render_template, request, abort

from mls import MLS

app = Flask(__name__)

MLS_BASE_URL = 'http://vow.mlspin.com/'

@app.route('/')
def root():
  if 'cid' not in request.args or 'pass' not in request.args or 'mls' not in request.args:
    abort(403)
  mls_url = f"{MLS_BASE_URL}?{request.query_string.decode('utf-8')}"
  mls_page = MLS(mls_url)
  mls_info = mls_page.info()

  return render_template('index.html', mls=mls_info)

if __name__ == '__main__':
  app.run(host='127.0.0.1', port=8080, debug=True)