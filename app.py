import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Tree, Person, Marriage

app = Flask(__name__)

# -------------------- КОНФИГУРАЦИЯ (переменные окружения) --------------------
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
_default_sqlite = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'genealogy.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', _default_sqlite)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 20)),
    'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 40)),
    'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
    'pool_pre_ping': os.environ.get('DB_POOL_PRE_PING', 'true').lower() == 'true',
    'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 30)),
}

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- ВСПОМОГАТЕЛЬНЫЕ --------------------
def find_duplicates(surname, name, patronymic, birth_date, tree):
    if not surname or not name or not birth_date:
        return {'own': [], 'others': []}
    query = Person.query.filter(
        Person.surname == surname,
        Person.name == name,
        Person.birth_date == birth_date
    )
    if patronymic:
        query = query.filter(Person.patronymic == patronymic)
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

# -------------------- АВТОРИЗАЦИЯ --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form['gender']
        maiden_name = None
        if gender == 'F':
            maiden_name = request.form.get('maiden_name', '').strip() or None

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html')

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            surname=surname,
            name=name,
            patronymic=patronymic,
            maiden_name=maiden_name,
            gender=gender
        )
        db.session.add(user)
        db.session.flush()

        tree = Tree(name=f'Род {surname}', user_id=user.id)
        db.session.add(tree)
        db.session.flush()

        # Корневая персона — сам пользователь
        person = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=None,
            death_date=None,
            city=None
        )
        db.session.add(person)
        db.session.commit()

        login_user(user)
        flash('Регистрация успешна! Ваше дерево создано.', 'success')
        return redirect(url_for('tree_detail'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('tree_detail'))
        flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        current_user.email = email or None
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('tree_detail'))
    return render_template('profile.html', user=current_user)

# -------------------- ГЛАВНАЯ --------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('tree_detail'))
    return redirect(url_for('login'))

# -------------------- ПРОСМОТР ДЕРЕВА --------------------
@app.route('/tree')
@login_required
def tree_detail():
    tree = current_user.tree
    if not tree:
        tree = Tree(name=f'Род {current_user.surname}', user_id=current_user.id)
        db.session.add(tree)
        db.session.commit()
    view = request.args.get('view', 'table')
    persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()

    if view == 'tree':
        nodes = []
        edges = []
        for p in persons:
            nodes.append({
                'id': p.id,
                'label': p.full_name,
                'full_name': p.full_name,
                'birth_date': p.birth_date.strftime('%d.%m.%Y') if p.birth_date else None,
                'death_date': p.death_date.strftime('%d.%m.%Y') if p.death_date else None,
                'city': p.city,
                'gender': p.gender
            })
            if p.father_id:
                edges.append({'from': p.father_id, 'to': p.id, 'arrows': 'to', 'label': 'отец'})
            if p.mother_id:
                edges.append({'from': p.mother_id, 'to': p.id, 'arrows': 'to', 'label': 'мать'})
        marriages = Marriage.query.join(Person, Person.id == Marriage.husband_id)\
                                 .filter(Person.tree_id == tree.id).all()
        for m in marriages:
            edges.append({
                'from': m.husband_id,
                'to': m.wife_id,
                'dashes': True,
                'label': 'брак',
                'color': {'color': 'red'}
            })
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='tree', nodes=nodes, edges=edges)

    if view == 'list':
        root_persons = tree.root_persons()
        return render_template('tree_detail.html', tree=tree, persons=persons,
                               view='list', root_persons=root_persons)

    return render_template('tree_detail.html', tree=tree, persons=persons, view='table')

# -------------------- ДОБАВЛЕНИЕ ПЕРСОНЫ --------------------
@app.route('/person/add', methods=['GET', 'POST'])
@login_required
def add_person():
    tree = current_user.tree
    if request.method == 'POST':
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form['gender']
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type=None, parent_id=None,
                                   second_parent_id=None, marriage_date=None)

        person = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=birth_date,
            death_date=datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None,
            city=city
        )
        db.session.add(person)
        db.session.commit()
        flash('Персона добавлена', 'success')
        return redirect(url_for('person_detail', person_id=person.id))

    return render_template('add_person.html', tree=tree)

# -------------------- КАРТОЧКА ПЕРСОНЫ --------------------
@app.route('/person/<int:person_id>')
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

