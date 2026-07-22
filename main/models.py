from datetime import datetime

from flask_login import UserMixin

from main import db


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.now)
    name = db.Column(db.Text)
    article = db.Column(db.Text)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.id'), nullable=False)
    send_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    likes = db.relationship('EntryLike', backref='entry', lazy=True, cascade='all, delete-orphan')
    replies = db.relationship('EntryReply', backref='entry', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Entry id={self.id} name={self.name!r} thread_id={self.thread_id}>'


class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    threadname = db.Column(db.String(80), unique=True)
    articles = db.relationship('Entry', backref='thread', lazy=True)

    def __init__(self, threadname, articles=None):
        self.threadname = threadname
        self.articles = articles or []

    def __repr__(self):
        return f'<Thread id={self.id} threadname={self.threadname!r}>'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text)
    login_user_id = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))
    picture_path = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    portfolio_url = db.Column(db.Text, nullable=True)
    skills = db.Column(db.Text, nullable=True)


class UserRelationship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    state = db.Column(db.Integer, default=0)

    def __init__(self, from_user_id, to_user_id, state=0):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.state = state


class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    create_date = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, from_user_id, to_user_id, message):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.message = message


class EntryLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('entry_id', 'user_id', name='uq_entry_like_user'),
    )


class EntryReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.Text)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    kind = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=True)
    reply_id = db.Column(db.Integer, db.ForeignKey('entry_reply.id'), nullable=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


def init():
    db.create_all()
