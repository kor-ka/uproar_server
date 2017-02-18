import os
import psycopg2
import urlparse
import pykka
import pickle

USER_TABLE = 'user_table'
TRACK_TABLE = 'track_table'


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

        if message.get('command') == "get":
            val = None
            try:
                cur = self.db.cursor()

                limit = message.get("limit")
                if limit is None:
                    cur.execute("SELECT * val from %s1 WHERE key = '%s2'" % (message.get("table"), message.get('key')))

                else:
                    cur.execute('''SELECT *
                                    FROM (SELECT * FROM %s1 ORDER BY id DESC LIMIT %s3)
                                    WHERE key = %s2
                                    ORDER BY id ASC;'''
                                % (message.get("table"), message.get('key'), limit))

                vals = cur.fetchall()
                for k, v in vals:
                    vals[k] = pickle.loads(v)
                val = pickle.loads(vals)
                cur.close()
            except Exception as ex:
                print ex

            return val

        elif message.get('command') == "put":
            try:
                cur = self.db.cursor()

                cur.execute('''INSERT INTO %s1 (key, val)
                    VALUES (%s2, %s3)
                    ON CONFLICT (key) DO UPDATE
                      SET key = excluded.key,
                          val = excluded.val;''' % (
                    message.get('table'), message.get('key'), pickle.dumps(message.get('val')))
                            )
                cur.close()
                return True
            except Exception as ex:
                print ex
                return False

        elif message.get('command') == "get_list":
            cur = self.db.cursor()
            table = "%s1_%s2" % (message.get('name'), message.get('suffix'))
            cur.execute('''CREATE TABLE %s1 (id SERIAL PRIMARY KEY, val varchar);''' % table)
            cur.execute('''CREATE OR REPLACE FUNCTION trf_keep_row_number_steady()
                            RETURNS TRIGGER AS
                            $body$
                            BEGIN
                                -- delete only where are too many rows
                                IF (SELECT count(id) FROM %s1) > %s2
                                THEN
                                    -- I assume here that id is an auto-incremented value in log_table
                                    DELETE FROM %s3
                                    WHERE id = (SELECT min(id) FROM %s4);
                                END IF;
                            END;
                            $body$
                            LANGUAGE plpgsql;

                            CREATE TRIGGER tr_keep_row_number_steady
                            AFTER INSERT ON %s5
                            FOR EACH ROW EXECUTE PROCEDURE trf_keep_row_number_steady();''' % (table, 100, table, table, table))
            cur.close()
            return DbList(message.get('name'), message.get('suffix'), self.actor_ref)


class DbList(object):
    def __init__(self, name, suffix, storage_ref):
        super(DbList, self).__init__()
        self.name = name
        self.suffix = suffix
        self.storage_ref = storage_ref

    def get(self, key, limit=None):
        return self.storage_ref.ask({"command": "get", "table": "%s1_%s2" % (self.name, self.suffix), "key": key, "limit":limit})

    def put(self, key, val):
        return self.storage_ref.ask(
            {"command": "put", "table": "%s1_%s2" % (self.name, self.suffix), "key": key, "val": val})


class GetList(object):
    def __init__(self, name, suffix):
        super(GetList, self).__init__()
        self.message = {'command': 'get_list', 'name': name, 'suffix': suffix}
