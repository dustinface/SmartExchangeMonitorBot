#!/usr/bin/env python3

import sys
import configparser
import logging
import json

from src import database
from src import telegram

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#                    level=logging.DEBUG)
                    level=logging.INFO)
#                    level=logging.WARNING)

def checkConfig(config,category, name):
    try:
        config.get(category,name)
    except configparser.NoSectionError as e:
        sys.exit("Config error {}".format(e))
    except configparser.NoOptionError as e:
        sys.exit("Config value error {}".format(e))

def main(argv):

    config = configparser.SafeConfigParser()

    try:
        config.read('smart.conf')
    except:
        sys.exit("Config file missing or corrupt.")

    checkConfig(config, 'bot','token')

    # Load the user database
    botdb = database.BotDatabase('bot.db')

    nodeBot = telegram.SmartExchangeMonitor(config.get('bot','token'), botdb)

    # Start and run forever!
    nodeBot.start()

if __name__ == '__main__':
    main(sys.argv[1:])
