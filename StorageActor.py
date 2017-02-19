import os
import psycopg2
import urlparse
import pykka
import pickle

USER_TABLE = 'user_table'
TRACK_TABLE = 'track_table'
CHAT_DEVICES_TABLE = 'chat_devices_table'


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

        key = message.get('key')
        if message.get('command') == "get":
            vals = []
            try:
                cur = self.db.cursor()

                limit = message.get("limit")

                where = '' if key is None else ("WHERE key = '%s'" % key)
                if limit is None:
                    cur.execute("SELECT val from %(table)s %(where)s", {'table': message.get("table"), 'where': where})

                else:
                    cur.execute('''SELECT *
                                    FROM (SELECT val FROM %(table)s ORDER BY id DESC LIMIT %(limit)s)
                                    %(where)s
                                    ORDER BY id ASC;''',
                                {'table': message.get("table"), 'limit': limit, 'where': where})

                vals = cur.fetchall()
                for k, v in vals:
                    vals[k] = pickle.loads(v[0])
                cur.close()
            except Exception as ex:
                print ex

            return vals

        elif message.get('command') == "put":
            try:
                cur = self.db.cursor()

                cur.execute('''INSERT INTO %(table)s (key, val)
                    VALUES (%(key)s, %(val)s)
                    ON CONFLICT (key) DO UPDATE
                      SET key = excluded.key,
                          val = excluded.val;''', {
                    'table': message.get('table'), 'key': key, 'val': pickle.dumps(message.get('val'))})
                cur.close()
                return True
            except Exception as ex:
                print ex
                return False

        elif message.get('command') == "remove":
            try:
                cur = self.db.cursor()

                cur.execute('''DELETE FROM %(table)s
                                WHERE key = %(key)s;''', {'table':message.get('table'), 'key':key})
                cur.close()
                return True
            except Exception as ex:
                print ex
                return False

        elif message.get('command') == "get_list":
            cur = self.db.cursor()
            table = "%s_%s" % (message.get('name'), message.get('suffix'))
            cur.execute('''CREATE TABLE IF NOT EXISTS %(table)s (id SERIAL PRIMARY KEY, val varchar, key varchar);''', {'table':table})
            cur.execute('''CREATE OR REPLACE FUNCTION trf_keep_row_number_steady()
                            RETURNS TRIGGER AS
                            $body$
                            BEGIN
                                -- delete only where are too many rows
                                IF (SELECT count(id) FROM %(table)s) > %(limit)s
                                THEN
                                    -- I assume here that id is an auto-incremented value in log_table
                                    DELETE FROM %(table)s
                                    WHERE id = (SELECT min(id) FROM %(table)s);
                                END IF;
                            END;
                            $body$
                            LANGUAGE plpgsql;

                            CREATE TRIGGER tr_keep_row_number_steady
                            AFTER INSERT ON %(table)s
                            FOR EACH ROW EXECUTE PROCEDURE trf_keep_row_number_steady();''',
                        {'table':table, 'limit':100})
            cur.close()
            return DbList(message.get('name'), message.get('suffix'), self.actor_ref)


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
