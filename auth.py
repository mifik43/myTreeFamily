import secrets
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from models import db, User, Tree, TreePermission, Person, Invite
from app import mail   # или from your_app import mail

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    invite_token = request.args.get('invite', '').strip()
    invite = None
    if invite_token:
        invite = Invite.query.filter_by(token=invite_token).first()
        if not invite:
            flash('Неверная ссылка приглашения', 'danger')
            invite_token = None

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form.get('email', '').strip() or None
        surname = request.form.get('surname', '').strip() or None
        name = request.form.get('name', '').strip() or None
        gender = request.form.get('gender', 'M')
        maiden_name = request.form.get('maiden_name', '').strip() or None

        if not email:
            flash('Email обязателен', 'danger')
            return render_template('register.html', invite_token=invite_token)

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html', invite_token=invite_token)
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return render_template('register.html', invite_token=invite_token)

        token = secrets.token_urlsafe(32)
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
            surname=surname, name=name, gender=gender, maiden_name=maiden_name,
            confirmation_token=token,
            is_confirmed=False
        )
        db.session.add(user)
        db.session.flush()

        if invite:
            tree_id = invite.tree_id
            tree_name = invite.tree.name
            tp = TreePermission(user_id=user.id, tree_id=tree_id, role='editor')
            db.session.add(tp)
            db.session.delete(invite)
            db.session.commit()
        else:
            tree = Tree(name=f'Род {surname}' if surname else 'Моё дерево', user_id=user.id)
            db.session.add(tree)
            db.session.flush()
            tp = TreePermission(user_id=user.id, tree_id=tree.id, role='owner')
            db.session.add(tp)
            if surname and name:
                person = Person(tree_id=tree.id, surname=surname, name=name, gender=gender)
                db.session.add(person)
            db.session.commit()

        # Отправляем подтверждение
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        msg = Message('Подтверждение регистрации',
                      recipients=[email])
        msg.body = f'''Здравствуйте!

Вы зарегистрировались на сайте "Семейное древо". Пожалуйста, подтвердите ваш email, перейдя по ссылке:
{confirm_url}

Если вы не регистрировались, проигнорируйте это письмо.'''
        try:
            mail.send(msg)
            flash('Регистрация успешна! На ваш email отправлено письмо с инструкцией.', 'success')
        except Exception as e:
            flash('Письмо не отправлено, но вы можете запросить его повторно позже.', 'warning')
            print(f'Confirmation URL: {confirm_url}')

        return redirect(url_for('auth.login'))

    return render_template('register.html', invite_token=invite_token,
                           invite_tree=invite.tree.name if invite else None)


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if not user or user.is_confirmed:
        flash('Неверная или устаревшая ссылка подтверждения.', 'danger')
        return redirect(url_for('auth.login'))

    user.is_confirmed = True
    user.confirmation_token = None
    db.session.commit()
    flash('Ваш email подтверждён! Теперь вы можете войти.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if not user.is_confirmed:
                flash('Ваш email ещё не подтверждён. Проверьте почту или запросите новое подтверждение.', 'warning')
                return render_template('login.html')
            login_user(user)
            perm = next((p for p in user.tree_permissions if p.role in ('owner', 'editor')), None)
            if perm:
                session['active_tree_id'] = perm.tree_id
            else:
                tree = Tree(name='Моё дерево', user_id=user.id)
                db.session.add(tree)
                db.session.flush()
                tp = TreePermission(user_id=user.id, tree_id=tree.id, role='owner')
                db.session.add(tp)
                db.session.commit()
                session['active_tree_id'] = tree.id
            return redirect(url_for('main.tree_detail'))
        flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('active_tree_id', None)
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


@auth_bp.route('/resend-confirmation', methods=['GET', 'POST'])
def resend_confirmation():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email, is_confirmed=False).first()
        if user:
            if not user.confirmation_token:
                user.confirmation_token = secrets.token_urlsafe(32)
                db.session.commit()
            confirm_url = url_for('auth.confirm_email', token=user.confirmation_token, _external=True)
            msg = Message('Подтверждение регистрации',
                          recipients=[email])
            msg.body = f'''Здравствуйте!

Пожалуйста, подтвердите ваш email, перейдя по ссылке:
{confirm_url}

Если вы не регистрировались, проигнорируйте это письмо.'''
            try:
                mail.send(msg)
                flash('Письмо с подтверждением отправлено повторно.', 'success')
            except Exception:
                flash('Не удалось отправить письмо. Попробуйте позже.', 'danger')
        else:
            flash('Пользователь с таким email не найден или уже подтверждён.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('resend_confirmation.html')