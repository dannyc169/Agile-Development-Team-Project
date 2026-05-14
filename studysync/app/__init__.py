import os
from datetime import datetime, date, timezone

from flask import Flask, Response, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

from app.forms import ChangePasswordForm, LoginForm, RegisterForm, ResetPasswordForm


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    if not user_id or not user_id.isdigit():
        return None

    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)

    database_path = os.path.join(app.instance_path, "studysync.db")
    app.config.from_mapping(
        SECRET_KEY="dev-secret-key",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=True,
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"
    csrf.init_app(app)

    from app import models  # noqa: F401
    from app.models import (
        User,
        Team,
        TeamMember,
        Task,
        Wager,
        WagerParticipant,
        WagerTask,
        Subtask,  # noqa: F401
    )
    from app.teams import teams_bp
    from app.tasks import tasks_bp
    from app.feed import feed_bp
    from app.wager_helpers import (
        calculate_participant_status,
        calculate_reward_amount,
        calculate_total_points,
        calculate_wager_progress,
        count_wagers_won_for_user,
        resolve_linked_task,
        sync_wager_status,
    )

    app.register_blueprint(teams_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(feed_bp)

    def is_team_leader(team_id, user_id):
        return (
            TeamMember.query.filter_by(
                team_id=team_id,
                user_id=user_id,
                role="leader",
            ).first()
            is not None
        )

    def format_date(value):
        if not value:
            return ""

        return value.strftime("%Y-%m-%d")

    def avatar_color_for_index(index):
        colors = [
            "bg-purple-500",
            "bg-indigo-500",
            "bg-pink-500",
            "bg-orange-500",
            "bg-teal-500",
            "bg-blue-500",
        ]

        return colors[index % len(colors)]

    def participant_status_class(status):
        mapping = {
            "on_track": "bg-green-100 text-green-700",
            "completed": "bg-green-100 text-green-700",
            "at_risk": "bg-yellow-200 text-yellow-800",
            "failed": "bg-red-200 text-red-800",
        }

        return mapping.get(status, "bg-gray-100 text-gray-700")

    def participant_progress_class(status):
        mapping = {
            "on_track": "bg-green-500",
            "completed": "bg-green-500",
            "at_risk": "bg-yellow-500",
            "failed": "bg-red-500",
        }

        return mapping.get(status, "bg-gray-400")

    def participant_row_class(status):
        mapping = {
            "at_risk": "bg-yellow-50 hover:bg-yellow-100",
            "failed": "bg-red-50 hover:bg-red-100",
        }

        return mapping.get(status, "")

    def participant_name_class(status):
        return "line-through text-gray-500" if status == "failed" else "text-gray-900"

    def participant_done_class(status):
        return "line-through text-gray-600" if status == "failed" else "text-gray-600"

    def get_required_tasks_for_wager(wager):
        tasks = []

        for link in wager.linked_tasks:
            linked_task = resolve_linked_task(link, wager)

            title = (
                linked_task.title
                if linked_task is not None
                else (getattr(link, "task_name", None) or "Unknown Task")
            )

            done = linked_task is not None and linked_task.status == "done"

            tasks.append(
                {
                    "title": title,
                    "done": done,
                }
            )

        return tasks

    def calculate_wager_status_key(wager, status_counts, total_participants):
        today = date.today()

        if total_participants > 0 and status_counts["completed"] == total_participants:
            return "completed"

        if (
            wager.end_date is not None
            and today > wager.end_date
            and status_counts["completed"] < total_participants
        ):
            return "failed"

        if status_counts["at_risk"] > 0:
            return "at_risk"

        return "active"

    def calculate_wager_status_label(status_key):
        mapping = {
            "active": "ACTIVE",
            "completed": "COMPLETED",
            "failed": "FAILED",
            "at_risk": "AT RISK",
        }

        return mapping.get(status_key, "ACTIVE")

    def build_wager_view_data(wager):
        total_tasks, tasks_done_for_wager, progress_percent = calculate_wager_progress(wager)
        total_participants = len(wager.participants)
        today = date.today()

        participants_view = []
        status_counts = {
            "on_track": 0,
            "completed": 0,
            "at_risk": 0,
            "failed": 0,
        }

        for idx, participant in enumerate(wager.participants):
            display_status = calculate_participant_status(
                tasks_done_for_wager,
                total_tasks,
                wager.end_date,
            )

            display_reward = calculate_reward_amount(
                display_status,
                wager.stake_amount,
            )

            status_counts[display_status] += 1

            username = participant.user.username if participant.user else "Unknown"

            participants_view.append(
                {
                    "name": username,
                    "avatar": username[0].upper() if username else "?",
                    "avatar_color": avatar_color_for_index(idx),
                    "tasks_done": tasks_done_for_wager,
                    "tasks_total": total_tasks,
                    "progress": progress_percent,
                    "status": display_status.replace("_", " ").title(),
                    "status_class": participant_status_class(display_status),
                    "reward": display_reward,
                    "row_class": participant_row_class(display_status),
                    "name_class": participant_name_class(display_status),
                    "done_class": participant_done_class(display_status),
                    "progress_class": participant_progress_class(display_status),
                }
            )

        overall_progress = progress_percent if total_participants > 0 else 0

        if wager.end_date is None:
            time_remaining = "No deadline"
        elif wager.end_date >= today:
            days_left = (wager.end_date - today).days
            time_remaining = f"{days_left}d"
        else:
            days_over = (today - wager.end_date).days
            time_remaining = f"Overdue by {days_over}d"

        status_key = calculate_wager_status_key(wager, status_counts, total_participants)
        status_label = calculate_wager_status_label(status_key)

        wager_view = {
            "id": wager.id,
            "title": wager.title,
            "status": status_label,
            "status_key": status_key,
            "team": wager.team.name if wager.team else "",
            "prize_pool": wager.stake_amount * max(total_participants, 1),
            "time_remaining": time_remaining,
            "participants_on_track": status_counts["on_track"] + status_counts["completed"],
            "total_participants": total_participants,
            "overall_progress": overall_progress,
            "goal": wager.description,
            "start_date": format_date(wager.start_date),
            "end_date": format_date(wager.end_date),
            "stake_amount": wager.stake_amount,
            "penalty_rule": "Miss deadline → lose full stake",
            "reward_rule": "Complete → get stake back + share of prize pool",
            "created_by": wager.creator.username if wager.creator else "",
            "can_manage": current_user.is_authenticated and wager.creator_id == current_user.id,
        }

        current_membership = None
        if current_user.is_authenticated:
            current_membership = WagerParticipant.query.filter_by(
                wager_id=wager.id,
                user_id=current_user.id,
            ).first()

        user_status_text = "You have not joined this wager yet."
        user_status_subtext = "Create or join a wager to track your progress."
        user_status_color = "text-gray-600"
        stake_frozen = 0
        potential_reward = 0

        if current_membership:
            current_status = calculate_participant_status(
                tasks_done_for_wager,
                total_tasks,
                wager.end_date,
            )

            potential_reward = calculate_reward_amount(
                current_status,
                wager.stake_amount,
            )
            stake_frozen = wager.stake_amount

            if current_status == "completed":
                user_status_text = "You are COMPLETED ✅"
                user_status_subtext = "Your team has finished all linked tasks."
                user_status_color = "text-green-600"
            elif current_status == "at_risk":
                user_status_text = "You are AT RISK ⚠️"
                user_status_subtext = "The deadline is close and there is still work remaining."
                user_status_color = "text-yellow-600"
            elif current_status == "failed":
                user_status_text = "You have FAILED ❌"
                user_status_subtext = "This wager has been missed."
                user_status_color = "text-red-600"
            else:
                remaining = max(total_tasks - tasks_done_for_wager, 0)
                user_status_text = "You are ON TRACK 🎉"
                user_status_subtext = f"Keep going! {remaining} task(s) remaining."
                user_status_color = "text-green-600"

        user_status_view = {
            "tasks_done": tasks_done_for_wager,
            "tasks_total": total_tasks,
            "status_text": user_status_text,
            "status_subtext": user_status_subtext,
            "status_color": user_status_color,
            "stake_frozen": stake_frozen,
            "potential_reward": potential_reward,
            "required_tasks": get_required_tasks_for_wager(wager),
        }

        return wager_view, participants_view, user_status_view

    def build_dashboard_wager_card(user_id):
        today = date.today()

        wagers = (
            Wager.query.join(TeamMember, Wager.team_id == TeamMember.team_id)
            .filter(TeamMember.user_id == user_id)
            .order_by(Wager.created_at.desc())
            .all()
        )

        for wager in wagers:
            total_tasks, done_tasks, progress_percent = calculate_wager_progress(wager)
            total_participants = len(wager.participants)

            if total_tasks > 0 and done_tasks >= total_tasks:
                continue

            if wager.end_date and wager.end_date < today:
                continue

            if wager.end_date:
                days_left = (wager.end_date - today).days
                time_remaining = f"{days_left}d left"
            else:
                time_remaining = "No deadline"

            return {
                "id": wager.id,
                "title": wager.title,
                "prize_pool": wager.stake_amount * max(total_participants, 1),
                "time_remaining": time_remaining,
                "progress_percent": progress_percent,
            }

        return None

    @app.context_processor
    def inject_global_points():
        if current_user.is_authenticated:
            return {
                "current_points": calculate_total_points(current_user.id)
            }

        return {
            "current_points": 0
        }

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        now = datetime.now(timezone.utc)
        today = now.date()

        all_tasks = Task.query.filter_by(user_id=current_user.id).all()
        todays_tasks = [
            task for task in all_tasks
            if task.due_date and task.due_date.date() == today
        ]
        todays_done = [
            task for task in todays_tasks
            if task.status == "done"
        ]

        memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
        teams = [membership.team for membership in memberships]

        dashboard_wager = build_dashboard_wager_card(current_user.id)
        wagers_won_count = count_wagers_won_for_user(current_user.id)
        current_points = calculate_total_points(current_user.id)

        return render_template(
            "dashboard/index.html",
            todays_tasks=todays_tasks,
            todays_done_count=len(todays_done),
            todays_total_count=len(todays_tasks),
            teams=teams,
            active_teams_count=len(teams),
            dashboard_wager=dashboard_wager,
            wagers_won_count=wagers_won_count,
            current_points=current_points,
        )

    @app.route("/wagers")
    @login_required
    def wagers_detail():
        wagers = (
            Wager.query.join(TeamMember, Wager.team_id == TeamMember.team_id)
            .filter(TeamMember.user_id == current_user.id)
            .order_by(Wager.created_at.desc())
            .all()
        )

        if not wagers:
            flash("No wager exists yet. Please create one first.", "info")
            return redirect(url_for("create_wager"))

        sections = {
            "active": [],
            "completed": [],
            "failed": [],
        }

        for wager in wagers:
            wager_view, participants_view, user_status_view = build_wager_view_data(wager)

            item = {
                "wager": wager_view,
                "participants": participants_view,
                "user_status": user_status_view,
            }

            if wager_view["status_key"] == "completed":
                sections["completed"].append(item)
            elif wager_view["status_key"] == "failed":
                sections["failed"].append(item)
            else:
                sections["active"].append(item)

        return render_template(
            "wagers/detail.html",
            sections=sections,
        )

    @app.route("/wagers/create", methods=["GET", "POST"])
    @login_required
    def create_wager():
        teams = (
            Team.query.join(TeamMember, Team.id == TeamMember.team_id)
            .filter(
                TeamMember.user_id == current_user.id,
                TeamMember.role == "leader",
            )
            .order_by(Team.name.asc())
            .all()
        )

        team_ids = [team.id for team in teams]

        task_options = []
        if team_ids:
            task_options = (
                Task.query.filter(
                    Task.team_id.in_(team_ids),
                    Task.status != "done",
                )
                .order_by(Task.created_at.asc())
                .all()
            )

        if request.method == "POST":
            team_id_raw = request.form.get("team", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            start_date_raw = request.form.get("start_date", "").strip()
            end_date_raw = request.form.get("end_date", "").strip()
            stake_amount_raw = request.form.get("stake_amount", "").strip()
            selected_task_ids = request.form.getlist("tasks")

            error = None
            selected_team = None

            if not team_id_raw:
                error = "Please choose a team."
            else:
                try:
                    selected_team = db.session.get(Team, int(team_id_raw))
                except ValueError:
                    selected_team = None

                if selected_team is None:
                    error = "Selected team does not exist."
                elif not is_team_leader(selected_team.id, current_user.id):
                    error = "Only a team leader can create a wager."

            if not error and not title:
                error = "Wager Name cannot be empty."
            elif not error and not description:
                error = "Description cannot be empty."
            elif not error and not selected_task_ids:
                error = "Please select at least one linked task."

            start_date = None
            end_date = None

            if not error:
                try:
                    start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()

                    if end_date < start_date:
                        error = "End Date cannot be earlier than Start Date."
                except ValueError:
                    error = "Please enter valid start and end dates."

            if not error:
                try:
                    stake_amount = int(stake_amount_raw)

                    if stake_amount <= 0:
                        error = "Stake Amount must be greater than 0."
                except ValueError:
                    error = "Stake Amount must be a valid number."

            selected_tasks = []
            if not error:
                try:
                    selected_task_ids_int = [
                        int(task_id) for task_id in selected_task_ids
                    ]
                except ValueError:
                    error = "Invalid task selection."
                    selected_task_ids_int = []

                if not error:
                    selected_tasks = (
                        Task.query.filter(Task.id.in_(selected_task_ids_int)).all()
                    )

                    if len(selected_tasks) != len(selected_task_ids_int):
                        error = "Some selected tasks do not exist."
                    elif any(task.team_id != selected_team.id for task in selected_tasks):
                        error = "Selected tasks must belong to the chosen team."
                    elif any(task.status == "done" for task in selected_tasks):
                        error = "Completed tasks cannot be linked to a wager."

            if error:
                return render_template(
                    "wagers/create.html",
                    teams=teams,
                    tasks=task_options,
                    error=error,
                    form_data={
                        "team": team_id_raw,
                        "title": title,
                        "description": description,
                        "start_date": start_date_raw,
                        "end_date": end_date_raw,
                        "stake_amount": stake_amount_raw,
                        "selected_tasks": selected_task_ids,
                    },
                )

            new_wager = Wager(
                title=title,
                description=description,
                team_id=selected_team.id,
                creator_id=current_user.id,
                start_date=start_date,
                end_date=end_date,
                stake_amount=stake_amount,
                status="active",
            )

            db.session.add(new_wager)
            db.session.flush()

            for task in selected_tasks:
                db.session.add(
                    WagerTask(
                        wager_id=new_wager.id,
                        task_name=task.title,
                        task_id=task.id,
                    )
                )

            for member in selected_team.members:
                db.session.add(
                    WagerParticipant(
                        wager_id=new_wager.id,
                        user_id=member.user_id,
                        progress=0,
                        status="on_track",
                        reward_amount=0,
                    )
                )

            db.session.flush()
            sync_wager_status(new_wager)
            db.session.commit()

            flash("Wager created successfully.", "success")
            return redirect(url_for("wagers_detail"))

        return render_template(
            "wagers/create.html",
            teams=teams,
            tasks=task_options,
            error=None,
            form_data={
                "team": "",
                "title": "",
                "description": "",
                "start_date": "",
                "end_date": "",
                "stake_amount": "",
                "selected_tasks": [],
            },
        )

    @app.route("/wagers/<int:wager_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_wager(wager_id):
        wager = db.session.get(Wager, wager_id)

        if wager is None:
            flash("Wager not found.", "error")
            return redirect(url_for("wagers_detail"))

        if wager.creator_id != current_user.id:
            flash("Only the creator can edit this wager.", "error")
            return redirect(url_for("wagers_detail"))

        teams = (
            Team.query.join(TeamMember, Team.id == TeamMember.team_id)
            .filter(
                TeamMember.user_id == current_user.id,
                TeamMember.role == "leader",
            )
            .order_by(Team.name.asc())
            .all()
        )

        existing_task_ids = {
            link.task_id
            for link in wager.linked_tasks
            if getattr(link, "task_id", None) is not None
        }

        if existing_task_ids:
            task_filter = or_(
                Task.status != "done",
                Task.id.in_(existing_task_ids),
            )
        else:
            task_filter = Task.status != "done"

        task_options = (
            Task.query.filter(
                Task.team_id == wager.team_id,
                task_filter,
            )
            .order_by(Task.created_at.asc())
            .all()
        )

        existing_task_ids_str = [str(task_id) for task_id in existing_task_ids]

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            start_date_raw = request.form.get("start_date", "").strip()
            end_date_raw = request.form.get("end_date", "").strip()
            stake_amount_raw = request.form.get("stake_amount", "").strip()
            selected_task_ids = request.form.getlist("tasks")

            error = None

            if not title:
                error = "Wager Name cannot be empty."
            elif not description:
                error = "Description cannot be empty."
            elif not selected_task_ids:
                error = "Please select at least one linked task."

            start_date = None
            end_date = None

            if not error:
                try:
                    start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()

                    if end_date < start_date:
                        error = "End Date cannot be earlier than Start Date."
                except ValueError:
                    error = "Please enter valid start and end dates."

            if not error:
                try:
                    stake_amount = int(stake_amount_raw)

                    if stake_amount <= 0:
                        error = "Stake Amount must be greater than 0."
                except ValueError:
                    error = "Stake Amount must be a valid number."

            selected_tasks = []
            if not error:
                try:
                    selected_task_ids_int = [
                        int(task_id) for task_id in selected_task_ids
                    ]
                except ValueError:
                    error = "Invalid task selection."
                    selected_task_ids_int = []

                if not error:
                    selected_tasks = (
                        Task.query.filter(Task.id.in_(selected_task_ids_int)).all()
                    )

                    if len(selected_tasks) != len(selected_task_ids_int):
                        error = "Some selected tasks do not exist."
                    elif any(task.team_id != wager.team_id for task in selected_tasks):
                        error = "Selected tasks must belong to the wager team."
                    else:
                        for task in selected_tasks:
                            if task.status == "done" and task.id not in existing_task_ids:
                                error = "Completed tasks cannot be newly linked to a wager."
                                break

            if error:
                return render_template(
                    "wagers/edit.html",
                    wager=wager,
                    teams=teams,
                    tasks=task_options,
                    error=error,
                    form_data={
                        "title": title,
                        "description": description,
                        "start_date": start_date_raw,
                        "end_date": end_date_raw,
                        "stake_amount": stake_amount_raw,
                        "selected_tasks": selected_task_ids,
                    },
                )

            wager.title = title
            wager.description = description
            wager.start_date = start_date
            wager.end_date = end_date
            wager.stake_amount = stake_amount

            WagerTask.query.filter_by(wager_id=wager.id).delete()

            for task in selected_tasks:
                db.session.add(
                    WagerTask(
                        wager_id=wager.id,
                        task_name=task.title,
                        task_id=task.id,
                    )
                )

            db.session.flush()
            db.session.expire(wager, ["linked_tasks"])
            sync_wager_status(wager)
            db.session.commit()

            flash("Wager updated successfully.", "success")
            return redirect(url_for("wagers_detail"))

        return render_template(
            "wagers/edit.html",
            wager=wager,
            teams=teams,
            tasks=task_options,
            error=None,
            form_data={
                "title": wager.title,
                "description": wager.description,
                "start_date": format_date(wager.start_date),
                "end_date": format_date(wager.end_date),
                "stake_amount": wager.stake_amount,
                "selected_tasks": existing_task_ids_str,
            },
        )

    @app.route("/wagers/<int:wager_id>/delete", methods=["POST"])
    @login_required
    def delete_wager(wager_id):
        wager = db.session.get(Wager, wager_id)

        if wager is None:
            flash("Wager not found.", "error")
            return redirect(url_for("wagers_detail"))

        if wager.creator_id != current_user.id:
            flash("Only the creator can delete this wager.", "error")
            return redirect(url_for("wagers_detail"))

        WagerTask.query.filter_by(wager_id=wager.id).delete()
        WagerParticipant.query.filter_by(wager_id=wager.id).delete()
        db.session.delete(wager)
        db.session.commit()

        flash("Wager deleted successfully.", "success")
        return redirect(url_for("wagers_detail"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data.strip()).first()

            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "error")

        return render_template("auth/login_form.html", form=form)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = RegisterForm()

        if form.validate_on_submit():
            username = form.username.data.strip()
            email = form.email.data.strip() if form.email.data else None

            if User.query.filter_by(username=username).first() is not None:
                flash("Username already exists.", "error")
                return render_template("auth/register_form.html", form=form)

            if email and User.query.filter_by(email=email).first() is not None:
                flash("Email is already in use.", "error")
                return render_template("auth/register_form.html", form=form)

            user = User(username=username, email=email)
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("Registration successful.", "success")
            return redirect(url_for("dashboard"))

        return render_template("auth/register_form.html", form=form)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def account_password():
        form = ChangePasswordForm()

        if form.validate_on_submit():
            if not current_user.check_password(form.old_password.data):
                flash("Current password is incorrect.", "error")
                return render_template("account/password.html", form=form)

            current_user.set_password(form.new_password.data)
            db.session.commit()

            flash("Password updated successfully.", "success")
            return redirect(url_for("dashboard"))

        return render_template("account/password.html", form=form)

    @app.route("/reset-password", methods=["GET", "POST"])
    def reset_password():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = ResetPasswordForm()

        if form.validate_on_submit():
            identifier = form.username_or_email.data.strip()

            user = User.query.filter_by(username=identifier).first()
            if user is None:
                user = User.query.filter_by(email=identifier).first()

            if user is None:
                flash("User not found.", "error")
                return render_template("auth/reset_password.html", form=form)

            user.set_password(form.new_password.data)
            db.session.commit()

            flash("Password updated, please login.", "success")
            return redirect(url_for("login"))

        return render_template("auth/reset_password.html", form=form)

    @app.route("/health")
    def health():
        return Response("ok", mimetype="text/plain")

    return app