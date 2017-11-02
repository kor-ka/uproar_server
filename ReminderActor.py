import logging
import uuid

import datetime
import time
from threading import Thread

import pykka as pykka

import Storage
from Storage import StorageProvider


class ReminderActor(pykka.ThreadingActor):
    def __init__(self, manager):
        super(ReminderActor, self).__init__()
        self.manager = manager

        self.db = StorageProvider().get_storage()
        self.storage = None

    def on_start(self):
        self.storage = self.db.ask(
            {'command': 'get_list', 'name': Storage.REMINDER_STORAGE, 'suffix': ""})
        self.check_delayed()

    def on_receive(self, message):
        try:
            print "ReminderActorr msg " + str(message)

            if message["command"] == "reminder":
                self.storage.put(uuid.uuid4(), message)
            elif message["command"] == "check":
                for r in self.storage.get():
                    date_saved = r["date"]
                    now = datetime.datetime.now()
                    print (str(date_saved) + " vs " + str(now))
                    if date_saved <= now:
                        self.manager.bot.ask(
                            {'command': 'send', 'chat_id': message["chat_id"],
                             'message': message["text"]})
                self.check_delayed()
        except Exception as ex:
            logging.exception(ex)

    def check_delayed(self, delay=10):
        def delayed():
            time.sleep(delay)
            self.actor_ref.tell({"command": "check"})

        thread = Thread(target=delayed)
        thread.start()
