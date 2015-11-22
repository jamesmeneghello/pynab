import regex
import pickle
import os.path

from pynab import log, root_dir


CATEGORISER = pickle.load(open(os.path.join(root_dir, 'db/release_categoriser.pkl'), 'rb'))

# category codes
# these are stored in the db, as well
CAT_GAME_NDS = 1010
CAT_GAME_PSP = 1020
CAT_GAME_WII = 1030
CAT_GAME_XBOX = 1040
CAT_GAME_XBOX360 = 1050
CAT_GAME_WIIWARE = 1060
CAT_GAME_XBOX360DLC = 1070
CAT_GAME_PS3 = 1080
CAT_MOVIE_FOREIGN = 2010
CAT_MOVIE_OTHER = 2020
CAT_MOVIE_SD = 2030
CAT_MOVIE_HD = 2040
CAT_MOVIE_BLURAY = 2050
CAT_MOVIE_3D = 2060
CAT_MUSIC_MP3 = 3010
CAT_MUSIC_VIDEO = 3020
CAT_MUSIC_AUDIOBOOK = 3030
CAT_MUSIC_LOSSLESS = 3040
CAT_PC_0DAY = 4010
CAT_PC_ISO = 4020
CAT_PC_MAC = 4030
CAT_PC_MOBILEOTHER = 4040
CAT_PC_GAMES = 4050
CAT_PC_MOBILEIOS = 4060
CAT_PC_MOBILEANDROID = 4070
CAT_TV_FOREIGN = 5020
CAT_TV_SD = 5030
CAT_TV_HD = 5040
CAT_TV_OTHER = 5050
CAT_TV_SPORT = 5060
CAT_TV_ANIME = 5070
CAT_TV_DOCU = 5080
CAT_XXX_DVD = 6010
CAT_XXX_WMV = 6020
CAT_XXX_XVID = 6030
CAT_XXX_X264 = 6040
CAT_XXX_PACK = 6050
CAT_XXX_IMAGESET = 6060
CAT_XXX_OTHER = 6070
CAT_BOOK_MAGS = 7010
CAT_BOOK_EBOOK = 7020
CAT_BOOK_COMICS = 7030

CAT_MISC_OTHER = 8010

CAT_PARENT_GAME = 1000
CAT_PARENT_MOVIE = 2000
CAT_PARENT_MUSIC = 3000
CAT_PARENT_PC = 4000
CAT_PARENT_TV = 5000
CAT_PARENT_XXX = 6000
CAT_PARENT_BOOK = 7000
CAT_PARENT_MISC = 8000


def extract_features(name):
    def find(reg, str):
        res = regex.findall(reg, str, regex.I)
        if res:
            return '|'.join(sorted(res))
        else:
            return None

    return {
        'length': len(name),
        'tokens': len(regex.findall('[\w\']+', name)),
        'resolution': find('(720|1080)', name),
        'quality': find('(SDTV|HDTV|PDTV|WEB-?DL|WEBRIP|XVID|DIVX|DVDR|DVD-RIP|x264|dvd|XvidHD|AVC|AAC|VC\-?1|wmvhd|web\-dl|BRRIP|HDRIP|HDDVD|bddvd|BDRIP|webscr|bluray|bd?25|bd?50|blu-ray|BDREMUX)', name),
        '3d': bool(find('(3D)', name)),
        'subgroup': find('\[(\w+)\]', name),
        'filehash': bool(find('\[([0-9a-fA-F]{8})\]', name)),
        'season': bool(find('(S\d{1,2})', name)),
        'episode': bool(find('(E\d{1,2})', name)),
        'airdate': bool(find('((?:\d{4}[.-/ ]\d{2}[.-/ ]\d{2})|(?:\d{2}[.-/ ]\d{2}[.-/ ]\d{4}))', name)),
        'year': bool(find('[.-/ ](\d{4})[.-/ ]', name)),
        'versus': bool(find('[.-/ ](vs?)[.-/ ]', name)),
        'music': bool(find('((?:^VA(?:\-|\_|\ ))|(?:MP3|VBR|NMR|CDM|FLAC|\-(?:CDR?|EP|LP|SAT|2CD|FM|VINYL|DE|CABLE|TAPE)\-))', name)),
        'ebook': bool(find('(e?\-?book|html|epub|pdf|mobi|azw|doc|isbn)', name)),
        'comic': bool(find('(cbr|cbz)', name)),
        'magazine': bool(find('(mag(?:s|azine?s?))', name)),
        'sport': find('(epl|motogp|bellator|supercup|wtcc|bundesliga|uefa|espn|wwe|wwf|wcw|mma|ucf|fia|pga|nfl|ncaa|fifa|mlb|nrl|nhl|afl|nba|wimbledon|cricket)[\. -_]', name),
        'xxx': bool(find('(xxx|imageset|porn|erotica)', name)),
        'game': find('(PS3|3DS|NDS|PS4|XBOX|XBONE|WII|DLC|CONSOLE|PSP|X360|PS4)', name),
        'foreign': bool(find('(seizoen|staffel|danish|flemish|dutch|Deutsch|nl\.?subbed|nl\.?sub|\.NL|\.ITA|norwegian|swedish|swesub|french|german|spanish|icelandic|finnish|Chinese\.Subbed|vostfr|Hebrew\.Dubbed|\.HEB\.|Nordic|Hebdub|NLSubs|NL\-Subs|NLSub|Deutsch| der |German | NL |\.PL\.)', name)),
        'pc': bool(find('((?:v?\d\.\d\.)|(?:x64|32bit|64bit|exe))', name)),
        'documentary': bool(find('(documentary|national geographic|natgeo)', name))
    }


def determine_category(name, group_name=''):
    """Categorise release based on release name and group name."""
    features = extract_features(name)
    features['name'] = name
    features['group'] = group_name

    category = int(CATEGORISER.classify(features))

    log.debug('category: ({}) [{}]: {}'.format(
        group_name,
        name,
        category
    ))
    return category
