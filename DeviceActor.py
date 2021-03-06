import json
import os

import logging
import pykka, shelve
import Storage
from pprint import pprint


def get_name(token):
    split = token.split('-')
    return split[0] + '\'s device: ' + split[1]


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt, context):
        super(DeviceActor, self).__init__()
        self.token = token
        self.mqtt = mqtt
        self.manager = manager
        self.bot = context.bot
        self.chat = None
        self.placeholder = None
        self.db = context.storage
        self.storage = None

    def on_start(self):

        self.storage = self.db.ask(
            {'command': 'get_list', 'name': Storage.DEVICE_STORAGE, 'suffix': str(self.token).replace(":", "")})
        for placeholder in self.storage.get('placeholder'):
            if placeholder:
                self.placeholder = placeholder
                self.chat = self.manager.ask({'command': 'get_chat', 'chat_id': self.placeholder.chat_id})

    def on_update_content_status(self, update, additional_id):
        if str(self.token).startswith("c-"):
            return

        msg = update['message']
        if msg == 'download':
            msg = u'\U00002B07 downloading...'
        elif msg == 'queue':
            msg = u'\U0000261D queued'
        elif msg == 'playing':
            msg = u'\U0001F3B6 playing'
        elif msg == 'done':
            msg = u'\U00002B1B stopped'
        elif msg == 'skip':
            msg = u'\U000023E9 skipped'
        elif msg == 'promote':
            msg = u'\U00002B06 promoted'
        device_id = self.token.split('-')[1]
        update['device'] = device_id + ("" if additional_id is None else additional_id)
        update['placeholder'] = self.placeholder
        update['device_name'] = additional_id[-5:] if additional_id else get_name(self.token) + update['device']
        update['message'] = msg
        if self.chat is not None:
            self.chat.tell({'command': 'device_content_status', 'content_status': update, 'token': self.token})

    def on_receive(self, message):
        try:
            print "Device Actor msg " + str(message)

            if message.get('command') == "add_track":
                self.publish("add_content",
                             {"audio": message.get('track')}, message.get('additional_id'))

            if message.get('command') == "add_youtube_link":
                self.publish("add_content", {"youtube_link": message.get('youtube_link')}, message.get('additional_id'))

            elif message.get('command') == "move_to":
                if self.chat is not None and self.chat != message.get('chat'):
                    self.chat.tell({'command': 'remove_device', 'device': self.actor_ref, 'token': self.token})

                self.chat = message.get('chat')
                self.placeholder = message.get('placeholder')

                self.storage.put('placeholder', self.placeholder)

            elif message.get('command') == "publish":
                return self.publish(message.get("topic"), message.get("data"),
                                    additional_id=message.get('additional_id'))

            elif message.get('command') == "get_name":
                return get_name(self.token)

            elif message.get('command') == "vol":
                self.publish('volume', message.get('param'))
            elif message.get('command') == "get_placeholder":
                return self.placeholder
            elif message.get('command') == "skip":
                self.publish('skip', message.get('orig'))
            elif message.get('command') == "promote":
                self.publish('promote', message.get('orig'))
            elif message.get('command') == "online":
                if self.chat is not None:
                    self.chat.tell(
                        {'command': 'device_online', 'token': self.token, "additional_id": message.get("additional_id"),
                         "start_with": message.get("start_with"),
                         'device': self.actor_ref})
            elif message.get('command') == "device_out":
                update = message.get("update")

                if update["update"] == "update_track_status":
                    self.on_update_content_status(update['data'], update.get('additional_id'))
                elif self.chat is not None:
                    self.chat.tell({'command': 'device_message', 'token': self.token,
                                    'device': self.actor_ref, "message": update})

        except Exception as ex:
            logging.exception(ex)

    def publish(self, topic, data, additional_id=None):
        payload = {"update": topic, "data": data}
        self.mqtt.tell(
            {'command': 'publish', 'topic': "device_in_" + self.token + ("_" + additional_id if additional_id else ""),
             'payload': str(json.dumps(payload))})
