import os

import pykka
import time
from telegram import LabeledPrice

import Storage
from Storage import StorageProvider

crown_requset = 0xff
class UserActor(pykka.ThreadingActor):
    def __init__(self, id, bot):
        super(UserActor, self).__init__()
        self.bot = bot
        self.id = id
        self.poo = u'\U0001F4A9'
        self.crown = u'\U0001F451'
        self.db = StorageProvider().get_storage()
        self.storage = None
        self.crown_data = {"ends":0}

    def on_start(self):
        self.storage = self.db.ask(
            {'command': 'get_list', 'name': Storage.USER_STORAGE, 'suffix': str(self.id)})
        for crown in self.storage.get('crown'):
            self.crown_data = crown

    def on_receive(self, message):
        if message['command'] == 'msg':
            self.on_message(message['msg'])
        elif message['command'] == 'pre':
            self.on_precheckout(message['pre'])
        elif message['command'] == 'crown_active':
            return self.crown_active()

    def on_message(self, message):
        if message.text and (message.text == '/crown' or message.text == '/start crown'):
            self.request_crown(message.chat.id)

        if message.successful_payment:
            if message.successful_payment.invoice_payload == crown_requset:
                self.crown_data.update({"ends":int(round(time.time() * 1000)) + 20000})
                self.storage.put("crown", self.crown_data)

    def request_crown(self, chat_id):
        args = {
            'chat_id': chat_id,
            'title': 'get a crown!',
            'description': u'replaces your selflike ' + self.poo + u' with ' + self.crown + " for 24h!",
            'payload': crown_requset,
            'provider_token': os.getenv("telegram_payment_token"),
            'start_parameter': "crown",
            'currency': "RUB",
            'prices': [LabeledPrice(self.crown, 6000)],

                }
        self.bot.tell({'command':'invoice', 'invoice_args':args})

    def on_precheckout(self, pre):
        if pre.invoice_payload == crown_requset:
            pre.answer(pre.id, True)

    def crown_active(self):
       return self.crown_data["ends"] >= int(round(time.time() * 1000))
