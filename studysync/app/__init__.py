import os
from datetime import datetime, timedelta

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
from sqlalchemy import and_, or_

from app.time_utils import now_app_time, today_app_date
from app.forms import LoginForm, RegisterForm, ChangePasswordForm


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    if not user_id or not user_id.isdigit():
        return None

    return db.session.get(User, int(user_id))


def create_app(test_config=None):
    app = Flask(__name__, template_folder='../frontend/templates')

    os.makedirs(app.instance_path, exist_ok=True)

    database_path = os.path.join(app.instance_path, "studysync.db")

    if os.getenv("APP_ENV") == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in production.")
    
    secret_key = (test_config or {}).get("SECRET_KEY") or os.getenv("SECRET_KEY")

    if not secret_key and not app.debug:
        raise RuntimeError(
            "SECRET_KEY must be set when running outside debug mode."
        )
    
    app.config.from_mapping(
        SECRET_KEY=secret_key or "dev-secret-key",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=True,
    )

    if test_config is not None:
        app.config.update(test_config)

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
        Activity,
        Notification,  # noqa: F401
        Wager,
        WagerParticipant,
        WagerTask,
        Subtask,  # noqa: F401
    )
    from app.teams import teams_bp
    from app.tasks import tasks_bp
    from app.feed import feed_bp
    from app.notifications import notifications_bp
    from app.wager_helpers import (
        POINTS_PER_TASK,
        calculate_participant_status,
        calculate_total_points,
        calculate_wager_points,
        calculate_wager_progress,
        calculate_wager_user_progress,
        count_wagers_won_for_user,
        get_active_personal_wagers_for_user,
        get_badge_for_points,
        get_personal_wagers_for_user,
        get_team_wagers_for_leader,
        resolve_linked_task,
        sync_wager_status,
        user_can_view_team_wagers,
        user_owns_or_is_assigned_task,
    )

    app.register_blueprint(teams_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(notifications_bp)

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

    def parse_wager_date(date_str):
        """Parse a wager date and require the exact YYYY-MM-DD format."""
        if len(date_str) != 10:
            raise ValueError("Date must use YYYY-MM-DD format.")

        return datetime.strptime(date_str, "%Y-%m-%d").date()

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
            "no_tasks": "bg-gray-100 text-gray-600",
        }

        return mapping.get(status, "bg-gray-100 text-gray-700")

    def participant_progress_class(status):
        mapping = {
            "on_track": "bg-green-500",
            "completed": "bg-green-500",
            "at_risk": "bg-yellow-500",
            "failed": "bg-red-500",
            "no_tasks": "bg-gray-300",
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

    def calculate_wager_status_key(
        wager,
        status_counts,
        team_tasks_done,
        team_tasks_total,
    ):
        """Return the overall wager status based on team-level progress."""
        today = today_app_date()

        if team_tasks_total > 0 and team_tasks_done >= team_tasks_total:
            return "completed"

        if (
            wager.end_date is not None
            and today > wager.end_date
            and team_tasks_done < team_tasks_total
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
        """Build display data for the wager detail page.

        The wager itself still uses team-level progress because linked tasks are
        shared by the whole team. Participant rows and the current user's status
        use personal progress so assigned tasks only count for the assignee.
        """
        total_tasks, tasks_done_for_wager, progress_percent = calculate_wager_progress(
            wager
        )
        total_participants = len(wager.participants)

        points_earned = calculate_wager_points(wager)
        total_possible_points = total_tasks * POINTS_PER_TASK
        badge = get_badge_for_points(points_earned)

        current_user_tasks_total = 0
        current_user_tasks_done = 0
        current_user_progress = 0
        current_user_points = 0
        current_user_total_possible_points = 0
        current_user_badge = get_badge_for_points(0)

        if current_user.is_authenticated:
            (
                current_user_tasks_total,
                current_user_tasks_done,
                current_user_progress,
            ) = calculate_wager_user_progress(wager, current_user.id)

            current_user_points = current_user_tasks_done * POINTS_PER_TASK
            current_user_total_possible_points = (
                current_user_tasks_total * POINTS_PER_TASK
            )
            current_user_badge = get_badge_for_points(current_user_points)

        today = today_app_date()

        participants_view = []
        status_counts = {
            "on_track": 0,
            "completed": 0,
            "at_risk": 0,
            "failed": 0,
        }

        for idx, participant in enumerate(wager.participants):
            (
                personal_tasks_total,
                personal_tasks_done,
                personal_progress,
            ) = calculate_wager_user_progress(wager, participant.user_id)

            personal_points = personal_tasks_done * POINTS_PER_TASK
            personal_badge = get_badge_for_points(personal_points)

            display_status = calculate_participant_status(
                personal_tasks_done,
                personal_tasks_total,
                wager.end_date,
            )

            status_counts[display_status] += 1

            username = participant.user.username if participant.user else "Unknown"

            participants_view.append(
                {
                    "name": username,
                    "avatar": username[0].upper() if username else "?",
                    "avatar_color": avatar_color_for_index(idx),
                    "tasks_done": personal_tasks_done,
                    "tasks_total": personal_tasks_total,
                    "progress": personal_progress,
                    "status": display_status.replace("_", " ").title(),
                    "status_class": participant_status_class(display_status),
                    "reward": personal_points,
                    "points": personal_points,
                    "badge": personal_badge,
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

        status_key = calculate_wager_status_key(
            wager,
            status_counts,
            tasks_done_for_wager,
            total_tasks,
        )
        status_label = calculate_wager_status_label(status_key)

        wager_view = {
            "id": wager.id,
            "title": wager.title,
            "status": status_label,
            "status_key": status_key,
            "team": wager.team.name if wager.team else "",
            "time_remaining": time_remaining,
            "participants_on_track": (
                status_counts["on_track"] + status_counts["completed"]
            ),
            "total_participants": total_participants,
            "overall_progress": overall_progress,
            "goal": wager.description,
            "start_date": format_date(wager.start_date),
            "end_date": format_date(wager.end_date),
            "points_earned": points_earned,
            "total_possible_points": total_possible_points,
            "points_per_task": POINTS_PER_TASK,
            "badge": badge,
            "penalty_rule": "Incomplete linked tasks do not earn points",
            "reward_rule": f"Each completed linked task gives {POINTS_PER_TASK} points",
            "created_by": wager.creator.username if wager.creator else "",
            "can_manage": (
                current_user.is_authenticated and wager.creator_id == current_user.id
            ),

            # Backward-compatible keys for older templates.
            # These should be renamed in templates later.
            "prize_pool": total_possible_points,
            "stake_amount": POINTS_PER_TASK,
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

        if current_membership:
            current_status = calculate_participant_status(
                current_user_tasks_done,
                current_user_tasks_total,
                wager.end_date,
            )

            if current_user_tasks_total == 0:
                user_status_text = "No linked task assigned to you yet"
                user_status_subtext = (
                    "You will earn points when a linked task is assigned to you "
                    "and completed."
                )
                user_status_color = "text-gray-600"
            elif current_status == "completed":
                user_status_text = "You are COMPLETED ✅"
                user_status_subtext = (
                    "You have completed your linked task contribution and earned "
                    f"{current_user_points} points."
                )
                user_status_color = "text-green-600"
            elif current_status == "at_risk":
                user_status_text = "You are AT RISK ⚠️"
                user_status_subtext = (
                    "The deadline is close and your linked tasks are not complete yet."
                )
                user_status_color = "text-yellow-600"
            elif current_status == "failed":
                user_status_text = "You have FAILED ❌"
                user_status_subtext = (
                    "Your linked tasks were not completed before the deadline."
                )
                user_status_color = "text-red-600"
            else:
                remaining = max(current_user_tasks_total - current_user_tasks_done, 0)
                user_status_text = "You are ON TRACK 🎉"
                user_status_subtext = f"Keep going! {remaining} task(s) remaining."
                user_status_color = "text-green-600"

        user_status_view = {
            "tasks_done": current_user_tasks_done,
            "tasks_total": current_user_tasks_total,
            "status_text": user_status_text,
            "status_subtext": user_status_subtext,
            "status_color": user_status_color,
            "progress": current_user_progress,
            "points_earned": current_user_points,
            "total_possible_points": current_user_total_possible_points,
            "points_per_task": POINTS_PER_TASK,
            "badge": current_user_badge,
            "required_tasks": get_required_tasks_for_wager(wager),

            # Backward-compatible keys for older templates.
            "stake_frozen": current_user_total_possible_points,
            "potential_reward": current_user_points,
        }

        return wager_view, participants_view, user_status_view

    def build_participant_status_overview(wagers):
        """Build one page-level participant status overview.

        The overview aggregates each participant's own linked tasks across the
        wagers visible to the current user. Assigned tasks count only for the
        assignee, while unassigned tasks count for the creator.
        """
        participant_map = {}

        for wager in wagers:
            for participant in wager.participants:
                user = participant.user

                if user is None:
                    continue

                if user.id not in participant_map:
                    participant_map[user.id] = {
                        "user_id": user.id,
                        "name": user.username,
                        "avatar": user.username[:1].upper() if user.username else "?",
                        "_task_ids": set(),
                        "_done_task_ids": set(),
                    }

            for link in wager.linked_tasks:
                linked_task = resolve_linked_task(link, wager)

                if linked_task is None:
                    continue

                for participant in wager.participants:
                    user = participant.user

                    if user is None:
                        continue

                    if not user_owns_or_is_assigned_task(linked_task, user.id):
                        continue

                    participant_map[user.id]["_task_ids"].add(linked_task.id)

                    if linked_task.status == "done":
                        participant_map[user.id]["_done_task_ids"].add(
                            linked_task.id
                        )

        rows = []

        for item in participant_map.values():
            tasks_total = len(item["_task_ids"])
            tasks_done = len(item["_done_task_ids"])
            points = tasks_done * POINTS_PER_TASK
            badge = get_badge_for_points(points)

            if tasks_total == 0:
                progress = 0
                status_key = "no_tasks"
                status_label = "No Tasks"
            elif tasks_done >= tasks_total:
                progress = 100
                status_key = "completed"
                status_label = "Completed"
            else:
                progress = min(100, int((tasks_done / tasks_total) * 100))
                status_key = "on_track"
                status_label = "In Progress"

            rows.append(
                {
                    "user_id": item["user_id"],
                    "name": item["name"],
                    "avatar": item["avatar"],
                    "tasks_done": tasks_done,
                    "tasks_total": tasks_total,
                    "progress": progress,
                    "status": status_label,
                    "status_class": participant_status_class(status_key),
                    "points": points,
                    "badge": badge,
                    "row_class": "",
                    "name_class": "text-gray-900",
                    "done_class": "text-gray-600",
                    "progress_class": participant_progress_class(status_key),
                }
            )

        rows.sort(
            key=lambda row: (
                -row["points"],
                -row["tasks_done"],
                row["name"].lower(),
            )
        )

        for index, row in enumerate(rows):
            row["avatar_color"] = avatar_color_for_index(index)

        return rows

    def build_dashboard_wager_card(user_id):
        """Build the Dashboard active wager card for the current user's own wagers."""
        today = today_app_date()

        # Dashboard is a personal page. Even leaders should only see wagers that
        # are personally relevant to them here, not every team member's wager.
        wagers = get_active_personal_wagers_for_user(user_id)

        for wager in wagers:
            total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

            if total_tasks > 0 and done_tasks >= total_tasks:
                continue

            if wager.end_date and wager.end_date < today:
                continue

            if wager.end_date:
                days_left = (wager.end_date - today).days
                time_remaining = f"{days_left}d left"
            else:
                time_remaining = "No deadline"

            user_total_tasks, user_done_tasks, user_progress_percent = (
                calculate_wager_user_progress(wager, user_id)
            )

            points_earned = user_done_tasks * POINTS_PER_TASK
            total_possible_points = user_total_tasks * POINTS_PER_TASK

            return {
                "id": wager.id,
                "title": wager.title,
                "time_remaining": time_remaining,
                "progress_percent": user_progress_percent,
                "points_earned": points_earned,
                "total_possible_points": total_possible_points,
                "points_per_task": POINTS_PER_TASK,

                # Backward-compatible key.
                "prize_pool": total_possible_points,
            }

        return None

    def build_dashboard_team_progress(user_id):
        """Build real team task completion progress for the dashboard."""
        memberships = TeamMember.query.filter_by(user_id=user_id).all()
        progress_rows = []

        for membership in memberships:
            team = membership.team

            if team is None:
                continue

            tasks = Task.query.filter_by(team_id=team.id).all()
            total_tasks = len(tasks)
            completed_tasks = sum(1 for task in tasks if task.status == "done")

            progress_percent = (
                int((completed_tasks / total_tasks) * 100)
                if total_tasks > 0
                else 0
            )

            progress_rows.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "completed_tasks": completed_tasks,
                    "total_tasks": total_tasks,
                    "progress_percent": progress_percent,
                }
            )

        progress_rows.sort(key=lambda row: row["team_name"].lower())
        return progress_rows

    def build_dashboard_focus_tasks(all_tasks, today, limit=5):
        """Build a small priority queue for the dashboard.

        The dashboard should highlight what needs attention now, while the
        full My Tasks page remains responsible for complete task management.
        """
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        focus_rows = []
        seen_task_ids = set()
        upcoming_cutoff = today + timedelta(days=7)

        def task_due_date(task):
            return task.due_date.date() if task.due_date else None

        def task_sort_key(task):
            due = task_due_date(task)
            return (
                due or datetime.max.date(),
                priority_rank.get(task.priority, 3),
                task.title.lower(),
            )

        def has_active_wager(task):
            for link in getattr(task, "wager_links", []):
                wager = getattr(link, "wager", None)

                if wager is not None and wager.status == "active":
                    return True

            return False

        def add_focus_task(task, category, label, badge_class, icon):
            if len(focus_rows) >= limit:
                return

            if task.id in seen_task_ids or task.status == "done":
                return

            due = task_due_date(task)

            if due is None:
                due_label = "No due date"
            elif due < today:
                days_overdue = (today - due).days
                due_label = f"{days_overdue}d overdue"
            elif due == today:
                due_label = "Due today"
            else:
                days_left = (due - today).days
                due_label = f"Due in {days_left}d"

            focus_rows.append(
                {
                    "task": task,
                    "category": category,
                    "label": label,
                    "badge_class": badge_class,
                    "icon": icon,
                    "due_label": due_label,
                }
            )
            seen_task_ids.add(task.id)

        active_tasks = [task for task in all_tasks if task.status != "done"]

        overdue_tasks = sorted(
            [
                task for task in active_tasks
                if task_due_date(task) is not None and task_due_date(task) < today
            ],
            key=task_sort_key,
        )
        due_today_tasks = sorted(
            [
                task for task in active_tasks
                if task_due_date(task) == today
            ],
            key=task_sort_key,
        )
        upcoming_tasks = sorted(
            [
                task for task in active_tasks
                if (
                    task_due_date(task) is not None
                    and today < task_due_date(task) <= upcoming_cutoff
                )
            ],
            key=task_sort_key,
        )
        wager_tasks = sorted(
            [task for task in active_tasks if has_active_wager(task)],
            key=task_sort_key,
        )

        for task in overdue_tasks:
            add_focus_task(
                task,
                "overdue",
                "Overdue",
                "bg-red-100 text-red-700",
                "fa-triangle-exclamation",
            )

        for task in due_today_tasks:
            add_focus_task(
                task,
                "due_today",
                "Due Today",
                "bg-orange-100 text-orange-700",
                "fa-calendar-day",
            )

        for task in upcoming_tasks:
            add_focus_task(
                task,
                "upcoming",
                "Next 7 Days",
                "bg-blue-100 text-blue-700",
                "fa-calendar-week",
            )

        for task in wager_tasks:
            add_focus_task(
                task,
                "wager",
                "Active Wager",
                "bg-purple-100 text-purple-700",
                "fa-trophy",
            )

        return focus_rows

    def build_dashboard_recent_activities(user_id, limit=5):
        """Build recent activity rows from teams the user belongs to."""
        memberships = TeamMember.query.filter_by(user_id=user_id).all()
        team_ids = [membership.team_id for membership in memberships]

        if not team_ids:
            return []

        activities = (
            Activity.query.filter(Activity.team_id.in_(team_ids))
            .order_by(Activity.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "message": activity.message,
                "team_name": activity.team.name if activity.team else "Team activity",
                "actor_name": activity.user.username if activity.user else "StudySync",
                "actor_initial": (
                    activity.user.username[:1].upper()
                    if activity.user and activity.user.username
                    else "S"
                ),
                "created_at": activity.created_at,
            }
            for activity in activities
        ]


    @app.context_processor
    def inject_global_points():
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False,
            ).count()

            return {
                "current_points": calculate_total_points(current_user.id),
                "unread_notification_count": unread_count,
            }

        return {
            "current_points": 0,
            "unread_notification_count": 0,
        }

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        now = now_app_time()
        today = now.date()

        all_tasks = Task.query.filter(
            or_(
                Task.assigned_to_user_id == current_user.id,
                and_(
                    Task.user_id == current_user.id,
                    Task.assigned_to_user_id.is_(None),
                ),
            )
        ).all()
        todays_tasks = [
            task for task in all_tasks
            if task.due_date and task.due_date.date() == today
        ]
        todays_done = [
            task for task in todays_tasks
            if task.status == "done"
        ]
        focus_tasks = build_dashboard_focus_tasks(all_tasks, today)

        memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
        teams = [membership.team for membership in memberships]

        dashboard_wager = build_dashboard_wager_card(current_user.id)
        wagers_won_count = count_wagers_won_for_user(current_user.id)
        current_points = calculate_total_points(current_user.id)
        current_badge = get_badge_for_points(current_points)
        team_progress_rows = build_dashboard_team_progress(current_user.id)
        recent_activities = build_dashboard_recent_activities(current_user.id)

        return render_template(
            "dashboard/index.html",
            todays_tasks=todays_tasks,
            focus_tasks=focus_tasks,
            todays_done_count=len(todays_done),
            todays_total_count=len(todays_tasks),
            teams=teams,
            active_teams_count=len(teams),
            dashboard_wager=dashboard_wager,
            wagers_won_count=wagers_won_count,
            current_points=current_points,
            current_badge=current_badge,
            team_progress_rows=team_progress_rows,
            recent_activities=recent_activities,
        )

    @app.route("/wagers")
    @login_required
    def wagers_detail():
        """Display the Wager page with scope and team filters.
    
        Scope rules:
        - Personal: everyone sees only their own wagers.
        - Team Members: leaders can view all wagers from teams they lead.
    
        Team filter rules:
        - Personal scope: filter by teams the current user belongs to.
        - Team Members scope: filter by teams the current user leads.
        """
        requested_scope = request.args.get("scope", "personal")
        selected_team_raw = request.args.get("team_id")
    
        can_view_team_wagers = user_can_view_team_wagers(current_user.id)
    
        memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
        all_user_teams = [membership.team for membership in memberships]
        leader_team_ids = {
            membership.team_id
            for membership in memberships
            if membership.role == "leader"
        }
    
        if requested_scope == "team" and can_view_team_wagers:
            scope = "team"
            team_filter_teams = [
                team for team in all_user_teams
                if team and team.id in leader_team_ids
            ]
            wagers = get_team_wagers_for_leader(current_user.id)
        else:
            scope = "personal"
            team_filter_teams = [
                team for team in all_user_teams
                if team is not None
            ]
            wagers = get_personal_wagers_for_user(current_user.id)
    
        allowed_team_ids = {team.id for team in team_filter_teams}
        selected_team_id = None

        if selected_team_raw:
            try:
                candidate_team_id = int(selected_team_raw)

                if candidate_team_id in allowed_team_ids:
                    selected_team_id = candidate_team_id
            except ValueError:
                selected_team_id = None

        # Wagers must always be viewed within one team to avoid mixing data
        # from different teams on the same page.
        if selected_team_id is None and team_filter_teams:
            selected_team_id = team_filter_teams[0].id

        if selected_team_id is not None:
            wagers = [
                wager for wager in wagers
                if wager.team_id == selected_team_id
            ]
        else:
            wagers = []
    
        sections = {
            "active": [],
            "completed": [],
            "failed": [],
        }
        
        overview_team_ids = []

        if selected_team_id is not None:
            overview_team_ids = [selected_team_id]
        
        overview_wagers = []
        
        if overview_team_ids:
            overview_wagers = (
                Wager.query.filter(Wager.team_id.in_(overview_team_ids))
                .order_by(Wager.created_at.desc())
                .all()
            )
        
        participant_overview = build_participant_status_overview(overview_wagers)
    
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
            participant_overview=participant_overview,
            scope=scope,
            can_view_team_wagers=can_view_team_wagers,
            team_filter_teams=team_filter_teams,
            selected_team_id=selected_team_id,
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

        used_task_ids_query = db.session.query(WagerTask.task_id).filter(
            WagerTask.task_id.isnot(None)
        )

        task_options = []
        if team_ids:
            task_options = (
                Task.query.filter(
                    Task.team_id.in_(team_ids),
                    Task.status != "done",
                    ~Task.id.in_(used_task_ids_query),
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
                    start_date = parse_wager_date(start_date_raw)
                    end_date = parse_wager_date(end_date_raw)

                    if end_date < start_date:
                        error = "End Date cannot be earlier than Start Date."
                except ValueError:
                    error = "Please enter valid start and end dates."

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

                    already_linked_task = WagerTask.query.filter(
                        WagerTask.task_id.in_(selected_task_ids_int)
                    ).first()

                    if len(selected_tasks) != len(selected_task_ids_int):
                        error = "Some selected tasks do not exist."
                    elif already_linked_task is not None:
                        error = "Each task can only be linked to one wager."
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
                        "stake_amount": POINTS_PER_TASK,
                        "selected_tasks": selected_task_ids,
                    },
                    points_per_task=POINTS_PER_TASK,
                )

            new_wager = Wager(
                title=title,
                description=description,
                team_id=selected_team.id,
                creator_id=current_user.id,
                start_date=start_date,
                end_date=end_date,
                # Keep this database field for compatibility.
                # Points are now calculated from completed linked tasks.
                stake_amount=POINTS_PER_TASK,
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
                "stake_amount": POINTS_PER_TASK,
                "selected_tasks": [],
            },
            points_per_task=POINTS_PER_TASK,
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

        used_by_other_wagers_query = db.session.query(WagerTask.task_id).filter(
            WagerTask.task_id.isnot(None),
            WagerTask.wager_id != wager.id,
        )

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
                ~Task.id.in_(used_by_other_wagers_query),
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
                    start_date = parse_wager_date(start_date_raw)
                    end_date = parse_wager_date(end_date_raw)

                    if end_date < start_date:
                        error = "End Date cannot be earlier than Start Date."
                except ValueError:
                    error = "Please enter valid start and end dates."

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

                    already_linked_task = WagerTask.query.filter(
                        WagerTask.task_id.in_(selected_task_ids_int),
                        WagerTask.wager_id != wager.id,
                    ).first()

                    if len(selected_tasks) != len(selected_task_ids_int):
                        error = "Some selected tasks do not exist."
                    elif already_linked_task is not None:
                        error = "Each task can only be linked to one wager."
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
                        "stake_amount": POINTS_PER_TASK,
                        "selected_tasks": selected_task_ids,
                    },
                    points_per_task=POINTS_PER_TASK,
                )

            wager.title = title
            wager.description = description
            wager.start_date = start_date
            wager.end_date = end_date
            wager.stake_amount = POINTS_PER_TASK

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
                "stake_amount": POINTS_PER_TASK,
                "selected_tasks": existing_task_ids_str,
            },
            points_per_task=POINTS_PER_TASK,
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
        """
        Disable public password reset for the MVP.
    
        A secure reset flow requires email/token verification. The previous
        demo-style reset allowed passwords to be changed with only a username
        or email, which creates an account takeover risk.
        """
        flash(
            "Password reset is not available in the MVP. "
            "If you can log in, please change your password from Account settings.",
            "info",
        )
    
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
    
        return redirect(url_for("login"))

    @app.route("/health")
    def health():
        return Response("ok", mimetype="text/plain")

    return app
