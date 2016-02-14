from contextlib import contextmanager
import datetime
import json
import copy
import time
import tempfile
import os
import hashlib

import psycopg2
from sqlalchemy import Column, Integer, BigInteger, LargeBinary, Text, String, Boolean, DateTime, ForeignKey, \
    create_engine, UniqueConstraint, Enum, Index, func, and_, exc, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker, scoped_session
from sqlalchemy.pool import Pool

import config
from pynab import log


def sqlalchemy_url():
    conn_string = '{engine}://{user}:{pass}@{host}'.format(**config.db)
    if 'port' in config.db and config.db.get('port'):
        conn_string += ':{}'.format(config.db.get('port'))

    conn_string += '/{}'.format(config.db.get('db'))

    if 'unix_socket' in config.db and config.db.get('unix_socket'):
        conn_string += '?unix_socket={}'.format(config.db.get('unix_socket'))

    return conn_string


def copy_file(engine, data, ordering, type):
    """
    Handles a fast-copy, or a slowass one.

    If you're using postgres or a mysql derivative, this should work fine.
    Anything else? Welllllllllllllp. It's gonna be slow. Really slow.

    In fact, I'm going to point out just how slow it is.
    """
    insert_start = time.time()
    if 'mysql' in config.db.get('engine'):
        # ho ho ho
        conn = engine.raw_connection()
        cur = conn.cursor()
        (fd, filename) = tempfile.mkstemp(prefix='pynab')
        filename = filename.replace('\\', '/')
        try:
            file = os.fdopen(fd, 'wb')
            data.seek(0)
            t = data.read(1048576)
            while t:
                file.write(t.encode('utf-8'))
                t = data.read(1048576)
            file.close()
            data.close()

            query = "LOAD DATA LOCAL INFILE '{}' INTO TABLE {} FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' ({})" \
                .format(filename, type.__tablename__, ','.join(ordering))

            cur.execute((query))
            conn.commit()
            cur.close()

            os.remove(filename)
        except Exception as e:
            log.error(e)
            return False
    elif 'postgre' in config.db.get('engine'):
        conn = engine.raw_connection()
        cur = conn.cursor()
        try:
            cur.copy_expert(
                "COPY {} ({}) FROM STDIN WITH CSV ESCAPE E'\\\\'".format(type.__tablename__, ', '.join(ordering)), data)
        except Exception as e:
            log.error(e)
            return False
        conn.commit()
        cur.close()
    else:
        # this... this is the slow one
        # i don't even want to think about how slow this is
        # it's really slow
        # slower than the github api
        engine.execute(type.__table__.insert(), data)

    insert_end = time.time()
    log.debug('parts: {} insert: {:.2f}s'.format(config.db.get('engine'), insert_end - insert_start))

    return True

def truncate_table(engine, table_type):
    """
    Handles truncate table for given table type.
    """
    query = ''
    if 'mysql' in config.db.get('engine'):
        query = "TRUNCATE {}".format(table_type.__tablename__)
    elif 'postgre' in config.db.get('engine'):
        # RESTART IDENTITY - reset sequences
        # CASCADE - follow FK references
        query = 'TRUNCATE {} RESTART IDENTITY CASCADE'.format(table_type.__tablename__)

    try:
        conn = engine.raw_connection()
        cur = conn.cursor()
        cur.execute((query))
        conn.commit()
        cur.close()
    except Exception as e:
        log.error(e)
        return False

    return True

