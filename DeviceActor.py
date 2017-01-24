import pykka


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt, bot):
        super(DeviceActor, self).__init__()
        self.token = token
        self.manager = manager
        self.mqtt = mqtt
        self.bot = bot
        self.chat = None

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
            old_msg = u'\U00002B1B stop'
        update['message'] = old_msg + '\n' + self.get_name()
        self.bot.tell({'command': 'update', 'update': update})

    def get_name(self):
        split = self.token.split(':')
        return split[0] + '\'s device (' + split[1] + ')'

    def on_receive(self, message):
        if message.get('command') == "add_track":
            self.publish("track",str(message.get('track')))

        elif message.get('command') == "move_to":
            self.mqtt.tell({'command': 'subscribe', 'token': self.token})
            if self.chat is not None and self.chat != message.get('chat'):
                self.chat.tell({'command': 'remove_device', 'device': self.actor_ref})
            self.chat = message.get('chat')

        elif message.get('command') == "get_name":

            return self.get_name()
        elif message.get('command') == "update":

            self.on_update(message)
        elif message.get('command') == "vol":
            self.publish('volume', message.get('param'))

    def publish(self, topic, payload):
        self.mqtt.tell({'command': 'publish', 'topic': topic+'_' + self.token, 'payload': payload})


