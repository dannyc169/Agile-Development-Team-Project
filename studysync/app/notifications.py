from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Notification


notifications_bp = Blueprint("notifications", __name__)


def _safe_redirect(link):
    """
    Redirect only to internal relative links.

    This prevents unexpected external redirects such as //example.com.
    """
    if link and link.startswith("/") and not link.startswith("//"):
        return redirect(link)

    return redirect(url_for("notifications.notifications"))


@notifications_bp.route("/notifications")
@login_required
def notifications():
    """
    Show the current user's notifications.

    This GET route only reads data.
    Notifications are marked as read only when the user opens them or uses
    Mark all as read.
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
    """Mark all of the current user's notifications as read."""
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

    The notification is loaded by both ID and current user ID, so users cannot
    open or mark other users' notifications.
    """
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id,
    ).first_or_404()

    if not notification.is_read:
        notification.is_read = True
        db.session.commit()

    return _safe_redirect(notification.link)
