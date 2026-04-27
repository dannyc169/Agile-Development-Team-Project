# Agile-Development-Team-Project

StudySync is a web application for student collaboration, focused on registration/login, team creation, joining by invite code, and follow-up teamwork features.

## Team Members

Please fill in the table below with your real team details:

| UWA ID | Name | GitHub username |
|---|---|---|
| TODO | TODO | TODO |
| TODO | TODO | TODO |
| TODO | TODO | TODO |
| TODO | TODO | TODO |

## Tech Stack

- Backend: Flask
- Database: SQLite (file-based)
- ORM: Flask-SQLAlchemy / SQLAlchemy
- Auth: Flask-Login
- Forms and CSRF: Flask-WTF
- Frontend styles: Tailwind CSS (CDN)

## Local Setup and Run

The following steps are based on the studysync directory.

1. Enter the project directory

	cd studysync

2. Create and activate a virtual environment

	python3 -m venv .venv
	source .venv/bin/activate

3. Install dependencies

	pip install -r requirements.txt

4. Configure environment variables

It is recommended to use a .env file (or export environment variables), and at minimum set SECRET_KEY.

Example .env.example content:

	SECRET_KEY=replace-with-a-local-dev-secret

If you prefer shell export:

	export SECRET_KEY=replace-with-a-local-dev-secret

Note: never commit real secrets to the repository.

5. Initialize the database

The current project uses db.create_all in run.py for automatic table creation.
On first startup, a SQLite file is automatically created in the instance directory.

6. Start the service

	python3 run.py

7. Open the app

	http://127.0.0.1:5000/login

## Database Notes

- The database type is fixed to SQLite.
- Default database file path: studysync/instance/studysync.db.
- Postgres or MySQL is not required.

## Basic Feature Demo

1. Register

- Open /register
- Enter a username and password, then submit
- Expected: registration succeeds and redirects to dashboard

2. Login / Logout

- Open /login and sign in with a registered account
- Expected: login succeeds and redirects to dashboard
- Click the Logout button in the sidebar
- Expected: logout succeeds and returns to /login

2.1 Password Change (Logged-in)

- After login, open /account/password
- Enter current password, a new password (8+ characters), and confirmation
- Expected: update succeeds, shows a message, and redirects to dashboard

2.2 Password Reset (Logged-out demo flow)

- Click Forgot password? on /login
- Open /reset-password, enter username or email + new password + confirm new password
- Expected: shows "Password updated, please login." and returns to /login
- Note: this is a simplified course demo flow and can later be replaced with an email token reset flow

3. Create Team

- After login, open /teams
- Click Create team
- Fill in name and description, then submit
- Expected: team is created, creator becomes leader automatically, redirects to team detail page, and shows invite code

4. Join Team

- Log in with another account
- Open /teams/join
- Enter invite code and submit
- Expected: successfully joins and enters the team detail page
- If invite code does not exist: an error message appears
- If joining twice: a duplicate-join message appears

## Tests

Current automated tests: TBD

Reserved test command:

	pytest
