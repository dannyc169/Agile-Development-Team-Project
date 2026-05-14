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

    created_teams = db.relationship(
        "Team",
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    memberships = db.relationship(
        "TeamMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )

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
        TeamMember.query.filter_by(team_id=team_id, user_id=user_id).first()
        is not None
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
    priority = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="todo")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("tasks", lazy=True))
    team = db.relationship("Team", backref=db.backref("tasks", lazy=True))
    assigned_to_user = db.relationship("User", foreign_keys=[assigned_to_user_id], backref=db.backref("assigned_tasks", lazy=True))


class Subtask(db.Model):
    __tablename__ = "subtasks"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_done = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    task = db.relationship(
        "Task",
        backref=db.backref("subtasks", lazy=True, cascade="all, delete-orphan"),
    )


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


class ActivityLike(db.Model):
    __tablename__ = "activity_likes"
    __table_args__ = (
        db.UniqueConstraint("activity_id", "user_id", name="uq_activity_likes_activity_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    activity = db.relationship(
        "Activity",
        backref=db.backref("likes", lazy=True, cascade="all, delete-orphan"),
    )
    user = db.relationship(
        "User",
        backref=db.backref("activity_likes", lazy=True),
    )


class Nudge(db.Model):
    __tablename__ = "nudges"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    nudger_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    task = db.relationship(
        "Task",
        backref=db.backref("nudges", lazy=True, cascade="all, delete-orphan"),
    )
    team = db.relationship(
        "Team",
        backref=db.backref("nudges", lazy=True, cascade="all, delete-orphan"),
    )
    nudger = db.relationship(
        "User",
        foreign_keys=[nudger_id],
        backref=db.backref("sent_nudges", lazy=True),
    )
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        backref=db.backref("received_nudges", lazy=True),
    )


class Wager(db.Model):
    __tablename__ = "wagers"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    stake_amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    team = db.relationship("Team", backref="wagers")
    creator = db.relationship("User", backref="created_wagers")
    participants = db.relationship(
        "WagerParticipant",
        back_populates="wager",
        cascade="all, delete-orphan",
    )
    linked_tasks = db.relationship(
        "WagerTask",
        back_populates="wager",
        cascade="all, delete-orphan",
    )


class WagerParticipant(db.Model):
    __tablename__ = "wager_participants"
    __table_args__ = (
        db.UniqueConstraint("wager_id", "user_id", name="uq_wager_participants_wager_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    wager_id = db.Column(db.Integer, db.ForeignKey("wagers.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    progress = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="on_track")
    reward_amount = db.Column(db.Integer, nullable=False, default=0)

    wager = db.relationship("Wager", back_populates="participants")
    user = db.relationship("User", backref="wager_memberships")


class WagerTask(db.Model):
    __tablename__ = "wager_tasks"

    id = db.Column(db.Integer, primary_key=True)
    wager_id = db.Column(db.Integer, db.ForeignKey("wagers.id"), nullable=False)

    # old data compatibility
    task_name = db.Column(db.String(120), nullable=True)

    # new linkage
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)

    wager = db.relationship("Wager", back_populates="linked_tasks")
    task = db.relationship("Task", backref=db.backref("wager_links", lazy=True))