def vacuum(mode='scan', full=False):
    conn = engine.connect()
    if 'postgre' in config.db.get('engine'):
        conn.connection.connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        if mode == 'scan':
            if full:
                conn.execute('VACUUM FULL ANALYZE binaries')
                conn.execute('VACUUM FULL ANALYZE parts')
                conn.execute('VACUUM FULL ANALYZE segments')
            else:
                conn.execute('VACUUM ANALYZE binaries')
                conn.execute('VACUUM ANALYZE parts')
                conn.execute('VACUUM ANALYZE segments')
        else:
            if full:
                conn.execute('VACUUM FULL ANALYZE releases')
                conn.execute('VACUUM FULL ANALYZE metablack')
                conn.execute('VACUUM FULL ANALYZE episodes')
                conn.execute('VACUUM FULL ANALYZE tvshows')
                conn.execute('VACUUM FULL ANALYZE movies')
                conn.execute('VACUUM FULL ANALYZE nfos')
                conn.execute('VACUUM FULL ANALYZE sfvs')
                conn.execute('VACUUM FULL ANALYZE files')
            else:
                conn.execute('VACUUM ANALYZE releases')
                conn.execute('VACUUM ANALYZE metablack')
                conn.execute('VACUUM ANALYZE episodes')
                conn.execute('VACUUM ANALYZE tvshows')
                conn.execute('VACUUM ANALYZE movies')
                conn.execute('VACUUM ANALYZE nfos')
                conn.execute('VACUUM ANALYZE sfvs')
                conn.execute('VACUUM ANALYZE files')

    elif 'mysql' in config.db.get('engine'):
        log.info('db: not optimising or analysing innodb tables, do it yourself.')
        pass

    conn.close()


connect_args = {}
if 'mysql' in config.db.get('engine'):
    connect_args = {'charset': 'utf8', 'local_infile': 1}

Base = declarative_base()
engine = create_engine(sqlalchemy_url(), pool_recycle=3600, connect_args=connect_args)
Session = scoped_session(sessionmaker(bind=engine))

# enable query debugging
# very noisy!
"""
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
from pynab import log


# --- debug info ---
class Queries:
    pass

_q = Queries()
_q.total = 0


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    log.debug("Start Query: %s" % statement)


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    _q.total += 1
    log.debug("Query Complete!")
    log.debug("Total Time: %f" % total)
    log.debug("Total Queries: %d" % _q.total)
# -------------------
"""

from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.sqltypes import String, DateTime, NullType

# python2/3 compatible.
PY3 = str is not bytes
text = str if PY3 else unicode
int_type = int if PY3 else (int, long)
str_type = str if PY3 else (str, unicode)


class StringLiteral(String):
    """Teach SA how to literalize various things."""
    def literal_processor(self, dialect):
        super_processor = super(StringLiteral, self).literal_processor(dialect)

        def process(value):
            if isinstance(value, int_type):
                return text(value)
            if not isinstance(value, str_type):
                value = text(value)
            result = super_processor(value)
            if isinstance(result, bytes):
                result = result.decode(dialect.encoding)
            return result
        return process


class LiteralDialect(DefaultDialect):
    colspecs = {
        # prevent various encoding explosions
        String: StringLiteral,
        # teach SA about how to literalize a datetime
        DateTime: StringLiteral,
        # don't format py2 long integers to NULL
        NullType: StringLiteral,
    }


def literalquery(statement):
    """NOTE: This is entirely insecure. DO NOT execute the resulting strings."""
    import sqlalchemy.orm
    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    return statement.compile(
        dialect=LiteralDialect(),
        compile_kwargs={'literal_binds': True},
    ).string

# handle mysql disconnections
@event.listens_for(Pool, "checkout")
def ping_connection(dbapi_connection, connection_record, connection_proxy):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1")
    except:
        # optional - dispose the whole pool
        # instead of invalidating one at a time
        # connection_proxy._pool.dispose()

        # raise DisconnectionError - pool will try
        # connecting again up to three times before raising.
        raise exc.DisconnectionError()
    cursor.close()


@contextmanager
def db_session():
    session = Session()

    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise


