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

Set the Flask `SECRET_KEY` (recommended through a `.env` file or shell export):

```bash
export SECRET_KEY=replace-with-your-local-secret
```

Do not commit real secrets into the repository.

5. Initialize the database

Tables are automatically created on startup via `db.create_all()` in `run.py`.
A SQLite file will be generated at:

```text
studysync/instance/studysync.db
```

6. Run the application

```bash
python3 run.py
```

7. Open in your browser

- Login: http://127.0.0.1:5000/login
- Register: http://127.0.0.1:5000/register

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
