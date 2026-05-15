from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Notification


notifications_bp = Blueprint("notifications", __name__)


def _safe_redirect(link):
    """
    Only redirect to internal links.

    This avoids redirecting users to unexpected external URLs.
    """
    if link and link.startswith("/"):
        return redirect(link)

    return redirect(url_for("notifications.notifications"))


@notifications_bp.route("/notifications")
@login_required
def notifications():
    """
    Show the user's notifications.

    This is a GET route, so it should only read data.
    It should not mark notifications as read automatically.
    """
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    unread_count = sum(1 for item in items if not item.is_read)

    return render_template(
        "notifications/index.html",
        notifications=items,
        unread_count=unread_count,
    )


@notifications_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    """
    Mark all notifications as read.

    This modifies the database, so it uses POST instead of GET.
    """
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).update(
        {"is_read": True},
        synchronize_session=False,
    )

    db.session.commit()

    return redirect(url_for("notifications.notifications"))


@notifications_bp.route("/notifications/<int:notification_id>/open", methods=["POST"])
@login_required
def open_notification(notification_id):
    """
    Open one notification and mark it as read.

    This modifies the database, so it uses POST instead of GET.
    """
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id,
    ).first_or_404()

    if notification.user_id != current_user.id:
        abort(403)

    if not notification.is_read:
        notification.is_read = True
        db.session.commit()

    return _safe_redirect(notification.link)