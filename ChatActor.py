#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import shelve
import string
from array import array
import random
import re
import logging

import apiai
import pykka, os, urllib, json
import requests
from requests.auth import HTTPBasicAuth
from telegram import InlineKeyboardButton
import base64
import Storage
import DeviceActor
from collections import OrderedDict
from operator import itemgetter
from time import time
import hashlib
import dateutil.parser
import pytz

from Storage import DbList
from chat_strategy import welcome, inline

from pprint import pprint

from telegram import InlineKeyboardMarkup

from apiai.text import TextRequest

import calendar
from datetime import datetime, timedelta

from dateutil import parser

loud = u'\U0001F50A'
not_so_loud = u'\U0001F509'

thumb_up = u'\U0001F44D'
thumb_down = u'\U0001F44E'

skip = u'\U000023E9'

downloading = u'\U00002B07'
queued = u'\U0000261D'
playing = u'\U0001F3B6'
stopped = u'\U00002B1B'
play = u'\U000025B6'
promoted = u'\U00002B06'
poo = u'\U0001F4A9'
crown = u'\U0001F451'

votes_to_skip = 2


class ChatActor(pykka.ThreadingActor):
    def __init__(self, chat_id, manager, bot, context):
        super(ChatActor, self).__init__()
        self.chat_id = chat_id
        self.manager = manager
        self.context = context
        self.dialog_context = context
        self.db = context.storage
        self.bot = bot
        self.token = os.getenv('token')
        self.secret = os.getenv('secret')
        self.mqtt_user = os.getenv("mqtt_user")
        self.mqtt_pass = os.getenv("mqtt_pass")
        # self.devices = set()
        # self.devices_tokens = set()
        # self.latest_tracks = OrderedDict()
        # self.users = dict()
        # self.storage = None
        self.devices = None
        self.devices_tokens = None
        self.latest_tracks = None
        self.current_orig_message_id = None
        self.users = None
        self.current_playing_ids = dict()
        self.skip_gifs = ["CgADBAADqWkAAtkcZAc7PiBvHsR8IwI", "CgADBAADrgMAAuMYZAcKVOFNREMINDER_STORAGEoEE_xgI",
                          "CgADBAADJkAAAnobZAftbqSTl-HsIQI", "CgADBAADLBkAAuIaZAej8zwqpX3GeAI"]
        self.promote_gifs = ["CgADBAADWSMAAjUeZAeEqT810zl7IgI", "CgADBAADUEkAAhEXZAfN5P28QjO3KQI",
                             "CgADBAADpAMAAvkcZAfm332885NH7AI", "CgADBAADyQMAAsUZZAe4b-POmx-A8AI"]

        self.strategies = [welcome]

        self.users_stat = None  # type: DbList
        self.events_stat = None  # type: DbList

    def on_start(self):
        self.latest_tracks = self.db.ask(
            {'command': 'get_list', 'name': Storage.TRACK_TABLE, 'suffix': self.chat_id})
        self.devices_tokens = self.db.ask(
            {'command': 'get_list', 'name': Storage.CHAT_DEVICES_TABLE, 'suffix': self.chat_id})

        self.users_stat = self.context.storage.ask(
            {'command': 'get_list', 'name': Storage.USER_STAT_TABLE, "type": "stat"})

        self.events_stat = self.context.storage.ask(
            {'command': 'get_list', 'name': Storage.EVENTS_STAT_TABLE, "type": "stat"})

        self.devices = set()

        self.users = self.db.ask({'command': 'get_list', 'name': Storage.USER_TABLE, 'suffix': self.chat_id})

        for t in self.devices_tokens.get():
            self.devices.add((t, self.manager.ask({'command': 'get_device', 'token': t})))

    def on_message(self, message):
        user_id = message.from_user.id if message.from_user else 0

        if message.text:
            text = message.text  # type: str

            if message.chat.type != 'private' and text.startswith('/crown'):
                self.bot.tell(
                    {'command': 'send', 'chat_id': message.chat_id,
                     'message': 'You can get crown instead of poo, just hit this button',
                     'reply_markup': InlineKeyboardMarkup(
                         [[InlineKeyboardButton('Get a crown!', url='t.me/uproarbot?start=crown')]]),

                     })
                return

            if text.startswith('/web'):
                self.send_url(message)

            if text.startswith('/token'):

                if not message.from_user.username:
                    self.bot.tell(
                        {'command': 'send', 'chat_id': message.chat_id,
                         'message': 'Please, setup username first'})
                    return

                random_str = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

                ok, r0, r1, r2, r3, token_set = self.issue_token(message.from_user.username, random_str)
                if ok:
                    token_message = self.bot.ask(
                        {'command': 'send', 'chat_id': message.chat_id,
                         'message': loud + ' ' + message.from_user.username + '\'s device: ' + random_str})

                    self.bot.tell({'command': 'send', 'chat_id': message.chat_id, 'message': token_set + '\n\nMessage '
                                                                                                         'above is your device '
                                                                                                         'holder, forward it to '
                                                                                                         'chat to subscribe'})
                else:
                    print(str(r0.status_code) + " " + r0.text)
                    print(str(r1.status_code) + " " + r1.text)
                    print(str(r2.status_code) + " " + r2.text)
                    print(str(r3.status_code) + " " + r3.text)
                    self.bot.tell(
                        {'command': 'send', 'chat_id': message.chat_id,
                         'message': "sorry, can't create token, try again later"})

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

            elif re.match("^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$", text):
                resp = urllib.urlopen(text)
                if resp.getcode() / 100 == 2:
                    page = resp.read()
                    regex = re.compile('<title>(.*?)</title>', re.IGNORECASE | re.DOTALL)
                    title = regex.search(page).group(1)
                    reply = self.reply_to_content(message, title)
                    status = YoutubeVidStatus(message.message_id, reply.message_id, message.chat_id, title, text,
                                              user_id, time(), self.get_chat_title(
                            message.from_user.to_dict() if message.from_user else None))
                    data = status.data
                    data['url'] = text

                    self.latest_tracks.put(message.message_id, status)

                    for device in self.devices:
                        device_ref = self.enshure_device_ref(device)
                        device_ref.tell({'command': 'add_youtube_link', 'youtube_link': data})


        if message.audio or message.voice:
            durl = None

            if message.audio:
                file_id = message.audio.file_id
            elif message.voice:
                file_id = message.voice.file_id
            else:
                return

            durl = self.get_d_url(file_id)

            if durl is None:
                return

            if message.audio:
                title = ' - '.join(filter(None, (message.audio.performer, message.audio.title)))
                title = playing if not title else title
                title = title.encode("utf-8")
            elif message.voice:
                title = message.from_user.first_name + " - voice"
            else:
                title = "some_audio"

            reply = self.reply_to_content(message, title)

            status = TrackStatus(message.message_id, reply.message_id, message.chat_id, title, file_id,
                                 user_id, time(),
                                 self.get_chat_title(message.from_user.to_dict() if message.from_user else None))
            data = status.data
            data['track_url'] = durl
            self.latest_tracks.put(message.message_id, status)

            for device in self.devices:
                device_ref = self.enshure_device_ref(device)
                device_ref.tell({'command': 'add_track', 'track': data})



        for s in self.strategies:
            s.on_message(self, message, self.events_stat)

    def send_url(self, message):
        chat_id = str(message.chat_id).replace('-', '')
        token = ("p-" if message.chat.type == 'private' else "c-" if message.chat.type == "channel" else "g-") + chat_id
        token_message = self.bot.ask(
            {'command': 'send', 'chat_id': message.chat_id,
             'message': 'https://kor-ka.github.io/uproar_client_web?token=' + token})
        placeholder = self.bot.ask({'command': 'send',
                                    'chat_id': message.chat_id,
                                    'message': "link added"
                                    })
        self.actor_ref.tell(
            {
                'command': 'add_device',
                'device': self.get_device(token),
                'token': token,
                'placeholder': placeholder,
            })

    def issue_token(self, username, random_str):
        token_set = username + '-' + random_str + '-' + str(
            hashlib.sha256(random_str + self.secret).hexdigest())
        device_mqtt_user = username + '-' + random_str
        pattern_prefix = ""
        r0 = requests.post("https://api.cloudmqtt.com/user",
                           data='{"username":"%s", "password":"%s"}' % (device_mqtt_user, token_set),
                           auth=HTTPBasicAuth(self.mqtt_user, self.mqtt_pass),
                           headers={"Content-Type": "application/json"})
        r1 = requests.post("https://api.cloudmqtt.com/acl",
                           data='{"type":"pattern","username":"%s",  "pattern":"%s", "read":false, "write":true}' % (
                               device_mqtt_user, pattern_prefix + "device_out"),
                           auth=HTTPBasicAuth(self.mqtt_user, self.mqtt_pass),
                           headers={"Content-Type": "application/json"})
        r2 = requests.post("https://api.cloudmqtt.com/acl",
                           data='{"type":"pattern","username":"%s", "pattern":"%s", "read":true, "write":false}' % (
                               device_mqtt_user, pattern_prefix + "device_in_" + token_set),
                           auth=HTTPBasicAuth(self.mqtt_user, self.mqtt_pass),
                           headers={"Content-Type": "application/json"})
        r3 = requests.post("https://api.cloudmqtt.com/acl",
                           data='{ "type":"pattern", "username":"%s","pattern":"%s", "read":false, "write":true}' % (
                               device_mqtt_user, pattern_prefix + "registry"),
                           auth=HTTPBasicAuth(self.mqtt_user, self.mqtt_pass),
                           headers={"Content-Type": "application/json"})
        ok = r0.status_code / 100 == 2 and r1.status_code / 100 == 2 and r2.status_code / 100 == 2 and r3.status_code / 100 == 2
        return ok, r0, r1, r2, r3, token_set

    def utc_to_local(self, utc_dt):
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        return local_dt.replace(microsecond=utc_dt.microsecond)

    def reply_to_content(self, message, title):
        # check web device
        chat_id = str(message.chat_id).replace('-', '')
        token = ("p-" if message.chat.type == 'private' else "c-" if message.chat.type == "channel" else "g-") + chat_id
        if not token in [device[0] for device in self.devices]:
            self.actor_ref.tell(
                {
                    'command': 'add_device',
                    'device': self.get_device(token),
                    'token': token,
                })

        if message.from_user:
            self.users_stat.put_stat({"id": message.from_user.id})
        self.events_stat.put_stat({"type": "reply_to_content", "chat_id":self.chat_id, "user": str( message.from_user.id if message.from_user else -1)})

        row = [InlineKeyboardButton(thumb_up + " 0", callback_data='like:1:' + str(message.message_id)),
               InlineKeyboardButton(thumb_down + " 0", callback_data='like:0:' + str(message.message_id)), ]

        row.append(InlineKeyboardButton("Play " + play, url=self.get_web_link(message.message_id, message=message)))

        keyboard = [
            row,
        ]

        title = title.decode("utf-8")
        reply = self.bot.ask(
            {'command': 'reply', 'base': message,
             'message': title, 'reply_markup': InlineKeyboardMarkup(keyboard)})

        return reply

    def get_web_link(self, message_id, message=None, token=None):
        if not token:
            chat_id = str(message.chat_id).replace('-', '')
            token = (
                        "p-" if message.chat.type == 'private' else "c-" if message.chat.type == "channel" else "g-") + chat_id

        return 'https://kor-ka.github.io/uproar_client_web?token=' + token + "&silent=true&start_with=" + str(
            message_id)

    def enshure_device_ref(self, device):
        device_ref = device[1]
        if device_ref is None or not device_ref.is_alive():
            device_ref = self.manager.ask({'command': 'get_device', 'token': device[0]})
            # TODO update device_ref in touple somehow
            # device[1] = device_ref
        return device_ref

    def get_d_url(self, file_id):
        durl = None
        try:
            url = 'https://api.telegram.org/bot' + self.token + '/getFile?file_id=' + file_id
            track_info_raw = urllib.urlopen(
                url)
            load = json.load(track_info_raw.fp)
            result = load.get('result')
            print(url)
            print(json.dumps(load))

            if result is not None:
                file_path = result.get('file_path')
                durl = 'http://uproar.ddns.net/proxy/' + urllib.quote(file_path.encode('utf-8'))
        except Exception as e:
            print (e)
        return durl

    def get_chat(self, chat_id):
        res = None
        try:
            url = 'https://api.telegram.org/bot' + self.token + '/getChat?chat_id=' + str(chat_id)
            track_info_raw = urllib.urlopen(
                url)
            res = json.load(track_info_raw.fp)["result"]

        except Exception as e:
            logging.exception(e)
        return res

    def get_token(self, text, user):
        last_str = string.split(text, '\n')[-1].replace(loud, '').replace(' ', '')
        token = string.split(last_str, '\'')[0] + '-' + last_str[-5:] + '-' + str(
            hashlib.sha256(last_str[-5:] + self.secret).hexdigest())
        return token

    def get_device(self, token):
        return self.manager.ask({'command': 'get_device', 'token': token})

    def on_callback_query(self, callback_query):
        callback = string.split(callback_query.data, ":")
        if 0 == len(callback):
            return

        if callback_query.from_user:
            self.users_stat.put_stat({"id": callback_query.from_user.id})

        answer = True
        text = None
        show_alert = False

        message = callback_query.message

        orig_with_track_msg = message.reply_to_message

        message_id = 0

        try:
            message_id = callback[-1]
        except:
            pass

        try:
            self.events_stat.put_stat({"type": callback[0], "chat_id": self.chat_id,
                                  "user": str(callback_query.from_user.id if callback_query.from_user else -1)})
        except:
            pass

        if callback[0] == 'vol':
            dev = DeviceData(self.get_token(message.text, callback_query.from_user))
            if dev.owner == callback_query.from_user.username:
                self.get_device(dev.token).tell({'command': 'vol', 'param': callback[1]})
            else:
                text = 'Ooops, looks like it\'s not yours'
        elif callback[0] == 'like':

            for likes_data in self.latest_tracks.get(key=message_id):

                user_id = callback_query.from_user.id
                user_nick = callback_query.from_user.username
                modifier = 1
                if user_nick and user_nick == "kor_ka":
                    modifier = 2
                if callback[1] == "1":
                    from_user_id = orig_with_track_msg.from_user.id if orig_with_track_msg.from_user else 0

                    liked_tracks = self.context.storage.ask(
                        {'command': 'get_list', 'name': Storage.LIKED_TRACKS_TABLE, "type": "stat",
                         "suffix": from_user_id})

                    if user_id in likes_data.likes_owners:
                        likes_data.likes -= 1 * modifier
                        likes_data.likes_owners.remove(user_id)
                        user_likes = (orig_with_track_msg.from_user, 0)
                        for user_likes_raw in self.users.get(from_user_id):
                            user_likes = (user_likes_raw[0], user_likes_raw[1] - 1)
                        self.users.put(from_user_id, user_likes)
                        text = "you took your like back"
                        if orig_with_track_msg.audio:
                            liked_tracks.remove(orig_with_track_msg.id)

                    elif user_id in likes_data.dislikes_owners:
                        text = "take your dislike back first"
                    else:
                        try:
                            if user_id == likes_data.owner:
                                emoji = poo

                                if user_nick and (user_nick == "asiazaytseva" or user_nick == "gossiks"):
                                    emoji = crown

                                if self.manager.ask({"command": "get_user", "user_id": user_id}).ask(
                                        {"command": "crown_active"}):
                                    emoji = crown

                                self.bot.tell(
                                    {'command': 'send', 'chat_id': self.chat_id,
                                     'message': '%s SELFLIKE by %s' % (emoji, callback_query.from_user.first_name)})

                        except Exception as e:
                            print  "selflike: %s" % str(e)
                        likes_data.likes += 1 * modifier
                        likes_data.likes_owners.add(user_id)
                        text = "+1 track saved and available from inline mode"
                        user_likes = (orig_with_track_msg.from_user, 0)
                        for user_likes_raw in self.users.get(from_user_id):
                            user_likes = (user_likes_raw[0], user_likes_raw[1] + 1)
                        self.users.put(from_user_id, user_likes)
                        if orig_with_track_msg.audio:
                            liked_tracks.put(orig_with_track_msg.id, orig_with_track_msg.audio.to_dict())

                elif callback[1] == "0":
                    if user_id in likes_data.dislikes_owners:
                        likes_data.dislikes -= 1 * modifier
                        likes_data.dislikes_owners.remove(user_id)
                        text = "you took your dislike back"
                    elif user_id in likes_data.likes_owners:
                        text = "take your like back first"
                    else:
                        likes_data.dislikes += 1 * modifier
                        likes_data.dislikes_owners.add(user_id)
                        text = "-1"

                self.latest_tracks.put(message_id, likes_data)

                keyboard = self.get_keyboard(likes_data, message_id, message=message)

                self.bot.tell({'command': 'edit_reply_markup', 'base': callback_query,
                               'reply_markup': InlineKeyboardMarkup(keyboard)})

        elif callback[0] == 'skip':
            for likes_data in self.latest_tracks.get(int(message_id)):
                text = "skipping %s" % likes_data.title
                for d in self.devices:
                    device_ref = self.enshure_device_ref(d)
                    device_ref.tell({'command': 'skip', 'orig': likes_data.original_msg_id})

                self.bot.tell({"command": "sendDoc", "chat_id": self.chat_id, "caption": "Skip by anon azazaz",
                               "reply_to": int(message_id), "file_id": random.choice(self.skip_gifs)})


        elif callback[0] == 'promote':
            for likes_data in self.latest_tracks.get(message_id):
                text = "promoting %s" % likes_data.title
                for d in self.devices:
                    device_ref = self.enshure_device_ref(d)
                    device_ref.tell({'command': 'promote', 'orig': likes_data.original_msg_id})
                self.bot.tell({"command": "sendDoc", "chat_id": self.chat_id,
                               "caption": "Promote by %s" % callback_query.from_user.first_name,
                               "reply_to": int(message_id), "file_id": random.choice(self.promote_gifs)})

        if answer:
            callback_query.answer(text=text, show_alert=show_alert)

    def get_keyboard(self, likes_data, orig_with_track_msg, message=None, token=None):
        option = None
        if likes_data.dislikes >= votes_to_skip and likes_data.dislikes > likes_data.likes:
            option = InlineKeyboardButton(skip, callback_data='skip:' + str(orig_with_track_msg))
        if likes_data.likes >= votes_to_skip and likes_data.likes > likes_data.dislikes:
            option = InlineKeyboardButton(promoted, callback_data='promote:' + str(orig_with_track_msg))
        if message and message.chat.type == "channel":
            option = None
        first_row = [InlineKeyboardButton(thumb_up + " " + str(likes_data.likes),
                                          callback_data='like:1:' + str(orig_with_track_msg)),
                     InlineKeyboardButton(thumb_down + " " + str(likes_data.dislikes),
                                          callback_data='like:0:' + str(orig_with_track_msg)),
                     InlineKeyboardButton("Play " + play,
                                          url=self.get_web_link(orig_with_track_msg, message=message, token=token))]
        if option is not None:
            first_row.append(option)
        keyboard = [first_row]
        return keyboard

    def on_device_update(self, update, token):

        track_keyboard = None

        org_msg = update.get('message')

        orig_with_track = update.get('orig')
        msg_with_btns = update.get('message_id')

        self.current_orig_message_id = update.get('orig')
        for track_status in self.latest_tracks.get(self.current_orig_message_id):
            message = update.get('title')

            track_status.device_status[update.get('device')] = org_msg

            for k, v in track_status.device_status.items():
                message += "\n" + v + ' : ' + k[-5:]

            update['message'] = message

            track_keyboard = self.get_keyboard(track_status, orig_with_track, token=token)

            self.bot.tell({'command': 'update', 'update': update, 'reply_markup': InlineKeyboardMarkup(track_keyboard)})
            self.latest_tracks.put(self.current_orig_message_id, track_status)

        if org_msg.startswith(u'\U0001F3B6') or org_msg.startswith(u'\U00002B1B'):

            callback_vol_plus = 'vol' + ':' + '1'
            callback_vol_minus = 'vol' + ':' + '0'

            holder_row = [InlineKeyboardButton(not_so_loud, callback_data=callback_vol_minus),
                          InlineKeyboardButton(loud, callback_data=callback_vol_plus)]

            option = None

            if update.get("boring", False):
                option = InlineKeyboardButton(skip, callback_data='skip:' + str(orig_with_track))

            if option:
                holder_row.append(option)

            keyboard = [
                holder_row
            ]

            # commented untill we cant get user from original message by id
            # if track_keyboard:
            #     for row in track_keyboard:
            #
            #         for btn in row:
            #             if btn.text.startswith(thumb_down):
            #                 btn.text = thumb_down
            #             elif btn.text.startswith(thumb_up):
            #                 btn.text = thumb_up
            #
            #
            #         keyboard.append(row)

            message = org_msg + " " + update.get('title')

            if update['placeholder'].chat.username:
                message += "\n" + "t.me/" + update['placeholder'].chat.username + '/' + str(msg_with_btns)

            message += '\n' + update.get('device_name')

            current_placeholder = update.get('placeholder')
            if current_placeholder:
                self.bot.tell({'command': 'edit', 'base': current_placeholder, 'message': message,
                               'reply_markup': InlineKeyboardMarkup(keyboard)})

    def on_device_online(self, token, device, additional_id, start_with):

        chat = self.get_chat(self.chat_id)
        title = self.get_chat_title(chat)

        context = {"title": title}

        photo = chat.get("photo")
        if photo:
            photo = self.get_d_url(photo["small_file_id"])
            context["photo"] = photo

        device.tell(
            {"command": "publish", "data": {"context": context}, "topic": "init", "additional_id": additional_id})

        latest_tracks = self.latest_tracks.get()
        for t in latest_tracks:
            try:
                if t.original_msg_id == start_with:
                    self.send_current(additional_id, device, t, token)
                    break
            except AttributeError:
                pass

        for t in latest_tracks:
            try:
                if t.original_msg_id != start_with and time() - t.time < 60 * 15:
                    self.send_current(additional_id, device, t, token)
            except AttributeError:
                pass

    def get_chat_title(self, chat):
        title = None
        if chat:
            title = chat.get("title") if chat.get("title") else chat.get("username") if chat.get("username") else (
            chat.get("first_name") + chat.get("last_name"))
        return title

    def send_current(self, additional_id, device, t, token):
        status = t.device_status.get(token.split('-')[1])
        if status is None or status.startswith(downloading) or status.startswith(
                queued) or status.startswith(promoted):
            if hasattr(t, "file_id"):
                t.data["track_url"] = self.get_d_url(t.file_id)
            device_message = None
            if isinstance(t, TrackStatus):
                device_message = {'command': 'add_track', 'track': t.data}
            elif isinstance(t, YoutubeVidStatus):
                device_message = {'command': 'add_youtube_link', 'youtube_link': t.data}
            if device_message:
                if additional_id:
                    device_message["additional_id"] = additional_id
                device.tell(device_message)

    def on_boring(self, token, device, additional_id, exclude):
        latest_tracks_list = self.latest_tracks.get()
        if len(latest_tracks_list) > 0:

            # old stuff
            t = random.choice(latest_tracks_list)
            status = t.device_status.get(token.split('-')[1])
            if status is None or not status.startswith(skip):
                t.data['boring'] = True
                if hasattr(t, "file_id"):
                    t.data["track_url"] = self.get_d_url(t.file_id)
                if isinstance(t, TrackStatus):
                    device.tell({'command': 'add_track', 'track': t.data, 'additional_id': additional_id})
                elif isinstance(t, YoutubeVidStatus):
                    device.tell({'command': 'add_youtube_link', 'youtube_link': t.data, 'additional_id': additional_id})

            # reach boring
            if exclude is None:
                return
            latest_tracks_list = sorted(latest_tracks_list,
                                        key=lambda track: (10000 + list(exclude).index(
                                            track.original_msg_id)) if track.original_msg_id in exclude else (
                                            random.randint(
                                                0, 1000) - track.likes * 100 + track.dislikes * 300))

            res = []
            for t in latest_tracks_list[:10]:
                t.data['boring'] = True
                content = None
                if isinstance(t, TrackStatus):
                    t.data["track_url"] = self.get_d_url(t.file_id)
                    content = {'audio': t.data}
                elif isinstance(t, YoutubeVidStatus):
                    content = {'youtube_link': t.data}
                res.append(content)
            device.tell({'command': 'publish', "data": {"boring_list": res}, "topic": "boring_list",
                         'additional_id': additional_id})

    def on_receive(self, message):
        try:
            print "Chat Actor msg " + str(message)
            if message.get('command') == 'message':
                self.on_message(message.get('message'))
            if message.get('command') == 'callback_query':
                self.on_callback_query(message.get('callback_query'))
            elif message.get('command') == 'add_device':
                self.devices.add((message.get('token'), message.get('device')))
                self.devices_tokens.put(message.get('token'), message.get('token'))
                message.get('device').tell(
                    {'command': 'move_to', 'chat': self.actor_ref, 'placeholder': message.get('placeholder')})
            elif message.get('command') == 'remove_device':
                to_remove = None
                for d in self.devices:
                    if d[0] == message.get('token'):
                        to_remove = d
                if to_remove:
                    self.devices.remove(to_remove)
                self.devices_tokens.remove(message.get('token'))
            elif message.get('command') == 'device_content_status':
                self.on_device_update(message.get('content_status'), message.get('token'))
            elif message.get('command') == 'device_online':
                self.on_device_online(message.get('token'), message.get('device'), message.get('additional_id'),
                                      message.get('start_with'))
            elif message.get('command') == 'device_message':
                msg = message.get("message")
                if msg["update"] == "boring":
                    self.on_boring(message.get("token"), message.get("device"), msg.get("additional_id"),
                                   msg.get("data").get("exclude"))
            elif message.get('command') == 'inline_query':
                inline.on_query(message.get("q"), self)
        except Exception as ex:
            logging.exception(ex)


