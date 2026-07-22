from datetime import datetime
import hashlib
import hmac
import os

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_user, logout_user
from flask_login.utils import login_required
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import aliased
from werkzeug.security import check_password_hash, generate_password_hash

from main import app, db
from main.models import (
    Chat,
    Entry,
    EntryLike,
    EntryReply,
    Notification,
    Thread,
    User,
    UserRelationship,
)


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


UPLOAD_FOLDER = 'main/static/imgs/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def ensure_phase3_schema():
    with app.app_context():
        db.create_all()
        if db.engine.url.get_backend_name() != 'sqlite':
            return

        user_columns = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(user)")).fetchall()
        }
        additions = {
            'bio': 'ALTER TABLE user ADD COLUMN bio TEXT',
            'portfolio_url': 'ALTER TABLE user ADD COLUMN portfolio_url TEXT',
            'skills': 'ALTER TABLE user ADD COLUMN skills TEXT',
        }
        for column, sql in additions.items():
            if column not in user_columns:
                db.session.execute(text(sql))
        db.session.commit()


ensure_phase3_schema()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def wants_json_response():
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )


def make_password_hash(password):
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password_hash(saved_hash, password):
    try:
        return check_password_hash(saved_hash, password)
    except ValueError:
        parts = (saved_hash or '').split('$')
        if len(parts) != 3 or parts[0] != 'sha256':
            return False
        _, salt, expected = parts
        actual = hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()
        return hmac.compare_digest(actual, expected)


def notify_user(user_id, actor_user_id, kind, message, entry_id=None, reply_id=None, chat_id=None):
    if not user_id or user_id == actor_user_id:
        return
    db.session.add(Notification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        kind=kind,
        message=message,
        entry_id=entry_id,
        reply_id=reply_id,
        chat_id=chat_id,
    ))


def unread_notification_count():
    if not current_user.is_authenticated:
        return 0
    return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()


@app.context_processor
def inject_notification_count():
    return {'unread_notification_count': unread_notification_count()}


