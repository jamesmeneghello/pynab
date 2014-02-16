#!/usr/local/bin/python2.7
# encoding: utf-8

import argparse
import os
import re
import string
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db

VALID_CHARS = string.ascii_lowercase + string.digits + '.-_'


def is_valid_group_name(name):
    return all(i in VALID_CHARS for i in set(name)) \
       and name[0] in string.ascii_lowercase \
       and name[-1] in string.ascii_lowercase
       
def wildcard_to_regex(filter):
    ' converts a group name with a wildcard character (*) to a valid regex ' 
    regex = '^{}$'.format(filter.replace('.', '\\.').replace('*', '.*'))
    return re.compile(regex)

def find_matching_groups(names, expand=True):
    ' find all groups in the db that match any of >names< '
    ' some names may have the wildcard character * '
    # if no name if provided, return all groups
    if not names:
        return list(db.groups.find()), ()
    
    # if a single name if provided instead of a list,
    # make a list so we can process it
    if isinstance(names, str):
        names = [names]
    
    matched_groups = []
    skipped_names = []
        
    for groupname in names:
        # handle wildcard character '*'
        # regex search is done only if needed
        if '*' in groupname and expand:
            regex = wildcard_to_regex(groupname)
            groups = db.groups.find({'name': regex})
            if groups:
                matched_groups.extend(groups)
            else:
                skipped_names.append(groupname)
        else:
            group = db.groups.find_one({'name': groupname})
            if group:
                matched_groups.append(group)
            else:
                skipped_names.append(groupname)
                
    return matched_groups, skipped_names


def add(args):
    enable = 0 if args.disabled else 1
    existing_groups, new_names = find_matching_groups(args.groups, expand=False)
    for group in existing_groups:
        print('Group {} is already in the database, skipping'.format(group['name']))
    for groupname in new_names:
        if is_valid_group_name(groupname):
            db.groups.insert({'name': groupname, 'active': enable})
        else:
            print("Group name '{}' is not valid".format(groupname))
        
def remove(args):
    groups, skipped_names = find_matching_groups(args.groups)
    for group in groups:
        db.groups.remove(group['_id'])
    if skipped_names:
        print('These groups where not in the database and where skipped:')
        for name in skipped_names:
            print('  ', name)

def enable(args):
    groups, skipped_names = find_matching_groups(args.groups)
    for group in groups:
        db.groups.update({'_id': group['_id']}, {'$set': {'active': 1}})
    if skipped_names:
        print('These groups where not in the database and where skipped:')
        for name in skipped_names:
            print('  ', name)

def disable(args):
    groups, skipped_names = find_matching_groups(args.groups)
    for group in groups:
        db.groups.update({'_id': group['_id']}, {'$set': {'active': 0}})
    if skipped_names:
        print('These groups where not in the database and where skipped:')
        for name in skipped_names:
            print('  ', name)

def list_(args):
    groups, skipped_names = find_matching_groups(args.filter)
    groups.sort(key=lambda group: group['name'])

    for group in groups:
        if group['active']:
            print(group['name'])
        else:
            print("{} (disabled)".format(group['name']))


def main(argv):

    parser = argparse.ArgumentParser(description='Manages groups. Added groups are enabled by default')
    subparsers = parser.add_subparsers()
    
    parser_add = subparsers.add_parser("add", aliases=["a"])
    parser_add.add_argument("groups", nargs="+", help="group names to add")
    parser_add.add_argument("-d", "--disabled", action="store_true", help="set added groups as disabled")
    parser_add.set_defaults(func=add)
    
    parser_remove = subparsers.add_parser("remove", aliases=["r", "rem"])
    parser_remove.add_argument("groups", nargs="+", help="group names to remove")
    parser_remove.set_defaults(func=remove)
    
    parser_enable = subparsers.add_parser("enable", aliases=["e"])
    parser_enable.add_argument("groups", nargs="+", help="group names to enable")
    parser_enable.set_defaults(func=enable)
    
    parser_disable = subparsers.add_parser("disable", aliases=["d"])
    parser_disable.add_argument("groups", nargs="+", help="group names to disable")
    parser_disable.set_defaults(func=disable)
    
    parser_list = subparsers.add_parser("list", aliases=["l"])
    parser_list.add_argument("filter", nargs="*", help="search filter(s)")
    parser_list.set_defaults(func=list_)
    
    args = parser.parse_args(argv)
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
        

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
    
