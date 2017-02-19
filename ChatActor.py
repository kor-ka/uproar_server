#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import shelve
import string
from array import array
import random

import pykka, os, urllib, json
from telegram import InlineKeyboardButton
import base64
import StorageActor
import DeviceActor
from collections import OrderedDict
from operator import itemgetter

from pprint import pprint

from telegram import InlineKeyboardMarkup

loud = u'\U0001F50A'
not_so_loud = u'\U0001F509'

thumb_up = u'\U0001F44D'
thumb_down = u'\U0001F44E'

skip = u'\U000023E9'

downloading = u'\U00002B07'
queued = u'\U0000261D'
playing = u'\U0001F3B6'
stopped = u'\U00002B1B'
promoted = u'\U00002B06'

votes_to_skip = 2


class ChatActor(pykka.ThreadingActor):
    def __init__(self, chat_id, manager, bot, db):
        super(ChatActor, self).__init__()
        self.chat_id = chat_id
        self.manager = manager
        self.db = db
        self.bot = bot
        self.token = os.getenv('token')
        self.secret = os.getenv('secret')
        # self.devices = set()
        # self.devices_tokens = set()
        # self.latest_tracks = OrderedDict()
        # self.users = dict()
        # self.storage = None
        self.devices = None
        self.devices_tokens = None
        self.latest_tracks = None
        self.users = None

    def on_start(self):
        print self.chat_id
        self.latest_tracks = self.db.ask(
            {'command': 'get_list', 'name': StorageActor.TRACK_TABLE, 'suffix': self.chat_id})
        self.devices_tokens = self.db.ask(
            {'command': 'get_list', 'name': StorageActor.CHAT_DEVICES_TABLE, 'suffix': self.chat_id})

        self.devices = set()

        self.users = self.db.ask({'command': 'get_list', 'name': StorageActor.USER_TABLE, 'suffix': self.chat_id})

        for t in self.devices_tokens.get():
            self.devices.add(self.manager.ask({'command': 'get_device', 'token': t}))

    def on_message(self, message):
        if message.text:
            text = message.text
            if text.startswith('/token'):

                if not message.from_user.username:
                    self.bot.tell(
                        {'command': 'send', 'chat_id': message.chat_id,
                         'message': 'Please, setup username first'})
                    return

                random_str = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

                token_message = self.bot.ask(
                    {'command': 'send', 'chat_id': message.chat_id,
                     'message': loud + ' ' + message.from_user.username + '\'s device: ' + random_str})

                token_set = message.from_user.username + ':' + random_str + ':' + str(
                    hash(self.secret + str(message.from_user.id)))

                # '\n\nСообщение выше - идентификатор '
                # 'вашего устройства. Перешлите его в '
                # 'чат, на который хотите подписать '
                # 'устройство'

                self.bot.tell({'command': 'send', 'chat_id': message.chat_id, 'message': token_set + '\n\nMessage '
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
                        [InlineKeyboardButton(not_so_loud, callback_data=callback_vol_minus),
                         InlineKeyboardButton(loud, callback_data=callback_vol_plus)],
                    ]

                    placeholder = self.bot.ask({'command': 'send',
                                                'chat_id': message.chat_id,
                                                'message': u'\U00002705 Device added!\n' + DeviceActor.get_name(token),
                                                'reply_markup': InlineKeyboardMarkup(keyboard),
                                                })

                    self.actor_ref.tell(
                        {
                            'command': 'add_device',
                            'device': self.get_device(token),
                            'token': token,
                            'placeholder': placeholder,
                        })



                else:
                    self.bot.tell({'command': 'reply', 'base': message, 'message': 'Ooops, looks like it\'s not yours'})

            elif text.startswith('/score'):
                sortd = sorted(self.users.get(), key=itemgetter(1))
                score = ""
                for user_likes in sortd:
                    user = user_likes[0]
                    score += (user.first_name if not user.username else  '@' + user.username) + ' ' + str(
                        user_likes[1]) + '\n'
                if not score:
                    score = 'no one have likes for now'
                self.bot.tell({'command': 'reply', 'base': message, 'message': score})

        if message.audio:
            # TODO try catch, move to func - regenerate url before send todevice
            durl = None

            file_id = message.audio.file_id
            durl = self.get_d_url(file_id)

            if durl is None:
                return

            if len(self.devices) > 0:

                keyboard = [
                    [InlineKeyboardButton(thumb_up + " 0", callback_data='like:1'),
                     InlineKeyboardButton(thumb_down + " 0", callback_data='like:0')],
                ]

                title = message.audio.performer + " - " + message.audio.title
                reply = self.bot.ask(
                    {'command': 'reply', 'base': message,
                     'message': title,
                     'reply_markup': InlineKeyboardMarkup(keyboard)})

                data = {"track_url": durl, "chat_id": reply.chat_id, "message_id": reply.message_id,
                        "orig": message.message_id, 'title': title}
                for device in self.devices:
                    device.tell({'command': 'add_track', 'track': json.dumps(data)})

                self.latest_tracks.put(message.message_id, TrackStatus(message.message_id, title, data, file_id))

            else:
                self.bot.tell(
                    {'command': 'reply', 'base': message, 'message': 'no devices, please forward one from @uproarbot'})

    def get_d_url(self, file_id):
        durl = None
        try:
            track_info_raw = urllib.urlopen(
                'https://api.telegram.org/bot' + self.token + '/getFile?file_id=' + file_id)
            load = json.load(track_info_raw.fp)
            result = load.get('result')
            if result is not None:
                file_path = result.get('file_path')
                durl = 'https://api.telegram.org/file/bot' + self.token + '/' + file_path
        except:
            pass
        return durl

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

        message_id = None if not callback_query.message.reply_to_message else callback_query.message.reply_to_message.message_id
        if callback[0] == 'vol':
            dev = DeviceData(self.get_token(callback_query.message.text, callback_query.from_user))
            if dev.owner == callback_query.from_user.username:
                self.get_device(dev.token).tell({'command': 'vol', 'param': callback[1]})
            else:
                text = 'Ooops, looks like it\'s not yours'
        elif callback[0] == 'like':
            for likes_data in self.latest_tracks.get(key=message_id):

                user_id = callback_query.from_user.id
                if callback[1] == "1":
                    if user_id in likes_data.likes_owners:
                        likes_data.likes -= 1
                        likes_data.likes_owners.remove(user_id)
                        user_likes = (callback_query.message.reply_to_message.from_user, 0)
                        for user_likes_raw in self.users.get(callback_query.message.reply_to_message.from_user.id):
                            user_likes = (user_likes_raw[0], user_likes_raw[1] - 1)
                        self.users.put(callback_query.message.reply_to_message.from_user.id, user_likes)
                        text = "you took your like back"
                    elif user_id in likes_data.dislikes_owners:
                        text = "take your dislike back first"
                    else:
                        likes_data.likes += 1
                        likes_data.likes_owners.add(user_id)
                        text = "+1"
                        user_likes = (callback_query.message.reply_to_message.from_user, 0)
                        for user_likes_raw in self.users.get(callback_query.message.reply_to_message.from_user.id):
                            user_likes = (user_likes_raw[0], user_likes_raw[1] + 1)
                        self.users.put(callback_query.message.reply_to_message.from_user.id, user_likes)

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

                self.latest_tracks.put(message_id, likes_data)

                keyboard = self.get_keyboard(likes_data)

                self.bot.tell({'command': 'edit_reply_markup', 'base': callback_query,
                               'reply_markup': InlineKeyboardMarkup(keyboard)})

        elif callback[0] == 'skip':
            for likes_data in self.latest_tracks.get(message_id):
                text = "skipping %s" % likes_data.title
                for d in self.devices:
                    d.tell({'command': 'skip', 'orig': likes_data.original_msg_id})

        elif callback[0] == 'promote':
            for likes_data in self.latest_tracks.get(message_id):
                text = "promoting %s" % likes_data.title
                for d in self.devices:
                    d.tell({'command': 'promote', 'orig': likes_data.original_msg_id})

        if answer:
            callback_query.answer(text=text, show_alert=show_alert)

    def get_keyboard(self, likes_data):
        option = None
        if likes_data.dislikes >= votes_to_skip and likes_data.dislikes > likes_data.likes:
            option = InlineKeyboardButton(skip, callback_data='skip')
        if likes_data.likes >= votes_to_skip and likes_data.likes > likes_data.dislikes:
            option = InlineKeyboardButton(promoted, callback_data='promote')
        first_row = [InlineKeyboardButton(thumb_up + " " + str(likes_data.likes), callback_data='like:1'),
                     InlineKeyboardButton(thumb_down + " " + str(likes_data.dislikes), callback_data='like:0')]
        if option is not None:
            first_row.append(option)
        keyboard = [first_row]
        return keyboard

    def on_device_update(self, update):

        org_msg = update.get('message')
        if org_msg.startswith(u'\U0001F3B6') or org_msg.startswith(u'\U00002B1B'):

            callback_vol_plus = 'vol' + ':' + '1'
            callback_vol_minus = 'vol' + ':' + '0'

            keyboard = [
                [InlineKeyboardButton(not_so_loud, callback_data=callback_vol_minus),
                 InlineKeyboardButton(loud, callback_data=callback_vol_plus)],
            ]

            message = org_msg + " " + update.get('title') + '\n' + update.get('device_name')

            if update.get('placeholder'):
                self.bot.tell({'command': 'edit', 'base': update.get('placeholder'), 'message': message,
                               'reply_markup': InlineKeyboardMarkup(keyboard)})

        org_message_id = update.get('orig')
        for track_status in self.latest_tracks.get(org_message_id):
            message = update.get('title')

            track_status.device_status[update.get('device')] = org_msg

            for k, v in track_status.device_status.items():
                message += "\n" + v + ' : ' + k

            update['message'] = message

            keyboard = self.get_keyboard(track_status)
            self.bot.tell({'command': 'update', 'update': update, 'reply_markup': InlineKeyboardMarkup(keyboard)})
            self.latest_tracks.put(org_message_id, track_status)

    def on_device_online(self, token, device):
        for t in self.latest_tracks.get():
            status = t.device_status.get(token.split(':')[1])
            if status is None or status.startswith(downloading) or status.startswith(playing) or status.startswith(
                    queued) or status.startswith(promoted):
                t.data["track_url"] = self.get_d_url(t.file_id)
                device.tell({'command': 'add_track', 'track': json.dumps(t.data)})

    def on_boring(self, token, device):
        t = random.choice(self.latest_tracks.get())
        status = t.device_status.get(token.split(':')[1])
        if status is not status.startswith(skip):
            t.data["track_url"] = self.get_d_url(t.file_id)
            device.tell({'command': 'add_track', 'track': json.dumps(t.data)})

    def on_receive(self, message):
        try:
            if message.get('command') == 'message':
                self.on_message(message.get('message'))
            if message.get('command') == 'callback_query':
                self.on_callback_query(message.get('callback_query'))
            elif message.get('command') == 'add_device':
                self.devices.add(message.get('device'))
                self.devices_tokens.put(message.get('token'), message.get('token'))
                message.get('device').tell(
                    {'command': 'move_to', 'chat': self.actor_ref, 'placeholder': message.get('placeholder')})
            elif message.get('command') == 'remove_device':
                self.devices.remove(message.get('device'))
                self.devices_tokens.remove(message.get('token'))
            elif message.get('command') == 'device_update':
                self.on_device_update(message.get('update'))
            elif message.get('command') == 'device_online':
                self.on_device_online(message.get('token'), message.get('device'))
            elif message.get('command') == 'device_message':
                msg = message.get("message")
                if msg == "boring":
                    self.on_boring(message.get("token"), message.get("device"))
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
    def __init__(self, orig, title, data, file_id):
        super(TrackStatus, self).__init__()
        self.original_msg_id = orig
        self.file_id = file_id
        self.likes = 0
        self.dislikes = 0
        self.likes_owners = set()
        self.dislikes_owners = set()
        self.device_status = OrderedDict()
        self.played_once = False
        self.title = title
        self.data = data
