import os
import traceback
import sqlite3

DB_VERSION = 1

class CueSheetDAO(object):
    instance = None

    def __init__(self, db_path):
        CueSheetDAO.instance = self
        self.db_path = "%s_v%d.db"%(os.path.splitext(db_path)[0],DB_VERSION)
        db_is_new = not os.path.exists(self.db_path)
        print '[CueSheetDAO] init', self.db_path
        if db_is_new:
            print '[CueSheetDAO] creating schema'
            self.create_schema()
        else:
            print '[CueSheetDAO] database exists, assume schema does, too.'

    def create_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            schema = """
                create table cuesheet (
                    id               integer primary key autoincrement not null,
                    path         text unique
                );

                create table mark (
                    id                            integer primary key autoincrement not null,
                    time                       integer,
                    type                       integer,
                    cuesheet_id         integer not null references cuesheet(id),
                    UNIQUE (time, cuesheet_id) ON CONFLICT IGNORE
                );
            """
            conn.executescript(schema)

    def clean_db(self):
        try:
            os.remove(self.db_path)
        except OSError as e:
            print '[CueSheetDAO] error when cleaning db', str(e)
            return False
        else:
            self.create_schema()
            return True

    def get_cut_list(self, path):
        print '[CueSheetDAO] getCutList for %s' % path.encode('utf-8')
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cutlist = []
            cursor = conn.cursor()
            query = """
                select time, type
                from mark
                    inner join cuesheet
                    on mark.cuesheet_id = cuesheet.id
                where cuesheet.path = ?
                """
            cursor.execute(query, (path,))
            for row in cursor.fetchall():
                cutlist.append((row['time'], row['type']))
            if len(cutlist) > 0:
                print '[CueSheetDAO] getCutList - succesfull'
            return cutlist

    def set_cut_list(self, path, cutlist):
        print '[CueSheetDAO] setCutList for %s' % path.encode('utf-8')
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("insert or ignore into cuesheet (path) values (?)", (path,))
                query = """
                    delete from mark
                    where cuesheet_id in
                        (select id from cuesheet where path = ?)
                    """
                cursor.execute(query, (path,))
                cuesheet_id = cursor.execute("select id from cuesheet where path = ?", (path,)).fetchone()[0]
                cursor.executemany("insert into mark (time, type, cuesheet_id) values (?,?,?)", ((time, type, cuesheet_id) for time, type in cutlist))
            except Exception:
                traceback.print_exc()
                conn.rollback()
            else:
                print '[CueSheetDAO] setCutList for %s was succesfull' % path.encode('utf-8')
                conn.commit()
