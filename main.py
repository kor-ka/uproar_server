#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

if __name__ == '__main__':
    ManagerActor.ManagerActor.start()
    while True:
        sleep(100)