# -------------------- РЕДАКТИРОВАНИЕ --------------------
@app.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_person(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        person.surname = request.form['surname'].strip()
        person.name = request.form['name'].strip()
        person.patronymic = request.form.get('patronymic', '').strip() or None
        person.gender = request.form['gender']
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        person.city = request.form.get('city', '').strip()
        person.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        person.death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None

        father_id = request.form.get('father_id')
        mother_id = request.form.get('mother_id')
        person.father_id = int(father_id) if father_id else None
        person.mother_id = int(mother_id) if mother_id else None

        db.session.commit()
        flash('Данные обновлены', 'success')
        return redirect(url_for('person_detail', person_id=person.id))

    all_persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_person.html', tree=tree, person=person, all_persons=all_persons, edit=True)

# -------------------- БРАК --------------------
@app.route('/marriage/add', methods=['GET', 'POST'])
@login_required
def add_marriage():
    tree = current_user.tree
    if request.method == 'POST':
        husband_id = int(request.form['husband_id'])
        wife_id = int(request.form['wife_id'])
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
        return redirect(url_for('tree_detail'))
    persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_marriage.html', tree=tree, persons=persons)

# -------------------- РЕБЁНОК --------------------
@app.route('/person/<int:person_id>/add_child', methods=['GET', 'POST'])
@login_required
def add_child(person_id):
    tree = current_user.tree
    parent = Person.query.get_or_404(person_id)
    if parent.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form['gender']
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()
        second_parent_id = request.form.get('second_parent_id')

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type='child', parent_id=parent.id,
                                   second_parent_id=second_parent_id,
                                   marriage_date=None)

        child = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=birth_date,
            death_date=death_date,
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
        return redirect(url_for('person_detail', person_id=parent.id))

    spouses = parent.spouses
    return render_template('add_child.html', tree=tree, parent=parent, spouses=spouses)

# -------------------- СУПРУГ --------------------
@app.route('/person/<int:person_id>/add_spouse', methods=['GET', 'POST'])
@login_required
def add_spouse(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    opposite_gender = 'F' if person.gender == 'M' else 'M'

    if request.method == 'POST':
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()
        marriage_date_str = request.form.get('marriage_date')

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=opposite_gender,
                                   birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type='spouse', parent_id=person.id,
                                   second_parent_id=None,
                                   marriage_date=marriage_date_str)

        spouse = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=opposite_gender,
            birth_date=birth_date,
            death_date=death_date,
            city=city
        )
        db.session.add(spouse)
        db.session.flush()
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None
        if person.gender == 'M':
            marriage = Marriage(husband_id=person.id, wife_id=spouse.id, marriage_date=marriage_date)
        else:
            marriage = Marriage(husband_id=spouse.id, wife_id=person.id, marriage_date=marriage_date)
        db.session.add(marriage)
        db.session.commit()
        flash('Супруг(а) добавлен(а)', 'success')
        return redirect(url_for('person_detail', person_id=person.id))

    return render_template('add_spouse.html', tree=tree, person=person, opposite_gender=opposite_gender)

# -------------------- РОДИТЕЛЬ --------------------
@app.route('/person/<int:person_id>/add_parent', methods=['GET', 'POST'])
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
        return redirect(url_for('person_detail', person_id=child.id))
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

        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type='parent', parent_id=child.id,
                                   second_parent_id=None, marriage_date=None)

        parent = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=birth_date,
            death_date=datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None,
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
        return redirect(url_for('person_detail', person_id=child.id))

    return render_template('add_parent.html', tree=tree, person=child, missing_gender=missing_gender)

# -------------------- БРАТ/СЕСТРА --------------------
@app.route('/person/<int:person_id>/add_sibling', methods=['GET', 'POST'])
@login_required
def add_sibling(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form['gender']
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type='sibling', parent_id=person.id,
                                   second_parent_id=None, marriage_date=None)

        sibling = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=birth_date,
            death_date=death_date,
            city=city
        )
        if person.father or person.mother:
            # Если есть родители, связываем через них
            sibling.father_id = person.father_id
            sibling.mother_id = person.mother_id
        else:
            # Родителей нет – создадим явную связь
            db.session.add(sibling)
            db.session.flush()
            # Упорядочиваем id для соблюдения unique constraint
            pid1, pid2 = sorted([person.id, sibling.id])
            link = SiblingLink(person1_id=pid1, person2_id=pid2, tree_id=tree.id)
            db.session.add(link)
            db.session.commit()
            flash(f'{"Брат" if gender == "M" else "Сестра"} добавлен(а) как предполагаемый родственник', 'success')
            return redirect(url_for('person_detail', person_id=person.id))

        db.session.add(sibling)
        db.session.commit()
        flash('Брат/сестра добавлен(а)', 'success')
        return redirect(url_for('person_detail', person_id=person.id))

    return render_template('add_sibling.html', tree=tree, person=person)

