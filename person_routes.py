from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from models import db, Person, Marriage
from utils import find_duplicates
from werkzeug.utils import secure_filename
import os

person_bp = Blueprint('person', __name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@person_bp.route('/person/add', methods=['GET', 'POST'])
@login_required
def add_person():
    tree = current_user.tree
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

        b_year = request.form.get('birth_year', type=int)
        b_month = request.form.get('birth_month', type=int)
        b_day = request.form.get('birth_day', type=int)
        b_notes = request.form.get('birth_notes', '').strip() or None
        birth_city = request.form.get('birth_city', '').strip()
        extra_info = request.form.get('extra_info', '').strip()
        social_ok = request.form.get('social_ok', '').strip()
        social_vk = request.form.get('social_vk', '').strip()
        social_telegram = request.form.get('social_telegram', '').strip()
        social_mail = request.form.get('social_mail', '').strip()
        maiden_name = request.form.get('maiden_name', '').strip() or None
        # Обработка даты смерти с галочкой
        is_dead = request.form.get('is_dead') == '1'
        death_str = ''
        d_notes = ''
        if is_dead:
            death_str = request.form.get('death_date_input', '').strip()
            d_notes = request.form.get('death_notes', '').strip() or None
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
                                   person_type=None, parent_id=None,
                                   second_parent_id=None, marriage_date=None)
        # Фотография
        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # генерируем уникальное имя
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                photo_filename = filename

        person = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day,
            birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day,
            death_notes=d_notes,
            city=city,
            birth_city=birth_city,
            extra_info=extra_info,
            photo=photo_filename,
            social_ok=social_ok,
            social_vk=social_vk,
            social_telegram=social_telegram,
            social_mail=social_mail
        )
        db.session.add(person)
        db.session.commit()
        flash('Персона добавлена', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    return render_template('add_person.html', tree=tree)

@person_bp.route('/person/<int:person_id>')
@login_required
def person_detail(person_id):
    tree = current_user.tree
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
    tree = current_user.tree
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

        person.birth_year = request.form.get('birth_year', type=int)
        person.birth_month = request.form.get('birth_month', type=int)
        person.birth_day = request.form.get('birth_day', type=int)
        person.birth_notes = request.form.get('birth_notes', '').strip() or None

        person.death_year = request.form.get('death_year', type=int)
        person.death_month = request.form.get('death_month', type=int)
        person.death_day = request.form.get('death_day', type=int)
        person.death_notes = request.form.get('death_notes', '').strip() or None

        person.city = request.form.get('city', '').strip()
        person.maiden_name = request.form.get('maiden_name', '').strip() or None
        db.session.commit()
        flash('Данные обновлены', 'success')
        return redirect(url_for('person.person_detail', person_id=person.id))

    all_persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_person.html', tree=tree, person=person, all_persons=all_persons, edit=True)

@person_bp.route('/person/<int:person_id>/delete', methods=['POST'])
@login_required
def delete_person(person_id):
    tree = current_user.tree
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