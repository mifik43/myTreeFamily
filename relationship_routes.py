from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from models import db, Person, Marriage, SiblingLink
from utils import find_duplicates

rel_bp = Blueprint('relationships', __name__)

@rel_bp.route('/marriage/add', methods=['GET', 'POST'])
@login_required
def add_marriage():
    tree = current_user.tree
    if request.method == 'POST':
        husband_id = int(request.form.get('husband_id', 0))
        wife_id = int(request.form.get('wife_id', 0))
        if not husband_id or not wife_id:
            flash('Необходимо выбрать мужа и жену', 'danger')
            return redirect(url_for('relationships.add_marriage'))
        marriage_date_str = request.form.get('marriage_date')
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        h = Person.query.get(husband_id)
        w = Person.query.get(wife_id)
        if not h or not w or h.tree_id != tree.id or w.tree_id != tree.id:
            abort(403)
        if h.gender != 'M' or w.gender != 'F':
            flash('Брак возможен только между мужчиной и женщиной', 'warning')
        marriage = Marriage(husband_id=husband_id, wife_id=wife_id, marriage_date=marriage_date)
        db.session.add(marriage)
        db.session.commit()
        flash('Брак добавлен', 'success')
        return redirect(url_for('main.tree_detail'))
    persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_marriage.html', tree=tree, persons=persons)

@rel_bp.route('/person/<int:person_id>/add_child', methods=['GET', 'POST'])
@login_required
def add_child(person_id):
    tree = current_user.tree
    parent = Person.query.get_or_404(person_id)
    if parent.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_child.html', tree=tree, parent=parent)
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_child.html', tree=tree, parent=parent)
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('city', '').strip()
        second_parent_id = request.form.get('second_parent_id')

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   duplicates=duplicates,
                                   person_type='child', parent_id=parent.id,
                                   second_parent_id=second_parent_id,
                                   marriage_date=None)

        child = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        if parent.gender == 'M':
            child.father_id = parent.id
            if second_parent_id:
                mother = Person.query.get(int(second_parent_id))
                if mother and mother.tree_id == tree.id and mother.gender == 'F':
                    child.mother_id = mother.id
        else:
            child.mother_id = parent.id
            if second_parent_id:
                father = Person.query.get(int(second_parent_id))
                if father and father.tree_id == tree.id and father.gender == 'M':
                    child.father_id = father.id

        db.session.add(child)
        db.session.commit()
        flash('Ребёнок добавлен', 'success')
        return redirect(url_for('person.person_detail', person_id=parent.id))

    spouses = parent.spouses
    return render_template('add_child.html', tree=tree, parent=parent, spouses=spouses)

@rel_bp.route('/person/<int:person_id>/add_spouse', methods=['GET', 'POST'])
@login_required
def add_spouse(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)
    opposite_gender = 'F' if person.gender == 'M' else 'M'

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_spouse.html', tree=tree, person=person, opposite_gender=opposite_gender)
        patronymic = request.form.get('patronymic', '').strip() or None
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('city', '').strip()
        marriage_date_str = request.form.get('marriage_date')
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=opposite_gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   duplicates=duplicates,
                                   person_type='spouse', parent_id=person.id,
                                   second_parent_id=None,
                                   marriage_date=marriage_date_str)

        spouse = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=opposite_gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        db.session.add(spouse)
        db.session.flush()
        if person.gender == 'M':
            marriage = Marriage(husband_id=person.id, wife_id=spouse.id, marriage_date=marriage_date)
        else:
            marriage = Marriage(husband_id=spouse.id, wife_id=person.id, marriage_date=marriage_date)
        db.session.add(marriage)
        db.session.commit()
        flash('Супруг(а) добавлен(а)', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    return render_template('add_spouse.html', tree=tree, person=person, opposite_gender=opposite_gender)

@rel_bp.route('/person/<int:person_id>/add_parent', methods=['GET', 'POST'])
@login_required
def add_parent(person_id):
    tree = current_user.tree
    child = Person.query.get_or_404(person_id)
    if child.tree_id != tree.id:
        abort(403)

    has_father = child.father_id is not None
    has_mother = child.mother_id is not None
    if has_father and has_mother:
        flash('У этой персоны уже указаны оба родителя', 'info')
        return redirect(url_for('person.person_detail', person_id=child.id))

    req_gender = request.args.get('gender')
    if req_gender == 'M' and not has_father:
        missing_gender = 'M'
    elif req_gender == 'F' and not has_mother:
        missing_gender = 'F'
    else:
        missing_gender = 'M' if not has_father else 'F'

    if request.method == 'POST':
        gender = request.form.get('gender')
        if not gender:
            flash('Не указан пол', 'danger')
            return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)
        if gender == 'M' and child.father_id:
            flash('У персоны уже есть отец', 'danger')
            return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)
        if gender == 'F' and child.mother_id:
            flash('У персоны уже есть мать', 'danger')
            return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)

        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)
        patronymic = request.form.get('patronymic', '').strip() or None
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('city', '').strip()

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   duplicates=duplicates,
                                   person_type='parent', parent_id=child.id,
                                   second_parent_id=None, marriage_date=None)

        parent = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        db.session.add(parent)
        db.session.flush()
        if gender == 'M':
            child.father_id = parent.id
        else:
            child.mother_id = parent.id
        db.session.commit()
        flash('Родитель добавлен', 'success')
        return redirect(url_for('person.person_detail', person_id=child.id))

    return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)