def reply_to_dict(reply):
    return {
        'id': reply.id,
        'entry_id': reply.entry_id,
        'username': reply.username,
        'body': reply.body,
        'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    }


def entry_to_dict(entry):
    likes_count = EntryLike.query.filter_by(entry_id=entry.id).count()
    liked = EntryLike.query.filter_by(entry_id=entry.id, user_id=current_user.id).first() is not None
    replies = EntryReply.query.filter_by(entry_id=entry.id).order_by(EntryReply.created_at.asc()).all()
    return {
        'id': entry.id,
        'name': entry.name,
        'article': entry.article,
        'date': entry.date.replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S'),
        'send_user_id': entry.send_user_id,
        'can_delete': entry.send_user_id == current_user.id,
        'likes_count': likes_count,
        'liked_by_current_user': liked,
        'replies': [reply_to_dict(reply) for reply in replies],
    }


def chat_to_dict(chat):
    sender = User.query.get(chat.from_user_id)
    return {
        'id': chat.id,
        'from_user_id': chat.from_user_id,
        'to_user_id': chat.to_user_id,
        'message': chat.message,
        'time': chat.create_date.strftime('%H:%M'),
        'username': sender.username if sender else 'Unknown',
        'mine': chat.from_user_id == current_user.id,
    }


def user_search_results(username):
    follow = aliased(UserRelationship)
    follower = aliased(UserRelationship)
    return User.query.filter(User.username.like(f'%{username}%'))\
        .outerjoin(follow, and_(
            follow.from_user_id == current_user.id,
            follow.to_user_id == User.id,
        ))\
        .outerjoin(follower, and_(
            follower.from_user_id == User.id,
            follower.to_user_id == current_user.id,
        ))\
        .with_entities(
            User.id,
            User.username,
            User.picture_path,
            User.bio,
            User.portfolio_url,
            User.skills,
            follow.state.label('state_from_currentuser'),
            follower.state.label('state_from_opponentuser'),
        )\
        .all()


@app.route('/', methods=['GET'])
@login_required
def top():
    return bbs()


@app.route('/index', methods=['GET'])
@login_required
def bbs():
    threads = Thread.query.all()
    return render_template('bbs.html', threads=threads, page_title='BBS')


@app.route('/thread', methods=['POST', 'GET'])
@login_required
def thread():
    thread_get = request.form.get('thread') or request.args.get('thread')
    if not thread_get:
        return redirect(url_for('bbs'))

    thread_record = Thread.query.filter_by(threadname=thread_get).first()
    if thread_record is None:
        thread_record = Thread(thread_get)
        db.session.add(thread_record)
        db.session.commit()

    articles = Entry.query.filter_by(thread_id=thread_record.id).order_by(Entry.date.asc()).all()
    return render_template(
        'thread.html',
        articles=articles,
        thread=thread_get,
        page_title='スレッド',
        entry_payload=[entry_to_dict(entry) for entry in articles],
    )


@app.route('/add', methods=['POST'])
@login_required
def add_entry():
    thread_name = request.form['thread']
    thread_record = Thread.query.filter_by(threadname=thread_name).first()
    if thread_record is None:
        message = 'スレッドが見つかりません'
        if wants_json_response():
            return jsonify({'ok': False, 'message': message}), 404
        flash(message)
        return redirect(url_for('bbs'))

    entry = Entry(
        date=datetime.now(),
        name=current_user.username,
        article=request.form['article'],
        thread_id=thread_record.id,
        send_user_id=current_user.id,
    )
    db.session.add(entry)
    db.session.commit()

    if wants_json_response():
        return jsonify({'ok': True, 'message': '投稿しました', 'entry': entry_to_dict(entry)})
    return render_template('result.html', article=entry.article, thread=thread_record)


@app.route('/delete_entry/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if entry.send_user_id != current_user.id:
        message = '自分の投稿だけ削除できます'
        if wants_json_response():
            return jsonify({'ok': False, 'message': message}), 403
        flash(message)
        return redirect(url_for('bbs'))

    db.session.delete(entry)
    db.session.commit()

    if wants_json_response():
        return jsonify({'ok': True, 'message': '投稿を削除しました', 'entry_id': entry_id})
    return redirect(url_for('bbs'))


@app.route('/entries/search', methods=['GET'])
@login_required
def search_entries():
    thread_name = request.args.get('thread', '')
    keyword = request.args.get('q', '').strip()
    thread_record = Thread.query.filter_by(threadname=thread_name).first_or_404()

    query = Entry.query.filter_by(thread_id=thread_record.id)
    if keyword:
        query = query.filter(Entry.article.like(f'%{keyword}%'))
    entries = query.order_by(Entry.date.asc()).all()

    return jsonify({
        'ok': True,
        'entries': [entry_to_dict(entry) for entry in entries],
        'count': len(entries),
    })


@app.route('/entry/<int:entry_id>/like', methods=['POST'])
@login_required
def toggle_like(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    like = EntryLike.query.filter_by(entry_id=entry.id, user_id=current_user.id).first()
    liked = like is None
    if like is None:
        db.session.add(EntryLike(entry_id=entry.id, user_id=current_user.id))
        notify_user(
            entry.send_user_id,
            current_user.id,
            'like',
            f'{current_user.username}さんがあなたの投稿にいいねしました',
            entry_id=entry.id,
        )
    else:
        db.session.delete(like)
    db.session.commit()

    return jsonify({
        'ok': True,
        'message': 'いいねしました' if liked else 'いいねを取り消しました',
        'liked': liked,
        'likes_count': EntryLike.query.filter_by(entry_id=entry.id).count(),
    })


@app.route('/entry/<int:entry_id>/reply', methods=['POST'])
@login_required
def add_reply(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    body = (request.form.get('body') or '').strip()
    if not body:
        return jsonify({'ok': False, 'message': '返信内容を入力してください'}), 400

    reply = EntryReply(
        entry_id=entry.id,
        user_id=current_user.id,
        username=current_user.username,
        body=body,
    )
    db.session.add(reply)
    db.session.flush()
    notify_user(
        entry.send_user_id,
        current_user.id,
        'reply',
        f'{current_user.username}さんがあなたの投稿に返信しました',
        entry_id=entry.id,
        reply_id=reply.id,
    )
    db.session.commit()
    return jsonify({'ok': True, 'message': '返信しました', 'reply': reply_to_dict(reply)})


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        login_user_id = request.form.get('login_user_id')
        password = request.form.get('password')

        existed_check = User.query.filter_by(login_user_id=login_user_id).first()
        if existed_check:
            flash('登録済みのユーザーIDです')
            return render_template('signup.html')

        user = User(
            username=username,
            login_user_id=login_user_id,
            password=make_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return redirect('/login')

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_user_id = request.form.get('login_user_id')
        password = request.form.get('password')
        user = User.query.filter_by(login_user_id=login_user_id).first()

        if user is None:
            flash('ユーザーが存在しません')
        elif verify_password_hash(user.password, password):
            login_user(user)
            return redirect('/')
        else:
            flash('パスワードが違います')
        return render_template('/login.html')

    return render_template('/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


@login_manager.unauthorized_handler
def unauthorized():
    return redirect('/login')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        login_user_id = request.form.get('login_user_id')
        user = User.query.filter_by(login_user_id=login_user_id).first()
        if user is not None:
            new_password = request.form.get('new_password')
            user.password = make_password_hash(new_password)
            db.session.commit()
            return redirect('/login')

        flash('ユーザーが存在しません')
        return render_template('/forgot_password.html')

    return render_template('/forgot_password.html')


@app.route('/setting', methods=['GET', 'POST'])
@login_required
def setting():
    user = User.query.filter_by(login_user_id=current_user.login_user_id).first()
    if request.method == 'POST':
        if user is not None:
            name = request.form.get('user_name')
            login_user_id = request.form.get('login_user_id')
            if name:
                user.username = name
            if login_user_id:
                user.login_user_id = login_user_id
            user.bio = request.form.get('bio')
            user.portfolio_url = request.form.get('portfolio_url')
            user.skills = request.form.get('skills')

            file = request.files.get('file')
            if file and allowed_file(file.filename):
                _, ext = os.path.splitext(file.filename)
                file_name = current_user.login_user_id + ext.lower()
                filepath = UPLOAD_FOLDER + file_name
                file.save(filepath)
                user.picture_path = 'imgs/' + file_name

        db.session.commit()
        flash('更新しました')
        return render_template('/setting.html')

    return render_template('/setting.html')


@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    entries = Entry.query.filter_by(send_user_id=user.id).order_by(Entry.date.desc()).limit(10).all()
    likes_count = db.session.query(EntryLike).join(Entry).filter(Entry.send_user_id == user.id).count()
    follow_count = UserRelationship.query.filter_by(from_user_id=user.id).count()
    follower_count = UserRelationship.query.filter_by(to_user_id=user.id).count()
    return render_template(
        'profile.html',
        user=user,
        entries=entries,
        likes_count=likes_count,
        follow_count=follow_count,
        follower_count=follower_count,
        page_title=f'{user.username}のポートフォリオ',
    )


@app.route('/user_search', methods=['GET', 'POST'])
@login_required
def user_search():
    users = None
    if request.method == 'POST':
        username = request.form.get('username') or ''
        users = user_search_results(username)
        if wants_json_response():
            return jsonify({
                'ok': True,
                'users': [{
                    'id': user.id,
                    'username': user.username,
                    'picture_url': url_for('static', filename=user.picture_path or 'imgs/no_img.png'),
                    'profile_url': url_for('profile', user_id=user.id),
                    'chat_url': url_for('chat', friend_id=user.id),
                    'bio': user.bio,
                    'skills': user.skills,
                    'is_current_user': user.id == current_user.id,
                    'state_from_currentuser': user.state_from_currentuser,
                    'state_from_opponentuser': user.state_from_opponentuser,
                } for user in users],
                'count': len(users),
                'message': '検索しました' if users else 'ユーザーが見つかりません',
            })
        if users:
            return render_template('user_search.html', users=users)
        flash('ユーザーが存在しません')

    return render_template('user_search.html', users=users)


@app.route('/follow', methods=['POST'])
@login_required
def follow():
    from_user_id = current_user.id
    to_user_id = request.form.get('to_user_id')

    existed = UserRelationship.query.filter(
        and_(
            UserRelationship.from_user_id == from_user_id,
            UserRelationship.to_user_id == to_user_id,
        )
    ).first()
    if existed is None:
        db.session.add(UserRelationship(from_user_id, to_user_id, state=1))
        notify_user(
            int(to_user_id),
            current_user.id,
            'follow',
            f'{current_user.username}さんがあなたをフォローしました',
        )
        db.session.commit()

    flash('フォローしました')
    return redirect(url_for('user_search'))


@app.route('/follow_lift', methods=['POST'])
@login_required
def follow_lift():
    opponent_id = request.form.get('opponent_id')
    lift = UserRelationship.query.filter(
        and_(
            UserRelationship.from_user_id == current_user.id,
            UserRelationship.to_user_id == opponent_id,
        )
    ).first()
    if lift is not None:
        db.session.delete(lift)
        db.session.commit()
    return redirect(url_for('bbs'))


@app.route('/follow_state', methods=['GET', 'POST'])
@login_required
def follow_management():
    follow_users = User.query.join(
        UserRelationship,
        and_(
            UserRelationship.from_user_id == current_user.id,
            UserRelationship.to_user_id == User.id,
        ),
    ).all()

    follower_users = User.query.join(
        UserRelationship,
        and_(
            UserRelationship.from_user_id == User.id,
            UserRelationship.to_user_id == current_user.id,
        ),
    ).all()

    return render_template(
        'follow_management.html',
        follow_users=follow_users,
        follower_users=follower_users,
    )


@app.route('/chat/<friend_id>', methods=['GET', 'POST'])
@login_required
def chat(friend_id):
    friend = User.query.filter_by(id=friend_id).first_or_404()
    messages = Chat.query.filter(or_(
        and_(Chat.from_user_id == current_user.id, Chat.to_user_id == friend.id),
        and_(Chat.from_user_id == friend.id, Chat.to_user_id == current_user.id),
    )).order_by(Chat.create_date.asc()).all()

    if request.method == 'POST':
        message = (request.form.get('message') or '').strip()
        if not message:
            if wants_json_response():
                return jsonify({'ok': False, 'message': 'メッセージを入力してください'}), 400
            flash('メッセージを入力してください')
            return redirect(url_for('chat', friend_id=friend_id))

        chat_message = Chat(from_user_id=current_user.id, to_user_id=friend_id, message=message)
        db.session.add(chat_message)
        db.session.flush()
        notify_user(
            int(friend_id),
            current_user.id,
            'dm',
            f'{current_user.username}さんからDMが届きました',
            chat_id=chat_message.id,
        )
        db.session.commit()
        if wants_json_response():
            return jsonify({'ok': True, 'message': 'DMを送信しました', 'chat': chat_to_dict(chat_message)})
        return redirect(url_for('chat', friend_id=friend_id))

    return render_template('chat.html', friend=friend, messages=messages)


@app.route('/notifications')
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', notifications=items, page_title='通知')


@app.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    if wants_json_response():
        return jsonify({'ok': True, 'message': '通知を既読にしました'})
    return redirect(url_for('notifications'))
