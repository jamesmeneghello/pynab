from sqlalchemy import Column, Integer, BigInteger, LargeBinary, Text, String, Boolean, DateTime, ForeignKey, create_engine, func, UniqueConstraint, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker, scoped_session
from contextlib import contextmanager
import config


def sqlalchemy_url():
    return 'postgresql://{user}:{pass}@{host}:{port}/{db}'.format(**config.postgre)


Base = declarative_base()
engine = create_engine(sqlalchemy_url())
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


@contextmanager
def db_session():
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise


class Release(Base):
    __tablename__ = 'releases'

    id = Column(Integer, primary_key=True)

    added = Column(DateTime, default=func.now())
    posted = Column(DateTime)

    name = Column(String)
    search_name = Column(String)
    posted_by = Column(String)

    status = Column(Integer)
    grabs = Column(Integer, default=0)

    passworded = Column(Enum('UNKNOWN', 'YES', 'NO', 'MAYBE', name='enum_passworded'), default='UNKNOWN')
    unwanted = Column(Boolean, default=False)

    group_id = Column(Integer, ForeignKey('groups.id'))
    group = relationship('Group', backref=backref('releases'))

    category_id = Column(Integer, ForeignKey('categories.id'))
    category = relationship('Category', backref=backref('releases'))

    regex_id = Column(Integer, ForeignKey('regexes.id'))
    regex = relationship('Regex', backref=backref('releases'))

    tvshow_id = Column(Integer, ForeignKey('tvshows.id'))
    tvshow = relationship('TvShow', backref=backref('releases'))
    tvshow_metablack_id = Column(Integer, ForeignKey('metablack.id'))

    movie_id = Column(String, ForeignKey('movies.id'))
    movie = relationship('Movie', backref=backref('releases'))
    movie_metablack_id = Column(Integer, ForeignKey('metablack.id'))

    nzb_id = Column(Integer, ForeignKey('nzbs.id'))
    nzb = relationship('NZB', backref=backref('release', uselist=False))

    rar_metablack_id = Column(Integer, ForeignKey('metablack.id'))

    nfo_id = Column(Integer, ForeignKey('nfos.id'))
    nfo = relationship('NFO', backref=backref('release', uselist=False))
    nfo_metablack_id = Column(Integer, ForeignKey('metablack.id'))

    episode_id = Column(Integer, ForeignKey('episodes.id'))
    episode = relationship('Episode', backref=backref('releases'))

    __table_args__ = (UniqueConstraint(name, posted),)


class MetaBlack(Base):
    __tablename__ = 'metablack'

    id = Column(Integer, primary_key=True)

    status = Column(Enum('ATTEMPTED', 'IMPOSSIBLE', name='enum_metablack_status'), default='ATTEMPTED')
    time = Column(DateTime, default=func.now())

    tvshow = relationship('Release', cascade='all, delete-orphan', uselist=False, foreign_keys=[Release.tvshow_metablack_id])
    movie = relationship('Release', cascade='all, delete-orphan', uselist=False, foreign_keys=[Release.movie_metablack_id])
    nfo = relationship('Release', cascade='all, delete-orphan', uselist=False, foreign_keys=[Release.nfo_metablack_id])
    rar = relationship('Release', cascade='all, delete-orphan', uselist=False, foreign_keys=[Release.rar_metablack_id])


class Episode(Base):
    __tablename__ = 'episodes'

    id = Column(Integer, primary_key=True)

    tvshow_id = Column(Integer, ForeignKey('tvshows.id'))
    tvshow = relationship('TvShow', backref=backref('episodes'))

    season = Column(String(10))
    episode = Column(String(20))
    series_full = Column(String)
    air_date = Column(String(16))
    year = Column(String(8))

    __table_args__ = (UniqueConstraint(tvshow_id, series_full),)


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)

    name = Column(String)
    size = Column(BigInteger)

    release_id = Column(Integer, ForeignKey('releases.id'))
    release = relationship('Release', backref=backref('files'))


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)

    active = Column(Boolean)
    first = Column(BigInteger)
    last = Column(BigInteger)
    name = Column(String)


class Binary(Base):
    __tablename__ = 'binaries'

    id = Column(Integer, primary_key=True)

    name = Column(String, index=True)
    total_parts = Column(Integer)

    posted = Column(DateTime)
    posted_by = Column(String)

    xref = Column(String)
    group_name = Column(String)

    regex_id = Column(Integer, ForeignKey('regexes.id'))
    regex = relationship('Regex', backref=backref('binaries'))

    parts = relationship('Part', cascade='all, delete-orphan', passive_deletes=True, order_by="asc(Part.subject)")


# it's unlikely these will ever be used in sqlalchemy
# for performance reasons, but keep them to create tables etc
class Part(Base):
    __tablename__ = 'parts'

    id = Column(Integer, primary_key=True)

    subject = Column(String, index=True)
    total_segments = Column(Integer)

    posted = Column(DateTime)
    posted_by = Column(String)

    xref = Column(String)
    group_name = Column(String)

    binary_id = Column(Integer, ForeignKey('binaries.id', ondelete='CASCADE'))

    segments = relationship('Segment', cascade='all, delete-orphan', passive_deletes=True, order_by="asc(Segment.segment)")

    #__table_args__ = (UniqueConstraint(subject),)


# likewise
class Segment(Base):
    __tablename__ = 'segments'

    id = Column(Integer, primary_key=True)

    segment = Column(Integer)
    size = Column(Integer)
    message_id = Column(String)

    part_id = Column(Integer, ForeignKey('parts.id', ondelete='CASCADE'))

    #__table_args__ = (UniqueConstraint(part_id, segment),)


class Regex(Base):
    __tablename__ = 'regexes'

    id = Column(Integer, primary_key=True)
    regex = Column(Text)
    description = Column(String)
    status = Column(Boolean, default=True)
    ordinal = Column(Integer)

    # don't reference this, we don't need it
    # and it'd hammer performance, plus it's
    # sometimes regex
    group_name = Column(String)


class Blacklist(Base):
    __tablename__ = 'blacklists'

    id = Column(Integer, primary_key=True)

    description = Column(String)
    group_name = Column(String, index=True)
    regex = Column(Text, unique=True)
    status = Column(Boolean, default=False)


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    parent_id = Column(Integer, ForeignKey('categories.id'))
    parent = relationship('Category', remote_side=[id])
    children = relationship('Category')


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)

    api_key = Column(String(32), unique=True)
    email = Column(String, unique=True)
    grabs = Column(Integer)


class NZB(Base):
    __tablename__ = 'nzbs'

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary)


class NFO(Base):
    __tablename__ = 'nfos'

    id = Column(Integer, primary_key=True)
    data = Column(LargeBinary)


class Movie(Base):
    __tablename__ = 'movies'

    id = Column(String, primary_key=True)

    name = Column(String)
    genre = Column(String)
    year = Column(Integer)


class TvShow(Base):
    __tablename__ = 'tvshows'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    country = Column(String(5))