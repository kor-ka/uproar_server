import pykka


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt, bot):
        super(DeviceActor, self).__init__()
        self.token = token
        self.manager = manager
        self.mqtt = mqtt
        self.bot = bot
        self.chat = None

    def get_name(self):
        split = self.token.split(':')
        return split[0] + '\'s device (' + split[1] + ')'

    def on_receive(self, message):
        if message.get('command') == "add_track":
            self.mqtt.tell({'command': 'publish', 'topic': 'track_' + self.token, 'payload': str(message.get('track'))})
        elif message.get('command') == "move_to":
            self.mqtt.tell({'command': 'subscribe', 'token': self.token})
            if self.chat is not None and self.chat != message.get('chat'):
                self.chat.tell({'command': 'remove_device', 'device': self.actor_ref})
            self.chat = message.get('chat')
        elif message.get('command') == "get_name":
            return self.get_name()
        elif message.get('command') == "update":
            update = message.get('update')
            old_msg = update['message']
            update['message'] = self.get_name() + ': ' + old_msg
            self.bot.tell({'command': 'update', 'update': update})


