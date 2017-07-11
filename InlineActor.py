import logging
import os
from time import sleep
import threading
from datetime import datetime

import pykka
from splinter import Browser


class InlineActor(pykka.ThreadingActor):
    def __init__(self, bot):
        super(InlineActor, self).__init__()
        self.bot = bot
        self.browser = None
        self.count = 0
        self.q_time = datetime.now()

    def on_start(self):
        try:
            # GOOGLE_CHROME_BIN
            suffix = ".apt/usr/bin/google-chrome-stable"
            chrome_path = os.getenv("GOOGLE_CHROME_SHIM", "")
            prefix = chrome_path[:-len(suffix)]
            os.environ['PATH'] = os.getenv("PATH", "")  + ":" + prefix + ".chromedriver/bin:" + chrome_path
            executable_path = {'executable_path': "/app/.chromedriver/bin/chromedriver"}

            #  executable_path = {'executable_path': '/tmp/build_3eb58544f5f97e761b0afd5314624668/kor-ka-uproar_server-bcbb420/.chromedriver/bin/chromedriver'}

            print executable_path
            
           #self.browser = Browser('chrome', **executable_path)
            self.browser = Browser('phantomjs')
            self.browser.driver.set_window_size(640, 480)

            self.browser.visit('http://m.vk.com')
            self.browser.fill("email", os.getenv("vk_login", ""))
            self.browser.fill("pass", os.getenv("vk_pass", ""))
            self.browser.find_by_value("Log in").first.click()
            self.browser.visit('http://m.vk.com/audio')
        except Exception as ex:
            logging.exception(ex)

    def on_receive(self, message):
        try:
            print "Inline Actor msg" + str(message)
            if message.get('command') == 'q':
                self.on_query(message.get('q'))
                # if message.get('time') is None:
                #     self.q_debounce(message.get('q'))
                # elif self.q_time == message.get('time'):
                #     self.on_query(message.get('q'))

        except Exception as ex:
            logging.exception(ex)

    def q_debounce(self, query):
        delayed = PostDelayed()
        self.q_time = delayed.time
        delayed.post(self.actor_ref, {'time': delayed.time, 'q':query, 'command':'q'}, 800)

    def on_query(self, query):
        if len(query.query) > 0:
            res = []
            self.browser.visit('http://m.vk.com/audio?act=search&q=' + query.query)


            # self.browser.find_by_id('au_search_field').first.fill(query.query)

            # driver = self.browser.driver
            # wait = WebDriverWait(driver, 10)
            # wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '.al_loading .qs_loading')))

            # print self.browser.html.encode('ascii', 'xmlcharrefreplace')
            for body in self.browser.find_by_css(".ai_body"):

                try:

                    inpt = body.find_by_tag('input').first
                    label = body.find_by_css('.ai_label')

                    r = AudioResult(inpt.value, label.text)

                    res.append(r)

                except Exception as ex:
                    logging.exception(ex)

            self.bot.tell({"command": "inline_res", "res": res, "q": query})


class AudioResult(object):
    def __init__(self, url, title):
        self.url = url
        self.title = title

class PostDelayed(threading.Thread):
    def __init__(self):
        self.running = True
        threading.Thread.__init__(self)
        self.time = datetime.now()
        super(PostDelayed, self).__init__()

    def run(self):
        while self.running:
            pass

    def post(self, ref, message, delay):
        sleep(delay)
        ref.tell(message)
        self.running = False
