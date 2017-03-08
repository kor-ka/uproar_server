import logging
from pprint import pprint

import paho.mqtt.client as mqtt, pykka, os, json
from telegram import InlineKeyboardButton


class MqttACtor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(MqttACtor, self).__init__()
        self.client = None
        self.manager = manager
        self.client = self.initMqtt()
        self.mqtt_user = os.getenv("mqtt_user")
        self.mqtt_pass = os.getenv("mqtt_pass")



    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        try:
            print "MQTT <-- topic: %s | msg: %s" % (msg.topic, str(msg.payload))

            if msg.topic == 'registry':
                self.client.subscribe("device_out_" + str(msg.payload), 2)
                device = self.manager.ask({'command': 'get_device', 'token': str(msg.payload)})
                device.tell({'command':'online'})
            elif str(msg.topic).startswith("device_out_"):
                token = msg.topic.replace("device_out_", "")
                self.manager.tell({'command':'device_out', 'token':token, 'update': str(msg.payload)})
            
        except Exception as ex:
            logging.exception(ex)
    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("server_" + "test", 2)
        client.subscribe("update_test", 2)

    def initMqtt(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.username_pw_set(self.mqtt_user, self.mqtt_pass)
        client.connect('m21.cloudmqtt.com', 18552)
        client.loop_start()
        return client

    def on_receive(self, message):
        try:
            if message.get('command') == "publish":
                print "MQTT --> topic: %s | msg: %s" % (message.get('topic'), message.get('payload'))

                self.client.publish(message.get('topic'), message.get('payload'))
            if message.get('command') == "subscribe":
                self.client.subscribe('device_out_' + message.get('token'), 2)
        except Exception as ex:
            logging.exception(ex)
