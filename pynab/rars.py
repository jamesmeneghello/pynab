import tempfile
import os
import regex
import shutil
import subprocess

import lib.rar
from pynab import log
from pynab.db import db_session, Release, Group, File, MetaBlack, NZB
import pynab.nzbs
import pynab.releases
import pynab.util
from pynab.server import Server
import config


MAYBE_PASSWORDED_REGEX = regex.compile('\.(ace|cab|tar|gz|url)$', regex.I)
PASSWORDED_REGEX = regex.compile('password\.url', regex.I)


def attempt_parse(file):
    name = ''
    match = pynab.util.Match()

    # Directory\Title.Year.Format.Group.mkv
    if match.match('(?<=\\\).*?BLURAY.(1080|720)P.*?KNORLOADING(?=\.MKV)', file, regex.I):
        name = match.match_obj.group(0)
    # Title.Format.ReleaseGroup.mkv
    elif match.match('.*?(1080|720)(|P).(SON)', file, regex.I):
        name = match.match_obj.group(0).replace('_', '.')
    # EBook
    elif match.match('.*\.(epub|mobi|azw3|pdf|prc)', file, regex.I):
        name = match.match_obj.group(0)\
            .replace('.epub', '')\
            .replace('.mobi', '')\
            .replace('.azw3', '')\
            .replace('.pdf', '')\
            .replace('.prc', '')
    # scene format generic
    elif match.match('([a-z0-9\'\-\.\_\(\)\+\ ]+\-[a-z0-9\'\-\.\_\(\)\ ]+)(.*?\\\\.*?|)\.(?:\w{3,4})$', file, regex.I):
        gen_s = match.match_obj.group(0)
        # scene format no folder
        if match.match('^([a-z0-9\.\_\- ]+\-[a-z0-9\_]+)(\\\\|)$', gen_s, regex.I):
            if len(match.match_obj.group(1)) > 15:
                name = match.match_obj.group(1)
        # check if file is in a folder, and use folder if so
        elif match.match('^(.*?\\\\)(.*?\\\\|)(.*?)$', gen_s, regex.I):
            folder_name = match.match_obj.group(1)
            folder_2_name = match.match_obj.group(2)
            if match.match('^([a-z0-9\.\_\- ]+\-[a-z0-9\_]+)(\\\\|)$', folder_name, regex.I):
                name = match.match_obj.group(1)
            elif match.match('(?!UTC)([a-z0-9]+[a-z0-9\.\_\- \'\)\(]+(\d{4}|HDTV).*?\-[a-z0-9]+)', folder_name, regex.I):
                name = match.match_obj.group(1)
            elif match.match('^([a-z0-9\.\_\- ]+\-[a-z0-9\_]+)(\\\\|)$', folder_2_name, regex.I):
                name = match.match_obj.group(1)
            elif match.match('^([a-z0-9\.\_\- ]+\-(?:.+)\(html\))\\\\', folder_name, regex.I):
                name = match.match_obj.group(1)
        elif match.match('(?!UTC)([a-z0-9]+[a-z0-9\.\_\- \'\)\(]+(\d{4}|HDTV).*?\-[a-z0-9]+)', gen_s, regex.I):
            name = match.match_obj.group(1)

    if not name:
        name = file

    return name


def check_rar(filename):
    """Determines whether a rar is passworded or not.
    Returns either a list of files (if the file is a rar and unpassworded),
    False if it's not a RAR, and True if it's a passworded/encrypted RAR.
    """
    try:
        rar = lib.rar.RarFile(filename)
    except:
        # wasn't a rar
        raise lib.rar.BadRarFile

    if rar:
        # was a rar! check for passworded inner rars
        if any([r.is_encrypted for r in rar.infolist()]):
            return False
        else:
            #TODO: doublecheck return from this for names
            return rar.infolist()
    else:
        # probably an encrypted rar!
        return False