# thanks zzzeek! https://bitbucket.org/zzzeek/sqlalchemy/wiki/UsageRecipes/WindowedRangeQuery
def column_windows(session, column, windowsize):
    """Return a series of WHERE clauses against
    a given column that break it into windows.

    Result is an iterable of tuples, consisting of
    ((start, end), whereclause), where (start, end) are the ids.

    Requires a database that supports window functions,
    i.e. Postgresql, SQL Server, Oracle.

    Enhance this yourself !  Add a "where" argument
    so that windows of just a subset of rows can
    be computed.
    """

    def int_for_range(start_id, end_id):
        if end_id:
            return and_(
                column >= start_id,
                column < end_id
            )
        else:
            return column >= start_id

    q = session.query(
        column,
        func.row_number().
        over(order_by=column).
        label('rownum')
    ). \
        from_self(column)
    if windowsize > 1:
        q = q.filter("rownum %% %d=1" % windowsize)

    intervals = [id for id, in q]

    while intervals:
        start = intervals.pop(0)
        if intervals:
            end = intervals[0]
        else:
            end = None
        yield int_for_range(start, end)


def windowed_query(qry, pk, size):
    """
    Break a Query into windows on a given column.
    """

    if 'postgre' in config.db.get('engine'):
        for whereclause in column_windows(qry.session, pk, size):
            for row in qry.filter(whereclause).order_by(pk):
                yield row
    else:
        # mysql etc
        firstid = None
        while True:
            q = qry
            if firstid is not None:
                q = qry.filter(pk > firstid)
            rec = None
            for rec in q.order_by(pk).limit(size):
                yield rec
            if rec is None:
                break
            firstid = pk.__get__(rec, pk) if rec else None


def json_serial(obj):
    if isinstance(obj, datetime.datetime):
        serial = obj.isoformat()
        return serial


def to_json(obj):
    dict = copy.deepcopy(obj.__dict__)
    del dict['_sa_instance_state']
    obj = json.dumps(dict, default=json_serial)
    return obj

def _create_hash(name, group_id, posted):
    return hashlib.sha1('{}.{}.{}'.format(
        name,
        group_id,
        posted
    ).encode('utf-8')).hexdigest()

def create_hash(context):
    return _create_hash(
        context.current_parameters['name'],
        context.current_parameters['group_id'],
        context.current_parameters['posted']
    )

