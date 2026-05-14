from datetime import date

from app import db
from app.models import Task, TeamMember, Wager, WagerParticipant, WagerTask


def resolve_linked_task(link, wager):
    """Get the real task linked to a wager task link."""
    if getattr(link, "task", None) is not None:
        return link.task

    task_id = getattr(link, "task_id", None)
    if task_id is not None:
        task = db.session.get(Task, task_id)
        if task is not None:
            return task

    if getattr(link, "task_name", None):
        return (
            Task.query.filter_by(
                team_id=wager.team_id,
                title=link.task_name,
            )
            .order_by(Task.created_at.desc())
            .first()
        )

    return None


def count_done_tasks_for_wager(wager):
    """Count how many linked tasks of this wager are completed."""
    done_count = 0

    for link in wager.linked_tasks:
        linked_task = resolve_linked_task(link, wager)

        if linked_task is not None and linked_task.status == "done":
            done_count += 1

    return done_count


def calculate_wager_progress(wager):
    """Calculate wager task progress based on linked tasks."""
    total_tasks = len(wager.linked_tasks)
    done_tasks = count_done_tasks_for_wager(wager)

    if total_tasks == 0:
        return 0, 0, 0

    progress_percent = min(100, int((done_tasks / total_tasks) * 100))
    return total_tasks, done_tasks, progress_percent


def calculate_participant_status(tasks_done, tasks_total, end_date_value):
    """Calculate participant status for a team-level wager."""
    today = date.today()

    if tasks_total > 0 and tasks_done >= tasks_total:
        return "completed"

    if end_date_value is None:
        return "on_track"

    if today > end_date_value and tasks_done < tasks_total:
        return "failed"

    days_left = (end_date_value - today).days
    if days_left <= 2 and tasks_done < tasks_total:
        return "at_risk"

    return "on_track"


def calculate_reward_amount(status, stake_amount):
    """Calculate reward amount based on participant status."""
    if status == "completed":
        return stake_amount

    if status in {"on_track", "at_risk"}:
        return stake_amount

    return 0


def sync_wager_status(wager):
    """
    Sync Wager and WagerParticipant status/progress.

    This function only updates SQLAlchemy objects.
    The caller is responsible for db.session.commit().
    """
    total_tasks, done_tasks, progress_percent = calculate_wager_progress(wager)

    participant_status = calculate_participant_status(
        done_tasks,
        total_tasks,
        wager.end_date,
    )

    if participant_status == "completed":
        wager_status = "completed"
    elif participant_status == "failed":
        wager_status = "failed"
    else:
        wager_status = "active"

    changed = False

    if wager.status != wager_status:
        wager.status = wager_status
        changed = True

    for participant in wager.participants:
        reward_amount = calculate_reward_amount(
            participant_status,
            wager.stake_amount,
        )

        if participant.progress != progress_percent:
            participant.progress = progress_percent
            changed = True

        if participant.status != participant_status:
            participant.status = participant_status
            changed = True

        if participant.reward_amount != reward_amount:
            participant.reward_amount = reward_amount
            changed = True

    return changed


def sync_wagers(wagers):
    """
    Sync multiple wagers.

    This function does not commit.
    Do not call this from GET routes just to update the database.
    """
    changed = False

    for wager in wagers:
        if sync_wager_status(wager):
            changed = True

    return changed


def sync_wagers_for_task(task):
    """
    Sync all wagers linked to this task.

    This should be called when task.status changes.
    The caller is responsible for db.session.commit().
    """
    if task is None:
        return False

    linked_rows = WagerTask.query.filter_by(task_id=task.id).all()
    wager_ids = [row.wager_id for row in linked_rows]

    if not wager_ids:
        return False

    wagers = Wager.query.filter(Wager.id.in_(wager_ids)).all()

    changed = False
    for wager in wagers:
        if sync_wager_status(wager):
            changed = True

    return changed


def count_wagers_won_for_user(user_id, team_ids=None):
    """Count how many wagers a user has completed."""
    if team_ids is not None:
        if not team_ids:
            return 0

        wagers = Wager.query.filter(Wager.team_id.in_(team_ids)).all()
    else:
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

        total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

        if total_tasks > 0 and done_tasks >= total_tasks:
            won_count += 1

    return won_count


def calculate_total_points(user_id, team_ids=None):
    """Calculate total wager points for a user."""
    if team_ids is not None:
        if not team_ids:
            return 0

        wagers = Wager.query.filter(Wager.team_id.in_(team_ids)).all()
    else:
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

        total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

        if total_tasks > 0 and done_tasks >= total_tasks:
            total_points += wager.stake_amount

    return total_points