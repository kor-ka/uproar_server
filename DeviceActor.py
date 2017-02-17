import os

import pykka, shelve


def get_name(token):
    split = token.split(':')
    return split[0] + '\'s device: ' + split[1]


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt, bot):
        super(DeviceActor, self).__init__()
        self.token = token
        self.mqtt = mqtt
        self.mqtt.tell({'command': 'subscribe', 'token': self.token})
        self.manager = manager
        self.bot = bot
        self.chat = None
        self.placeholder = None
        self.storage = None


    def on_start(self):
        if not os.path.exists('devices'):
            os.makedirs('devices')
        self.storage = shelve.open('devices/%s' % self.token, writeback=True)
        self.placeholder = self.storage.get('placeholder')
        if self.placeholder:
            self.chat = self.manager.ask({'command': 'get_chat', 'chat_id': self.placeholder.chat_id})

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

    def open_shelve(self, path):
        try:
            return shelve.open(path)
        except:
            os.remove(path)
            return shelve.open(path)


    def on_receive(self, message):
        try:
            if message.get('command') == "add_track":
                self.publish("track", str(message.get('track')))

            elif message.get('command') == "move_to":
                if self.chat is not None and self.chat != message.get('chat'):
                    self.chat.tell({'command': 'remove_device', 'device': self.actor_ref, 'token':self.token})

                self.chat = message.get('chat')
                self.placeholder = message.get('placeholder')

                self.storage['placeholder'] = self.placeholder
                self.storage.close()
                self.storage = self.open_shelve('devices/%s' % self.token)


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
