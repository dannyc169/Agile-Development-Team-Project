# StudySync

A lightweight Flask web application built as part of a UWA Agile Development project. StudySync helps student teams stay organized and accountable by providing team spaces, user authentication, and an incentive-based challenge system called Wagers.

This project is designed to be simple to run locally, easy to extend, and clear enough to serve as a student portfolio or capstone project.

## Overview

StudySync provides a basic collaboration environment for student teams. Users can create or join teams, track shared goals, and participate in Wagers, team challenges that include stakes, deadlines, and task lists. The goal is to encourage motivation and consistent progress within groups.

## Key Features

### Authentication and Account Management

- User registration and login using Flask-Login
- Session management and logout
- Change password for logged-in users
- Demo-style password reset flow that can be extended to email token verification later

### Teams

- Create teams with a name and description
- Join teams using a generated invite code
- Role-based behavior, with team leader permissions enforced in key actions such as creating Wagers

### Wagers (Team Challenges)

Wagers convert team goals into structured challenges with clear incentives.

- Team leaders can create Wagers with titles, descriptions, start/end dates, stake amounts, and checklists
- Team members are automatically enrolled once a Wager is created
- Participants track progress with statuses like On Track, At Risk, Completed, Failed
- A simple prize-pool model based on stake amounts is illustrated through the interface

### User Interface

- Dashboard after login
- Team pages for creating, joining, and viewing details
- Wager creation and detail pages
- Placeholder feed page for future updates

## Tech Stack

- Backend: Flask
- Database: SQLite, stored under `instance/`
- ORM: SQLAlchemy / Flask-SQLAlchemy
- Authentication: Flask-Login
- Forms and CSRF protection: Flask-WTF
- Frontend: HTML templates with Jinja and Tailwind CSS (CDN)

## Getting Started (Local Development)

The following steps assume you are running commands inside the `studysync` directory.

1. Enter the project directory

```bash
cd studysync
```

2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Configure environment variables

Set the Flask `SECRET_KEY` for the Host, and set the Host address for Clients:

```bash
export SECRET_KEY=replace-with-your-local-secret
export HOST_BASE_URL=http://192.168.1.50:5000
```

Do not commit real secrets into the repository.

## Host-Client Deployment

StudySync now runs in a Host-Client layout for LAN use, while keeping the existing features, pages, and business logic unchanged.

### Host

The Host owns the SQLite database and runs the full Flask backend.

Run it with:

```bash
python3 host.py
```

Default Host settings:

- Bind address: `0.0.0.0`
- Port: `5000`
- Database file: `studysync/instance/studysync.db`

Optional Host overrides:

```bash
export HOST_BIND=0.0.0.0
export HOST_PORT=5000
export FLASK_DEBUG=1
```

### Client

The Client is a thin local reverse proxy. It does not access the database directly; it forwards browser traffic to the Host over the LAN while keeping the same routes, forms, sessions, and responses.

Run it with:

```bash
python3 client.py
```

Default Client settings:

- Bind address: `0.0.0.0`
- Port: `5001`
- Upstream Host: `http://127.0.0.1:5000`

Set the Host IP or hostname with:

```bash
export HOST_BASE_URL=http://192.168.1.50:5000
export CLIENT_PORT=5001
```

Open the Client in your browser:

- Client URL: http://127.0.0.1:5001

The Client forwards all requests to the Host, so the existing login, dashboard, teams, tasks, feed, and wager flows remain unchanged.

### Backward Compatibility

The original `python3 run.py` command still starts the Host for compatibility.

## End-to-End Testing

An automated end-to-end test is available using Playwright. It exercises the full user journey: registration, team creation, joining, task management, and wagers.

### Setup

Install Playwright (required for e2e testing):

```bash
pip install playwright
python -m playwright install
```

### Run the Test

From the `studysync` directory:

```bash
python3 e2e_test.py --base-url http://127.0.0.1:5000
```

Options:

- `--base-url` (default: http://127.0.0.1:5000) — URL of Host or Client
- `--headed` — Show browser window (default: headless)
- `--slowmo <ms>` — Slow down actions by N milliseconds for demo

Example with visible browser and slowdown:

```bash
python3 e2e_test.py --base-url http://127.0.0.1:5001 --headed --slowmo 500
```

The test will:
- Create 4 users with unique suffixes
- Create a team and extract the invite code
- Register members and join the team
- Visit key pages (dashboard, todos, teams, wagers, feed)
- Perform operations (change password, logout, login with new credentials)
- Print clear step-by-step logs
- Save screenshots on failure
- Exit with status 0 on success, 1 on failure

## Quick Feature Walkthrough

### Register

Navigate to `/register`, create an account, and you will be redirected to the dashboard.

### Login / Logout

Use `/login` to log in. The sidebar includes a logout button.

### Create a Team

Go to `/teams` to create a new team. The team detail page will display its invite code.

### Join a Team

Log in as another user and go to `/teams/join`. Enter the invite code to join.

### Create a Wager (Team Leader)

Visit `/wagers/create` and select a team you lead.
Configure the stake, dates, tasks, and create the Wager.
All team members will be automatically added as participants.

## Project Structure

```text
.
├── README.md
└── studysync/
    ├── client.py
    ├── client_proxy.py
    ├── host.py
    ├── run.py
    ├── requirements.txt
    ├── seed.py
    └── app/
        ├── __init__.py
        ├── models.py
        ├── forms.py
        ├── teams.py
        ├── tasks.py
        └── templates/
```
