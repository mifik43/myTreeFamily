import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Tree, Person, Marriage
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'genealogy.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- АВТОРИЗАЦИЯ ----
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html')
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна. Войдите.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---- ГЛАВНАЯ (список деревьев) ----
@app.route('/')
def index():
    if current_user.is_authenticated:
        trees = Tree.query.filter_by(user_id=current_user.id).all()
        return render_template('index.html', trees=trees)
    return redirect(url_for('login'))

@app.route('/tree/create', methods=['POST'])
@login_required
def create_tree():
    name = request.form['name'].strip()
    if not name:
        flash('Название дерева не может быть пустым', 'danger')
        return redirect(url_for('index'))
    tree = Tree(name=name, user_id=current_user.id)
    db.session.add(tree)
    db.session.commit()
    flash(f'Дерево "{name}" создано', 'success')
    return redirect(url_for('index'))

# ---- РАБОТА С ДЕРЕВОМ (просмотр) ----
@app.route('/tree/<int:tree_id>')
@login_required
def tree_detail(tree_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('tree_detail.html', tree=tree, persons=persons)

# ---- ДОБАВЛЕНИЕ ПЕРСОНЫ ----
@app.route('/tree/<int:tree_id>/person/add', methods=['GET', 'POST'])
@login_required
def add_person(tree_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        surname = request.form['surname'].strip()
        name = request.form['name'].strip()
        patronymic = request.form.get('patronymic', '').strip() or None
        gender = request.form['gender']  # 'M' или 'F'
        birth_date_str = request.form.get('birth_date')
        death_date_str = request.form.get('death_date')
        city = request.form.get('city', '').strip()

        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d').date() if death_date_str else None

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
        db.session.commit()
        flash('Персона добавлена. Теперь можно указать родителей и супругов.', 'success')
        return redirect(url_for('person_detail', tree_id=tree.id, person_id=person.id))

    return render_template('add_person.html', tree=tree)

# ---- КАРТОЧКА ПЕРСОНЫ ----
@app.route('/tree/<int:tree_id>/person/<int:person_id>')
@login_required
def person_detail(tree_id, person_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        flash('Персона не принадлежит этому дереву', 'danger')
        return redirect(url_for('tree_detail', tree_id=tree.id))

    # получаем детей (объединяем children_father и children_mother)
    children = set(person.children_father + person.children_mother)
    return render_template('person.html', tree=tree, person=person,
                           parents=[p for p in (person.father, person.mother) if p],
                           children=children,
                           spouses=person.spouses,
                           siblings=person.siblings)

# ---- РЕДАКТИРОВАНИЕ ПЕРСОНЫ ----
@app.route('/tree/<int:tree_id>/person/<int:person_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_person(tree_id, person_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        flash('Неверное дерево', 'danger')
        return redirect(url_for('tree_detail', tree_id=tree.id))

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

        # Родители: выбор из списка людей дерева
        father_id = request.form.get('father_id')
        mother_id = request.form.get('mother_id')
        person.father_id = int(father_id) if father_id else None
        person.mother_id = int(mother_id) if mother_id else None

        db.session.commit()
        flash('Данные обновлены', 'success')
        return redirect(url_for('person_detail', tree_id=tree.id, person_id=person.id))

    all_persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_person.html', tree=tree, person=person, all_persons=all_persons, edit=True)

# ---- ДОБАВЛЕНИЕ БРАКА ----
@app.route('/tree/<int:tree_id>/marriage/add', methods=['GET', 'POST'])
@login_required
def add_marriage(tree_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        husband_id = int(request.form['husband_id'])
        wife_id = int(request.form['wife_id'])
        marriage_date_str = request.form.get('marriage_date')
        marriage_date = datetime.strptime(marriage_date_str, '%Y-%m-%d').date() if marriage_date_str else None

        # Проверка, что обе персоны в этом дереве
        h = Person.query.get(husband_id)
        w = Person.query.get(wife_id)
        if h.tree_id != tree.id or w.tree_id != tree.id:
            flash('Ошибка: персоны из разных деревьев', 'danger')
            return redirect(url_for('tree_detail', tree_id=tree.id))
        if h.gender != 'M' or w.gender != 'F':
            flash('Брак возможен только между мужчиной и женщиной', 'warning')
        marriage = Marriage(husband_id=husband_id, wife_id=wife_id, marriage_date=marriage_date)
        db.session.add(marriage)
        db.session.commit()
        flash('Брак добавлен', 'success')
        return redirect(url_for('tree_detail', tree_id=tree.id))

    persons = Person.query.filter_by(tree_id=tree.id).order_by(Person.surname, Person.name).all()
    return render_template('add_marriage.html', tree=tree, persons=persons)

# ---- УДАЛЕНИЕ (по желанию) ----
@app.route('/tree/<int:tree_id>/person/<int:person_id>/delete', methods=['POST'])
@login_required
def delete_person(tree_id, person_id):
    tree = Tree.query.get_or_404(tree_id)
    if tree.user_id != current_user.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    person = Person.query.get_or_404(person_id)
    if person.tree_id != tree.id:
        flash('Ошибка', 'danger')
        return redirect(url_for('tree_detail', tree_id=tree.id))
    # Удаляем связанные браки, устанавливаем родителей в NULL для детей
    Marriage.query.filter((Marriage.husband_id == person.id) | (Marriage.wife_id == person.id)).delete()
    # Обнуляем ссылки на родителей у детей
    Person.query.filter_by(father_id=person.id).update({Person.father_id: None})
    Person.query.filter_by(mother_id=person.id).update({Person.mother_id: None})
    db.session.delete(person)
    db.session.commit()
    flash('Персона удалена', 'success')
    return redirect(url_for('tree_detail', tree_id=tree.id))

# ---- СОЗДАНИЕ ТАБЛИЦ ----
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)