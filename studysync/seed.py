from datetime import timedelta

from app import create_app, db
from app.models import Activity, ActivityLike, Nudge, Task, Team, TeamMember, User
from app.time_utils import now_app_time


app = create_app()


def get_or_create_user(username, email, password="password123"):
    """Create a demo user if the username does not already exist."""
    user = User.query.filter_by(username=username).first()

    if user is None:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

    return user


def get_or_create_team(name, description, code, leader):
    """Create a demo team and leader membership if they do not already exist."""
    team = Team.query.filter_by(code=code).first()

    if team is None:
        team = Team(
            name=name,
            description=description,
            code=code,
            created_by_user_id=leader.id,
        )
        db.session.add(team)
        db.session.flush()

        db.session.add(
            TeamMember(
                team_id=team.id,
                user_id=leader.id,
                role="leader",
            )
        )
        db.session.commit()

    return team


def add_member_if_missing(team, user, role="member"):
    """Add a user to the demo team if they are not already a member."""
    existing_member = TeamMember.query.filter_by(
        team_id=team.id,
        user_id=user.id,
    ).first()

    if existing_member is None:
        db.session.add(
            TeamMember(
                team_id=team.id,
                user_id=user.id,
                role=role,
            )
        )
        db.session.commit()


def add_task_if_missing(title, description, status, priority, due_date, team, user):
    """Create a demo task if a task with the same title does not already exist for this team."""
    existing_task = Task.query.filter_by(
        title=title,
        team_id=team.id,
    ).first()

    if existing_task is None:
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            team_id=team.id,
            user_id=user.id,
        )
        db.session.add(task)
        db.session.commit()
        return task

    return existing_task


def add_activity_if_missing(message, action_type, user, team, task=None):
    """Create a demo activity record if the same message does not already exist."""
    existing_activity = Activity.query.filter_by(
        message=message,
        team_id=team.id,
    ).first()

    if existing_activity is None:
        activity = Activity(
            user_id=user.id,
            team_id=team.id,
            task_id=task.id if task else None,
            action_type=action_type,
            message=message,
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    return existing_activity


def add_activity_like_if_missing(activity, user):
    """Create a demo like if the user has not already liked this activity."""
    existing_like = ActivityLike.query.filter_by(
        activity_id=activity.id,
        user_id=user.id,
    ).first()

    if existing_like is None:
        db.session.add(
            ActivityLike(
                activity_id=activity.id,
                user_id=user.id,
            )
        )
        db.session.commit()


def add_nudge_if_missing(task, team, nudger, recipient, created_at):
    """Create a demo nudge if the same nudger has not already nudged this task."""
    existing_nudge = Nudge.query.filter_by(
        task_id=task.id,
        team_id=team.id,
        nudger_id=nudger.id,
        recipient_id=recipient.id,
    ).first()

    if existing_nudge is None:
        nudge = Nudge(
            task_id=task.id,
            team_id=team.id,
            nudger_id=nudger.id,
            recipient_id=recipient.id,
            created_at=created_at,
        )
        db.session.add(nudge)
        db.session.commit()
        return nudge

    return existing_nudge


with app.app_context():
    # Make sure all tables exist before inserting demo data.
    db.create_all()

    now = now_app_time()

    # Demo users
    leader = get_or_create_user(
        username="demo_leader",
        email="demo.leader@example.com",
    )

    member_one = get_or_create_user(
        username="demo_member",
        email="demo.member@example.com",
    )

    member_two = get_or_create_user(
        username="demo_partner",
        email="demo.partner@example.com",
    )

    # Demo team
    team = get_or_create_team(
        name="StudySync Demo Team",
        description="A checkpoint demo team for testing team tasks and activity feed.",
        code="DEMO01",
        leader=leader,
    )

    add_member_if_missing(team, member_one)
    add_member_if_missing(team, member_two)

    # Demo team tasks.
    # The app no longer uses in_progress as a separate task state.
    # Partially completed subtask progress remains Todo until the task is fully done.
    task_one = add_task_if_missing(
        title="Design database schema",
        description="Prepare the first version of the database models for the project.",
        status="todo",
        priority="high",
        due_date=now + timedelta(days=2),
        team=team,
        user=leader,
    )

    task_two = add_task_if_missing(
        title="Build team detail page",
        description="Render team members, task board, and recent activity using Jinja.",
        status="todo",
        priority="medium",
        due_date=now + timedelta(days=1),
        team=team,
        user=member_one,
    )

    task_three = add_task_if_missing(
        title="Create Flask app skeleton",
        description="Set up the Flask app factory, templates, login, and basic routes.",
        status="done",
        priority="low",
        due_date=now - timedelta(days=1),
        team=team,
        user=member_two,
    )

    # Demo recent activity
    activity_one = add_activity_if_missing(
        message="demo_leader created StudySync Demo Team.",
        action_type="created_team",
        user=leader,
        team=team,
    )

    activity_two = add_activity_if_missing(
        message="demo_member has a todo task: Build team detail page.",
        action_type="moved_task_status",
        user=member_one,
        team=team,
        task=task_two,
    )

    activity_three = add_activity_if_missing(
        message="demo_partner completed Create Flask app skeleton.",
        action_type="completed_task",
        user=member_two,
        team=team,
        task=task_three,
    )

    # Demo likes for Activity Feed testing
    add_activity_like_if_missing(activity_one, member_one)
    add_activity_like_if_missing(activity_one, member_two)
    add_activity_like_if_missing(activity_two, leader)
    add_activity_like_if_missing(activity_three, leader)
    add_activity_like_if_missing(activity_three, member_one)

    # Demo nudge for Team Task Board testing
    add_nudge_if_missing(
        task=task_two,
        team=team,
        nudger=member_two,
        recipient=member_one,
        created_at=now - timedelta(hours=25),
    )

    add_activity_if_missing(
        message="demo_partner nudged demo_member to finish Build team detail page.",
        action_type="nudged_member",
        user=member_two,
        team=team,
        task=task_two,
    )

    print("Demo seed data created successfully.")
    print("Login with:")
    print("  username: demo_leader")
    print("  password: password123")
    print("Then open:")
    print(f"  /teams/{team.id}")