# ---- УДАЛЕНИЕ ЯВНОЙ СВЯЗИ С БРАТОМ/СЕСТРОЙ ----
@app.route('/person/<int:person_id>/remove_sibling/<int:sibling_id>', methods=['POST'])
@login_required
def remove_sibling(person_id, sibling_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    sibling = Person.query.get_or_404(sibling_id)
    if person.tree_id != tree.id or sibling.tree_id != tree.id:
        abort(403)

    # Удаляем явную связь, если она есть
    pid1, pid2 = sorted([person.id, sibling.id])
    link = SiblingLink.query.filter_by(person1_id=pid1, person2_id=pid2, tree_id=tree.id).first()
    if link:
        db.session.delete(link)
        db.session.commit()
        flash('Связь брата/сестры удалена', 'success')
    else:
        flash('Явная связь не найдена', 'warning')
    return redirect(url_for('person_detail', person_id=person.id))

# -------------------- ПРИЁМНЫЙ РОДИТЕЛЬ --------------------
@app.route('/person/<int:person_id>/add_step_parent', methods=['GET', 'POST'])
@login_required
def add_step_parent(person_id):
    tree = current_user.tree
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        abort(403)

    if request.method == 'POST':
        parent_id = int(request.form['parent_id'])
        parent = Person.query.get_or_404(parent_id)
        if parent.tree_id != tree.id or parent.id not in [person.father_id, person.mother_id]:
            abort(403)

        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = 'F' if parent.gender == 'M' else 'M'
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()
        marriage_date_str = request.form.get('marriage_date')

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        duplicates = find_duplicates(surname, name, patronymic, birth_date, tree)
        if duplicates['own'] or duplicates['others']:
            return render_template('confirm_person.html', tree=tree,
                                   surname=surname, name=name, patronymic=patronymic,
                                   gender=gender, birth_date=birth_date_str,
                                   death_date=death_date_str, city=city,
                                   duplicates=duplicates,
                                   person_type='step_parent', parent_id=parent.id,
                                   second_parent_id=None, marriage_date=marriage_date_str,
                                   original_person_id=person.id)

        spouse = Person(
            tree_id=tree.id,
            surname=surname,
            name=name,
            patronymic=patronymic,
            gender=gender,
            birth_date=birth_date,
            death_date=death_date,
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
        return redirect(url_for('person_detail', person_id=person.id))

    available_parents = [p for p in (person.father, person.mother) if p]
    return render_template('add_step_parent.html', tree=tree, person=person, available_parents=available_parents)

# -------------------- УДАЛЕНИЕ СВЯЗИ С РОДИТЕЛЕМ --------------------
@app.route('/person/<int:person_id>/remove_parent/<int:parent_id>', methods=['POST'])
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
    return redirect(url_for('person_detail', person_id=person.id))

# -------------------- ПОДТВЕРЖДЕНИЕ ДУБЛИКАТОВ --------------------
@app.route('/confirm_person', methods=['POST'])
@login_required
def confirm_person():
    tree = current_user.tree
    action = request.form.get('action')
    if action == 'cancel':
        flash('Добавление отменено', 'info')
        return redirect(url_for('tree_detail'))

    surname = request.form['surname'].strip()
    name = request.form['name'].strip()
    patronymic = request.form.get('patronymic', '').strip() or None
    gender = request.form['gender']
    birth_date_str = request.form.get('birth_date')
    death_date_str = request.form.get('death_date')
    city = request.form.get('city', '').strip()
    person_type = request.form.get('person_type')
    parent_id = request.form.get('parent_id')
    second_parent_id = request.form.get('second_parent_id')
    marriage_date_str = request.form.get('marriage_date')
    original_person_id = request.form.get('original_person_id')

    birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
    death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None
    marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

    person = Person(
        tree_id=tree.id,
        surname=surname,
        name=name,
        patronymic=patronymic,
        gender=gender,
        birth_date=birth_date,
        death_date=death_date,
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
                marriage = Marriage(husband_id=current_person.id, wife_id=person.id,
                                    marriage_date=marriage_date)
            else:
                marriage = Marriage(husband_id=person.id, wife_id=current_person.id,
                                    marriage_date=marriage_date)
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
    return redirect(url_for('person_detail', person_id=parent_id if parent_id else person.id))

# -------------------- УДАЛЕНИЕ ПЕРСОНЫ --------------------
@app.route('/person/<int:person_id>/delete', methods=['POST'])
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
    return redirect(url_for('tree_detail'))

# -------------------- СОЗДАНИЕ ТАБЛИЦ --------------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)