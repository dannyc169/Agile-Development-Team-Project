from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db
from app.models import (
    Activity,
    ActivityComment,
    ActivityLike,
    Notification,
    Team,
    TeamMember,
)
from app.wager_helpers import (
    POINTS_PER_TASK,
    build_team_leaderboard,
    calculate_wager_user_progress,
    get_active_personal_wagers_for_user,
)


feed_bp = Blueprint("feed", __name__)


def _current_user_team_ids():
    """Return team ids that the current user belongs to."""
    return [
        membership.team_id
        for membership in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def _current_user_teams():
    """Return teams that the current user belongs to, ordered by name."""
    memberships = (
        TeamMember.query.join(Team, Team.id == TeamMember.team_id)
        .filter(TeamMember.user_id == current_user.id)
        .order_by(Team.name.asc())
        .all()
    )

    return [membership.team for membership in memberships]


def _select_feed_team(user_teams):
    """
    Pick the team currently shown on the feed page.

    If the requested team_id is invalid or not owned by the current user,
    fall back to the first team.
    """
    if not user_teams:
        return None

    selected_team_id = request.args.get("team_id", type=int)
    valid_team_ids = [team.id for team in user_teams]

    if selected_team_id not in valid_team_ids:
        selected_team_id = valid_team_ids[0]

    for team in user_teams:
        if team.id == selected_team_id:
            return team

    return user_teams[0]


def _can_view_activity(activity, team_ids):
    """Return whether the current user is allowed to view this activity."""
    if activity.team_id is None:
        return True

    return activity.team_id in team_ids


def _selected_team_redirect_args():
    """Preserve the selected team after like/comment actions."""
    selected_team_id = request.form.get("team_id", type=int)

    if selected_team_id:
        return {"team_id": selected_team_id}

    return {}


def _leaderboard_display_class(rank):
    """Return display classes for leaderboard rank."""
    if rank == 1:
        return "text-yellow-600"

    if rank == 2:
        return "text-gray-400"

    if rank == 3:
        return "text-orange-600"

    return "text-gray-500"


def _add_feed_display_fields(leaderboard):
    """
    Add feed-only display fields to leaderboard rows.

    The actual leaderboard logic stays in wager_helpers.py.
    """
    avatar_colors = [
        "bg-purple-500",
        "bg-pink-500",
        "bg-orange-500",
        "bg-teal-500",
        "bg-indigo-500",
        "bg-blue-500",
    ]

    decorated_rows = []

    for index, item in enumerate(leaderboard[:5]):
        row = dict(item)
        rank = row.get("rank", index + 1)

        row["rank"] = rank
        row["avatar_class"] = avatar_colors[index % len(avatar_colors)]
        row["rank_class"] = _leaderboard_display_class(rank)

        badge = row.get("badge") or {}
        row["badge_name"] = badge.get("name", "New Learner")
        row["badge_class"] = badge.get("class", "bg-slate-100 text-slate-600")

        decorated_rows.append(row)

    return decorated_rows


def _build_active_wager_cards(team_id):
    """Build personal active wager cards for the selected team.

    Activity Feed is a personal page. Even if the current user is a team
    leader, this sidebar should only show wagers that belong to the current
    user in the selected team. Team-wide wager management stays on the Wager
    page's Team Members view.
    """
    if team_id is None:
        return []

    today = date.today()
    wagers = get_active_personal_wagers_for_user(
        current_user.id,
        team_ids=[team_id],
    )

    active_wagers = []

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

    for wager in wagers:
        if wager.end_date and wager.end_date < today:
            continue

        user_tasks_total, user_tasks_done, user_progress_percent = (
            calculate_wager_user_progress(wager, current_user.id)
        )

        if user_tasks_total > 0 and user_tasks_done >= user_tasks_total:
            continue

        if wager.end_date:
            days_left = (wager.end_date - today).days
            time_remaining = f"{days_left}d left"
        else:
            time_remaining = "No deadline"

        points_earned = user_tasks_done * POINTS_PER_TASK
        total_possible_points = user_tasks_total * POINTS_PER_TASK
        theme = theme_options[len(active_wagers) % len(theme_options)]

        active_wagers.append(
            {
                "id": wager.id,
                "title": wager.title,
                "time_remaining": time_remaining,
                "points_earned": points_earned,
                "total_possible_points": total_possible_points,
                "points_per_task": POINTS_PER_TASK,
                "progress_percent": user_progress_percent,
                "tasks_done": user_tasks_done,
                "tasks_total": user_tasks_total,
                "container_class": theme["container_class"],
                "badge_class": theme["badge_class"],
            }
        )

    return active_wagers[:3]


def _get_feed_activities(selected_team):
    """Return activities for the selected team."""
    if selected_team is None:
        return []

    return (
        Activity.query.filter(Activity.team_id == selected_team.id)
        .order_by(Activity.created_at.desc())
        .limit(50)
        .all()
    )


@feed_bp.route("/feed")
@login_required
def activity_feed():
    """Render the Activity Feed page for the selected team."""
    user_teams = _current_user_teams()
    selected_team = _select_feed_team(user_teams)
    selected_team_id = selected_team.id if selected_team else None

    activities = _get_feed_activities(selected_team)
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

    active_wagers = _build_active_wager_cards(selected_team_id)

    if selected_team_id:
        leaderboard = build_team_leaderboard(
            selected_team_id,
            current_user_id=current_user.id,
        )
    else:
        leaderboard = []

    leaderboard = _add_feed_display_fields(leaderboard)

    return render_template(
        "feed/index.html",
        activities=activities,
        user_teams=user_teams,
        selected_team=selected_team,
        selected_team_id=selected_team_id,
        liked_activity_ids=liked_activity_ids,
        like_counts=like_counts,
        active_wagers=active_wagers,
        leaderboard=leaderboard,
        points_per_task=POINTS_PER_TASK,
    )


@feed_bp.route("/feed/<int:activity_id>/like", methods=["POST"])
@login_required
def toggle_activity_like(activity_id):
    """Like or unlike an activity record if the current user can view it."""
    activity = Activity.query.get_or_404(activity_id)

    team_ids = _current_user_team_ids()

    if not _can_view_activity(activity, team_ids):
        abort(403)

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

    return redirect(url_for("feed.activity_feed", **_selected_team_redirect_args()))


@feed_bp.route("/feed/<int:activity_id>/comments", methods=["POST"])
@login_required
def add_comment(activity_id):
    """Add a comment to an activity if the current user can view it."""
    activity = Activity.query.get_or_404(activity_id)

    team_ids = _current_user_team_ids()

    if not _can_view_activity(activity, team_ids):
        abort(403)

    comment_count = ActivityComment.query.filter_by(
        activity_id=activity.id,
    ).count()

    if comment_count >= 50:
        flash("Comment limit of 50 reached.", "error")
        return redirect(url_for("feed.activity_feed", **_selected_team_redirect_args()))

    body = request.form.get("body", "").strip()

    if not body:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("feed.activity_feed", **_selected_team_redirect_args()))

    comment_body = body[:500]

    db.session.add(
        ActivityComment(
            activity_id=activity.id,
            user_id=current_user.id,
            body=comment_body,
        )
    )

    if activity.user_id != current_user.id:
        preview = body[:80]
        if len(body) > 80:
            preview += "..."

        db.session.add(
            Notification(
                user_id=activity.user_id,
                type="comment",
                message=f'{current_user.username} commented on your activity: "{preview}"',
                link=url_for(
                    "feed.activity_feed",
                    team_id=activity.team_id,
                    _anchor=f"activity-{activity.id}",
                ),
            )
        )

    db.session.commit()

    return redirect(url_for("feed.activity_feed", **_selected_team_redirect_args()))


@feed_bp.route("/feed/<int:activity_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(activity_id, comment_id):
    """Delete the current user's own comment."""
    activity = Activity.query.get_or_404(activity_id)

    team_ids = _current_user_team_ids()

    if not _can_view_activity(activity, team_ids):
        abort(403)

    comment = ActivityComment.query.filter_by(
        id=comment_id,
        activity_id=activity.id,
    ).first_or_404()

    if comment.user_id != current_user.id:
        abort(403)

    db.session.delete(comment)
    db.session.commit()

    return redirect(url_for("feed.activity_feed", **_selected_team_redirect_args()))
