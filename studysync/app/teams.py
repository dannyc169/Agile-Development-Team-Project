import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import TeamCreateForm, TeamJoinForm
from app.models import Activity, Nudge, Task, Team, TeamMember, User, is_team_leader, is_team_member

teams_bp = Blueprint("teams", __name__, url_prefix="/teams")


def _generate_team_code(length=6):
	alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	while True:
		code = "".join(secrets.choice(alphabet) for _ in range(length))
		if Team.query.filter_by(code=code).first() is None:
			return code


@teams_bp.route("")
@login_required
def index():
	teams = (
		Team.query.join(TeamMember, Team.id == TeamMember.team_id)
		.filter(TeamMember.user_id == current_user.id)
		.order_by(Team.created_at.desc())
		.all()
	)
	return render_template("teams/index.html", teams=teams)


@teams_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_team():
	form = TeamCreateForm()
	if form.validate_on_submit():
		team = Team(
			name=form.name.data.strip(),
			description=form.description.data.strip() or None,
			code=_generate_team_code(),
			created_by_user_id=current_user.id,
		)
		db.session.add(team)
		db.session.flush()
		db.session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="leader"))
		db.session.commit()
		flash("Team created.", "success")
		return redirect(url_for("teams.team_detail", team_id=team.id))
	return render_template("teams/create.html", form=form)


@teams_bp.route("/join", methods=["GET", "POST"])
@login_required
def join_team():
	form = TeamJoinForm()
	if form.validate_on_submit():
		code = form.code.data.strip().upper()
		team = Team.query.filter_by(code=code).first()
		if team is None:
			flash("Team code not found.", "error")
		elif is_team_member(team.id, current_user.id):
			flash("You are already a member of this team.", "error")
		else:
			db.session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="member"))
			db.session.commit()
			flash("Joined team successfully.", "success")
			return redirect(url_for("teams.team_detail", team_id=team.id))
	return render_template("teams/join.html", form=form)


@teams_bp.route("/<int:team_id>")
@login_required
def team_detail(team_id):
	team = Team.query.get_or_404(team_id)
	if not is_team_member(team.id, current_user.id):
		abort(403)

	member_rows = (
		TeamMember.query.filter_by(team_id=team.id)
		.join(User, User.id == TeamMember.user_id)
		.order_by(TeamMember.joined_at.asc())
		.all()
	)
	member_count = len(member_rows)
	leader_username = next((row.user.username for row in member_rows if row.role == "leader"), None)
	is_leader = is_team_leader(team.id, current_user.id)

	todo_tasks = (
		Task.query.filter_by(team_id=team.id, status="todo")
		.order_by(Task.due_date.asc(), Task.created_at.desc())
		.all()
	)

	in_progress_tasks = (
		Task.query.filter_by(team_id=team.id, status="in_progress")
		.order_by(Task.due_date.asc(), Task.created_at.desc())
		.all()
	)

	done_tasks = (
		Task.query.filter_by(team_id=team.id, status="done")
		.order_by(Task.created_at.desc())
		.all()
	)

	recent_activities = (
		Activity.query.filter_by(team_id=team.id)
		.order_by(Activity.created_at.desc())
		.limit(5)
		.all()
	)

	team_tasks = todo_tasks + in_progress_tasks + done_tasks
	team_task_ids = [task.id for task in team_tasks]

	total_tasks_count = len(team_tasks)
	todo_tasks_count = len(todo_tasks)
	in_progress_tasks_count = len(in_progress_tasks)
	done_tasks_count = len(done_tasks)

	completion_rate = 0
	if total_tasks_count > 0:
		completion_rate = int((done_tasks_count / total_tasks_count) * 100)

	member_task_stats = {}

	for row in member_rows:
		member_tasks = [task for task in team_tasks if task.user_id == row.user_id]
		member_total = len(member_tasks)
		member_done = len([task for task in member_tasks if task.status == "done"])

		member_completion_rate = 0
		if member_total > 0:
			member_completion_rate = int((member_done / member_total) * 100)

		member_task_stats[row.user_id] = {
			"total": member_total,
			"done": member_done,
			"completion_rate": member_completion_rate,
		}

	latest_nudges_by_task = {}
	cooldown_task_ids = set()

	if team_task_ids:
		all_recent_nudges = (
			Nudge.query.filter(
				Nudge.team_id == team.id,
				Nudge.task_id.in_(team_task_ids),
			)
			.order_by(Nudge.created_at.desc())
			.all()
		)

		for nudge in all_recent_nudges:
			if nudge.task_id not in latest_nudges_by_task:
				latest_nudges_by_task[nudge.task_id] = nudge

		cooldown_start = datetime.now(timezone.utc) - timedelta(hours=24)
		cooldown_task_ids = {
			nudge.task_id
			for nudge in Nudge.query.filter(
				Nudge.team_id == team.id,
				Nudge.nudger_id == current_user.id,
				Nudge.task_id.in_(team_task_ids),
				Nudge.created_at >= cooldown_start,
			).all()
		}

	return render_template(
		"teams/detail.html",
		team=team,
		member_rows=member_rows,
		member_count=member_count,
		leader_username=leader_username,
		is_leader=is_leader,
		todo_tasks=todo_tasks,
		in_progress_tasks=in_progress_tasks,
		done_tasks=done_tasks,
		recent_activities=recent_activities,
		latest_nudges_by_task=latest_nudges_by_task,
		cooldown_task_ids=cooldown_task_ids,
		total_tasks_count=total_tasks_count,
		todo_tasks_count=todo_tasks_count,
		in_progress_tasks_count=in_progress_tasks_count,
		done_tasks_count=done_tasks_count,
		completion_rate=completion_rate,
		member_task_stats=member_task_stats,
	)


