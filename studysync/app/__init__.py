import os

from flask import Flask, Response, flash, redirect, render_template, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy

from app.forms import ChangePasswordForm, LoginForm, RegisterForm, ResetPasswordForm


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
	from app.models import User

	if not user_id or not user_id.isdigit():
		return None
	return db.session.get(User, int(user_id))


def create_app():
	app = Flask(__name__, instance_relative_config=True)

	os.makedirs(app.instance_path, exist_ok=True)

	database_path = os.path.join(app.instance_path, "studysync.db")
	app.config.from_mapping(
		SECRET_KEY="dev-secret-key",
		SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
		SQLALCHEMY_TRACK_MODIFICATIONS=False,
		WTF_CSRF_ENABLED=True,
	)

	db.init_app(app)
	login_manager.init_app(app)
	login_manager.login_view = "login"
	login_manager.login_message = "Please log in to continue."
	login_manager.login_message_category = "error"
	csrf.init_app(app)

	# Import models so SQLAlchemy registers tables before create_all runs.
	from app import models  # noqa: F401
	from app.models import User
	from app.teams import teams_bp

	app.register_blueprint(teams_bp)

	@app.route("/")
	def index():
		if current_user.is_authenticated:
			return redirect(url_for("dashboard"))
		return redirect(url_for("login"))

	@app.route("/dashboard")
	@login_required
	def dashboard():
		return render_template("dashboard/index.html")

	@app.route("/todos")
	def todos():
		return render_template("todos/index.html")

	@app.route("/feed")
	def feed():
		return render_template("feed/index.html")

	@app.route("/wagers")
	def wagers_detail():
		return render_template("wagers/detail.html")

	@app.route("/login", methods=["GET", "POST"])
	def login():
		if current_user.is_authenticated:
			return redirect(url_for("dashboard"))

		form = LoginForm()
		if form.validate_on_submit():
			user = User.query.filter_by(username=form.username.data.strip()).first()
			if user and user.check_password(form.password.data):
				login_user(user, remember=form.remember_me.data)
				flash("Logged in successfully.", "success")
				return redirect(url_for("dashboard"))
			flash("Invalid username or password.", "error")

		return render_template("auth/login_form.html", form=form)

	@app.route("/register", methods=["GET", "POST"])
	def register():
		if current_user.is_authenticated:
			return redirect(url_for("dashboard"))

		form = RegisterForm()
		if form.validate_on_submit():
			username = form.username.data.strip()
			email = form.email.data.strip() if form.email.data else None

			if User.query.filter_by(username=username).first() is not None:
				flash("Username already exists.", "error")
				return render_template("auth/register_form.html", form=form)

			if email and User.query.filter_by(email=email).first() is not None:
				flash("Email is already in use.", "error")
				return render_template("auth/register_form.html", form=form)

			user = User(username=username, email=email)
			user.set_password(form.password.data)
			db.session.add(user)
			db.session.commit()
			login_user(user)
			flash("Registration successful.", "success")
			return redirect(url_for("dashboard"))

		return render_template("auth/register_form.html", form=form)

	@app.route("/logout", methods=["POST"])
	@login_required
	def logout():
		logout_user()
		flash("You have been logged out.", "success")
		return redirect(url_for("login"))

	@app.route("/account/password", methods=["GET", "POST"])
	@login_required
	def account_password():
		form = ChangePasswordForm()
		if form.validate_on_submit():
			if not current_user.check_password(form.old_password.data):
				flash("Current password is incorrect.", "error")
				return render_template("account/password.html", form=form)

			current_user.set_password(form.new_password.data)
			db.session.commit()
			flash("Password updated successfully.", "success")
			return redirect(url_for("dashboard"))

		return render_template("account/password.html", form=form)

	@app.route("/reset-password", methods=["GET", "POST"])
	def reset_password():
		if current_user.is_authenticated:
			return redirect(url_for("dashboard"))

		form = ResetPasswordForm()
		if form.validate_on_submit():
			identifier = form.username_or_email.data.strip()
			user = User.query.filter_by(username=identifier).first()
			if user is None:
				user = User.query.filter_by(email=identifier).first()

			if user is None:
				flash("User not found.", "error")
				return render_template("auth/reset_password.html", form=form)

			user.set_password(form.new_password.data)
			db.session.commit()
			flash("Password updated, please login.", "success")
			return redirect(url_for("login"))

		return render_template("auth/reset_password.html", form=form)

	@app.route("/health")
	def health():
		return Response("ok", mimetype="text/plain")

	return app
