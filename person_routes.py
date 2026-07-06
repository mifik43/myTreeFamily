import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, session
from flask_login import login_required, current_user
from models import db, Person, Marriage
from utils import find_duplicates, parse_date
from helpers import get_active_tree

person_bp = Blueprint('person', __name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@person_bp.route('/person/add', methods=['GET', 'POST'])
@login_required
def add_person():
    tree = get_active_tree()
    if not tree:
        flash('Нет активного дерева', 'danger')
        return redirect(url_for('main.tree_detail'))

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_person.html', tree=tree)
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_person.html', tree=tree)
        maiden_name = request.form.get('maiden_name', '').strip() or None

        birth_str = request.form.get('birth_date_input', '').strip()
        death_str = request.form.get('death_date_input', '').strip()
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_notes = request.form.get('death_notes', '').strip() or None
        is_dead = request.form.get('is_dead') == '1'
        if not is_dead:
            death_str = ''
            d_notes = ''

        b_year, b_month, b_day, b_notes_parsed = parse_date(birth_str)
        if b_notes_parsed:
            b_notes = (b_notes_parsed + '; ' + b_notes) if b_notes else b_notes_parsed
        d_year, d_month, d_day, d_notes_parsed = parse_date(death_str)
        if d_notes_parsed:
            d_notes = (d_notes_parsed + '; ' + d_notes) if d_notes else d_notes_parsed

        birth_city = request.form.get('birth_city', '').strip()
        extra_info = request.form.get('extra_info', '').strip()
        social_ok = request.form.get('social_ok', '').strip()
        social_vk = request.form.get('social_vk', '').strip()
        social_telegram = request.form.get('social_telegram', '').strip()
        social_mail = request.form.get('social_mail', '').strip()

        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                photo_filename = filename

        duplicates = find_duplicates(surname, name, patronymic, b_year, tree, maiden_name)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, maiden_name=maiden_name,
                                   birth_year=b_year, birth_month=b_month, birth_day=b_day,
                                   birth_notes=b_notes,
                                   death_year=d_year, death_month=d_month, death_day=d_day,
                                   death_notes=d_notes,
                                   birth_city=birth_city, extra_info=extra_info,
                                   duplicates=duplicates,
                                   person_type=None, parent_id=None,
                                   second_parent_id=None, marriage_date=None)

        person = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            maiden_name=maiden_name,
            birth_year=b_year, birth_month=b_month, birth_day=b_day,
            birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day,
            death_notes=d_notes,
            birth_city=birth_city, extra_info=extra_info,
            photo=photo_filename,
            social_ok=social_ok, social_vk=social_vk,
            social_telegram=social_telegram, social_mail=social_mail
        )
        db.session.add(person)
        db.session.commit()
        flash('Персона добавлена', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    return render_template('add_person.html', tree=tree)

@person_bp.route('/person/<int:person_id>')
@login_required
def person_detail(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)
    children = set(person.children_father + person.children_mother)
    return render_template('person.html', tree=tree, person=person,
                           parents=[p for p in (person.father, person.mother) if p],
                           children=children,
                           spouses=person.spouses,
                           siblings=person.siblings)

@person_bp.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_person(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_person.html', tree=tree, person=person, edit=True)
        person.surname = surname
        person.name = name
        person.patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_person.html', tree=tree, person=person, edit=True)
        person.gender = gender
        person.maiden_name = request.form.get('maiden_name', '').strip() or None

        birth_str = request.form.get('birth_date_input', '').strip()
        death_str = request.form.get('death_date_input', '').strip()
        b_notes = request.form.get('birth_notes', '').strip() or None
        d_notes = request.form.get('death_notes', '').strip() or None
        is_dead = request.form.get('is_dead') == '1'
        if not is_dead:
            death_str = ''
            d_notes = ''

        b_year, b_month, b_day, b_notes_parsed = parse_date(birth_str)
        if b_notes_parsed:
            b_notes = (b_notes_parsed + '; ' + b_notes) if b_notes else b_notes_parsed
        d_year, d_month, d_day, d_notes_parsed = parse_date(death_str)
        if d_notes_parsed:
            d_notes = (d_notes_parsed + '; ' + d_notes) if d_notes else d_notes_parsed

        person.birth_year = b_year
        person.birth_month = b_month
        person.birth_day = b_day
        person.birth_notes = b_notes
        person.death_year = d_year
        person.death_month = d_month
        person.death_day = d_day
        person.death_notes = d_notes

        person.birth_city = request.form.get('birth_city', '').strip()
        person.extra_info = request.form.get('extra_info', '').strip()

        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                person.photo = filename

        person.social_ok = request.form.get('social_ok', '').strip()
        person.social_vk = request.form.get('social_vk', '').strip()
        person.social_telegram = request.form.get('social_telegram', '').strip()
        person.social_mail = request.form.get('social_mail', '').strip()

        db.session.commit()
        flash('Данные обновлены', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    all_persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_person.html', tree=tree, person=person, all_persons=all_persons, edit=True)

@person_bp.route('/person/<int:person_id>/delete', methods=['POST'])
@login_required
def delete_person(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)
    Marriage.query.filter((Marriage.husband_id == person.id) | (Marriage.wife_id == person.id)).delete()
    Person.query.filter_by(father_id=person.id).update({Person.father_id: None})
    Person.query.filter_by(mother_id=person.id).update({Person.mother_id: None})
    db.session.delete(person)
    db.session.commit()
    flash('Персона удалена', 'success')
    return redirect(url_for('main.tree_detail'))

@person_bp.route('/person/merge', methods=['POST'])
@login_required
def merge_persons():
    tree = get_active_tree()
    if not tree:
        abort(403)

    primary_id = request.form.get('primary_id', type=int)
    secondary_id = request.form.get('secondary_id', type=int)
    if not primary_id or not secondary_id:
        flash('Не указаны персоны для объединения', 'danger')
        return redirect(url_for('main.tree_detail'))

    primary = Person.query.get_or_404(primary_id)
    secondary = Person.query.get_or_404(secondary_id)
    if primary.tree_id != tree.id or secondary.tree_id != tree.id:
        abort(403)

    # Перенос родителей у детей
    for child in Person.query.filter_by(father_id=secondary.id).all():
        child.father_id = primary.id
    for child in Person.query.filter_by(mother_id=secondary.id).all():
        child.mother_id = primary.id

    # Перенос браков
    for m in secondary.marriages_as_husband:
        existing = Marriage.query.filter_by(husband_id=primary.id, wife_id=m.wife_id).first()
        if not existing:
            m.husband_id = primary.id
        else:
            db.session.delete(m)
    for m in secondary.marriages_as_wife:
        existing = Marriage.query.filter_by(husband_id=m.husband_id, wife_id=primary.id).first()
        if not existing:
            m.wife_id = primary.id
        else:
            db.session.delete(m)

    # Перенос явных sibling‑связей
    for link in secondary.sibling_links_1:
        other_id = link.person2_id
        if other_id != primary.id:
            pid1, pid2 = sorted([primary.id, other_id])
            if not SiblingLink.query.filter_by(
                person1_id=pid1, person2_id=pid2, tree_id=tree.id
            ).first():
                new_link = SiblingLink(
                    person1_id=pid1, person2_id=pid2,
                    tree_id=tree.id, relation_type=link.relation_type
                )
                db.session.add(new_link)
        db.session.delete(link)
    for link in secondary.sibling_links_2:
        other_id = link.person1_id
        if other_id != primary.id:
            pid1, pid2 = sorted([primary.id, other_id])
            if not SiblingLink.query.filter_by(
                person1_id=pid1, person2_id=pid2, tree_id=tree.id
            ).first():
                new_link = SiblingLink(
                    person1_id=pid1, person2_id=pid2,
                    tree_id=tree.id, relation_type=link.relation_type
                )
                db.session.add(new_link)
        db.session.delete(link)

    # Фотография
    if not primary.photo and secondary.photo:
        primary.photo = secondary.photo

    db.session.delete(secondary)
    db.session.commit()
    flash(f'Персоны объединены в {primary.full_name}', 'success')
    return redirect(url_for('person.person_detail', person_id=primary.id))