from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Tree, Person

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
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

        person = Person(
            tree_id=tree.id,
            surname=surname, name=name, patronymic=patronymic, gender=gender,
            birth_year=None, birth_month=None, birth_day=None, birth_notes=None,
            death_year=None, death_month=None, death_day=None, death_notes=None,
            city=None
        )
        db.session.add(person)
        db.session.commit()

        login_user(user)
        flash('Регистрация успешна! Ваше дерево создано.', 'success')
        return redirect(url_for('main.tree_detail'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('main.tree_detail'))
        flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        current_user.email = email or None
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('main.tree_detail'))
    return render_template('profile.html', user=current_user)