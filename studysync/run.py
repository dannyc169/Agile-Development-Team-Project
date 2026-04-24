from flask import Flask, render_template, redirect, url_for, request

# Create Flask app
app = Flask(__name__, template_folder='app/templates')

# Configuration
app.secret_key = "dev-secret-key"
app.config['DEBUG'] = True

# -----------------------------
# Fake data for Wager MVP
# -----------------------------
sample_wager = {
    "id": 1,
    "title": "Complete 5 Flask Modules",
    "status": "ACTIVE",
    "prize_pool": 500,
    "time_remaining": "2d 14h",
    "participants_on_track": 4,
    "total_participants": 5,
    "overall_progress": 54,
    "goal": "Complete all 5 required Flask module assignments (routing, templates, forms, database, authentication) and submit before the deadline with all tests passing.",
    "start_date": "Mar 15, 2026",
    "end_date": "Mar 31, 2026",
    "stake_amount": 100,
    "penalty_rule": "Miss deadline → lose full stake",
    "reward_rule": "Complete → get stake back + share of prize pool",
    "created_by": "Alex",
    "team": "CITS Team Alpha",
}

sample_participants = [
    {
        "name": "Alex",
        "avatar": "A",
        "avatar_color": "bg-purple-500",
        "tasks_done": 5,
        "tasks_total": 5,
        "progress": 100,
        "status": "On Track",
        "status_class": "bg-green-100 text-green-700",
        "reward": 250,
        "row_class": "",
        "name_class": "text-gray-900",
        "done_class": "text-gray-600",
        "progress_class": "bg-green-500",
    },
    {
        "name": "Danny",
        "avatar": "D",
        "avatar_color": "bg-indigo-500",
        "tasks_done": 3,
        "tasks_total": 5,
        "progress": 60,
        "status": "On Track",
        "status_class": "bg-green-100 text-green-700",
        "reward": 250,
        "row_class": "",
        "name_class": "text-gray-900",
        "done_class": "text-gray-600",
        "progress_class": "bg-green-500",
    },
    {
        "name": "Sarah",
        "avatar": "S",
        "avatar_color": "bg-pink-500",
        "tasks_done": 4,
        "tasks_total": 5,
        "progress": 80,
        "status": "On Track",
        "status_class": "bg-green-100 text-green-700",
        "reward": 250,
        "row_class": "",
        "name_class": "text-gray-900",
        "done_class": "text-gray-600",
        "progress_class": "bg-green-500",
    },
    {
        "name": "Mike",
        "avatar": "M",
        "avatar_color": "bg-orange-500",
        "tasks_done": 2,
        "tasks_total": 5,
        "progress": 40,
        "status": "At Risk",
        "status_class": "bg-yellow-200 text-yellow-800",
        "reward": 100,
        "row_class": "bg-yellow-50 hover:bg-yellow-100",
        "name_class": "text-gray-900",
        "done_class": "text-gray-600",
        "progress_class": "bg-yellow-500",
    },
    {
        "name": "Jordan",
        "avatar": "J",
        "avatar_color": "bg-teal-500",
        "tasks_done": 1,
        "tasks_total": 5,
        "progress": 20,
        "status": "Failed",
        "status_class": "bg-red-200 text-red-800",
        "reward": 0,
        "row_class": "bg-red-50 hover:bg-red-100",
        "name_class": "line-through text-gray-500",
        "done_class": "line-through text-gray-600",
        "progress_class": "bg-red-500",
    },
]

sample_user_status = {
    "tasks_done": 3,
    "tasks_total": 5,
    "status_text": "You are ON TRACK 🎉",
    "status_subtext": "Keep up the momentum! 2 tasks remaining.",
    "status_color": "text-green-600",
    "stake_frozen": 100,
    "potential_reward": 250,
    "required_tasks": [
        {"title": "Flask Routing", "done": True},
        {"title": "Jinja2 Templates", "done": True},
        {"title": "Forms & Validation", "done": True},
        {"title": "Database Integration", "done": False},
        {"title": "Authentication", "done": False},
    ]
}

current_wager = sample_wager.copy()


# Routes
@app.route('/')
def index():
    """Redirect root to dashboard"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    return render_template('dashboard/index.html')


@app.route('/todos')
def todos():
    """My Tasks page"""
    return render_template('todos/index.html')


@app.route("/teams")
def teams_board():
    """Teams board page"""
    return render_template('teams/board.html')


@app.route('/feed')
def feed():
    """Activity Feed page"""
    return render_template('feed/index.html')


@app.route("/wagers")
def wagers_detail():
    """Wagers detail page"""
    return render_template(
        "wagers/detail.html",
        wager=current_wager,
        participants=sample_participants,
        user_status=sample_user_status
    )


@app.route("/wagers/create", methods=["GET", "POST"])
def create_wager():
    """Create wager page"""
    global current_wager, sample_user_status

    teams = ["CITS Team Alpha", "Study Group Beta", "Flask Project Team"]
    tasks = [
        "Flask Routing",
        "Jinja2 Templates",
        "Forms & Validation",
        "Database Integration",
        "Authentication"
    ]

    if request.method == "POST":
        team = request.form.get("team", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        stake_amount_raw = request.form.get("stake_amount", "").strip()
        selected_tasks = request.form.getlist("tasks")

        error = None

        # Validation
        if not title:
            error = "Wager Name cannot be empty."
        elif not description:
            error = "Description cannot be empty."
        elif not team:
            error = "Please choose a team."
        elif start_date and end_date and end_date < start_date:
            error = "End Date cannot be earlier than Start Date."
        elif not selected_tasks:
            error = "Please select at least one linked task."
        else:
            try:
                stake_amount = int(stake_amount_raw)
                if stake_amount <= 0:
                    error = "Stake Amount must be greater than 0."
            except ValueError:
                error = "Stake Amount must be a valid number."

        if error:
            return render_template(
                "wagers/create.html",
                teams=teams,
                tasks=tasks,
                error=error,
                form_data={
                    "team": team,
                    "title": title,
                    "description": description,
                    "start_date": start_date,
                    "end_date": end_date,
                    "stake_amount": stake_amount_raw,
                    "selected_tasks": selected_tasks
                }
            )

        # Update current wager
        current_wager["team"] = team
        current_wager["title"] = title
        current_wager["goal"] = description
        current_wager["start_date"] = start_date
        current_wager["end_date"] = end_date
        current_wager["stake_amount"] = stake_amount

        # Update right side task list
        sample_user_status["required_tasks"] = [
            {"title": task, "done": False} for task in selected_tasks
        ]
        sample_user_status["tasks_total"] = len(selected_tasks)
        sample_user_status["tasks_done"] = 0
        sample_user_status["status_text"] = "You are JUST STARTING 🚀"
        sample_user_status["status_subtext"] = f"You have {len(selected_tasks)} tasks to complete."
        sample_user_status["potential_reward"] = 250

        # Keep participant table in sync with new task total
        for participant in sample_participants:
            participant["tasks_total"] = len(selected_tasks)

        return redirect(url_for("wagers_detail"))

    return render_template(
        "wagers/create.html",
        teams=teams,
        tasks=tasks,
        error=None,
        form_data={
            "team": teams[0],
            "title": "",
            "description": "",
            "start_date": "",
            "end_date": "",
            "stake_amount": "",
            "selected_tasks": []
        }
    )


@app.route('/login')
def login():
    """Login page"""
    return render_template('auth/login.html')


@app.route('/register')
def register():
    """Register page"""
    return render_template('auth/register.html')


if __name__ == '__main__':
    app.run(debug=True)