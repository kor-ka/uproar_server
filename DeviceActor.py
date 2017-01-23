import pykka


class DeviceActor(pykka.ThreadingActor):
    def __init__(self, token, manager, mqtt):
        super(DeviceActor, self).__init__()
        self.token = token
        self.manager = manager
        self.mqtt = mqtt
        self.chat = None

    def on_receive(self, message):
        if message.get('command') == "add_track":
            self.mqtt.tell({'command': 'publish', 'topic': 'track_' + self.token, 'payload': str(message.get('track'))})
        elif message.get('command') == "move_to":
            self.mqtt.tell({'command': 'subscribe', 'token': self.token})
            if self.chat is not None and self.chat != message.get('chat'):
                self.chat.tell({'command': 'remove_device', 'device': self.actor_ref})
            self.chat = message.get('chat')
        elif message.get('command') == "get_name":
            split = self.token.split(':')
            return split[0] + '\'s device (' + split[1] + ')'
