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
        if msg.topic == 'server_test':
            print(str(msg.payload))
            # if last_chat_id is not None:
            #     print('have last message, forvard to to chat')
            #     btn_down = InlineKeyboardButton('vol -', callback_data="volume_down")
            #     btn_up = InlineKeyboardButton('vol +', callback_data="volume_up")
            #
            #     bot.send_message(last_chat_id, 'lets make some nooooise!', reply_markup=InlineKeyboardMarkup(
            #         [[btn_down, btn_up]]))
        elif str(msg.topic).startswith("update_"):
            token = msg.topic.replce("update_", 1)
            self.manager.tell({'command':'device_update_status', 'token':token, 'update':json.loads(str(msg.payload))})

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("server_" + "test", 0)
        client.subscribe("update_test", 0)

    def initMqtt(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.username_pw_set('eksepjal', 'UyPdNESZw5yo')
        client.connect('m21.cloudmqtt.com', 18552)
        client.loop_start()
        return client

    def on_receive(self, message):
        if message.get('command') == "publish":
            self.client.publish(message.get('topic'), message.get('payload'))