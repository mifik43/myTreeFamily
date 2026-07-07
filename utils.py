from models import Person, Tree, db
from datetime import datetime
import re
from helpers import get_active_tree, get_active_persons

def find_duplicates(surname, name, patronymic, birth_year, tree, maiden_name=None):
    if not surname or not name:
        return {'own': [], 'others': []}
    query = Person.query.filter(
        db.or_(Person.surname == surname, Person.maiden_name == surname),
        Person.name == name
    )
    if patronymic:
        query = query.filter(Person.patronymic == patronymic)
    if birth_year:
        query = query.filter(Person.birth_year == birth_year)
    if maiden_name:
        query = query.filter(db.or_(Person.surname == surname, Person.maiden_name == maiden_name))
    persons = query.all()
    own = [p for p in persons if p.tree_id == tree.id]
    others = []
    for p in persons:
        if p.tree_id != tree.id:
            t = Tree.query.get(p.tree_id)
            if t:
                owner = t.owner
                others.append((p, owner.username, owner.email))
    return {'own': own, 'others': others}

def parse_date(date_str):
    if not date_str:
        return None, None, None, None
    date_str = date_str.strip()
    for fmt in ('%d.%m.%Y', '%d.%m.%y', '%d %B %Y', '%d %b %Y', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.year, dt.month, dt.day, None
        except ValueError:
            continue
    m = re.match(r'^(\d{4})$', date_str)
    if m:
        return int(m.group(1)), None, None, None
    for pat in (r'^(\d{1,2})\.(\d{4})$', r'^(\d{4})-(\d{1,2})$'):
        m = re.match(pat, date_str)
        if m:
            if pat.startswith(r'^(\d{1,2})'):
                month, year = int(m.group(1)), int(m.group(2))
            else:
                year, month = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12:
                return year, month, None, None
    return None, None, None, date_str

def log_audit(user_id, person, action):
    old_attrs = {
        'surname': person.surname,
        'name': person.name,
        'patronymic': person.patronymic,
        'maiden_name': person.maiden_name,
        'gender': person.gender,
        'birth_year': person.birth_year,
        'birth_month': person.birth_month,
        'birth_day': person.birth_day,
        'birth_notes': person.birth_notes,
        'death_year': person.death_year,
        'death_month': person.death_month,
        'death_day': person.death_day,
        'death_notes': person.death_notes,
        'birth_city': person.birth_city,
        'extra_info': person.extra_info
    }
    from models import AuditLog, db
    log = AuditLog(
        user_id=user_id,
        person_id=person.id,
        action=action,
        old_values=json.dumps(old_attrs, ensure_ascii=False, default=str),
        new_values=json.dumps(old_attrs, ensure_ascii=False, default=str)  # будет перезаписано после изменений
    )
    db.session.add(log)
    return log