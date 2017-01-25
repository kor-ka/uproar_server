#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import string
from array import array

import pykka, os, urllib, json, config
from telegram import InlineKeyboardButton
import base64
import DeviceActor
from collections import OrderedDict

from telegram import InlineKeyboardMarkup

loud = u'\U0001F50A'
not_so_loud = u'\U0001F509'

thumb_up = u'\U0001F44D'
thumb_down = u'\U0001F44E'

votes_to_skip = 2

latest_tracks = OrderedDict()

class ChatActor(pykka.ThreadingActor):
    def __init__(self, chat_id, manager, bot):
        super(ChatActor, self).__init__()
        self.chat_id = chat_id
        self.manager = manager
        self.bot = bot
        self.token = config.bottoken
        self.secret = config.secret
        self.devices = set()

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
                    {'command': 'send', 'chat_id':message.chat_id, 'message': loud + ' ' + message.from_user.username + '\'s device: ' + random_str})

                token_set = message.from_user.username + ':' + random_str + ':' + str(hash(self.secret + str(message.from_user.id)))

                # '\n\nСообщение выше - идентификатор '
                # 'вашего устройства. Перешлите его в '
                # 'чат, на который хотите подписать '
                # 'устройство'

                self.bot.tell({'command': 'send','chat_id':message.chat_id, 'message': token_set + '\n\nMessage '
                                                                                               'above is your device '
                                                                                               'holder, forward it to '
                                                                                               'chat to subscribe'})

            elif text.startswith(loud):
                if message.from_user.username and message.text.replace(loud + ' ', '').startswith(
                        message.from_user.username):
                    token = self.get_token(message.text, message.from_user)


                    callback_vol_plus = 'vol' + ':' + '1'

                    callback_vol_minus = 'vol' + ':' + '0'

                    keyboard = [
                                    [InlineKeyboardButton(not_so_loud, callback_data=callback_vol_minus), InlineKeyboardButton(loud, callback_data=callback_vol_plus)],
                               ]

                    placeholder = self.bot.ask({'command': 'send',
                                   'chat_id': message.chat_id,
                                   'message': u'\U00002705 Device added!\n'+ DeviceActor.get_name(token),
                                   'reply_markup': InlineKeyboardMarkup(keyboard),
                                   })

                    self.actor_ref.tell(
                        {
                            'command': 'add_device',
                            'device': self.get_device(token),
                            'placeholder':placeholder,
                        })



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
            if len(self.devices) > 0:

                keyboard = [
                    [InlineKeyboardButton(thumb_up, callback_data='like:1'),
                     InlineKeyboardButton(thumb_down, callback_data='like:0')],
                ]

                title = message.audio.performer + " - " + message.audio.title
                reply = self.bot.ask(
                    {'command': 'reply', 'base': message,
                     'message': title,
                     'reply_markup': InlineKeyboardMarkup(keyboard)})

                for device in self.devices:
                    data = json.dumps({"track_url": durl, "chat_id": reply.chat_id, "message_id": reply.message_id, "orig":message.message_id, 'title':title})
                    device.tell({'command': 'add_track', 'track': data, 'chat': self.actor_ref})

                latest_tracks[message.message_id] = TrackStatus(message.message_id)
                if len(latest_tracks) >= 100:
                    # TODO update deleted track - remove buttons
                    latest_tracks.popitem(False)

            else:
                self.bot.tell({'command': 'reply', 'base': message, 'message': 'no devices, please forward one from @uproarbot'})

    def get_token(self, text, user):
        last_str = string.split(text, '\n')[-1].replace(loud, '').replace(' ', '')
        token = string.split(last_str, '\'')[0] + ':' + last_str[-5:] + ':' + str(hash(self.secret + str(user.id)))
        return token

    def get_device(self, token):
        return self.manager.ask({'command': 'get_device', 'token': token})

    def on_callback_query(self, callback_query):
        callback = string.split(callback_query.data, ":")
        if 0 == len(callback):
            return

        answer = True
        text = None
        show_alert = False

        if callback[0] == 'vol':
            dev = DeviceData(self.get_token(callback_query.message.text, callback_query.from_user))
            if dev.owner == callback_query.from_user.username:
                self.get_device(dev.token).tell({'command':'vol', 'param':callback[1]})
            else:
                text = 'Ooops, looks like it\'s not yours'
        elif callback[0] == 'like':
            likes_data = latest_tracks[callback_query.message.reply_to_message.message_id]
            if likes_data:
                user_id = callback_query.from_user.id
                if callback[1] == "1":
                    if user_id in likes_data.likes_owners:
                        likes_data.likes -= 1
                        likes_data.likes_owners.remove(user_id)
                        text = "you took your like back"
                    elif user_id in likes_data.dislikes_owners:
                        text = "take your dislike back first"
                    else:
                        likes_data.likes += 1
                        likes_data.likes_owners.add(user_id)
                        text = "+1"

                elif callback[1] == "0":
                    if user_id in likes_data.dislikes_owners:
                        likes_data.dislikes -= 1
                        likes_data.dislikes_owners.remove(user_id)
                        text = "you took your dislike back"
                    elif user_id in likes_data.likes_owners:
                        text = "take your like back first"
                    else:
                        likes_data.dislikes += 1
                        likes_data.dislikes_owners.add(user_id)
                        text = "-1"

                keyboard = [
                    [InlineKeyboardButton(thumb_up + " " + str(likes_data.likes), callback_data='like:1'),
                     InlineKeyboardButton(thumb_down + " " + str(likes_data.dislikes), callback_data='like:0')],
                ]

                self.bot.tell({'command':'edit_reply_markup', 'base':callback_query, 'reply_markup':InlineKeyboardMarkup(keyboard)})

        if answer:
            callback_query.answer(text=text, show_alert=show_alert)

    def on_device_update(self, update):

        if update.get('message').startswith(u'\U0001F3B6'):

            callback_vol_plus = 'vol' + ':' + '1'
            callback_vol_minus = 'vol' + ':' + '0'

            keyboard = [
                [InlineKeyboardButton(not_so_loud, callback_data=callback_vol_minus),
                 InlineKeyboardButton(loud, callback_data=callback_vol_plus)],
            ]

            if update.get('placeholder'):
                self.bot.tell({'command':'edit', 'base':update.get('placeholder'), 'message':update.get('message'), 'reply_markup':InlineKeyboardMarkup(keyboard)})

        likes_data = latest_tracks[update.get('orig')]
        if likes_data:
            message = update.get('title')

            likes_data.device_status[update.get('device')] = update.get('message')

            for k,v in likes_data.device_status.items():
                message += "\n" + v

            update['message'] = message

            keyboard = [
                [InlineKeyboardButton(thumb_up + " " + str(likes_data.likes), callback_data='like:1'),
                 InlineKeyboardButton(thumb_down + " " + str(likes_data.dislikes), callback_data='like:0')],
            ]
            self.bot.tell({'command': 'update', 'update': update, 'reply_markup':InlineKeyboardMarkup(keyboard)})


    def on_receive(self, message):
        try:
            if message.get('command') == 'message':
                self.on_message(message.get('message'))
            if message.get('command') == 'callback_query':
                self.on_callback_query(message.get('callback_query'))
            elif message.get('command') == 'add_device':
                self.devices.add(message.get('device'))
                message.get('device').tell({'command': 'move_to', 'chat': self.actor_ref})
            elif message.get('command') == 'remove_device':
                self.devices.remove(message.get('device'))
            elif message.get('command') == 'device_update':
                self.on_device_update(message.get('update'))
        except Exception as ex:
            print ex


class DeviceData(object):
    def __init__(self, token):
        super(DeviceData, self).__init__()
        self.token = token
        token_split = string.split(token, ':')
        self.owner = token_split[0]
        self.id = token_split[1]

class TrackStatus(object):
    def __init__(self, orig):
        super(TrackStatus, self).__init__()
        self.original_msg_id = orig
        self.likes = 0
        self.dislikes = 0
        self.likes_owners = set()
        self.dislikes_owners = set()
        self.device_status = OrderedDict()
