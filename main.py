from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from models import db, Tree, Person, Marriage

main_bp = Blueprint('main', __name__)

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

    surnames = sorted(list({p.surname for p in all_persons}))

    if surname_filter and surname_filter != 'Все':
        persons = [p for p in all_persons if p.surname == surname_filter]
    else:
        persons = all_persons

    if view == 'tree':
        nodes = []
        edges = []
        valid_ids = {p.id for p in persons}
        for p in all_persons:
            if surname_filter and surname_filter != 'Все' and p.surname != surname_filter:
                continue
            nodes.append({
                'id': p.id,
                'label': p.full_name,
                'full_name': p.full_name,
                'birth_date': p.birth_display,
                'death_date': p.death_display,
                'city': p.city,
                'gender': p.gender,
                'surname': p.surname
            })
            if p.father_id and p.father_id in valid_ids:
                edges.append({'from': p.father_id, 'to': p.id, 'arrows': 'to', 'label': 'отец'})
            if p.mother_id and p.mother_id in valid_ids:
                edges.append({'from': p.mother_id, 'to': p.id, 'arrows': 'to', 'label': 'мать'})
        marriages = Marriage.query.join(Person, Person.id == Marriage.husband_id)\
                                 .filter(Person.tree_id == tree.id).all()
        for m in marriages:
            if m.husband_id in valid_ids and m.wife_id in valid_ids:
                edges.append({
                    'from': m.husband_id,
                    'to': m.wife_id,
                    'dashes': True,
                    'label': 'брак',
                    'color': {'color': 'red'}
                })
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='tree', nodes=nodes, edges=edges,
                               surnames=surnames, current_surname=surname_filter)

    if view == 'list':
        root_persons = tree.root_persons()
        if surname_filter and surname_filter != 'Все':
            root_persons = [r for r in root_persons if r.surname == surname_filter]
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='list', root_persons=root_persons,
                               surnames=surnames, current_surname=surname_filter)

    return render_template('tree_detail.html', tree=tree, persons=persons,
                           view='table', surnames=surnames, current_surname=surname_filter)