@teams_bp.route("/<int:team_id>/tasks/<int:task_id>/nudge", methods=["POST"])
@login_required
def nudge_task(team_id, task_id):
	"""Allow a team member to nudge another member's active team task."""
	team = Team.query.get_or_404(team_id)

	if not is_team_member(team.id, current_user.id):
		abort(403)

	task = Task.query.get_or_404(task_id)

	if task.team_id != team.id:
		abort(404)

	if task.user_id == current_user.id:
		flash("You cannot nudge your own task.", "error")
		return redirect(url_for("teams.team_detail", team_id=team.id))

	if task.status not in ("todo", "in_progress"):
		flash("Only active tasks can be nudged.", "error")
		return redirect(url_for("teams.team_detail", team_id=team.id))

	if not is_team_member(team.id, task.user_id):
		flash("You can only nudge members of this team.", "error")
		return redirect(url_for("teams.team_detail", team_id=team.id))

	cooldown_start = datetime.now(timezone.utc) - timedelta(hours=24)

	recent_nudge = (
		Nudge.query.filter_by(
			task_id=task.id,
			team_id=team.id,
			nudger_id=current_user.id,
		)
		.filter(Nudge.created_at >= cooldown_start)
		.first()
	)

	if recent_nudge is not None:
		flash("You have already nudged this task in the last 24 hours.", "error")
		return redirect(url_for("teams.team_detail", team_id=team.id))

	recipient = User.query.get(task.user_id)

	nudge = Nudge(
		task_id=task.id,
		team_id=team.id,
		nudger_id=current_user.id,
		recipient_id=task.user_id,
	)

	db.session.add(nudge)

	recipient_name = recipient.username if recipient else "a team member"

	activity = Activity(
		user_id=current_user.id,
		team_id=team.id,
		task_id=task.id,
		action_type="nudged_member",
		message=f"{current_user.username} nudged {recipient_name} to finish {task.title}.",
	)

	db.session.add(activity)
	db.session.commit()

	flash("Nudge sent successfully.", "success")
	return redirect(url_for("teams.team_detail", team_id=team.id))


@teams_bp.route("/<int:team_id>/members/<int:user_id>/tasks")
@login_required
def member_tasks(team_id, user_id):
	"""Show tasks assigned to a selected team member within the current team."""
	team = Team.query.get_or_404(team_id)

	if not is_team_member(team.id, current_user.id):
		abort(403)

	member_row = TeamMember.query.filter_by(
		team_id=team.id,
		user_id=user_id,
	).first()

	if member_row is None:
		abort(404)


	member_user = db.session.get(User, user_id)
	if member_user is None:
	    abort(404)
	
	member_tasks_list = (
	    Task.query.filter_by(team_id=team.id, user_id=member_user.id)
	    .order_by(Task.due_date.asc(), Task.created_at.desc())
	    .all()
	)
	
	todo_tasks = [task for task in member_tasks_list if task.status == "todo"]
	in_progress_tasks = [task for task in member_tasks_list if task.status == "in_progress"]
	done_tasks = [task for task in member_tasks_list if task.status == "done"]
	
	total_tasks = len(member_tasks_list)
	
	return render_template(
		"teams/member_tasks.html",
		team=team,
		member_row=member_row,
		member_user=member_user,
		todo_tasks=todo_tasks,
		in_progress_tasks=in_progress_tasks,
		done_tasks=done_tasks,
		total_tasks=total_tasks,
	)
