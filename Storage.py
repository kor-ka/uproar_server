import os

import logging
from pprint import pprint

import psycopg2
import urlparse
import pykka
import pickle

USER_TABLE = 'users_table'
TRACK_TABLE = 'tracks_table'
CHAT_DEVICES_TABLE = 'chats_devices_table'
DEVICE_STORAGE = 'device_storage'


class StorageProvider(object):
    def __init__(self):
        super(StorageProvider, self).__init__()
        self.storage = None

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(StorageProvider, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def get_storage(self):
        if self.storage is None:
            self.storage = StorageActor.start()
        return self.storage


class StorageActor(pykka.ThreadingActor):
    def __init__(self):
        super(StorageActor, self).__init__()
        self.db = None

    def on_start(self):

        urlparse.uses_netloc.append("postgres")
        url = urlparse.urlparse(os.environ["DATABASE_URL"])

        self.db = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )

    def on_receive(self, message):
        try:
            print "Storage Actor msg " + str(message)
            key = message.get('key')
            if message.get('command') == "get":
                res = []
                cur = self.db.cursor()
                try:

                    limit = message.get("limit")

                    where = '' if key is None else ("WHERE key = '%s'" % key)
                    if limit is None:
                        cur.execute("SELECT val from %s %s" % (message.get("table"), where))

                    else:
                        cur.execute('''SELECT *
                                        FROM (SELECT val FROM %s ORDER BY id DESC LIMIT %s)
                                        %s
                                        ORDER BY id ASC;''' % (message.get("table"), limit, where))

                    vals = cur.fetchall()
                    for v in vals:
                        res.append(pickle.loads(str(v[0])))
                    cur.close()
                except Exception as ex:
                    print 'on get:' + str(ex)
                    self.db.rollback()
                cur.close()
                return res

            elif message.get('command') == "put":
                cur = self.db.cursor()
                try:

                    cur.execute('''INSERT INTO ${table} (key, val)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET
                            key = excluded.key,
                            val = excluded.val;'''.replace('${table}',
                                                           message.get('table')), (key, pickle.dumps(message.get('val')))
                                )
                    self.db.commit()
                    return True
                except Exception as ex:
                    print 'on put:' + str(ex)
                    self.db.rollback()
                    return False
                finally:
                    cur.close()

            elif message.get('command') == "remove":
                cur = self.db.cursor()
                try:

                    cur.execute('''DELETE FROM ${table}
                                    WHERE key = %s;'''.replace('${table}',
                                                               message.get('table')), (key))
                    self.db.commit()
                    return True
                except Exception as ex:
                    print 'on remove:' + str(ex)
                    self.db.rollback()
                    return False
                finally:
                    cur.close()

            elif message.get('command') == "get_list":
                cur = self.db.cursor()
                table = "%s_%s" % (message.get('name'), clean_suffix(message.get('suffix')))
                cur.execute('''CREATE TABLE IF NOT EXISTS %s (id SERIAL, val varchar, key varchar PRIMARY KEY);''' % table)
                self.db.commit()
                print table + " created"
                cur.close()
                return DbList(message.get('name'), message.get('suffix'), self.actor_ref)
        except Exception as ex:
            logging.exception(ex)


class DbList(object):
    def __init__(self, name, suffix, storage_ref):
        super(DbList, self).__init__()
        self.name = name
        self.suffix = clean_suffix(suffix)
        self.storage_ref = storage_ref

    def get(self, key=None, limit=None):
        return self.storage_ref.ask(
            {"command": "get", "table": "%s_%s" % (self.name, self.suffix), "key": key, "limit": limit})

    def remove(self, key):
        return self.storage_ref.ask({"command": "remove", "table": "%s_%s" % (self.name, self.suffix), "key": key})

    def put(self, key, val):
        return self.storage_ref.ask(
            {"command": "put", "table": "%s_%s" % (self.name, self.suffix), "key": key, "val": val})


def clean_suffix(suffix):
    return str(suffix).replace("-", "")