class DeviceData(object):
    def __init__(self, token):
        super(DeviceData, self).__init__()
        self.token = token
        token_split = string.split(token, '-')
        self.owner = token_split[0]
        self.id = token_split[1]


class ContentStatus(object):
    def __init__(self, orig, msg_id, chat_id, title, owner, time, chat_title):
        super(ContentStatus, self).__init__()
        self.original_msg_id = orig
        self.likes = 0
        self.dislikes = 0
        self.likes_owners = set()
        self.dislikes_owners = set()
        self.device_status = OrderedDict()
        self.played_once = False
        self.title = title
        self.owner = owner
        self.time = time
        self.data = {"chat_id": chat_id, "message_id": msg_id,
                     "orig": orig, 'title': title, "owner": chat_title}
        self.chat_title = chat_title


class TrackStatus(ContentStatus):
    def __init__(self, orig, msg_id, chat_id, title, file_id, owner, time, chat_title):
        super(TrackStatus, self).__init__(orig, msg_id, chat_id, title, owner, time, chat_title)
        self.file_id = file_id


class YoutubeVidStatus(ContentStatus):
    def __init__(self, orig, msg_id, chat_id, title, link, owner, time, chat_title):
        super(YoutubeVidStatus, self).__init__(orig, msg_id, chat_id, title, owner, time, chat_title)
        self.link = link
