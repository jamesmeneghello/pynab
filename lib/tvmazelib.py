#All credit to https://github.com/srob650/pytvmaze as this was only modified to support python3
import urllib.request
import json
from datetime import datetime

class Show():
  def __init__(self, data):
    self.data = data
    self.__dict__.update(data)
    self.maze_id = self.data.get('id')
    self.episodes = self.get_episode_list()

  def get_episode_list(self):
    eps = []
    episodes = self.data.get('_embedded').get('episodes')
    for episode in episodes:
      eps.append(Episode(episode))
    return eps

  def get_episode(self, season_number, episode_number):
    for episode in self.episodes:
      if episode.season_number == season_number and episode.episode_number == episode_number:
        return episode

class Episode():
  def __init__(self, data):
    self.data = data
    self.title = self.data.get('name')
    self.airdate = self.data.get('airdate')
    self.url = self.data.get('url')
    self.season_number = self.data.get('season')
    self.episode_number = self.data.get('number')
    self.image = self.data.get('image')
    self.airstamp = self.data.get('airstamp')
    self.runtime = self.data.get('runtime')
    self.maze_id = self.data.get('id')

# Query TV Maze endpoints
def query(url):

  url = url.replace(' ', '+')

  try:
    with urllib.request.urlopen(url) as response:
      data = response.read()
  except:
    print('Show not found')
    return None

  try:
    results = json.loads(data)
  except:
    results = json.loads(data.decode('utf8'))

  if results:
    return results
  else:
    return None

# Create Show object
def get_show(show):
  return Show(show_single_search(show, embed='episodes'))

# TV Maze Endpoints
def show_search(show):
  url = 'http://api.tvmaze.com/search/shows?q={0}'.format(show)
  return query(url)

def show_single_search(show, embed=False):
  if embed:
    url = 'http://api.tvmaze.com/singlesearch/shows?q={0}&embed={1}'.format(show, embed)
  else:
    url = 'http://api.tvmaze.com/singlesearch/shows?q={0}'.format(show)
  return query(url)

def lookup_tvrage(tvrage_id):
  url = 'http://api.tvmaze.com/lookup/shows?tvrage={0}'.format(tvrage_id)
  return query(url)

def lookup_tvdb(tvdb_id):
  url = 'http://api.tvmaze.com/lookup/shows?thetvdb={0}'.format(tvdb_id)
  return query(url)

def get_schedule(country='US', date=str(datetime.today().date())):
  url = 'http://api.tvmaze.com/schedule?country={0}&date={1}'.format(country, date)
  return query(url)

# ALL known future episodes
# Several MB large, cached for 24 hours
def get_full_schedule():
  url = 'http://api.tvmaze.com/schedule/full'
  return query(url)

def show_main_info(maze_id, embed=False):
  if embed:
    url = 'http://api.tvmaze.com/shows/{0}?embed={1}'.format(maze_id, embed)
  else:
    url = 'http://api.tvmaze.com/shows/{0}'.format(maze_id)
  return query(url)

def episode_list(maze_id, specials=False):
  if specials:
    url = 'http://api.tvmaze.com/shows/{0}/episodes?specials=1'.format(maze_id)
  else:
    url = 'http://api.tvmaze.com/shows/{0}/episodes'.format(maze_id)
  return query(url)

def episode_by_number(maze_id, season_number, episode_number):
  url = 'http://api.tvmaze.com/shows/{0}/episodebynumber?season={1}&number={2}'.format(maze_id,
                                                                    season_number, episode_number)
  return query(url)

def episodes_by_date(maze_id, airdate):
  url = 'http://api.tvmaze.com/shows/1/episodesbydate?date={0}'.format(airdate)
  return query(url)

def show_cast(maze_id):
  url = 'http://api.tvmaze.com/shows/{0}/cast'.format(maze_id)
  return query(url)

def show_index(page=1):
  url = 'http://api.tvmaze.com/shows?page={0}'.format(page)
  return query(url)

def people_search(person):
  url = 'http://api.tvmaze.com/search/people?q={0}'.format(person)
  return query(url)

def person_main_info(person_id, embed=False):
  if embed:
    url = 'http://api.tvmaze.com/people/{0}?embed={1}'.format(person_id, embed)
  else:
    url = 'http://api.tvmaze.com/people/{0}'.format(person_id)
  return query(url)

def person_cast_credits(person_id, embed=False):
  if embed:
    url = 'http://api.tvmaze.com/people/{0}/castcredits?embed={1}'.format(person_id, embed)
  else:
    url = 'http://api.tvmaze.com/people/{0}/castcredits'.format(person_id)
  return query(url)

def person_crew_credits(person_id, embed=False):
  if embed:
    url = 'http://api.tvmaze.com/people/{0}/crewcredits?embed={1}'.format(person_id, embed)
  else:
    url = 'http://api.tvmaze.com/people/{0}/crewcredits'.format(person_id)
  return query(url)

def show_updates():
  url = 'http://api.tvmaze.com/updates/shows'
  return query(url)
