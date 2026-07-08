import io
import secrets
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for, request,
                   abort, session, flash, send_file)
from flask_login import login_required, current_user
from models import (db, Tree, Person, Marriage, SiblingLink,
                    Invite, TreePermission)
from helpers import get_active_tree, get_active_persons, geocode
from utils import parse_date, apply_filters
import openpyxl

main_bp = Blueprint('main', __name__)

# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------
def masculine_surname(s):
    """Приводит женскую фамилию к мужской форме."""
    if s.endswith(('а', 'я')):
        return s[:-1]
    return s


def parse_gedcom_date(date_str):
    """Разбирает дату из GEDCOM‑строки."""
    if not date_str:
        return None, None, None, None
    date_str = date_str.strip()
    for fmt in ('%d %b %Y', '%d %B %Y', '%Y', '%d.%m.%Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.year, dt.month, dt.day, None
        except ValueError:
            continue
    if date_str.isdigit():
        year = int(date_str)
        return year, None, None, None
    return None, None, None, date_str   # неопознанный формат → notes


# ----------------------------------------------------------------------
# Основные маршруты
# ----------------------------------------------------------------------
@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.tree_detail'))
    return redirect(url_for('auth.login'))


@main_bp.route('/tree')
@login_required
def tree_detail():
    tree = get_active_tree()
    if not tree:
        flash('У вас нет доступа ни к одному дереву.', 'danger')
        return redirect(url_for('auth.login'))

    view = request.args.get('view', 'table')
    surname_filter = request.args.get('surname', '').strip()

    persons_query = get_active_persons(tree_id=tree.id).order_by(Person.surname, Person.name)
    all_persons = persons_query.all()
    surnames = sorted(list({masculine_surname(p.surname) for p in all_persons}))

    if surname_filter and surname_filter != 'Все':
        persons = [p for p in all_persons if masculine_surname(p.surname) == surname_filter]
    else:
        persons = all_persons

    search_query = request.args.get('search', '').strip()
    ye = request.args.get('ye', '0') == '1'

    birth_year_from = request.args.get('birth_year_from', '').strip()
    birth_year_to = request.args.get('birth_year_to', '').strip()
    birth_city_search = request.args.get('birth_city_search', '').strip()
    extra_info_search = request.args.get('extra_info_search', '').strip()

    # Применяем все фильтры через единую функцию
    persons = apply_filters(persons, search_query, ye, birth_year_from, birth_year_to,
                            birth_city_search, extra_info_search)

    common_params = dict(
        tree=tree, persons=persons, surnames=surnames,
        current_surname=surname_filter,
        search_query=search_query, ye=ye,
        birth_year_from=birth_year_from, birth_year_to=birth_year_to,
        birth_city_search=birth_city_search, extra_info_search=extra_info_search,
        active_tree=tree
    )

    if view == 'tree':
        nodes, edges = [], []
        valid_ids = {p.id for p in persons}
        for p in persons:
            nodes.append({
                'id': p.id, 'label': p.full_name, 'full_name': p.full_name,
                'birth_date': p.birth_display, 'death_date': p.death_display,
                'city': p.birth_city or '', 'gender': p.gender, 'surname': p.surname
            })
            if p.father_id and p.father_id in valid_ids:
                edges.append({'from': p.father_id, 'to': p.id, 'arrows': 'to', 'label': 'отец'})
            if p.mother_id and p.mother_id in valid_ids:
                edges.append({'from': p.mother_id, 'to': p.id, 'arrows': 'to', 'label': 'мать'})

        marriages = Marriage.query.join(Person, Person.id == Marriage.husband_id)\
                                 .filter(Person.tree_id == tree.id).all()
        for m in marriages:
            if m.husband_id in valid_ids and m.wife_id in valid_ids:
                date_label = ''
                if m.marriage_date:
                    date_label = m.marriage_date.strftime('%d.%m.%Y')
                edges.append({
                    'from': m.husband_id, 'to': m.wife_id,
                    'dashes': True, 'label': 'брак' + (f' ({date_label})' if date_label else ''),
                    'color': {'color': 'red'}
                })

        sibling_links = SiblingLink.query.filter_by(tree_id=tree.id).all()
        for link in sibling_links:
            if link.person1_id in valid_ids and link.person2_id in valid_ids:
                label = 'брат/сестра' if link.relation_type == 'sibling' else 'крестный(ая)'
                color = 'green' if link.relation_type == 'sibling' else 'purple'
                edges.append({
                    'from': link.person1_id, 'to': link.person2_id,
                    'dashes': True, 'label': label, 'color': {'color': color}
                })

        return render_template('tree_detail.html', nodes=nodes, edges=edges,
                               view='tree', **common_params)

    if view == 'list':
        root_persons = tree.root_persons()
        if surname_filter and surname_filter != 'Все':
            root_persons = [r for r in root_persons if masculine_surname(r.surname) == surname_filter]
        return render_template('tree_detail.html', view='list',
                               root_persons=root_persons, **common_params)

    if view == 'tree_view':
        root_persons = tree.root_persons()
        if surname_filter and surname_filter != 'Все':
            root_persons = [r for r in root_persons if masculine_surname(r.surname) == surname_filter]
        person_map = {p.id: p for p in Person.query.filter_by(tree_id=tree.id).all()}
        return render_template('tree_detail.html', view='tree_view',
                               root_persons=root_persons, person_map=person_map, **common_params)

    # таблица по умолчанию
    return render_template('tree_detail.html', view='table', **common_params)


@main_bp.route('/tree/data')
@login_required
def tree_data():
    tree = get_active_tree()
    if not tree:
        return {'error': 'no active tree'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = 50
    surname_filter = request.args.get('surname', '').strip()
    search_query = request.args.get('search', '').strip()
    ye = request.args.get('ye', '0') == '1'
    birth_year_from = request.args.get('birth_year_from', '').strip()
    birth_year_to = request.args.get('birth_year_to', '').strip()
    birth_city_search = request.args.get('birth_city_search', '').strip()
    extra_info_search = request.args.get('extra_info_search', '').strip()

    persons = get_active_persons(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    if surname_filter and surname_filter != 'Все':
        persons = [p for p in persons if masculine_surname(p.surname) == surname_filter]
    persons = apply_filters(persons, search_query, ye, birth_year_from, birth_year_to,
                            birth_city_search, extra_info_search)

    total = len(persons)
    start = (page - 1) * per_page
    end = start + per_page
    page_persons = persons[start:end]

    data = {
        'persons': [{
            'id': p.id,
            'surname': p.surname,
            'name': p.name,
            'patronymic': p.patronymic or '',
            'birth_display': p.birth_display,
            'birth_city': p.birth_city or '',
        } for p in page_persons],
        'has_more': end < total
    }
    return data


@main_bp.route('/invite/generate')
@login_required
def generate_invite():
    tree = get_active_tree()
    if not tree:
        flash('Дерево не найдено', 'danger')
        return redirect(url_for('main.tree_detail'))
    if tree.user_id != current_user.id:
        flash('Только владелец может приглашать', 'danger')
        return redirect(url_for('main.tree_detail'))
    token = secrets.token_urlsafe(16)
    invite = Invite(token=token, tree_id=tree.id, role='editor')
    db.session.add(invite)
    db.session.commit()
    invite_link = url_for('auth.register', invite=token, _external=True)
    flash(f'Ссылка для приглашения: {invite_link}', 'success')
    return redirect(url_for('main.tree_detail'))


# ----------------------------------------------------------------------
# Дубликаты
# ----------------------------------------------------------------------
@main_bp.route('/tree/duplicates')
@login_required
def find_duplicates():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    persons = get_active_persons(tree_id=tree.id).all()
    groups = {}
    for p in persons:
        key = (
            p.name.strip().lower(),
            p.patronymic.strip().lower() if p.patronymic else None,
            p.birth_year
        )
        groups.setdefault(key, []).append(p)

    duplicates = [group for group in groups.values() if len(group) > 1]
    return render_template('duplicates.html', tree=tree, duplicates=duplicates)


# ----------------------------------------------------------------------
# Корзина
# ----------------------------------------------------------------------
@main_bp.route('/trash')
@login_required
def trash():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))
    deleted_persons = Person.query.filter(
        Person.tree_id == tree.id,
        Person.deleted_at != None
    ).order_by(Person.deleted_at.desc()).all()
    return render_template('trash.html', tree=tree, deleted_persons=deleted_persons)


# ----------------------------------------------------------------------
# GEDCOM экспорт / импорт
# ----------------------------------------------------------------------
@main_bp.route('/tree/export/gedcom')
@login_required
def export_gedcom():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    lines = []
    lines.append('0 HEAD')
    lines.append('1 SOUR FamilyTree')
    lines.append('1 DEST GEDCOM')
    lines.append('1 DATE ' + datetime.now().strftime('%d %b %Y'))
    lines.append('1 CHAR UTF-8')
    lines.append('1 SUBM @SUBM@')
    lines.append('0 @SUBM@ SUBM')
    lines.append('1 NAME ' + current_user.username)

    persons = get_active_persons(tree_id=tree.id).all()
    person_gedcom_ids = {}
    for idx, person in enumerate(persons):
        gedcom_id = f'I{idx+1}'
        person_gedcom_ids[person.id] = gedcom_id

        lines.append(f'0 @{gedcom_id}@ INDI')
        lines.append(f'1 NAME {person.surname} {person.name} /{person.patronymic or ""}/')
        if person.maiden_name:
            lines.append(f'2 NICK {person.maiden_name}')
        if person.gender:
            lines.append(f'1 SEX {person.gender}')
        if person.birth_date_obj:
            lines.append('1 BIRT')
            lines.append(f'2 DATE {person.birth_date_obj.strftime("%d %b %Y")}')
            if person.birth_city:
                lines.append(f'2 PLAC {person.birth_city}')
        elif person.birth_year:
            lines.append('1 BIRT')
            lines.append(f'2 DATE {person.birth_year}')
            if person.birth_city:
                lines.append(f'2 PLAC {person.birth_city}')
        if person.death_date_obj:
            lines.append('1 DEAT')
            lines.append(f'2 DATE {person.death_date_obj.strftime("%d %b %Y")}')
            if person.birth_city:
                lines.append(f'2 PLAC {person.birth_city}')
        elif person.death_year:
            lines.append('1 DEAT')
            lines.append(f'2 DATE {person.death_year}')
        if person.extra_info:
            lines.append(f'1 NOTE {person.extra_info}')

    # Семьи и браки
    marriages = Marriage.query.join(Person, Person.id == Marriage.husband_id)\
                             .filter(Person.tree_id == tree.id).all()
    family_counter = 1
    for marriage in marriages:
        if marriage.husband_id in person_gedcom_ids and marriage.wife_id in person_gedcom_ids:
            fam_id = f'F{family_counter}'
            lines.append(f'0 @{fam_id}@ FAM')
            lines.append(f'1 HUSB @{person_gedcom_ids[marriage.husband_id]}@')
            lines.append(f'1 WIFE @{person_gedcom_ids[marriage.wife_id]}@')
            if marriage.marriage_date:
                lines.append('1 MARR')
                lines.append(f'2 DATE {marriage.marriage_date.strftime("%d %b %Y")}')
            children = Person.query.filter(
                Person.father_id == marriage.husband_id,
                Person.mother_id == marriage.wife_id,
                Person.tree_id == tree.id
            ).all()
            for child in children:
                if child.id in person_gedcom_ids:
                    lines.append(f'1 CHIL @{person_gedcom_ids[child.id]}@')
            family_counter += 1

    lines.append('0 TRLR')

    output = io.BytesIO()
    output.write('\n'.join(lines).encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/plain', as_attachment=True,
                     download_name=f'tree_{tree.id}.ged')


@main_bp.route('/tree/import/gedcom', methods=['GET', 'POST'])
@login_required
def import_gedcom():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    if request.method == 'POST':
        file = request.files.get('gedcom_file')
        if not file or file.filename == '':
            flash('Файл не выбран', 'danger')
            return render_template('import_gedcom.html', tree=tree)

        content = file.read().decode('utf-8', errors='ignore')
        individuals = {}
        families = []

        lines = content.splitlines()
        i = 0
        current_person = None
        current_section = None

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            level, rest = int(line[0]), line[2:]

            if level == 0 and rest.startswith('@') and 'INDI' in rest:
                current_id = rest.split('@')[1]
                current_person = {
                    'id': current_id, 'surname': '', 'name': '', 'patronymic': '',
                    'maiden': None, 'gender': None,
                    'birth_date': None, 'birth_place': None,
                    'death_date': None, 'death_place': None, 'note': ''
                }
                individuals[current_id] = current_person
            elif level == 1 and current_person is not None:
                tag = rest.split(' ')[0]
                value = ' '.join(rest.split(' ')[1:]) if ' ' in rest else ''
                if tag == 'NAME':
                    parts = value.split('/')
                    full_name = parts[0].strip().split()
                    if len(full_name) >= 1:
                        current_person['surname'] = full_name[0]
                    if len(full_name) >= 2:
                        current_person['name'] = full_name[1]
                    if len(parts) > 1 and parts[1].strip():
                        current_person['patronymic'] = parts[1].strip()
                elif tag == 'SEX':
                    current_person['gender'] = value
                elif tag == 'NICK':
                    current_person['maiden'] = value
                elif tag == 'BIRT':
                    current_section = 'BIRT'
                elif tag == 'DEAT':
                    current_section = 'DEAT'
                elif tag == 'DATE' and current_section:
                    if current_section == 'BIRT':
                        current_person['birth_date'] = value
                    elif current_section == 'DEAT':
                        current_person['death_date'] = value
                elif tag == 'PLAC' and current_section:
                    if current_section == 'BIRT':
                        current_person['birth_place'] = value
                    elif current_section == 'DEAT':
                        current_person['death_place'] = value
                elif tag == 'NOTE':
                    current_person['note'] = value
            elif level == 0 and rest.startswith('@') and 'FAM' in rest:
                fam_id = rest.split('@')[1]
                fam = {'id': fam_id, 'husb': None, 'wife': None, 'children': []}
                j = i + 1
                while j < len(lines):
                    l2 = lines[j].strip()
                    if not l2:
                        j += 1
                        continue
                    lev2 = int(l2[0])
                    if lev2 == 0 and j > i:
                        break
                    rest2 = l2[2:]
                    tag2 = rest2.split(' ')[0]
                    value2 = ' '.join(rest2.split(' ')[1:]) if ' ' in rest2 else ''
                    if tag2 == 'HUSB':
                        fam['husb'] = value2.replace('@', '')
                    elif tag2 == 'WIFE':
                        fam['wife'] = value2.replace('@', '')
                    elif tag2 == 'CHIL':
                        fam['children'].append(value2.replace('@', ''))
                    j += 1
                families.append(fam)
                i = j
                continue
            i += 1

        # Создаём персоны
        id_map = {}
        for gedcom_id, data in individuals.items():
            birth_year, birth_month, birth_day, birth_notes = parse_gedcom_date(data.get('birth_date'))
            death_year, death_month, death_day, death_notes = parse_gedcom_date(data.get('death_date'))

            person = Person(
                tree_id=tree.id,
                surname=data['surname'] or 'Неизвестно',
                name=data['name'] or 'Имя',
                patronymic=data['patronymic'] or None,
                maiden_name=data['maiden'],
                gender=data['gender'] if data['gender'] in ('M','F') else 'M',
                birth_year=birth_year, birth_month=birth_month, birth_day=birth_day,
                birth_notes=birth_notes or None,
                death_year=death_year, death_month=death_month, death_day=death_day,
                death_notes=death_notes or None,
                birth_city=data['birth_place'] or None,
                extra_info=data['note'] if data['note'] else None
            )
            db.session.add(person)
            db.session.flush()
            id_map[gedcom_id] = person.id

        db.session.commit()

        # Семьи и браки
        for fam in families:
            husb_id = id_map.get(fam['husb'])
            wife_id = id_map.get(fam['wife'])
            if husb_id and wife_id:
                marriage = Marriage(husband_id=husb_id, wife_id=wife_id)
                db.session.add(marriage)
                db.session.flush()
                for child_gedcom in fam['children']:
                    child_id = id_map.get(child_gedcom)
                    if child_id:
                        child = db.session.get(Person, child_id)
                        if child:
                            child.father_id = husb_id
                            child.mother_id = wife_id
        db.session.commit()

        flash('Импорт завершён успешно', 'success')
        return redirect(url_for('main.tree_detail'))

    return render_template('import_gedcom.html', tree=tree)


# ----------------------------------------------------------------------
# Экспорт в Excel
# ----------------------------------------------------------------------
@main_bp.route('/tree/export/excel')
@login_required
def export_excel():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    persons = get_active_persons(tree_id=tree.id).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Персоны"
    headers = ['Фамилия', 'Имя', 'Отчество', 'Девичья фамилия', 'Пол',
               'Дата рождения', 'Дата смерти', 'Город рождения', 'Дополнительная информация']
    ws.append(headers)

    for p in persons:
        ws.append([
            p.surname,
            p.name,
            p.patronymic,
            p.maiden_name or '',
            'Мужской' if p.gender == 'M' else 'Женский',
            p.birth_display,
            p.death_display,
            p.birth_city or '',
            p.extra_info or ''
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'tree_{tree.id}_persons.xlsx')


# ----------------------------------------------------------------------
# Карта (Яндекс.Карты)
# ----------------------------------------------------------------------
@main_bp.route('/tree/map')
@login_required
def tree_map():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    persons = get_active_persons(tree_id=tree.id).all()

    points = []
    migrations = []

    for p in persons:
        city = p.birth_city
        if city:
            lat, lon = geocode(city)
            if lat and lon:
                points.append({
                    'name': p.full_name,
                    'city': city,
                    'lat': lat,
                    'lon': lon,
                    'person_id': p.id,
                    'birth_year': p.birth_year,
                    'gender': p.gender
                })

        # Миграция: от родителя к ребёнку (только если оба имеют разные города)
        if p.father and p.father.birth_city and p.birth_city and p.father.birth_city != p.birth_city:
            flat, flon = geocode(p.father.birth_city)
            clat, clon = geocode(p.birth_city)
            if flat and flon and clat and clon:
                migrations.append({
                    'from_name': p.father.full_name,
                    'to_name': p.full_name,
                    'from_lat': flat, 'from_lon': flon,
                    'to_lat': clat, 'to_lon': clon
                })
        if p.mother and p.mother.birth_city and p.birth_city and p.mother.birth_city != p.birth_city:
            mlat, mlon = geocode(p.mother.birth_city)
            clat, clon = geocode(p.birth_city)
            if mlat and mlon and clat and clon:
                migrations.append({
                    'from_name': p.mother.full_name,
                    'to_name': p.full_name,
                    'from_lat': mlat, 'from_lon': mlon,
                    'to_lat': clat, 'to_lon': clon
                })

    return render_template('map.html', tree=tree, points=points, migrations=migrations)