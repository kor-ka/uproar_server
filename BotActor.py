import logging
from pprint import pprint

import telegram
from telegram import Bot
from telegram import InlineKeyboardMarkup
from telegram.error import NetworkError, Unauthorized
from time import sleep
import paho.mqtt.client as mqtt
import pykka
import urllib
import json
import os
import ManagerActor
from telegram import InlineKeyboardButton, CallbackQuery

class UpdatesFetcher(pykka.ThreadingActor):
    def __init__(self, bot, manager):
        super(UpdatesFetcher, self).__init__()
        self.bot = bot
        self.update_id = None
        self.manager = manager
        try:
            self.update_id = self.bot.getUpdates()[0].update_id
        except IndexError:
            self.update_id = None

    def on_receive(self, message):
        if message.get('command') == 'loop':
            self.loop()

    def loop(self):
        try:
            self.apply(self.bot)
        except NetworkError:
            sleep(1)
        except Unauthorized:
            # The user has removed or blocked the bot.
            self.update_id += 1
        finally:
            self.actor_ref.tell({'command': 'loop'})

    def apply(self, bot):

        # Request updates after the last update_id
        for update in bot.getUpdates(offset=self.update_id, timeout=10):
            self.update_id = update.update_id + 1
            self.manager.tell({'command': 'update', 'update': update})
            pprint(vars(update.message))


class BotActor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(BotActor, self).__init__()
        self.manager = manager
        self.token = os.getenv('token')
        self.bot = None
        self.main()
        self.fetcher = None

    def main(self):
        # Telegram Bot Authorization Token
        bot = telegram.Bot(self.token)
        self.bot = bot
        self.fetcher = UpdatesFetcher.start(bot, self.manager)

        # get the first pending update_id, this is so we can skip over it in case
        # we get an "Unauthorized" exception.
        try:
            update_id = bot.getUpdates()[0].update_id
        except IndexError:
            update_id = None

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.fetcher.tell({'command': 'loop'})

    def update(self, update, reply_markup):
        self.bot.editMessageText(update.get("message"), chat_id=update.get("chat_id"),
                                 message_id=update.get("message_id"), reply_markup=reply_markup)

    def reply(self, base_message, message, reply_markup):
        return base_message.reply_text(message, reply_markup=reply_markup)

    def edit(self, base_message, message, reply_markup):
        return base_message.edit_text(message, reply_markup=reply_markup)

    def edit_reply_markup(self, query, reply_markup):
        return query.edit_message_reply_markup(reply_markup=reply_markup)

    def send(self, message, chat_id, reply_markup):
        return self.bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup)

    def on_receive(self, message):
        try:

            if message.get('command') == 'update':
                self.update(message.get('update'), message.get('reply_markup'))
            elif message.get('command') == 'reply':
                return self.reply(message.get('base'), message.get('message'), message.get('reply_markup'))
            elif message.get('command') == 'edit':
                return self.edit(message.get('base'), message.get('message'), message.get('reply_markup'))
            elif message.get('command') == 'edit_reply_markup':
                return self.edit_reply_markup(message.get('base'), message.get('reply_markup'))
            elif message.get('command') == 'send':
                return self.send(message.get('message'), message.get('chat_id'), message.get('reply_markup'))
        except Exception as ex:
            print ex
