import os

from flask import Flask
from flask import request


def run(manager):
    app = Flask(__name__)

    @app.route('/')
    @app.route('/crown')
    def index():
        return '<iframe src="https://money.yandex.ru/quickpay/shop-widget?writer=seller&targets=Crown%F0%9F%91%91&targets-hint=&default-sum=10&button-text=12&payment-type-choice=on&hint=&successURL=http%3A%2F%2Ft.me%2Fuproarbot%3Fstart%3Ddone&quickpay=shop&account=410011799344776" width="450" height="204" frameborder="0" allowtransparency="true" scrolling="no"></iframe>'

    @app.route('/pay_callback', methods=['POST'])
    def pay_callback():
        manager.tell({"command":"payment", "data":request.data})


    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
