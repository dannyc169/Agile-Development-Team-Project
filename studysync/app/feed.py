from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.models import Activity, ActivityLike, TeamMember


feed_bp = Blueprint("feed", __name__)


@feed_bp.route("/feed")
@login_required
def activity_feed():
    """Render the global activity feed with optional My Teams filtering."""
    active_filter = request.args.get("filter", "all")

    if active_filter not in ("all", "my-teams"):
        active_filter = "all"

    team_ids = [
        membership.team_id
        for membership in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]

    activity_query = Activity.query.order_by(Activity.created_at.desc())

    if active_filter == "my-teams":
        if team_ids:
            activity_query = activity_query.filter(Activity.team_id.in_(team_ids))
            activities = activity_query.limit(50).all()
        else:
            activities = []
    else:
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
