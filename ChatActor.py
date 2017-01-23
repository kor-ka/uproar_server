#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import string
from array import array

import pykka, os, urllib, json, config

emoji_prefix = u'\U0001F50A'

class ChatActor(pykka.ThreadingActor):
    def __init__(self, chat_id, manager, bot):
        super(ChatActor, self).__init__()
        self.chat_id = chat_id
        self.manager = manager
        self.bot = bot
        self.token = config.bottoken
        self.secret = config.secret
        self.devices = array()

    def on_message(self, message):
        if message.text:
            text = message.text
            if text.startswith('/token'):

                if not message.from_user.username:
                    self.bot.tell(
                        {'command': 'send', 'chat_id':message.chat_id,
                         'message': 'Please, setup username first'})
                    return

                random_str = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

                token_message = self.bot.ask(
                    {'command': 'send', 'chat_id':message.chat_id, 'message': emoji_prefix + ' ' + message.from_user.username + '\' device: ' + random_str})

                token_set = message.from_user.username + ':' + random_str + ':' + str(hash(self.secret + str(message.from_user.id)))

                # '\n\nСообщение выше - идентификатор '
                # 'вашего устройства. Перешлите его в '
                # 'чат, на который хотите подписать '
                # 'устройство'

                self.bot.tell({'command': 'send','chat_id':message.chat_id, 'message': token_set + '\n\nMessage '
                                                                                               'above is your device '
                                                                                               'holder, forward it to '
                                                                                               'chat to subscribe'})

            elif text.startswith(emoji_prefix):
                if message.from_user.username and message.text.replace(emoji_prefix + ' ', '').startswith(
                        message.from_user.username):
                    token = message.from_user.username + ':' + text[-5:] + ':' + str(hash(self.secret + str(message.from_user.id)))
                    self.actor_ref.tell(
                        {
                            'command': 'add_device',
                            'device': self.manager.ask({'command': 'get_device', 'token': token})
                        })
                    self.bot.tell({'command': 'reply', 'base': message, 'message': 'Device added!'})

                else:
                    self.bot.tell({'command': 'reply', 'base': message, 'message': 'Ooops, looks like it\'s not yours'})

        if message.audio:
            track_info_raw = urllib.urlopen(
                'https://api.telegram.org/bot' + self.token + '/getFile?file_id=' + message.audio.file_id)
            load = json.load(track_info_raw.fp)
            result = load.get('result')
            if result is None:
                return
            file_path = result.get('file_path')
            durl = 'https://api.telegram.org/file/bot' + self.token + '/' + file_path
            if self.devices.__sizeof__() > 0:
                for device in self.devices:
                    device_str = device.ask({'command':'get_name'})
                    reply = self.bot.ask(
                        {'command': 'reply', 'base': message, 'message': "sent  " + message.audio.title + " to " + device_str})
                    data = json.dumps({"track_url": durl, "chat_id": reply.chat_id, "message_id": reply.message_id})
                    device.tell({'command': 'add_track', 'track': data, 'chat': self.actor_ref})
            else:
                self.bot.ask({'command': 'reply', 'base': message, 'message': 'no devices, please forward one from @uproarbot'})


    def on_receive(self, message):
        if message.get('command') == 'message':
            self.on_message(message.get('message'))
        elif message.get('command') == 'add_device':
            self.devices.append(message.get('device'))
            message.get('device').tell({'command': 'move_to', 'chat': self.actor_ref})
        elif message.get('command') == 'remove_device':
            if self.device == message.get('device'):
                self.devices.remove(message.get('device'))
