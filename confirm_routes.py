from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Person, Marriage, SiblingLink

confirm_bp = Blueprint('confirm', __name__)

@confirm_bp.route('/confirm_person', methods=['POST'])
@login_required
def confirm_person():
    tree = current_user.tree
    action = request.form.get('action')

    # Отмена или пропуск – возвращаемся обратно
    if action in ('cancel', 'skip'):
        flash('Добавление отменено', 'info')
        # Редиректим на дерево или на карточку персоны, если был parent_id
        parent_id = request.form.get('parent_id')
        if parent_id:
            return redirect(url_for('person.person_detail', person_id=int(parent_id)))
        return redirect(url_for('main.tree_detail'))

    # Данные новой персоны (из скрытых полей)
    surname = request.form.get('surname', '').strip()
    name = request.form.get('name', '').strip()
    if not surname or not name:
        flash('Ошибка: отсутствует фамилия или имя', 'danger')
        return redirect(url_for('main.tree_detail'))

    patronymic = request.form.get('patronymic', '').strip() or None
    gender = request.form.get('gender')
    b_year = request.form.get('birth_year', type=int)
    b_month = request.form.get('birth_month', type=int)
    b_day = request.form.get('birth_day', type=int)
    b_notes = request.form.get('birth_notes', '').strip() or None
    d_year = request.form.get('death_year', type=int)
    d_month = request.form.get('death_month', type=int)
    d_day = request.form.get('death_day', type=int)
    d_notes = request.form.get('death_notes', '').strip() or None
    city = request.form.get('city', '').strip()

    person_type = request.form.get('person_type')
    parent_id = request.form.get('parent_id')       # контекст: для кого добавляем (ребёнка, супруга и т.д.)
    second_parent_id = request.form.get('second_parent_id')
    marriage_date_str = request.form.get('marriage_date')
    original_person_id = request.form.get('original_person_id')

    # Если выбрали "использовать существующего" (только для своего дерева)
    if action == 'use_existing':
        existing_person_id = request.form.get('existing_person_id', type=int)
        if not existing_person_id:
            flash('Не выбрана существующая персона', 'danger')
            return redirect(url_for('main.tree_detail'))
        existing_person = Person.query.get(existing_person_id)
        if not existing_person or existing_person.tree_id != tree.id:
            flash('Персона не найдена или не принадлежит вашему дереву', 'danger')
            return redirect(url_for('main.tree_detail'))

        # Создаём связь в зависимости от типа
        if person_type == 'spouse' and parent_id:
            current_person = Person.query.get(int(parent_id))
            if current_person and current_person.tree_id == tree.id:
                marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None
                if current_person.gender == 'M':
                    marriage = Marriage(husband_id=current_person.id, wife_id=existing_person.id, marriage_date=marriage_date)
                else:
                    marriage = Marriage(husband_id=existing_person.id, wife_id=current_person.id, marriage_date=marriage_date)
                db.session.add(marriage)
                db.session.commit()
                flash('Брак добавлен с существующей персоной', 'success')
                return redirect(url_for('person.person_detail', person_id=current_person.id))

        elif person_type == 'child' and parent_id:
            parent = Person.query.get(int(parent_id))
            if parent and parent.tree_id == tree.id:
                if parent.gender == 'M':
                    existing_person.father_id = parent.id
                    if second_parent_id:
                        mother = Person.query.get(int(second_parent_id))
                        if mother and mother.tree_id == tree.id and mother.gender == 'F':
                            existing_person.mother_id = mother.id
                else:
                    existing_person.mother_id = parent.id
                    if second_parent_id:
                        father = Person.query.get(int(second_parent_id))
                        if father and father.tree_id == tree.id and father.gender == 'M':
                            existing_person.father_id = father.id
                db.session.commit()
                flash('Связь с родителем установлена', 'success')
                return redirect(url_for('person.person_detail', person_id=parent.id))

        elif person_type == 'parent' and parent_id:
            child = Person.query.get(int(parent_id))
            if child and child.tree_id == tree.id:
                if existing_person.gender == 'M' and not child.father_id:
                    child.father_id = existing_person.id
                elif existing_person.gender == 'F' and not child.mother_id:
                    child.mother_id = existing_person.id
                else:
                    flash('Родитель этого пола уже существует или не совпадает', 'warning')
                    return redirect(url_for('person.person_detail', person_id=child.id))
                db.session.commit()
                flash('Родитель добавлен из существующей персоны', 'success')
                return redirect(url_for('person.person_detail', person_id=child.id))

        elif person_type == 'sibling' and parent_id:
            original = Person.query.get(int(parent_id))
            if original and original.tree_id == tree.id:
                if original.father or original.mother:
                    existing_person.father_id = original.father_id
                    existing_person.mother_id = original.mother_id
                    db.session.commit()
                else:
                    pid1, pid2 = sorted([original.id, existing_person.id])
                    if not SiblingLink.query.filter_by(person1_id=pid1, person2_id=pid2).first():
                        link = SiblingLink(person1_id=pid1, person2_id=pid2, tree_id=tree.id)
                        db.session.add(link)
                        db.session.commit()
                flash('Брат/сестра добавлен(а) из существующей персоны', 'success')
                return redirect(url_for('person.person_detail', person_id=original.id))

        elif person_type == 'step_parent' and parent_id:
            parent = Person.query.get(int(parent_id))
            if parent and parent.tree_id == tree.id:
                marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None
                if parent.gender == 'M':
                    marriage = Marriage(husband_id=parent.id, wife_id=existing_person.id, marriage_date=marriage_date)
                else:
                    marriage = Marriage(husband_id=existing_person.id, wife_id=parent.id, marriage_date=marriage_date)
                db.session.add(marriage)
                db.session.commit()
                flash('Приёмный родитель добавлен через брак с существующей персоной', 'success')
                return redirect(url_for('person.person_detail', person_id=original_person_id if original_person_id else parent.id))

        else:
            # Если тип неизвестен, просто редиректим на карточку существующей персоны
            flash('Тип связи не поддерживается для существующей персоны', 'warning')
            return redirect(url_for('person.person_detail', person_id=existing_person.id))

    # action == 'confirm' (создать нового)
    if action == 'confirm':
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        person = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=b_year, birth_month=b_month, birth_day=b_day, birth_notes=b_notes,
            death_year=d_year, death_month=d_month, death_day=d_day, death_notes=d_notes,
            city=city
        )
        db.session.add(person)
        db.session.flush()

        if person_type == 'child' and parent_id:
            parent = Person.query.get(int(parent_id))
            if parent and parent.tree_id == tree.id:
                if parent.gender == 'M':
                    person.father_id = parent.id
                    if second_parent_id:
                        mother = Person.query.get(int(second_parent_id))
                        if mother and mother.tree_id == tree.id and mother.gender == 'F':
                            person.mother_id = mother.id
                else:
                    person.mother_id = parent.id
                    if second_parent_id:
                        father = Person.query.get(int(second_parent_id))
                        if father and father.tree_id == tree.id and father.gender == 'M':
                            person.father_id = father.id

        elif person_type == 'spouse' and parent_id:
            current_person = Person.query.get(int(parent_id))
            if current_person and current_person.tree_id == tree.id:
                if current_person.gender == 'M':
                    marriage = Marriage(husband_id=current_person.id, wife_id=person.id, marriage_date=marriage_date)
                else:
                    marriage = Marriage(husband_id=person.id, wife_id=current_person.id, marriage_date=marriage_date)
                db.session.add(marriage)

        elif person_type == 'parent' and parent_id:
            child = Person.query.get(int(parent_id))
            if child and child.tree_id == tree.id:
                if person.gender == 'M' and not child.father_id:
                    child.father_id = person.id
                elif person.gender == 'F' and not child.mother_id:
                    child.mother_id = person.id
                else:
                    flash('Родитель этого пола уже существует, связь не изменена', 'warning')

        elif person_type == 'sibling' and parent_id:
            original = Person.query.get(int(parent_id))
            if original and original.tree_id == tree.id:
                if original.father or original.mother:
                    person.father_id = original.father_id
                    person.mother_id = original.mother_id
                else:
                    db.session.flush()
                    pid1, pid2 = sorted([original.id, person.id])
                    link = SiblingLink(person1_id=pid1, person2_id=pid2, tree_id=tree.id)
                    db.session.add(link)

        elif person_type == 'step_parent' and parent_id:
            parent = Person.query.get(int(parent_id))
            if parent and parent.tree_id == tree.id:
                if parent.gender == 'M':
                    marriage = Marriage(husband_id=parent.id, wife_id=person.id, marriage_date=marriage_date)
                else:
                    marriage = Marriage(husband_id=person.id, wife_id=parent.id, marriage_date=marriage_date)
                db.session.add(marriage)

        db.session.commit()
        flash('Персона добавлена', 'success')
        if parent_id:
            return redirect(url_for('person.person_detail', person_id=int(parent_id)))
        else:
            return redirect(url_for('person.person_detail', person_id=person.id))

    flash('Неизвестное действие', 'danger')
    return redirect(url_for('main.tree_detail'))