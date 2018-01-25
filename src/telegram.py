#!/usr/bin/env python3

import logging
import telegram
import json
import time

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.ext import CommandHandler,MessageHandler,Filters
from telegram.ext import Updater

from requests_futures.sessions import FuturesSession

from src import util

logger = logging.getLogger("bot")

HITBTC = 1
CRYPTOPIA = 2
COINEXCHANGE = 3

class Request(object):

    def __init__(self,exchange, future, cb):
        self.exchange = exchange
        self.future = future
        self.future.add_done_callback(self.futureCB)
        self.result = None
        self.cb = cb
        self.data = None
        self.status = -1

    def futureCB(self, future):
        self.result = self.future.result()
        self.status = self.result.status_code

        try:
            self.data = self.result.json()
        except:
            self.data = {}

        self.cb(self)

class SmartExchangeMonitor(object):

    def __init__(self, botToken, db):

        # Create a bot instance for async messaging
        self.bot = telegram.Bot(token=botToken)
        # Create the updater instance for configuration
        self.updater = Updater(token=botToken)
        # Set the database of the pools/users/nodes
        self.database = db
        # Sesstion for exchange requests
        self.session = FuturesSession(max_workers=20)
        # Timer for exchange updates
        self.timer = util.RepeatingTimer(60, self.poll)
        self.timer.start()

        self.hitbtc = {'deposit':False, 'withdraw':False, 'updated': 0 }
        self.cryptopia = {'status': 'Maintenance', 'updated': 0 }
        self.coinexchange = {'wallet':'offline', 'updated': 0 }

        self.poll()

        # Get the dispather to add the needed handlers
        dp = self.updater.dispatcher

        #### Setup node related handler ####
        dp.add_handler(CommandHandler('start', self.subscribe))
        dp.add_handler(CommandHandler('status', self.status))

        dp.add_handler(MessageHandler(Filters.command, self.unknown))
        dp.add_error_handler(self.error)

    ######
    # Starts the bot and block until the programm will be stopped.
    ######
    def start(self):

        self.updater.start_polling()
        self.updater.idle()

    def poll(self):

        self.updateCryptopia()
        self.updateHitBTC()
        self.updateCoinexchangeIO()

    def sendMessage(self, chatId, text):

        logger.info("sendMessage - Chat: {}, Text: {}".format(chatId,text))

        try:
            self.bot.sendMessage(chat_id=chatId, text = text,parse_mode=telegram.ParseMode.MARKDOWN )
        except Unauthorized:
            logger.warning("Exception: Unauthorized")
            self.database.deleteChat(chatId)
        except TimedOut:
            logger.warning("Exception: TimedOut")
        except NetworkError:
            logger.warning("Exception: NetworkError")
        except ChatMigrated as e:
            logger.warning("Exception: ChatMigrated from {} to {}".format(chatId, e.new_chat_id))
            self.database.updateChat(chatId,e.new_chat_id)
        except BadRequest:
            logger.warning("Exception: BadRequest")
        except NetworkError:
            logger.warning("Exception: NetworkError")
        else:
            logger.debug("sendMessage - OK!")


    def updateCoinexchangeIO(self):

        requestUrl = "https://www.coinexchange.io/api/v1/getcurrency?ticker_code=SMART"

        Request(COINEXCHANGE, self.session.get(requestUrl), self.updatedExchange)

    def updateCryptopia(self):

        requestUrl = "https://www.cryptopia.co.nz/api/GetCurrencies"
        Request(CRYPTOPIA, self.session.get(requestUrl), self.updatedExchange)


    def updateHitBTC(self):

        requestUrl = "https://api.hitbtc.com/api/2/public/currency/SMART"
        Request(HITBTC, self.session.get(requestUrl), self.updatedExchange)

    def updatedExchange(self, request):

        data = request.data

        notify = None

        if request.status != 200:
            logger.warning("Request failed {}, {}".format(request.exchange,data))
            return

        if request.exchange == CRYPTOPIA:
            logger.info("Updated cryptopia")

            status = "Unknown"

            if 'Success' in data and data['Success'] and 'Data' in data:

                for entry in data['Data']:
                    if 'Id' in entry and entry['Id'] == 582:
                        status = entry['Status']

                if self.cryptopia['status'] != status:
                    logger.info("Cryptopia notify {}".format(status))
                    notify = CRYPTOPIA

                self.cryptopia['status'] = status
                self.cryptopia['updated'] = time.time()

        elif request.exchange == HITBTC:
            logger.info("Updated hitbtc")

            if 'id' in data and data['id'] == 'SMART':

                deposit = data['payinEnabled']
                withdraw = data['payoutEnabled']

                if self.hitbtc['deposit'] != deposit:
                    notify = HITBTC

                if self.hitbtc['withdraw'] != withdraw:
                    notify = HITBTC

                self.hitbtc['deposit'] = deposit
                self.hitbtc['withdraw'] = withdraw
                self.hitbtc['updated'] = time.time()

        elif request.exchange == COINEXCHANGE:
            logger.info("Updated coinexchange")

            if 'success' in data and data['success'] == '1' and\
                'result' in data:

                wallet = data['result']['WalletStatus']

                if self.coinexchange['wallet'] != wallet:
                    notify = COINEXCHANGE

                self.coinexchange['wallet'] = wallet
                self.coinexchange['updated'] = time.time()
                
        else:
            logger.warning("unknown exchange")

        if notify:
            self.notify(notify)

    def status(self, bot, update):

        response = "*Cryptopia*\n"
        response += "Last updated {}\n".format(util.secondsToText(int(time.time() - self.cryptopia['updated'])))
        response += "*Deposit* `{}`\n\n".format(self.cryptopia['status'])

        response += "*HitBTC*\n"
        response += "Last updated {}\n".format(util.secondsToText(int(time.time() - self.hitbtc['updated'])))
        response += "*Deposit* `{}`\n".format(self.hitbtc['deposit'])
        response += "*Withdraw* `{}`\n\n".format(self.hitbtc['withdraw'])

        response += "*Coinexchange*\n"
        response += "Last updated {}\n".format(util.secondsToText(int(time.time() - self.coinexchange['updated'])))
        response += "*Wallet* `{}`\n".format(self.coinexchange['wallet'])

        self.sendMessage(update.message.chat_id, response)

    def subscribe(self, bot, update):

        response = "*Welcome. You are on the notification list now!*\n\n"
        response += "If any of the 3 currently closed exchanges re-open their SMART wallets"
        response += " you will receive a notification about it! Stay patient...and HODL your SMART! :D\n\n"
        response += "Beer? `STsDhYJZZrVFCaA5FX2AYWP27noYo3RUjD`\n\n"
        response += "*Greetz - dustinface*"

        self.database.addChat(update.message.chat_id)

        self.sendMessage(update.message.chat_id, response)

    def unknown(self, bot, update):
        self.sendMessage(update.message.chat_id, "What?")

    def error(self, bot, update, error):
        logger.error('Update "%s" caused error "%s"' % (update, error))

    def notify(self, exchange):

        logger.info("notify {}".format(exchange))

        response = "*Wallet update*\n\n"

        if exchange == CRYPTOPIA:
            response += "*Cryptopia*\n"
            response += "*Status* `{}`\n\n".format(self.cryptopia['status'])

        if exchange == HITBTC:
            response += "*HitBTC*\n"
            response += "*Deposit* `{}`\n".format(self.hitbtc['deposit'])
            response += "*Withdraw* `{}`\n\n".format(self.hitbtc['withdraw'])
        if exchange == COINEXCHANGE:
            response += "*Coinexchange*\n"
            response += "*Wallet* `{}`\n".format(self.coinexchange['wallet'])

        for user in self.database.getChats():
            self.sendMessage(user['id'], response)
