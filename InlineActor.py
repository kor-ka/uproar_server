import logging
import os
from time import sleep
import threading
from datetime import datetime

import pykka
from selenium.webdriver.chrome.options import Options
from splinter import Browser
import urllib


class InlineActor(pykka.ThreadingActor):
    def __init__(self, bot):
        super(InlineActor, self).__init__()
        self.bot = bot
        self.browser = None

        self.current_q = None

    def on_start(self):
        try:
            # GOOGLE_CHROME_BIN
            suffix = ".apt/usr/bin/google-chrome-stable"
            chrome_path = os.getenv("GOOGLE_CHROME_SHIM", "")
            prefix = chrome_path[:-len(suffix)]
            os.environ['PATH'] = os.getenv("PATH", "") + ":" + prefix + ".chromedriver/bin:" + chrome_path

            chrome_options = Options()
            chrome_options.binary_location = "/app/.apt/usr/bin/google-chrome-stable"

            driver_options = {'executable_path': "/app/.chromedriver/bin/chromedriver", 'options': chrome_options}

            #  executable_path = {'executable_path': '/tmp/build_3eb58544f5f97e761b0afd5314624668/kor-ka-uproar_server-bcbb420/.chromedriver/bin/chromedriver'}

            print driver_options

            self.browser = Browser('phantomjs')
            # self.browser = Browser('chrome', **driver_options)
            self.browser.driver.set_window_size(640, 480)

            self.browser.visit('http://m.vk.com')
            self.browser.fill("email", os.getenv("vk_login", ""))
            self.browser.fill("pass", os.getenv("vk_pass", ""))
            self.browser.find_by_value("Log in").first.click()
            self.browser.visit('http://m.vk.com/audio?act=search&q=mozart')
        except Exception as ex:
            logging.exception(ex)

    def on_receive(self, message):
        try:
            print "Inline Actor msg" + str(message)
            if message.get('command') == 'q':
                self.on_query(message.get('q'))

        except Exception as ex:
            logging.exception(ex)

    def on_query(self, query):
        if len(query.query) >= 3:
            res = []

            quote = urllib.quote(query.query.encode('utf-8'))
            print ('start search: ' + query.query.encode('utf-8'))
            self.browser.visit('http://m.vk.com/audio?act=search&q=' + quote + "&offset=" + (0 if query.offset is None else query.offset))

            limit = 0

            for body in self.browser.find_by_css(".ai_body"):
                if limit == 5:
                    break
                try:

                    inpt = body.find_by_tag('input').first
                    label = body.find_by_css('.ai_title')
                    artist = body.find_by_css('.ai_artist')

                    print (label.text.encode('utf-8') + " - " + artist.text.encode('utf-8'))

                    r = AudioResult(inpt.value, label.text, artist.text)

                    res.append(r)
                    limit += 1

                except Exception as ex:
                    logging.exception(ex)

            self.bot.tell({"command": "inline_res", "res": res, "q": query})


class AudioResult(object):
    def __init__(self, url, title, artist):
        self.url = url
        self.title = title
        self.artist = artist
