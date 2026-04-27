import secrets

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import TeamCreateForm, TeamJoinForm
from app.models import Team, TeamMember, User, is_team_leader, is_team_member


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

	return render_template(
		"teams/detail.html",
		team=team,
		member_rows=member_rows,
		member_count=member_count,
		leader_username=leader_username,
		is_leader=is_leader,
	)