@rel_bp.route('/person/<int:person_id>/add_sibling', methods=['GET', 'POST'])
@login_required
def add_sibling(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_sibling.html', tree=tree, person=person)
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_sibling.html', tree=tree, person=person)
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('city', '').strip()

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   duplicates=duplicates,
                                   person_type='sibling', parent_id=person.id,
                                   second_parent_id=None, marriage_date=None)

        sibling = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        if person.father or person.mother:
            sibling.father_id = person.father_id
            sibling.mother_id = person.mother_id
        else:
            db.session.add(sibling)
            db.session.flush()
            pid1, pid2 = sorted([person.id, sibling.id])
            link = SiblingLink(person1_id=pid1, person2_id=pid2, tree_id=tree.id)
            db.session.add(link)
            db.session.commit()
            flash(f'{"Брат" if gender == "M" else "Сестра"} добавлен(а) как предполагаемый родственник', 'success')
            return redirect(url_for('person.person_detail', person_id=person.id))

        db.session.add(sibling)
        db.session.commit()
        flash('Брат/сестра добавлен(а)', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    return render_template('add_sibling.html', tree=tree, person=person)

@rel_bp.route('/person/<int:person_id>/add_godparent', methods=['GET', 'POST'])
@login_required
def add_godparent(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_godparent.html', tree=tree, person=person)
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_godparent.html', tree=tree, person=person)
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('birth_city', '').strip()
        extra_info = request.form.get('extra_info', '').strip()

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   extra_info=extra_info,
                                   duplicates=duplicates,
                                   person_type='godparent', parent_id=person.id,
                                   second_parent_id=None, marriage_date=None)

        godparent = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            birth_city=city, extra_info=extra_info
        )
        db.session.add(godparent)
        db.session.flush()
        pid1, pid2 = sorted([person.id, godparent.id])
        link = SiblingLink(person1_id=pid1, person2_id=pid2, tree_id=tree.id,
                           relation_type='godparent')
        db.session.add(link)
        db.session.commit()
        flash('Крёстный/крёстная добавлен(а)', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    return render_template('add_godparent.html', tree=tree, person=person)

@rel_bp.route('/person/<int:person_id>/add_step_parent', methods=['GET', 'POST'])
@login_required
def add_step_parent(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        parent_id = int(request.form.get('parent_id', 0))
        if not parent_id:
            flash('Необходимо выбрать родителя', 'danger')
            return redirect(url_for('relationships.add_step_parent', person_id=person.id))
        parent = Person.query.get(parent_id)
        if not parent or parent.tree_id != tree.id or parent.id not in [person.father_id, person.mother_id]:
            abort(403)

        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_step_parent.html', tree=tree, person=person)
        gender = 'F' if parent.gender == 'M' else 'M'
        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_year = request.form.get('death_year', type=int)
        d_month = request.form.get('death_month', type=int)
        d_day = request.form.get('death_day', type=int)
        d_notes = request.form.get('death_notes', '').strip() or None
        city = request.form.get('city', '').strip()
        marriage_date_str = request.form.get('marriage_date')
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        duplicates = find_duplicates(surname, name, None, b_year, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=None,
                                   gender=gender,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes, city=city,
                                   duplicates=duplicates,
                                   person_type='step_parent', parent_id=parent.id,
                                   second_parent_id=None, marriage_date=marriage_date_str,
                                   original_person_id=person.id)

        spouse = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=None, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        db.session.add(spouse)
        db.session.flush()
        if parent.gender == 'M':
            marriage = Marriage(husband_id=parent.id, wife_id=spouse.id, marriage_date=marriage_date)
        else:
            marriage = Marriage(husband_id=spouse.id, wife_id=parent.id, marriage_date=marriage_date)
        db.session.add(marriage)
        db.session.commit()
        flash('Приёмный родитель добавлен через брак', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    available_parents = [p for p in (person.father, person.mother) if p]
    return render_template('add_step_parent.html', tree=tree, person=person, available_parents=available_parents)

@rel_bp.route('/person/<int:person_id>/remove_parent/<int:parent_id>', methods=['POST'])
@login_required
def remove_parent(person_id, parent_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    parent = Person.query.get_or_404(parent_id)
    if person.tree_id != tree.id or parent.tree_id != tree.id:
        abort(403)

    if person.father_id == parent.id:
        person.father_id = None
        db.session.commit()
        flash('Связь с отцом удалена', 'success')
    elif person.mother_id == parent.id:
        person.mother_id = None
        db.session.commit()
        flash('Связь с матерью удалена', 'success')
    else:
        if parent.gender == 'M' and person.mother:
            Marriage.query.filter(
                Marriage.husband_id == parent.id,
                Marriage.wife_id == person.mother.id
            ).delete()
        elif parent.gender == 'F' and person.father:
            Marriage.query.filter(
                Marriage.wife_id == parent.id,
                Marriage.husband_id == person.father.id
            ).delete()
        db.session.commit()
        flash('Связь с приёмным родителем удалена', 'success')
    return redirect(url_for('person.person_detail', person_id=person.id))

@rel_bp.route('/person/<int:person_id>/remove_sibling/<int:sibling_id>', methods=['POST'])
@login_required
def remove_sibling(person_id, sibling_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    sibling = Person.query.get_or_404(sibling_id)
    if person.tree_id != tree.id or sibling.tree_id != tree.id:
        abort(403)

    pid1, pid2 = sorted([person.id, sibling.id])
    link = SiblingLink.query.filter_by(person1_id=pid1, person2_id=pid2, tree_id=tree.id).first()
    if link:
        db.session.delete(link)
        db.session.commit()
        flash('Связь брата/сестры удалена', 'success')
    else:
        flash('Явная связь не найдена', 'warning')
    return redirect(url_for('person.person_detail', person_id=person.id))