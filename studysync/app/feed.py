from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import Activity, ActivityLike, TeamMember, Task, User, Wager, WagerParticipant


feed_bp = Blueprint("feed", __name__)


def _current_user_team_ids():
    """Return team ids that the current user belongs to."""
    return [
        membership.team_id
        for membership in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def _can_view_activity(activity, team_ids):
    """Return whether the current user is allowed to view this activity."""
    if activity.team_id is None:
        return True

    return activity.team_id in team_ids


def _resolve_linked_task_for_user(link, wager, user_id):
    """
    Resolve a wager linked task for a user.
    Supports both new data (task_id) and old compatibility data (task_name).
    """
    if getattr(link, "task", None) is not None:
        if link.task.user_id == user_id:
            return link.task
        return None

    if getattr(link, "task_name", None):
        return (
            Task.query.filter_by(
                user_id=user_id,
                team_id=wager.team_id,
                title=link.task_name,
            )
            .order_by(Task.created_at.desc())
            .first()
        )

    return None


def _count_done_tasks_for_user(wager, user_id):
    done_count = 0

    for link in wager.linked_tasks:
        linked_task = _resolve_linked_task_for_user(link, wager, user_id)
        if linked_task is not None and linked_task.status == "done":
            done_count += 1

    return done_count


def _count_wagers_won_for_user(user_id):
    wagers = (
        Wager.query.join(TeamMember, Wager.team_id == TeamMember.team_id)
        .filter(TeamMember.user_id == user_id)
        .all()
    )

    won_count = 0

    for wager in wagers:
        participant = WagerParticipant.query.filter_by(
            wager_id=wager.id,
            user_id=user_id,
        ).first()

        if not participant:
            continue

        total_tasks = len(wager.linked_tasks)
        done_count = _count_done_tasks_for_user(wager, user_id)

        if total_tasks > 0 and done_count >= total_tasks:
            won_count += 1

    return won_count


def _calculate_total_points(user_id):
    """
    Points come from completed wagers.
    Each completed wager contributes its configured stake_amount.
    """
    wagers = (
        Wager.query.join(TeamMember, Wager.team_id == TeamMember.team_id)
        .filter(TeamMember.user_id == user_id)
        .all()
    )

    total_points = 0

    for wager in wagers:
        participant = WagerParticipant.query.filter_by(
            wager_id=wager.id,
            user_id=user_id,
        ).first()

        if not participant:
            continue

        total_tasks = len(wager.linked_tasks)
        done_count = _count_done_tasks_for_user(wager, user_id)

        if total_tasks > 0 and done_count >= total_tasks:
            total_points += wager.stake_amount

    return total_points


def _build_active_wager_cards(team_ids):
    """
    Build a small list of real wager cards for the right sidebar.
    Keep this lightweight and independent so it does not affect
    the existing activity feed behaviour.
    """
    if not team_ids:
        return []

    today = date.today()

    wagers = (
        Wager.query.filter(Wager.team_id.in_(team_ids))
        .order_by(Wager.created_at.desc())
        .all()
    )

    active_wagers = []

    for index, wager in enumerate(wagers):
        if wager.end_date and wager.end_date < today:
            continue

        total_tasks = len(wager.linked_tasks)
        total_participants = len(wager.participants)

        completed_participants = 0
        for participant in wager.participants:
            done_count = _count_done_tasks_for_user(wager, participant.user_id)
            if total_tasks > 0 and done_count >= total_tasks:
                completed_participants += 1

        if total_participants > 0 and completed_participants == total_participants:
            continue

        if wager.end_date:
            days_left = (wager.end_date - today).days
            time_remaining = f"{days_left}d left"
        else:
            time_remaining = "No deadline"

        prize_pool = wager.stake_amount * max(len(wager.participants), 1)

        theme_options = [
            {
                "container_class": "border border-indigo-200 bg-indigo-50",
                "badge_class": "bg-indigo-600 text-white",
            },
            {
                "container_class": "border border-purple-200 bg-purple-50",
                "badge_class": "bg-purple-600 text-white",
            },
            {
                "container_class": "border border-orange-200 bg-orange-50",
                "badge_class": "bg-orange-500 text-white",
            },
        ]
        theme = theme_options[index % len(theme_options)]

        active_wagers.append(
            {
                "id": wager.id,
                "title": wager.title,
                "prize_pool": prize_pool,
                "time_remaining": time_remaining,
                "container_class": theme["container_class"],
                "badge_class": theme["badge_class"],
            }
        )

    return active_wagers[:3]


def _build_leaderboard():
    """
    Build a simple leaderboard based on:
    - completed wager points total
    - completed task count
    """
    users = User.query.order_by(User.username.asc()).all()
    leaderboard = []

    avatar_colors = [
        "bg-purple-500",
        "bg-pink-500",
        "bg-orange-500",
        "bg-teal-500",
        "bg-indigo-500",
        "bg-blue-500",
    ]

    for user in users:
        completed_task_count = Task.query.filter_by(user_id=user.id, status="done").count()
        points = _calculate_total_points(user.id)

        leaderboard.append(
            {
                "user_id": user.id,
                "name": user.username,
                "initial": user.username[:1].upper() if user.username else "?",
                "completed_task_count": completed_task_count,
                "points": points,
                "is_current_user": user.id == current_user.id,
            }
        )

    leaderboard.sort(
        key=lambda item: (-item["points"], -item["completed_task_count"], item["name"].lower())
    )

    for index, item in enumerate(leaderboard):
        item["rank"] = index + 1
        item["avatar_class"] = avatar_colors[index % len(avatar_colors)]

        if item["rank"] == 1:
            item["rank_class"] = "text-yellow-600"
        elif item["rank"] == 2:
            item["rank_class"] = "text-gray-400"
        elif item["rank"] == 3:
            item["rank_class"] = "text-orange-600"
        else:
            item["rank_class"] = "text-gray-500"

    return leaderboard[:5]


@feed_bp.route("/feed")
@login_required
def activity_feed():
    """Render the Activity Feed page with visibility-aware filtering."""
    active_filter = request.args.get("filter", "all")

    if active_filter not in ("all", "my-teams"):
        active_filter = "all"

    team_ids = _current_user_team_ids()

    activity_query = Activity.query.order_by(Activity.created_at.desc())

    if active_filter == "my-teams":
        if team_ids:
            activity_query = activity_query.filter(Activity.team_id.in_(team_ids))
        else:
            activities = []
            return render_template(
                "feed/index.html",
                activities=activities,
                active_filter=active_filter,
                liked_activity_ids=set(),
                like_counts={},
                active_wagers=[],
                leaderboard=[],
            )
    else:
        if team_ids:
            activity_query = activity_query.filter(
                or_(
                    Activity.team_id.is_(None),
                    Activity.team_id.in_(team_ids),
                )
            )
        else:
            activity_query = activity_query.filter(Activity.team_id.is_(None))

    activities = activity_query.limit(50).all()
    activity_ids = [activity.id for activity in activities]

    liked_activity_ids = set()
    if activity_ids:
        liked_activity_ids = {
            like.activity_id
            for like in ActivityLike.query.filter(
                ActivityLike.user_id == current_user.id,
                ActivityLike.activity_id.in_(activity_ids),
            ).all()
        }

    like_counts = {
        activity.id: len(activity.likes)
        for activity in activities
    }

    active_wagers = _build_active_wager_cards(team_ids)
    leaderboard = _build_leaderboard()

    return render_template(
        "feed/index.html",
        activities=activities,
        active_filter=active_filter,
        liked_activity_ids=liked_activity_ids,
        like_counts=like_counts,
        active_wagers=active_wagers,
        leaderboard=leaderboard,
    )


@feed_bp.route("/feed/<int:activity_id>/like", methods=["POST"])
@login_required
def toggle_activity_like(activity_id):
    """Like or unlike an activity record if the current user can view it."""
    activity = Activity.query.get_or_404(activity_id)

    team_ids = _current_user_team_ids()
    if not _can_view_activity(activity, team_ids):
        abort(403)

    active_filter = request.form.get("filter", "all")
    if active_filter not in ("all", "my-teams"):
        active_filter = "all"

    existing_like = ActivityLike.query.filter_by(
        activity_id=activity.id,
        user_id=current_user.id,
    ).first()

    if existing_like:
        db.session.delete(existing_like)
        flash("Activity unliked.", "success")
    else:
        db.session.add(
            ActivityLike(
                activity_id=activity.id,
                user_id=current_user.id,
            )
        )
        flash("Activity liked.", "success")

    db.session.commit()

    return redirect(url_for("feed.activity_feed", filter=active_filter))