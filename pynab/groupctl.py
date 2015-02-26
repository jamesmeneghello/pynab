from pynab.db import db_session, Group

def add_group(group_name):
    with db_session() as db:
        group = db.query(Group).filter(Group.name == group_name).first()
        if group:
            # Already exists, set active to True and update
            group.active = True
            db.add(group)
            db.commit()
            return True

        group = Group()
        group.name = group_name
        group.active = True
        group.first = 0
        group.last = 0
        db.add(group)
        db.commit()
        return True

def remove_group(group_name):
    with db_session() as db:
        deleted = db.query(Group).filter(Group.name == group_name).delete()
        if deleted:
            db.commit()
            return True
    return False

def enable_group(group_name):
    with db_session() as db:
        group = db.query(Group).filter(Group.name == group_name).first()
        if group:
            group.active = True
            db.add(group)
            db.commit()
            return True
    return False

def disable_group(group_name):
    with db_session() as db:
        group = db.query(Group).filter(Group.name == group_name).first()
        if group:
            group.active = False
            db.add(group)
            db.commit()
            return True
    return False

def reset_group(group_name):
    with db_session() as db:
        group = db.query(Group).filter(Group.name == group_name).first()
        if group:
            group.first = 0
            group.last = 0
            db.add(group)
            db.commit()
            return True
    return False

def group_info(group_name):
    with db_session() as db:
        group = db.query(Group).filter(Group.name == group_name).first()
        if group:
            return group
    return None

def group_list():
    with db_session() as db:
        groups = db.query(Group).order_by(Group.name)
        group_list = []
        for group in groups:
            group_list.append(group)

        return group_list

