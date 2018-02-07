import logging
from pprint import pprint

import pykka
import BotActor, MqttActor, ChatActor, DeviceActor, Storage
import FlaskRunner
import InlineActor
import UserActor
from Storage import DbList


class Context(object):
    def __init__(self):
        self.bot = None
        self.reminder = None
        self.storage = None


class ManagerActor(pykka.ThreadingActor):
    def __init__(self):
        super(ManagerActor, self).__init__()
        self.context = Context()
        self.bot = BotActor.BotActor.start(self.actor_ref)
        self.mqtt = MqttActor.MqttACtor.start(self.actor_ref)
        self.storage = Storage.StorageActor.start()
        # self.flask = FlaskRunner.FlaskRunner.start(self.actor_ref)

        self.context.bot = self.bot
        self.context.storage = self.storage

        self.devices = dict()
        self.chats = dict()
        self.users = dict()
        self.inline_actors = dict()

        self.chats_stat = self.context.storage.ask(
            {'command': 'get_list', 'name': Storage.CHAT_STAT_TABLE, "type": "stat"})  # type: DbList

    def on_message(self, message):
        self.get_chat(message.chat_id, chat_type=message.chat.type).tell({'command': 'message', 'message': message})
        if message.chat.type == 'private':
            self.get_user(message.from_user.id).tell({"command": "msg", "msg": message})

    def on_callback_query(self, callback_query):
        if callback_query.message:
            self.get_chat(callback_query.message.chat_id, chat_type=callback_query.message.chat.type).tell(
                {'command': 'callback_query', 'callback_query': callback_query})

    def on_inline_query(self, inline_query):
        self.get_chat(inline_query.from_user.id).tell({"command": "inline_query", "q": inline_query})
        # self.get_inline_actor(inline_query.from_user.id).tell({"command": "q", "q":inline_query})

    def on_pre_checkout_query(self, pre_checkout_query):
        self.get_user(pre_checkout_query.from_user.id).tell({"command": "pre", "pre": pre_checkout_query})

    def on_device_update(self, token, update):
        self.get_device(token).tell({'command': 'update', 'update': update})

    def on_device_out_update(self, token, message):
        self.get_device(token).tell({'command': 'device_out', 'update': message})

    def get_chat(self, chat_id, chat_type=None):
        chat = self.chats.get(chat_id)
        if chat is None or not chat.is_alive:
            chat = ChatActor.ChatActor.start(chat_id, self.actor_ref, self.bot, self.context)
            self.chats[chat_id] = chat

        if chat_type and chat_type != 'private':
            self.chats_stat.put_stat({"id": chat_id})

        return chat

    def get_user(self, user_id):
        user = self.users.get(user_id)
        if user is None or not user.is_alive:
            user = UserActor.UserActor.start(user_id, self.context)
            self.users[user_id] = user
        return user

    def get_inline_actor(self, user_id):
        inline_actor = self.inline_actors.get(user_id)
        if inline_actor is None or not inline_actor.is_alive:
            inline_actor = InlineActor.InlineActor.start(self.bot)
            print("new inline_actor")
            self.inline_actors[user_id] = inline_actor
        return inline_actor

    def get_device(self, token):
        device = self.devices.get(token)
        if device is None or not device.is_alive:
            device = DeviceActor.DeviceActor.start(token, self.actor_ref, self.mqtt, self.context)
            self.devices[token] = device
        return device

    def on_receive(self, message):
        try:
            print "Manager Actor msg " + str(message)
            if message.get('command') == 'update':
                update = message.get('update')
                if update.message or update.channel_post:
                    self.on_message(update.message if update.message else update.channel_post)
                elif update.callback_query:
                    self.on_callback_query(update.callback_query)
                elif update.inline_query:
                    self.on_inline_query(update.inline_query)
                elif update.pre_checkout_query:
                    self.on_pre_checkout_query(update.pre_checkout_query)
            elif message.get('command') == 'device_out':
                self.on_device_out_update(message.get('token'), message.get('update'))
            elif message.get('command') == 'get_device':
                return self.get_device(message.get('token'))
            elif message.get('command') == 'get_chat':
                return self.get_chat(message.get('chat_id'))
            elif message.get('command') == 'get_user':
                return self.get_user(message.get('user_id'))
            elif message.get('command') == 'payment':
                pprint(message['data'])
        except Exception as ex:
            logging.exception(ex)
