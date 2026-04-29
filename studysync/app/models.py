from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utc_now():
	return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
	__tablename__ = "users"

	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(80), unique=True, nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=True)
	password_hash = db.Column(db.String(255), nullable=False)
	created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

	created_teams = db.relationship("Team", back_populates="created_by_user", cascade="all, delete-orphan")
	memberships = db.relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")

	def set_password(self, password):
		self.password_hash = generate_password_hash(password)

	def check_password(self, password):
		return check_password_hash(self.password_hash, password)


class Team(db.Model):
	__tablename__ = "teams"

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	description = db.Column(db.Text, nullable=True)
	code = db.Column(db.String(32), unique=True, nullable=False)
	created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
	created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

	created_by_user = db.relationship("User", back_populates="created_teams")
	members = db.relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(db.Model):
	__tablename__ = "team_members"
	__table_args__ = (
		db.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
	)

	id = db.Column(db.Integer, primary_key=True)
	team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
	user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
	role = db.Column(db.String(20), nullable=False, default="member")
	joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

	team = db.relationship("Team", back_populates="members")
	user = db.relationship("User", back_populates="memberships")


def is_team_member(team_id, user_id):
	return (
		TeamMember.query.filter_by(team_id=team_id, user_id=user_id).first() is not None
	)


def is_team_leader(team_id, user_id):
	return (
		TeamMember.query.filter_by(team_id=team_id, user_id=user_id, role="leader").first()
		is not None
	)

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    priority = db.Column(db.String(20), nullable=False, default="medium")  # low / medium / high
    status = db.Column(db.String(20), nullable=False, default="todo")      # todo / in_progress / done
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)  # NULL = personal task
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", backref=db.backref("tasks", lazy=True))
    team = db.relationship("Team", backref=db.backref("tasks", lazy=True))

class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)

    action_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", backref=db.backref("activities", lazy=True))
    team = db.relationship("Team", backref=db.backref("activities", lazy=True))
    task = db.relationship("Task", backref=db.backref("activities", lazy=True))
