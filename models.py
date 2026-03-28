from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(20), nullable=False, default='student')  # student / faculty / admin
    course     = db.Column(db.String(100), nullable=True)
    year       = db.Column(db.Integer, nullable=True)
    department = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ FIX: clear relationship name
    submissions = db.relationship(
        'Submission',
        backref='user',   # <-- THIS is important (used in HTML)
        lazy=True,
        foreign_keys='Submission.user_id'
    )

    def __repr__(self):
        return f'<User {self.username}>'


class Submission(db.Model):
    __tablename__ = 'submissions'

    id                = db.Column(db.Integer, primary_key=True)
    title             = db.Column(db.String(200), nullable=False)
    description       = db.Column(db.Text, nullable=True)
    filename          = db.Column(db.String(300), nullable=False)
    original_filename = db.Column(db.String(300), nullable=False)
    submitted_at      = db.Column(db.DateTime, default=datetime.utcnow)
    grade             = db.Column(db.String(10), nullable=True)
    comments          = db.Column(db.Text, nullable=True)

    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ✅ faculty relationship (already correct)
    faculty = db.relationship('User', foreign_keys=[faculty_id])

    def __repr__(self):
        return f'<Submission {self.title}>'