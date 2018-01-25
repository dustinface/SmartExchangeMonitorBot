#!/usr/bin/env python3

import logging
from src import util
import threading
import sqlite3 as sql

logger = logging.getLogger("database")

class BotDatabase(object):

    def __init__(self, dburi):

        self.connection = util.ThreadedSQLite(dburi)

        if self.isEmpty():
            self.reset()

    def isEmpty(self):

        tables = []

        with self.connection as db:

            db.cursor.execute("SELECT name FROM sqlite_master")

            tables = db.cursor.fetchall()

        return len(tables) == 0

    def addChat(self, chatId):

        chat = self.getChat(chatId)

        if chat == None:

            with self.connection as db:

                logger.debug("addChat: New chat {}".format(chatId))

                db.cursor.execute("INSERT INTO chats( id ) values( ? )", [chatId])
                chat = db.cursor.lastrowid
        else:

            chat = chat['id']

        return chat

    def getChats(self):

        chats = []

        with self.connection as db:

            db.cursor.execute("SELECT * FROM chats")

            chats = db.cursor.fetchall()

        return chats

    def getChat(self, chatId):

        chat = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM chats WHERE id=?",[chatId])

            chat = db.cursor.fetchone()

        return chat

    def updateChat(self, oldId, newId):

        with self.connection as db:

            db.cursor.execute("UPDATE chats SET id=? WHERE id=?",(newId,oldId))

    def deleteChat(self, chatId):

        with self.connection as db:

            db.cursor.execute("DELETE FROM chats WHERE id=?",[chatId])

    def reset(self):

        sql = 'BEGIN TRANSACTION;\
        CREATE TABLE "chats" (\
        	`id`	INTEGER NOT NULL PRIMARY KEY\
        );\
        COMMIT;'

        with self.connection as db:
            db.cursor.executescript(sql)
