import logging
import os
from time import sleep
import threading
from datetime import datetime

import pykka
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.phantomjs import webdriver
from splinter import Browser
import urllib
from rx.concurrency.threadpoolscheduler import ThreadPoolScheduler
from rx.subjects import Subject
import time


def mark_debounced(m):
    m.update({'debounced': True})
    return m


class InlineActor(pykka.ThreadingActor):
    def __init__(self, bot):
        super(InlineActor, self).__init__()
        self.bot = bot
        self.browser = None
        self.current_q = None
        self.q_debounce_s = Subject()
        self.scheduler = ThreadPoolScheduler()

    def on_start(self):
        try:

            searcher = self.q_debounce_s.debounce(
                0.750,  # Pause for 750ms
                scheduler=self.scheduler
            ).map(mark_debounced).map(self.actor_ref.tell)
            searcher.subscribe()

            # GOOGLE_CHROME_BIN
            suffix = ".apt/usr/bin/google-chrome-stable"
            chrome_path = os.getenv("GOOGLE_CHROME_SHIM", "")
            prefix = chrome_path[:-len(suffix)]
            os.environ['PATH'] = os.getenv("PATH", "") + ":" + prefix + ".chromedriver/bin:" + chrome_path

            # chrome_options = Options()
            # chrome_options.binary_location = "/app/.apt/usr/bin/google-chrome-stable"
            #
            # driver_options = {'executable_path': "/app/.chromedriver/bin/chromedriver", 'options': chrome_options}

            #  executable_path = {'executable_path': '/tmp/build_3eb58544f5f97e761b0afd5314624668/kor-ka-uproar_server-bcbb420/.chromedriver/bin/chromedriver'}

            cap = webdriver.DesiredCapabilities.PHANTOMJS
            cap["phantomjs.page.settings.loadImages"] = True

            cap["phantomjs.page.settings.resourceTimeout"] = 0
            cap["phantomjs.page.settings.webSecurityEnabled"] = False
            cap["phantomjs.page.settings.clearMemoryCaches"] = True
            driver_options = {'desired_capabilities': cap}

            self.browser = Browser('phantomjs', **driver_options)
            # self.browser = Browser('chrome', **driver_options)
            self.browser.driver.set_window_size(640, 480)

            self.browser.visit('http://m.vk.com')
            self.browser.fill("email", os.getenv("vk_login", ""))
            self.browser.fill("pass", os.getenv("vk_pass", ""))
            self.browser.find_by_value("Log in").first.click()

            # dont know is it working
            cap["phantomjs.page.settings.javascriptEnabled"] = False

            self.browser.visit('http://m.vk.com/audio?act=search&q=mozart')
        except Exception as ex:
            logging.exception(ex)


    def on_receive(self, message):
        try:
            print "Inline Actor msg" + str(message)
            if message.get('command') == 'q':
                if message.get('debounced', False):
                    self.on_query(message.get('q'))
                else:
                    self.q_debounce_s.on_next(message)

        except Exception as ex:
            logging.exception(ex)

    def on_query(self, query):
        self.browser.windows[0].close_others()
        if len(query.query) >= 3:
            res = []

            quote = urllib.quote(query.query.encode('utf-8'))
            print ('start search: ' + query.query.encode('utf-8'))
            self.browser.visit('http://m.vk.com/audio?act=search&q=' + quote + "&offset=" + (
                0 if query.offset is None else query.offset))

            print("parsing...")

            for body in self.browser.find_by_css(".ai_body"):
                try:

                    inpt = body.find_by_tag('input').first

                    label = body.find_by_css('.ai_title')

                    artist = body.find_by_css('.ai_artist')

                    d = None
                    try:
                        duration = body.find_by_css('.ai_dur')
                        d = int(duration['data-dur'])
                    except:
                        pass
                    # print (label.text.encode('utf-8') + " - " + artist.text.encode('utf-8'))

                    r = AudioResult(inpt.value, label.text, artist.text, d)

                    res.append(r)

                except Exception as ex:
                    logging.exception(ex)

            self.bot.tell({"command": "inline_res", "res": res, "q": query})


class AudioResult(object):
    def __init__(self, url, title, artist, duration):
        self.url = url
        self.title = title
        self.artist = artist
        self.duration = duration
