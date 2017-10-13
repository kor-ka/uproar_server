import os

from flask import Flask
from flask import json
from flask import request


def run(manager):
    app = Flask(__name__)

    @app.route('/pay_callback', methods=['POST'])
    def pay_callback():
        manager.tell({"command":"payment", "data":request.form})
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'}


    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
