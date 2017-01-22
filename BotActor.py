import logging
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


class BotActor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(BotActor, self).__init__()
        self.manager = manager
        self.token = os.getenv('BOTTOKEN', '')
        self.update_id = None
        self.bot = None
        self.main()

    def main(self):
        # Telegram Bot Authorization Token
        bot = telegram.Bot(self.token)
        self.bot = bot

        # get the first pending update_id, this is so we can skip over it in case
        # we get an "Unauthorized" exception.
        try:
            update_id = bot.getUpdates()[0].update_id
        except IndexError:
            update_id = None

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.actor_ref.tell({'command': 'loop'})

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

    def update(self, update):
        self.bot.editMessageText(update.get("message"), chat_id=update.get("chat_id"),
                                 message_id=update.get("message_id"))

    def reply(self, base_message, message):
        return base_message.reply_text(message)

    def edit(self, base_message, message):
        return base_message.edit_text(message)

    def send(self, message, chat_id):
        return self.bot.sendMessage(chat_id=chat_id, text=message)

    def on_receive(self, message):
        if message.get('command') == 'loop':
            self.loop()
        elif message.get('command') == 'update':
            self.update(message.get('update'))
        elif message.get('command') == 'reply':
            return self.reply(message.get('base'), message.get('message'))
        elif message.get('command') == 'edit':
            return self.edit(message.get('base'), message.get('message'))
        elif message.get('command') == 'send':
            return self.send(message.get('message'), message.get('chat_id'))
