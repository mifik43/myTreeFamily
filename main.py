from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from models import db, Tree, Person, Marriage, SiblingLink

main_bp = Blueprint('main', __name__)

def masculine_surname(s):
    """Приводит женскую фамилию к мужской форме (убирает окончание -а/-я)."""
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
    tree = current_user.tree
    if not tree:
        tree = Tree(name=f'Род {current_user.surname}', user_id=current_user.id)
        db.session.add(tree)
        db.session.commit()
    view = request.args.get('view', 'table')
    surname_filter = request.args.get('surname', '').strip()

    persons_query = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name)
    all_persons = persons_query.all()

    # Уникальные фамилии в мужской форме
    surnames = sorted(list({masculine_surname(p.surname) for p in all_persons}))

    if surname_filter and surname_filter != 'Все':
        persons = [p for p in all_persons if masculine_surname(p.surname) == surname_filter]
    else:
        persons = all_persons

    # Поиск по ФИО (опционально)
    search_query = request.args.get('search', '').strip()
    ye = request.args.get('ye', '0') == '1'
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

    if view == 'tree':
        nodes = []
        edges = []
        valid_ids = {p.id for p in persons}
        for p in persons:
            nodes.append({
                'id': p.id,
                'label': p.full_name,
                'full_name': p.full_name,
                'birth_date': p.birth_display,
                'death_date': p.death_display,
                'city': p.birth_city or '',
                'gender': p.gender,
                'surname': p.surname
            })
            if p.father_id and p.father_id in valid_ids:
                edges.append({'from': p.father_id, 'to': p.id, 'arrows': 'to', 'label': 'отец'})
            if p.mother_id and p.mother_id in valid_ids:
                edges.append({'from': p.mother_id, 'to': p.id, 'arrows': 'to', 'label': 'мать'})
        # Браки
        marriages = Marriage.query.join(Person, Person.id == Marriage.husband_id)\
                                 .filter(Person.tree_id == tree.id).all()
        for m in marriages:
            if m.husband_id in valid_ids and m.wife_id in valid_ids:
                date_label = ''
                if m.marriage_date:
                    date_label = m.marriage_date.strftime('%d.%m.%Y')
                edges.append({
                    'from': m.husband_id,
                    'to': m.wife_id,
                    'dashes': True,
                    'label': 'брак' + (f' ({date_label})' if date_label else ''),
                    'color': {'color': 'red'}
                })
        # Явные связи брат/сестра и крёстные
        sibling_links = SiblingLink.query.filter_by(tree_id=tree.id).all()
        for link in sibling_links:
            if link.person1_id in valid_ids and link.person2_id in valid_ids:
                label = 'брат/сестра' if link.relation_type == 'sibling' else 'крестный(ая)'
                color = 'green' if link.relation_type == 'sibling' else 'purple'
                edges.append({
                    'from': link.person1_id,
                    'to': link.person2_id,
                    'dashes': True,
                    'label': label,
                    'color': {'color': color}
                })
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='tree', nodes=nodes, edges=edges,
                               surnames=surnames, current_surname=surname_filter,
                               search_query=search_query, ye=ye)

    if view == 'list':
        root_persons = tree.root_persons()
        if surname_filter and surname_filter != 'Все':
            root_persons = [r for r in root_persons if masculine_surname(r.surname) == surname_filter]
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='list', root_persons=root_persons,
                               surnames=surnames, current_surname=surname_filter,
                               search_query=search_query, ye=ye)

    if view == 'tree_view':
        root_persons = tree.root_persons()
        if surname_filter and surname_filter != 'Все':
            root_persons = [r for r in root_persons if masculine_surname(r.surname) == surname_filter]
        person_map = {p.id: p for p in Person.query.filter_by(tree_id=tree.id).all()}
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='tree_view', root_persons=root_persons,
                               person_map=person_map, surnames=surnames,
                               current_surname=surname_filter,
                               search_query=search_query, ye=ye)

    # По умолчанию таблица
    return render_template('tree_detail.html', tree=tree, persons=persons,
                           view='table', surnames=surnames, current_surname=surname_filter,
                           search_query=search_query, ye=ye)