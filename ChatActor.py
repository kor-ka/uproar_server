#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import string

import pykka, os, urllib, json

emoji_prefix = u'\U0001F50A'

class ChatActor(pykka.ThreadingActor):
    def __init__(self, chat_id, manager, bot):
        super(ChatActor, self).__init__()
        self.chat_id = chat_id
        self.manager = manager
        self.bot = bot
        self.token = os.getenv('BOTTOKEN', '')
        self.device = None

    def on_message(self, message):
        if message.text:
            text = str(message.text)
            if text.startswith('/token'):

                if not message.from_user.username:
                    self.bot.tell(
                        {'command': 'send',
                         'message': 'У тебя что, ник не установлен? Омг, это в 21 то веке! Сходи поставь, потом возвращайся'})
                    return

                token_message = self.bot.ask(
                    {'command': 'send', 'chat_id':message.chat_id, 'message': emoji_prefix + ' ' + message.from_user.username + '\' device'})

                token = token_message.from_user.username + ':' + str(hash(token_message.date))

                # '\n\nСообщение выше - идентификатор '
                # 'вашего устройства. Перешлите его в '
                # 'чат, на который хотите подписать '
                # 'устройство'

                self.bot.tell({'command': 'send','chat_id':message.chat_id, 'message': 'token: ' + token})

                if text.startswith(emoji_prefix):
                    if message.forward_date and message.text.replase(emoji_prefix + ' ', 1).startsWith(
                            message.from_user.username):
                        token = message.from_user.username + ':' + str(hash(message.forward_date))
                        self.actor_ref.tell(
                            {
                                'command': 'add_device',
                                'device': self.manager.ask({'command': 'get_device', 'token': token})
                            })
                    else:
                        self.bot.tell({'command': 'reply', 'base': message, 'message': 'Кажется, это не твое'})

        if message.audio:
            track_info_raw = urllib.urlopen(
                'https://api.telegram.org/bot' + self.token + '/getFile?file_id=' + message.audio.file_id)
            load = json.load(track_info_raw.fp)
            result = load.get('result')
            if result is None:
                return
            file_path = result.get('file_path')
            durl = 'https://api.telegram.org/file/bot' + self.token + '/' + file_path
            reply = self.bot.ask({'command': 'reply', 'base': message, 'message': "added " + message.audio.title})

            data = json.dumps({"track_url": durl, "chat_id": reply.chat_id, "message_id": reply.message_id})
            if self.device is not None:
                self.device.tell({'command': 'add_track', 'track': data, 'chat': self.actor_ref})

    def on_receive(self, message):
        if message.get('command') == 'message':
            self.on_message(message.get('message'))
        elif message.get('command') == 'add_device':
            self.device = message.get('device')
            self.device.tell({'command': 'move_to', 'chat': self.actor_ref})
        elif message.get('command') == 'remove_device':
            if self.device == message.get('device'):
                self.device = None
