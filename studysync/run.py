from flask import Flask, render_template, redirect, url_for

# Create Flask app
app = Flask(__name__, template_folder='app/templates')

# Configuration
app.secret_key = "dev-secret-key"
app.config['DEBUG'] = True

# Routes

@app.route('/')
def index():
    """Redirect root to login"""
    return redirect(url_for('login'))

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
    return render_template('wagers/detail.html')

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
