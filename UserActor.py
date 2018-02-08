import os

import logging
from pprint import pprint

import pykka
import time
from telegram import LabeledPrice

import Storage

crown_requset = "crown_requset"
class UserActor(pykka.ThreadingActor):
    def __init__(self, id, context):
        super(UserActor, self).__init__()
        self.bot = context.bot
        self.id = id
        self.poo = u'\U0001F4A9'
        self.crown = u'\U0001F451'
        self.db = context.storage
        self.storage = None
        self.crown_data = {"ends":0}

        liked_tracks = None

    def on_start(self):
        try:
            self.storage = self.db.ask(
                {'command': 'get_list', 'name': Storage.USER_STORAGE, 'suffix': str(self.id)})

            self.liked_tracks = self.context.storage.ask(
                {'command': 'get_list', 'name': Storage.LIKED_TRACKS_TABLE,
                 "suffix": self.id})

            for crown in self.storage.get('crown'):
                self.crown_data = crown
                pprint(self.crown_data)
        except Exception as ex:
            logging.exception(ex)

    def on_receive(self, message):
        try:
            print "User Actor msg " + str(message)
            if message['command'] == 'msg':
                self.on_message(message['msg'])
            elif message['command'] == 'pre':
                self.on_precheckout(message['pre'])
            elif message['command'] == 'crown_active':
                return self.crown_active()
            elif message['command'] == 'remove_track':
                self.liked_tracks.remove(message.get("file_id"))
            elif message['command'] == 'add_track':
                self.liked_tracks.put(message.get("file_id"), message.get("data"))
        except Exception as ex:
            logging.exception(ex)

    def on_message(self, message):
        if message.text and (message.text == '/crown' or message.text == '/start crown'):
            self.request_crown(message.chat.id)

        if message.successful_payment:
            if message.successful_payment.invoice_payload == crown_requset:
                self.crown_data.update({"ends":int(round(time.time() * 1000)) + 1000 * 60 * 60 * 24})
                self.storage.put("crown", self.crown_data)

    def request_crown(self, chat_id):
        args = {
            'chat_id': chat_id,
            'title': 'Get a crown!',
            'description': u'Replaces your selflike ' + self.poo + u' with ' + self.crown + " for 24h!",
            'payload': crown_requset,
            'provider_token': os.getenv("telegram_payment_token"),
            'start_parameter': "crown",
            'currency': "RUB",
            'prices': [LabeledPrice(self.crown, 6000)],

                }
        self.bot.tell({'command':'invoice', 'invoice_args':args})

    def on_precheckout(self, pre):
        if pre.invoice_payload == crown_requset:
            self.bot.tell({"command":"confirm_precheckout", "id":pre.id})

    def crown_active(self):
       return self.crown_data["ends"] >= int(round(time.time() * 1000))