def get_rar_info(server, group_name, messages):
    try:
        data = server.get(group_name, messages)
    except:
        data = None

    if data:
        # if we got the requested articles, save them to a temp rar
        t = None
        with tempfile.NamedTemporaryFile('wb', suffix='.rar', delete=False) as t:
            t.write(data.encode('ISO-8859-1'))
            t.flush()

        try:
            files = check_rar(t.name)
        except lib.rar.BadRarFile:
            os.remove(t.name)
            return False, None

        # build a list of files to return
        info = []

        passworded = False
        if files:
            info = [{'size': r.file_size, 'name': r.filename} for r in files]

            unrar_path = config.postprocess.get('unrar_path', '/usr/bin/unrar')
            if not (unrar_path and os.path.isfile(unrar_path) and os.access(unrar_path, os.X_OK)):
                log.error('rar: skipping archive decompression because unrar_path is not set or incorrect')
                log.error('rar: if the rar is not password protected, but contains an inner archive that is, we will not know')
            else:
                # make a tempdir to extract rar to
                tmp_dir = tempfile.mkdtemp()
                exe = [
                    '"{}"'.format(unrar_path),
                    'e', '-ai', '-ep', '-r', '-kb',
                    '-c-', '-id', '-p-', '-y', '-inul',
                    '"{}"'.format(t.name),
                    '"{}"'.format(tmp_dir)
                ]
    
                try:
                    subprocess.check_call(' '.join(exe), stderr=subprocess.STDOUT, shell=True)
                except subprocess.CalledProcessError as cpe:
                    log.debug('rar: issue while extracting rar: {}: {} {}'.format(cpe.cmd, cpe.returncode, cpe.output))

                inner_passwords = []
                for file in files:
                    fpath = os.path.join(tmp_dir, file.filename)
                    try:
                        inner_files = check_rar(fpath)
                    except lib.rar.BadRarFile:
                        continue
    
                    if inner_files:
                        inner_passwords += [r.is_encrypted for r in inner_files]
                    else:
                        passworded = True
                        break
    
                if not passworded:
                    passworded = any(inner_passwords)

                os.remove(t.name)
                shutil.rmtree(tmp_dir)
        else:
            passworded = True

        return passworded, info

    # couldn't get article
    return False, None


def check_release_files(server, group_name, nzb):
    """Retrieves rar metadata for release files."""

    for rar in nzb['rars']:
        messages = []
        if not rar['segments']:
            continue

        for s in rar['segments']:
            messages.append(s['message_id'])
            break

        if messages:
            passworded, info = get_rar_info(server, group_name, messages)

            if info and not passworded:
                for file in info:
                    result = MAYBE_PASSWORDED_REGEX.search(file['name'])
                    if result:
                        passworded = 'MAYBE'
                        break

                    result = PASSWORDED_REGEX.search(file['name'])
                    if result:
                        passworded = 'YES'
                        break

            if not passworded:
                passworded = 'NO'

            return passworded, info

    return None


def process(limit=20, category=0):
    """Processes release rarfiles to check for passwords and filecounts."""

    with Server() as server:
        with db_session() as db:
            query = db.query(Release).join(Group).join(NZB).filter(Release.passworded=='UNKNOWN')
            if category:
                query = query.filter(Release.category_id==int(category))

            if limit:
                releases = query.order_by(Release.posted.desc()).limit(limit)
            else:
                releases = query.order_by(Release.posted.desc()).all()

            for release in releases:
                nzb = pynab.nzbs.get_nzb_details(release.nzb)

                if nzb and 'rars' in nzb:
                    passworded, info = check_release_files(server, release.group.name, nzb)
                    if info:
                        log.info('[{}] - [{}] - file info: added'.format(
                            release.id,
                            release.search_name
                        ))
                        release.passworded = passworded

                        for file in info:
                            f = File(name=file['name'], size=file['size'])
                            f.release = release
                            db.add(f)

                        release.rar_metablack_id = None
                        db.add(release)
                        continue

                log.warning('rar: [{}] - [{}] - file info: no rars in release'.format(
                    release.id,
                    release.search_name
                ))
                mb = MetaBlack(rar=release, status='IMPOSSIBLE')
                db.add(mb)
            db.commit()