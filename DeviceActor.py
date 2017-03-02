import os

import pykka, shelve
import StorageActor

def get_name(token):
    split = token.split(':')
    return split[0] + '\'s device: ' + split[1]


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt, bot, db):
        super(DeviceActor, self).__init__()
        self.token = token
        self.mqtt = mqtt
        self.mqtt.tell({'command': 'subscribe', 'token': self.token})
        self.manager = manager
        self.bot = bot
        self.chat = None
        self.placeholder = None
        self.db = db
        self.storage = None


    def on_start(self):
        self.storage = self.db.ask(
            {'command': 'get_list', 'name': StorageActor.DEVICE_STORAGE, 'suffix': get_name(self.token)})
        for placeholder in self.storage.get('placeholder'):
            self.placeholder = placeholder
 
    def on_update(self, message):
        update = message.get('update')
        old_msg = update['message']
        if old_msg == 'download':
            old_msg = u'\U00002B07 downloading...'
        elif old_msg == 'queue':
            old_msg = u'\U0000261D queued'
        elif old_msg == 'playing':
            old_msg = u'\U0001F3B6 playing'
        elif old_msg == 'done':
            old_msg = u'\U00002B1B stopped'
        elif old_msg == 'skip':
            old_msg = u'\U000023E9 skipped'
        elif old_msg == 'promote':
            old_msg = u'\U00002B06 promoted'
        device_id = self.token.split(':')[1]
        update['device'] = device_id
        update['placeholder'] = self.placeholder
        update['device_name'] = get_name(self.token)
        update['message'] = old_msg
        if self.chat is not None:
            self.chat.tell({'command': 'device_update', 'update': update})

    def on_receive(self, message):
        try:
            if message.get('command') == "add_track":
                self.publish("track", str(message.get('track')))

            elif message.get('command') == "move_to":
                if self.chat is not None and self.chat != message.get('chat'):
                    self.chat.tell({'command': 'remove_device', 'device': self.actor_ref, 'token':self.token})

                self.chat = message.get('chat')
                self.placeholder = message.get('placeholder')

                self.storage.put('placeholder', self.placeholder)


            elif message.get('command') == "get_name":
                return get_name(self.token)

            elif message.get('command') == "update":

                self.on_update(message)
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
                    self.chat.tell({'command': 'device_online', 'token': self.token, 'device': self.actor_ref})
            elif message.get('command') == "device_message":
                if self.chat is not None:
                    self.chat.tell({'command': 'device_message', 'token': self.token,
                                    'device': self.actor_ref, "message": message.get("message")})

        except Exception as ex:
            print ex

    def publish(self, topic, payload):
        self.mqtt.tell({'command': 'publish', 'topic': topic + '_' + self.token, 'payload': payload})
