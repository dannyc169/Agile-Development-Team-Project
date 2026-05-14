from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import Activity, ActivityComment, ActivityLike, TeamMember, Task, User, Wager
from app.wager_helpers import (
    calculate_total_points,
    calculate_wager_progress,
)


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


def _build_active_wager_cards(team_ids):
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

        total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)
        total_participants = len(wager.participants)

        if total_tasks > 0 and done_tasks >= total_tasks:
            continue

        if wager.end_date:
            days_left = (wager.end_date - today).days
            time_remaining = f"{days_left}d left"
        else:
            time_remaining = "No deadline"

        prize_pool = wager.stake_amount * max(total_participants, 1)

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


def _build_leaderboard(team_ids):
    if not team_ids:
        return []

    member_rows = TeamMember.query.filter(TeamMember.team_id.in_(team_ids)).all()
    user_ids = sorted(set(row.user_id for row in member_rows))

    if not user_ids:
        return []

    users = (
        User.query.filter(User.id.in_(user_ids))
        .order_by(User.username.asc())
        .all()
    )

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
        completed_task_count = Task.query.filter(
            Task.user_id == user.id,
            Task.status == "done",
            Task.team_id.in_(team_ids),
        ).count()

        points = calculate_total_points(user.id, team_ids)

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
        key=lambda item: (
            -item["points"],
            -item["completed_task_count"],
            item["name"].lower(),
        )
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
    leaderboard = _build_leaderboard(team_ids)

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


@feed_bp.route("/feed/<int:activity_id>/comments", methods=["POST"])
@login_required
def add_comment(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    team_ids = _current_user_team_ids()
    if not _can_view_activity(activity, team_ids):
        abort(403)

    if len(activity.comments) >= 50:
        flash("Comment limit of 50 reached.", "error")
        active_filter = request.form.get("filter", "all")
        return redirect(url_for("feed.activity_feed", filter=active_filter))

    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
        active_filter = request.form.get("filter", "all")
        return redirect(url_for("feed.activity_feed", filter=active_filter))

    db.session.add(ActivityComment(
        activity_id=activity.id,
        user_id=current_user.id,
        body=body[:500],
    ))
    db.session.commit()

    active_filter = request.form.get("filter", "all")
    return redirect(url_for("feed.activity_feed", filter=active_filter))


@feed_bp.route("/feed/<int:activity_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(activity_id, comment_id):
    comment = ActivityComment.query.get_or_404(comment_id)
    if comment.activity_id != activity_id or comment.user_id != current_user.id:
        abort(403)

    db.session.delete(comment)
    db.session.commit()

    active_filter = request.form.get("filter", "all")
    return redirect(url_for("feed.activity_feed", filter=active_filter))
