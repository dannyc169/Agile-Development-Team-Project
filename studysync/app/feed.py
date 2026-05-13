from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import Activity, ActivityLike, TeamMember


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

    return render_template(
        "feed/index.html",
        activities=activities,
        active_filter=active_filter,
        liked_activity_ids=liked_activity_ids,
        like_counts=like_counts,
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
