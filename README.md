# StudySync

StudySync is a team study collaboration web app for university students. It brings together the common tasks of group study and assignments into one place: member management, task assignment, progress tracking, team activity feeds, and notifications.

The app is built around **teams** as the core unit. Users can create or join teams, then create tasks within a team, assign them to members, and update completion status. Team members can stay up to date through the activity feed and receive alerts for key events via the notification system. To help motivate task completion, the app also includes a **Wager** feature, where members can stake points on who finishes a task on time.

**Example use cases:**
- Course group assignments: break down tasks, assign to members, track progress
- Study groups: set tasks, check team activity, keep each other accountable
- Student clubs or projects: use tasks and notifications to stay in sync

---

## Features

- User registration and login
- Create and join teams
- Create tasks within a team, assign to members, and mark as complete
- Activity feed to follow team updates
- Notification system for key events
- Wager feature — stake points on who completes a task on time

---

## Tech Stack

- Python Flask
- SQLite
- SQLAlchemy
- Jinja2 templates
- Tailwind CSS
- Selenium for end-to-end testing

---

## Team Members

| UWA ID   | Name        | GitHub Username |
|----------|-------------|-----------------|
| 24289151 | Wu Jinghan  | Jinghan0412     |
| 24213379 | Kunyu He    | Y0gnut          |
| 24993619 | Chen Di     | dannyc169       |
| 24458695 | Keming Cao  | kemingcao       |

---

## Project Requirements Mapping

- **Client-server architecture:** The application uses Flask routes, Jinja templates, and a SQLite database.
- **Login and logout:** Users can register, log in, and log out.
- **Persistent user data:** User, team, task, notification, and wager data are stored using SQLite and SQLAlchemy.
- **Viewing other users' data:** Team members can view team tasks, member progress, activity feed updates, and notifications.

---

## Getting Started

Run the following commands from inside the `studysync` directory:

```bash
cd studysync
pip install -r requirements.txt
python3 host.py
```

Once started, open the address shown in the terminal output in your browser.

---

## Running Tests

### Unit Tests

```bash
pytest tests/unit/
```

### Selenium E2E Tests

Selenium tests require a running server. Start `python3 host.py` in one terminal, then in a second terminal run:

```bash
pytest tests/e2e_selenium/ -m e2e -v
```