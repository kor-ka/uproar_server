import paho.mqtt.client as mqtt, pykka, os, json
from telegram import InlineKeyboardButton


class MqttACtor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(MqttACtor, self).__init__()
        self.client = None
        self.manager = manager
        self.client = self.initMqtt()


    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == 'server_test':
                self.client.subscribe("update_" + str(msg.payload), 1)
            elif str(msg.topic).startswith("update_"):
                token = msg.topic.replace("update_", "")
                self.manager.tell({'command':'device_update_status', 'token':token, 'update':json.loads(str(msg.payload))})
        except Exception as ex:
            print ex
    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("server_" + "test", 1)
        client.subscribe("update_test", 1)

    def initMqtt(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.username_pw_set('eksepjal', 'UyPdNESZw5yo')
        client.connect('m21.cloudmqtt.com', 18552)
        client.loop_start()
        return client

    def on_receive(self, message):
        try:
            if message.get('command') == "publish":
                self.client.publish(message.get('topic'), message.get('payload'))
            if message.get('command') == "subscribe":
                self.client.subscribe('update_' + message.get('token'), 1)
        except Exception as ex:
            print ex
