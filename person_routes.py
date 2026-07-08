import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, abort)
from flask_login import login_required, current_user
from models import db, Person, Photo
from utils import parse_date
from helpers import get_active_tree, get_active_persons

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

        # Дата рождения
        birth_str = request.form.get('birth_date_input', '').strip()
        b_notes = request.form.get('birth_notes', '').strip() or None
        b_year, b_month, b_day, b_notes_parsed = parse_date(birth_str)
        if b_notes_parsed:
            b_notes = (b_notes_parsed + '; ' + b_notes) if b_notes else b_notes_parsed

        # Дата смерти
        is_dead = request.form.get('is_dead') == '1'
        death_str = request.form.get('death_date_input', '').strip() if is_dead else ''
        d_notes = request.form.get('death_notes', '').strip() or None if is_dead else None
        d_year, d_month, d_day, d_notes_parsed = parse_date(death_str) if death_str else (None, None, None, None)
        if d_notes_parsed:
            d_notes = (d_notes_parsed + '; ' + d_notes) if d_notes else d_notes_parsed

        birth_city = request.form.get('birth_city', '').strip()
        extra_info = request.form.get('extra_info', '').strip()
        social_ok = request.form.get('social_ok', '').strip()
        social_vk = request.form.get('social_vk', '').strip()
        social_telegram = request.form.get('social_telegram', '').strip()
        social_mail = request.form.get('social_mail', '').strip()

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
            social_ok=social_ok, social_vk=social_vk,
            social_telegram=social_telegram, social_mail=social_mail
        )
        db.session.add(person)
        db.session.flush()

        # Фотографии
        if 'photos' in request.files:
            files = request.files.getlist('photos')
            for i, file in enumerate(files):
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    photo = Photo(person_id=person.id, filename=filename)
                    db.session.add(photo)
                    if i == 0 and not person.photo:
                        person.photo = filename

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

    person = get_active_persons(tree_id=tree.id).filter_by(id=person_id).first()
    if not person:
        abort(404)

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

    person = get_active_persons(tree_id=tree.id).filter_by(id=person_id).first()
    if not person:
        abort(404)

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        if not surname or not name:
            flash('Фамилия и Имя обязательны', 'danger')
            return render_template('add_person.html', tree=tree, person=person, edit=True)

        # Обновляем поля
        person.surname = surname
        person.name = name
        person.patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form.get('gender', 'M')
        if gender not in ('M', 'F'):
            flash('Некорректный пол', 'danger')
            return render_template('add_person.html', tree=tree, person=person, edit=True)
        person.gender = gender
        person.maiden_name = request.form.get('maiden_name', '').strip() or None

        # Дата рождения
        birth_str = request.form.get('birth_date_input', '').strip()
        b_notes = request.form.get('birth_notes', '').strip() or None
        b_year, b_month, b_day, b_notes_parsed = parse_date(birth_str)
        if b_notes_parsed:
            b_notes = (b_notes_parsed + '; ' + b_notes) if b_notes else b_notes_parsed
        person.birth_year = b_year
        person.birth_month = b_month
        person.birth_day = b_day
        person.birth_notes = b_notes

        # Дата смерти
        is_dead = request.form.get('is_dead') == '1'
        if is_dead:
            death_str = request.form.get('death_date_input', '').strip()
            d_notes = request.form.get('death_notes', '').strip() or None
            d_year, d_month, d_day, d_notes_parsed = parse_date(death_str)
            if d_notes_parsed:
                d_notes = (d_notes_parsed + '; ' + d_notes) if d_notes else d_notes_parsed
            person.death_year = d_year
            person.death_month = d_month
            person.death_day = d_day
            person.death_notes = d_notes
        else:
            person.death_year = None
            person.death_month = None
            person.death_day = None
            person.death_notes = None

        person.birth_city = request.form.get('birth_city', '').strip()
        person.extra_info = request.form.get('extra_info', '').strip()

        person.social_ok = request.form.get('social_ok', '').strip()
        person.social_vk = request.form.get('social_vk', '').strip()
        person.social_telegram = request.form.get('social_telegram', '').strip()
        person.social_mail = request.form.get('social_mail', '').strip()

        try:
            db.session.commit()
            flash('Данные обновлены', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении: {str(e)}', 'danger')
            return render_template('add_person.html', tree=tree, person=person, edit=True)

        return redirect(url_for('person.person_detail', person_id=person.id))

    # GET-запрос
    all_persons = get_active_persons(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_person.html', tree=tree, person=person,
                           all_persons=all_persons, edit=True)


@person_bp.route('/person/<int:person_id>/delete', methods=['POST'])
@login_required
def delete_person(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)

    person = get_active_persons(tree_id=tree.id).filter_by(id=person_id).first()
    if not person:
        abort(404)

    person.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('Персона перемещена в корзину', 'success')
    return redirect(url_for('main.tree_detail'))


@person_bp.route('/person/<int:person_id>/restore', methods=['POST'])
@login_required
def restore_person(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)

    person = db.session.get(Person, person_id)
    if not person or person.tree_id != tree.id:
        abort(404)

    if not person.is_deleted:
        flash('Персона не в корзине', 'warning')
        return redirect(url_for('person.person_detail', person_id=person.id))

    person.deleted_at = None
    db.session.commit()
    flash('Персона восстановлена', 'success')
    return redirect(url_for('person.person_detail', person_id=person.id))


@person_bp.route('/person/<int:person_id>/purge', methods=['POST'])
@login_required
def purge_person(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)

    person = db.session.get(Person, person_id)
    if not person or person.tree_id != tree.id:
        abort(404)

    Marriage.query.filter(
        (Marriage.husband_id == person.id) | (Marriage.wife_id == person.id)
    ).delete()
    Person.query.filter_by(father_id=person.id).update({Person.father_id: None})
    Person.query.filter_by(mother_id=person.id).update({Person.mother_id: None})
    db.session.delete(person)
    db.session.commit()
    flash('Персона удалена окончательно', 'success')
    return redirect(url_for('main.trash'))


@person_bp.route('/person/<int:person_id>/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(person_id, photo_id):
    tree = get_active_tree()
    if not tree:
        abort(403)

    person = get_active_persons(tree_id=tree.id).filter_by(id=person_id).first()
    if not person:
        abort(404)

    photo = db.session.get(Photo, photo_id)
    if not photo or photo.person_id != person.id:
        abort(404)

    filepath = os.path.join(UPLOAD_FOLDER, photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    if person.photo == photo.filename:
        next_photo = Photo.query.filter(
            Photo.person_id == person.id, Photo.id != photo.id
        ).first()
        person.photo = next_photo.filename if next_photo else None

    db.session.delete(photo)
    db.session.commit()
    flash('Фото удалено', 'success')
    return redirect(url_for('person.person_detail', person_id=person.id))


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

    primary = get_active_persons(tree_id=tree.id).filter_by(id=primary_id).first()
    secondary = get_active_persons(tree_id=tree.id).filter_by(id=secondary_id).first()
    if not primary or not secondary:
        abort(404)

    # Перенос детей
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

    # Перенос явных sibling-связей
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

    # Перенос фото
    if not primary.photo and secondary.photo:
        primary.photo = secondary.photo

    # Удаляем второстепенную персону
    db.session.delete(secondary)
    db.session.commit()
    flash(f'Персоны объединены в {primary.full_name}', 'success')
    return redirect(url_for('person.person_detail', person_id=primary.id))


@person_bp.route('/mass_action', methods=['POST'])
@login_required
def mass_action():
    tree = get_active_tree()
    if not tree:
        abort(403)

    action = request.form.get('action')
    person_ids = request.form.getlist('person_ids')

    if not person_ids:
        flash('Не выбрано ни одной персоны', 'warning')
        return redirect(url_for('main.tree_detail'))

    persons = [db.session.get(Person, int(pid)) for pid in person_ids]
    persons = [p for p in persons if p and p.tree_id == tree.id]

    if action == 'delete':
        for p in persons:
            p.deleted_at = datetime.utcnow()
        db.session.commit()
        flash(f'{len(persons)} персон перемещено в корзину', 'success')

    elif action == 'assign_parent':
        parent_id = request.form.get('parent_id', type=int)
        parent = db.session.get(Person, parent_id) if parent_id else None
        if not parent or parent.tree_id != tree.id:
            flash('Родитель не найден', 'danger')
            return redirect(url_for('main.tree_detail'))
        for p in persons:
            if parent.gender == 'M':
                p.father_id = parent.id
            else:
                p.mother_id = parent.id
        db.session.commit()
        flash(f'Родитель назначен для {len(persons)} персон', 'success')

    elif action == 'move':
        target_tree_id = request.form.get('target_tree_id', type=int)
        target_tree = db.session.get(Tree, target_tree_id)
        if not target_tree:
            flash('Целевое дерево не найдено', 'danger')
            return redirect(url_for('main.tree_detail'))
        perm = TreePermission.query.filter_by(
            user_id=current_user.id, tree_id=target_tree_id
        ).first()
        if not perm or perm.role not in ('owner', 'editor'):
            flash('У вас нет прав на перемещение в это дерево', 'danger')
            return redirect(url_for('main.tree_detail'))
        for p in persons:
            p.tree_id = target_tree.id
        db.session.commit()
        flash(f'{len(persons)} персон перемещено в дерево «{target_tree.name}»', 'success')

    return redirect(url_for('main.tree_detail'))

@person_bp.route('/person/<int:person_id>/history')
@login_required
def person_history(person_id):
    tree = get_active_tree()
    if not tree:
        abort(403)
    person = db.session.get(Person, person_id)
    if not person or person.tree_id != tree.id:
        abort(404)
    logs = AuditLog.query.filter_by(person_id=person.id).order_by(AuditLog.timestamp.desc()).all()
    return render_template('person_history.html', tree=tree, person=person, logs=logs)