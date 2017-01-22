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
            self.mqtt.tell({'command':'publish', 'topic':'track_'+self.token, 'payload':str(message.get('track'))})
        if message.get('command') == "move_to":
            self.mqtt.tell({'command':'subscribe', 'token':self.token})
            if self.chat is not None:
                self.chat.tell({'command':'remove_device', 'device':self.actor_ref})
            self.chat = message.get('chat')
