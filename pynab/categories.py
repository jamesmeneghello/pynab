import regex
import pickle
import os.path

from pynab import log, root_dir


CATEGORISER = pickle.load(open(os.path.join(root_dir, 'db/release_categoriser.pkl'), 'rb'))


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
