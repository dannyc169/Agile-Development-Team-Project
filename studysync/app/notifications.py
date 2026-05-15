from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def notifications():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    unread_ids = [n.id for n in items if not n.is_read]
    if unread_ids:
        Notification.query.filter(Notification.id.in_(unread_ids)).update(
            {"is_read": True}, synchronize_session=False
        )
        db.session.commit()

    return render_template("notifications/index.html", notifications=items)


@notifications_bp.route("/notifications/<int:notification_id>/open")
@login_required
def open_notification(notification_id):
    n = Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first_or_404()

    n.is_read = True
    db.session.commit()

    if n.link:
        return redirect(n.link)
    return redirect(url_for("notifications.notifications"))