class Release(Base):
    __tablename__ = 'releases'

    id = Column(Integer, primary_key=True)
    uniqhash = Column(String(40), default=create_hash, unique=True)

    added = Column(DateTime, default=func.now())
    posted = Column(DateTime)

    name = Column(String(512))
    search_name = Column(String(512), index=True)
    original_name = Column(String(512))
    posted_by = Column(String(200))

    status = Column(Integer)
    grabs = Column(Integer, default=0)
    size = Column(BigInteger, default=0)

    passworded = Column(Enum('UNKNOWN', 'YES', 'NO', 'MAYBE', name='enum_passworded'), default='UNKNOWN')
    unwanted = Column(Boolean, default=False, index=True)

    group_id = Column(Integer, ForeignKey('groups.id'), index=True)
    group = relationship('Group', backref=backref('releases'))

    category_id = Column(Integer, ForeignKey('categories.id'), index=True)
    category = relationship('Category', backref=backref('releases'))

    regex_id = Column(Integer, ForeignKey('regexes.id', ondelete='SET NULL'), index=True)
    regex = relationship('Regex', backref=backref('releases'))

    tvshow_id = Column(Integer, ForeignKey('tvshows.id'), index=True)
    tvshow = relationship('TvShow', backref=backref('releases'))
    tvshow_metablack_id = Column(Integer, ForeignKey('metablack.id', ondelete='SET NULL'), index=True)
    tvshow_metablack = relationship('MetaBlack', foreign_keys=[tvshow_metablack_id])

    movie_id = Column(Integer, ForeignKey('movies.id'), index=True)
    movie = relationship('Movie', backref=backref('releases'))
    movie_metablack_id = Column(Integer, ForeignKey('metablack.id', ondelete='SET NULL'), index=True)
    movie_metablack = relationship('MetaBlack', foreign_keys=[movie_metablack_id])

    nzb_id = Column(Integer, ForeignKey('nzbs.id', ondelete='CASCADE'), index=True)
    nzb = relationship('NZB', backref=backref('release', uselist=False))

    files = relationship('File', passive_deletes=True, cascade='all, delete, delete-orphan', backref=backref('release'))
    rar_metablack_id = Column(Integer, ForeignKey('metablack.id', ondelete='SET NULL'), index=True)
    rar_metablack = relationship('MetaBlack', foreign_keys=[rar_metablack_id])

    nfo_id = Column(Integer, ForeignKey('nfos.id', ondelete='CASCADE'), index=True)
    nfo = relationship('NFO', backref=backref('release', uselist=False))
    nfo_metablack_id = Column(Integer, ForeignKey('metablack.id', ondelete='SET NULL'), index=True)
    nfo_metablack = relationship('MetaBlack', foreign_keys=[nfo_metablack_id])

    sfv_id = Column(Integer, ForeignKey('sfvs.id', ondelete='CASCADE'), index=True)
    sfv = relationship('SFV', backref=backref('release', uselist=False))
    sfv_metablack_id = Column(Integer, ForeignKey('metablack.id', ondelete='SET NULL'), index=True)
    sfv_metablack = relationship('MetaBlack', foreign_keys=[sfv_metablack_id])

    episode_id = Column(Integer, ForeignKey('episodes.id'), index=True)
    episode = relationship('Episode', backref=backref('releases'))

    pre_id = Column(Integer, ForeignKey('pres.id'), index=True)
    pre = relationship('Pre', backref=backref('pre'))

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class MetaBlack(Base):
    __tablename__ = 'metablack'

    id = Column(Integer, primary_key=True)

    status = Column(Enum('ATTEMPTED', 'IMPOSSIBLE', name='enum_metablack_status'), default='ATTEMPTED')
    time = Column(DateTime, default=func.now())

    tvshow = relationship('Release', cascade='all, delete, delete-orphan', uselist=False,
                          foreign_keys=[Release.tvshow_metablack_id])
    movie = relationship('Release', cascade='all, delete, delete-orphan', uselist=False,
                         foreign_keys=[Release.movie_metablack_id])
    nfo = relationship('Release', cascade='all, delete, delete-orphan', uselist=False,
                       foreign_keys=[Release.nfo_metablack_id])
    sfv = relationship('Release', cascade='all, delete, delete-orphan', uselist=False,
                       foreign_keys=[Release.sfv_metablack_id])
    rar = relationship('Release', cascade='all, delete, delete-orphan', uselist=False,
                       foreign_keys=[Release.rar_metablack_id])

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Episode(Base):
    __tablename__ = 'episodes'

    id = Column(Integer, primary_key=True)

    tvshow_id = Column(Integer, ForeignKey('tvshows.id'), index=True)
    tvshow = relationship('TvShow', backref=backref('episodes'))

    season = Column(String(10))
    episode = Column(String(20))
    series_full = Column(String(60))
    air_date = Column(String(16))
    year = Column(String(8))

    __table_args__ = (
        UniqueConstraint(tvshow_id, series_full),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)

    name = Column(String(512))
    size = Column(BigInteger)

    release_id = Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'), index=True)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)

    active = Column(Boolean, index=True)
    first = Column(BigInteger)
    last = Column(BigInteger)
    name = Column(String(200))

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Binary(Base):
    __tablename__ = 'binaries'

    id = Column(Integer, primary_key=True)
    hash = Column(BigInteger, index=True)

    name = Column(String(512), index=True)
    total_parts = Column(Integer)

    posted = Column(DateTime)
    posted_by = Column(String(200))

    xref = Column(String(1024))
    group_name = Column(String(200))

    regex_id = Column(Integer, ForeignKey('regexes.id', ondelete='SET NULL'), index=True)
    regex = relationship('Regex', backref=backref('binaries'))

    parts = relationship('Part', passive_deletes=True, order_by="asc(Part.subject)")

    def size(self):
        size = 0
        for part in self.parts:
            for segment in part.segments:
                size += segment.size

        return size

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )

