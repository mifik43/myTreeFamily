from flask import Blueprint, render_template, redirect, url_for, request, abort, session, flash
from flask_login import login_required, current_user
from models import db, Tree, Person, Marriage, SiblingLink, Invite, TreePermission
from helpers import get_active_tree
import secrets

main_bp = Blueprint('main', __name__)

def masculine_surname(s):
    """Приводит женскую фамилию к мужской форме."""
    if s.endswith(('а', 'я')):
        return s[:-1]
    return s

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

    persons_query = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name)
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

    if search_query:
        def match_person(p):
            fields = [p.surname, p.name, p.patronymic or '']
            if ye:
                def normalize(s):
                    return s.replace('ё', 'е').replace('Ё', 'Е')
                query_norm = normalize(search_query)
                return any(query_norm in normalize(f) for f in fields)
            else:
                return any(search_query.lower() in f.lower() for f in fields)
        persons = [p for p in persons if match_person(p)]

    if birth_year_from:
        try:
            year_from = int(birth_year_from)
            persons = [p for p in persons if p.birth_year and p.birth_year >= year_from]
        except ValueError:
            pass
    if birth_year_to:
        try:
            year_to = int(birth_year_to)
            persons = [p for p in persons if p.birth_year and p.birth_year <= year_to]
        except ValueError:
            pass
    if birth_city_search:
        persons = [p for p in persons if p.birth_city and birth_city_search.lower() in p.birth_city.lower()]
    if extra_info_search:
        persons = [p for p in persons if p.extra_info and extra_info_search.lower() in p.extra_info.lower()]

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

    return render_template('tree_detail.html', view='table', **common_params)

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

@main_bp.route('/tree/duplicates')
@login_required
def find_duplicates():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    persons = Person.query.filter_by(tree_id=tree.id).all()
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