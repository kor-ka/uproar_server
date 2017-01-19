#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Simple Bot to reply to Telegram messages. This is built on the API wrapper, see
# echobot2.py to see the same example built on the telegram.ext bot framework.
# This program is dedicated to the public domain under the CC0 license.
import logging
import telegram
from telegram import Bot
from telegram import InlineKeyboardMarkup
from telegram.error import NetworkError, Unauthorized
from time import sleep
import paho.mqtt.client as mqtt
import urllib
import json
from telegram import InlineKeyboardButton, CallbackQuery

update_id = None

client = mqtt.Client()


def main():
    global update_id
    # Telegram Bot Authorization Token
    bot = telegram.Bot('304064430:AAGy50irNZ2tD1_jBO-8imca5_jhTHgI618')

    # get the first pending update_id, this is so we can skip over it in case
    # we get an "Unauthorized" exception.
    try:
        update_id = bot.getUpdates()[0].update_id
    except IndexError:
        update_id = None

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    while True:
        try:
            echo(bot)
        except NetworkError:
            sleep(1)
        except Unauthorized:
            # The user has removed or blocked the bot.
            update_id += 1


bott = None
last_chat_id = None

def echo(bot):
    global bott
    global last_chat_id
    global update_id

    bott = bot
    # Request updates after the last update_id
    for update in bot.getUpdates(offset=update_id, timeout=10):
        # chat_id is required to reply to any message
        update_id = update.update_id + 1

        if update.message:
            chat_id = update.message.chat_id
            last_chat_id = update.message.chat_id

            if update.message.audio:  # your bot can receive updates without messages
                track_info_raw = urllib.urlopen(
                    'https://api.telegram.org/bot304064430:AAGy50irNZ2tD1_jBO-8imca5_jhTHgI618/getFile?file_id=' + update.message.audio.file_id)
                load = json.load(track_info_raw.fp)
                result = load.get('result')
                if result is None:
                    return
                file_path = result.get('file_path')
                durl = 'https://api.telegram.org/file/bot304064430:AAGy50irNZ2tD1_jBO-8imca5_jhTHgI618/' + file_path
                client.publish("track_test", durl)
                update.message.reply_text("added!")

        if update.callback_query:
            if str(update.callback_query.data) == "volume_down":
                client.publish("volume_test", 0)
            elif str(update.callback_query.data) == "volume_up":
                client.publish("volume_test", 1)
            else:
                return
            bott.answer_callback_query(update.callback_query.id)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    if (msg.topic == 'server_test'):
        print(str(msg.payload))
        if (last_chat_id is not None):
            print('have last message, forvard to to chat')
            btn_down = InlineKeyboardButton('vol -', callback_data="volume_down")
            btn_up = InlineKeyboardButton('vol +', callback_data="volume_up")

            bott.send_message(last_chat_id, 'lets make some nooooise!',  reply_markup=InlineKeyboardMarkup(
                            [[btn_down, btn_up]]))


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("server_" + "test", 0)


def initMqtt():
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set('eksepjal', 'UyPdNESZw5yo')
    client.connect('m21.cloudmqtt.com', 18552)
    client.loop_start()


if __name__ == '__main__':
    initMqtt()
    main()