import os

import pykka
from telegram import LabeledPrice

crown_requset = 0xff
class UserActor(pykka.ThreadingActor):
    def __init__(self, id, bot):
        super(UserActor, self).__init__()
        self.bot = bot
        self.id = id
        self.poo = u'\U0001F4A9'
        self.crown = u'\U0001F451'

    def on_receive(self, message):
        if message['command'] == 'msg':
            self.on_message(message['msg'])
        elif message['command'] == 'pre':
            self.on_precheckout(message['pre'])

    def on_message(self, message):
        if message.text and message.text == '/crown':
            self.request_crown(message.chat.id)

    def request_crown(self, chat_id):
        args = {
            'chat_id': chat_id,
            'title': 'get a crown!',
            'description': u'replaces your selflike ' + self.poo + u' with ' + self.crown + "!",
            'payload': crown_requset,
            'provider_token': os.getenv("telegram_payment_token"),
            'start_parameter': "crown",
            'currency': "RUB",
            'prices': [LabeledPrice(self.crown, 10)],

                }
        self.bot.tell({'command':'invoice', 'invoice_args':args})

    def on_precheckout(self, pre):
        pass