# it's unlikely these will ever be used in sqlalchemy
# for performance reasons, but keep them to create tables etc
class Part(Base):
    __tablename__ = 'parts'

    id = Column(BigInteger, primary_key=True)
    hash = Column(BigInteger, index=True)

    subject = Column(String(512))
    total_segments = Column(Integer, index=True)

    posted = Column(DateTime, index=True)
    posted_by = Column(String(200))

    xref = Column(String(1024))
    group_name = Column(String(200), index=True)

    binary_id = Column(Integer, ForeignKey('binaries.id', ondelete='CASCADE'), index=True)

    segments = relationship('Segment', passive_deletes=True, order_by="asc(Segment.segment)")

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


# likewise
class Segment(Base):
    __tablename__ = 'segments'

    id = Column(BigInteger, primary_key=True)

    segment = Column(Integer, index=True)
    size = Column(Integer)
    message_id = Column(String(256))

    part_id = Column(BigInteger, ForeignKey('parts.id', ondelete='CASCADE'), index=True)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Miss(Base):
    __tablename__ = 'misses'

    id = Column(Integer, primary_key=True)
    group_name = Column(String(200), index=True)

    message = Column(BigInteger, index=True, nullable=False)

    attempts = Column(Integer)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Regex(Base):
    __tablename__ = 'regexes'

    id = Column(Integer, primary_key=True)
    regex = Column(Text)
    description = Column(String(256))
    status = Column(Boolean, default=True)
    ordinal = Column(Integer)

    # don't reference this, we don't need it
    # and it'd hammer performance, plus it's
    # sometimes regex
    group_name = Column(String(200))

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Blacklist(Base):
    __tablename__ = 'blacklists'

    id = Column(Integer, primary_key=True)

    description = Column(String(256))
    group_name = Column(String(200), index=True)
    field = Column(String(20), server_default='subject', nullable=False)
    regex = Column(Text)
    status = Column(Boolean, default=False)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(256))

    parent_id = Column(Integer, ForeignKey('categories.id'), index=True)
    parent = relationship('Category', remote_side=[id])
    children = relationship('Category')

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)

    api_key = Column(String(32), unique=True)
    email = Column(String(256), unique=True)
    grabs = Column(Integer)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class NZB(Base):
    __tablename__ = 'nzbs'

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary((2**32)-1))

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class NFO(Base):
    __tablename__ = 'nfos'

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class SFV(Base):
    __tablename__ = 'sfvs'

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class DataLog(Base):
    __tablename__ = 'datalogs'

    id = Column(Integer, primary_key=True)
    description = Column(String(256), index=True)
    data = Column(Text)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Pre(Base):
    __tablename__ = 'pres'

    id = Column(Integer, primary_key=True)

    pretime = Column(DateTime)
    name = Column(String(512), index=True)
    searchname = Column(String(512))
    category = Column(String(256))
    source = Column(String(256))
    requestid = Column(Integer, index=True)
    requestgroup = Column(String(500), index=True)
    filename = Column(String(512))
    nuked = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint(requestid, pretime, requestgroup),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )

# --------------------------------
# for dealing with tv/movie db ids
# --------------------------------

class DBID(Base):
    __tablename__ = 'dbids'

    id = Column(BigInteger, primary_key=True)
    db_id = Column(String(50))
    db = Column(Enum('TVRAGE', 'TVMAZE', 'OMDB', name='enum_dbid_name'))

    tvshow = relationship('TvShow', backref='ids')
    tvshow_id = Column(Integer, ForeignKey('tvshows.id'), index=True)

    movie = relationship('Movie', backref='ids')
    movie_id = Column(Integer, ForeignKey('movies.id'), index=True)

    __table_args__ = (
        (
            Index('idx_db_id_db', 'db_id', 'db')
        ),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class Movie(Base):
    __tablename__ = 'movies'

    id = Column(Integer, primary_key=True)
    name = Column(String(256), index=True)
    genre = Column(String(256))
    year = Column(Integer, index=True)

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


class TvShow(Base):
    __tablename__ = 'tvshows'

    id = Column(Integer, primary_key=True)
    name = Column(String(256), index=True)
    country = Column(String(5))

    __table_args__ = (
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'DYNAMIC'
        }
    )


