import logging
from pprint import pprint

import pykka
import BotActor, MqttActor, ChatActor, DeviceActor, Storage

class ManagerActor(pykka.ThreadingActor):
    def __init__(self):
        super(ManagerActor, self).__init__()
        self.bot = BotActor.BotActor.start(self.actor_ref)
        self.mqtt = MqttActor.MqttACtor.start(self.actor_ref)

        self.devices = dict()
        self.chats = dict()

    def on_message(self, message):
        self.get_chat(message.chat_id).tell({'command':'message', 'message':message})

    def on_callback_query(self, callback_query):
        if callback_query.message:
            self.get_chat(callback_query.message.chat_id).tell({'command':'callback_query', 'callback_query':callback_query})

    def on_device_update(self, token, update):
        self.get_device(token).tell({'command':'update', 'update':update})

    def on_device_out_update(self, token, message):
        self.get_device(token).tell({'command':'device_out', 'update':message})

    def get_chat(self, chat_id):
        chat = self.chats.get(chat_id)
        if chat is None or not chat.is_alive:
            chat = ChatActor.ChatActor.start(chat_id, self.actor_ref, self.bot)
            self.chats[chat_id] = chat
        return chat

    def get_device(self, token):
        device = self.devices.get(token)
        if device is None or not device.is_alive:
            device = DeviceActor.DeviceActor.start(token, self.actor_ref, self.mqtt, self.bot)
            self.devices[token] = device
        return device

    def on_receive(self, message):
        try:
            print "Manager Actor msg " + message
            if message.get('command') == 'update':
                update = message.get('update')
                if update.message:
                    self.on_message(update.message)
                elif update.callback_query:
                    self.on_callback_query(update.callback_query)
            elif message.get('command') == 'device_out':
                self.on_device_out_update(message.get('token'), message.get('update'))
            elif message.get('command') == 'get_device':
                return self.get_device(message.get('token'))
            elif message.get('command') == 'get_chat':
                return self.get_chat(message.get('chat_id'))
        except Exception as ex:
            logging.exception(ex)

