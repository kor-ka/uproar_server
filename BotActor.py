import logging
from pprint import pprint

import sys
import telegram
from telegram import Bot
from telegram import InlineKeyboardMarkup
from telegram import InlineQueryResult
from telegram import InlineQueryResultAudio
from telegram.error import NetworkError, Unauthorized
from time import sleep
import paho.mqtt.client as mqtt
import pykka
import urllib
import logging
import json
import os

from telegram.ext import CallbackQueryHandler
from telegram.ext import Filters
from telegram.ext import InlineQueryHandler
from telegram.ext import MessageHandler
from telegram.ext import PreCheckoutQueryHandler
from telegram.ext import Updater

import ManagerActor
from telegram import InlineKeyboardButton, CallbackQuery


class BotActor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(BotActor, self).__init__()
        self.manager = manager
        self.token = os.getenv('token')
        self.bot = None

    def on_start(self):
        updater = Updater(self.token)
        self.bot = updater.bot

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        # on noncommand i.e message - echo the message on Telegram
        dp.add_handler(MessageHandler(Filters.all, self.post))
        dp.add_handler(CallbackQueryHandler(self.post))
        dp.add_handler(InlineQueryHandler(self.post))
        dp.add_handler(PreCheckoutQueryHandler(self.post))

        # Start the Bot
        updater.start_polling()

    def post(self, bot, update):
        self.manager.tell({'command': 'update', 'update': update})

    def update(self, update, reply_markup):
        self.bot.editMessageText(update.get("message"), chat_id=update.get("chat_id"),
                                 message_id=update.get("message_id"), reply_markup=reply_markup)

    def reply(self, base_message, message, reply_markup):
        return base_message.reply_text(message, reply_markup=reply_markup)

    def edit(self, base_message, message, reply_markup):
        return base_message.edit_text(message, reply_markup=reply_markup)

    def edit_reply_markup(self, query, reply_markup):
        return query.edit_message_reply_markup(reply_markup=reply_markup)

    def send(self, message, chat_id, reply_markup, disable_notification, parse_mode):
        return self.bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup, disable_notification = disable_notification, parse_mode=parse_mode)

    def sendDoc(self, caption, chat_id, file_id, reply_to):
        return self.bot.sendDocument(chat_id, file_id, caption=caption, reply_to_message_id=reply_to)

    def reply_inline(self, q, res):
        offset = 0
        try:
            offset = int(q.offset)
        except:
            pass

        return self.bot.answerInlineQuery(q.id, results=res,
                                          next_offset=(None if len(res) < 10 else len(res) + offset),
                                          cache_time=1)

    def on_receive(self, message):
        try:
            print "Bot Actor msg" + str(message)
            if message.get('command') == 'update':
                self.update(message.get('update'), message.get('reply_markup'))
            elif message.get('command') == 'reply':
                return self.reply(message.get('base'), message.get('message'), message.get('reply_markup'))
            elif message.get('command') == 'edit':
                return self.edit(message.get('base'), message.get('message'), message.get('reply_markup'))
            elif message.get('command') == 'edit_reply_markup':
                return self.edit_reply_markup(message.get('base'), message.get('reply_markup'))
            elif message.get('command') == 'send':
                return self.send(message.get('message'), message.get('chat_id'), message.get('reply_markup'), message.get('disable_notification', False), message.get('parse_mode'))
            elif message.get('command') == 'sendDoc':
                return self.sendDoc(message.get('caption'), message.get('chat_id'), message.get('file_id'), message.get("reply_to"))
            elif message.get('command') == 'inline_res':
                return self.reply_inline(message.get('q'), message.get('res'))
            elif message.get('command') == 'invoice':
                return self.bot.sendInvoice(**message["invoice_args"])
            elif message.get('command') == 'confirm_precheckout':
                return self.bot.answer_pre_checkout_query(message["id"], True)
            elif message.get('command') == 'delete':
                return self.bot.delete(message["message"])
        except Exception as ex:
            logging.exception(ex)
