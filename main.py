#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Simple Bot to reply to Telegram messages. This is built on the API wrapper, see
# echobot2.py to see the same example built on the telegram.ext bot framework.
# This program is dedicated to the public domain under the CC0 license.
import logging
import telegram
from telegram.error import NetworkError, Unauthorized
from time import sleep
import paho.mqtt.client as mqtt
import urllib
import json

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


lastmessage = None


def echo(bot):
    global lastmessage
    global update_id
    # Request updates after the last update_id
    for update in bot.getUpdates(offset=update_id, timeout=10):
        # chat_id is required to reply to any message
        chat_id = update.message.chat_id
        update_id = update.update_id + 1

        if update.message:
            lastmessage = update.message
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


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    if (msg.topic == 'server_test'):
        print(str(msg.payload))
        if (lastmessage is not None):
            print('have last message, forvard to to chat')
            lastmessage.reply_text(str(msg.payload))


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