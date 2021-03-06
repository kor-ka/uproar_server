import logging
import ssl
from pprint import pprint

import paho.mqtt.client as mqtt, pykka, os, json
from telegram import InlineKeyboardButton


class MqttACtor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(MqttACtor, self).__init__()
        self.client = None
        self.manager = manager
        self.mqtt_user = os.getenv("mqtt_user")
        self.mqtt_pass = os.getenv("mqtt_pass")

    def on_start(self):
        self.client = self.initMqtt()

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        try:
            print "MQTT <-- topic: %s | msg: %s" % (msg.topic, str(msg.payload))

            if msg.topic == 'registry':
                reg_json = None
                try:
                    reg_json = json.loads(msg.payload)
                except Exception as ex:
                   pass
                if reg_json:
                    device = self.manager.ask({'command': 'get_device', 'token': reg_json["token"]})
                    device.tell({'command': 'online', "additional_id":reg_json.get("additional_id"), "start_with":reg_json.get("start_with")})
                else:
                    device = self.manager.ask({'command': 'get_device', 'token': str(msg.payload)})
                    device.tell({'command': 'online'})
            elif str(msg.topic).startswith("device_out"):
                update = json.loads(str(msg.payload))
                token = update.get("token")
                if token:
                    self.manager.tell({'command':'device_out', 'token':token, 'update': update})
            
        except Exception as ex:
            logging.exception(ex)
    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("registry", 2)
        client.subscribe("device_out", 2)

    def initMqtt(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.username_pw_set("web", "web")
        client.connect('uproar.servebeer.com', 1883)
        client.loop_start()
        return client

    def on_receive(self, message):
        try:
            print "Mqtt Actor msg " + str(message)
            if message.get('command') == "publish":
                print "MQTT --> topic: %s | msg: %s" % (message.get('topic'), message.get('payload'))

                self.client.publish(message.get('topic'), payload =str(message.get('payload')).encode('ascii', 'ignore').decode('ascii'), qos= 2)
        except Exception as ex:
            logging.exception(ex)
