from app.models import Task, Team, TeamMember, User


def register_user(client, username, password="password123"):
	return client.post(
		"/register",
		data={
			"username": username,
			"email": "",
			"password": password,
			"confirm_password": password,
		},
		follow_redirects=True,
	)


def login_user(client, username, password="password123"):
	return client.post(
		"/login",
		data={
			"username": username,
			"password": password,
			"remember_me": "y",
		},
		follow_redirects=True,
	)


def test_unauthenticated_team_page_redirects_to_login(client):
	response = client.get("/teams", follow_redirects=False)

	assert response.status_code == 302
	assert "/login" in response.headers["Location"]


def test_register_creates_user(client, app):
	response = register_user(client, "alice")

	assert response.status_code == 200

	with app.app_context():
		user = User.query.filter_by(username="alice").one()
		assert user.email is None
		assert user.check_password("password123")


def test_login_allows_dashboard_and_teams_access(client):
	register_user(client, "bob")

	logout_response = client.post("/logout", follow_redirects=True)
	assert logout_response.status_code == 200

	login_response = login_user(client, "bob")
	assert login_response.status_code == 200

	dashboard_response = client.get("/dashboard")
	teams_response = client.get("/teams")

	assert dashboard_response.status_code == 200
	assert teams_response.status_code == 200


def test_create_team_creates_leader_membership(client, app):
	register_user(client, "carol")

	response = client.post(
		"/teams/create",
		data={
			"name": "Project Alpha",
			"description": "Study group",
		},
		follow_redirects=True,
	)

	assert response.status_code == 200

	with app.app_context():
		user = User.query.filter_by(username="carol").one()
		team = Team.query.filter_by(name="Project Alpha").one()
		membership = TeamMember.query.filter_by(team_id=team.id, user_id=user.id).one()

		assert team.created_by_user_id == user.id
		assert membership.role == "leader"


def test_create_task_and_mark_done_updates_database(client, app):
	register_user(client, "dave")

	client.post(
		"/teams/create",
		data={
			"name": "Project Beta",
			"description": "Team for task testing",
		},
		follow_redirects=True,
	)

	with app.app_context():
		team = Team.query.filter_by(name="Project Beta").one()
		user = User.query.filter_by(username="dave").one()

	create_response = client.post(
		"/tasks/create",
		data={
			"title": "Draft report",
			"description": "Write the first draft",
			"priority": "high",
			"due_date": "",
			"team_id": str(team.id),
			"assigned_to_user_id": "",
		},
		follow_redirects=False,
	)

	assert create_response.status_code == 302

	with app.app_context():
		task = Task.query.filter_by(title="Draft report").one()
		assert task.user_id == user.id
		assert task.team_id == team.id
		assert task.priority == "high"
		assert task.status == "todo"

	done_response = client.post(
		f"/tasks/{task.id}/status",
		data={"status": "done"},
		follow_redirects=False,
	)

	assert done_response.status_code == 302

	with app.app_context():
		updated_task = Task.query.get(task.id)
		assert updated_task is not None
		assert updated_task.status == "done"
