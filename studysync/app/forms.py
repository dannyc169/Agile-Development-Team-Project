from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Optional


class LoginForm(FlaskForm):
	username = StringField("Username", validators=[DataRequired(message="Please enter your username.")])
	password = PasswordField("Password", validators=[DataRequired(message="Please enter your password.")])
	remember_me = BooleanField("Remember me")
	submit = SubmitField("Login")


class RegisterForm(FlaskForm):
	username = StringField(
		"Username",
		validators=[DataRequired(message="Please enter your username."), Length(min=3, max=80)],
	)
	email = StringField("Email", validators=[Optional(), Length(max=120)])
	password = PasswordField(
		"Password",
		validators=[DataRequired(message="Please enter your password."), Length(min=6, max=128)],
	)
	confirm_password = PasswordField(
		"Confirm password",
		validators=[DataRequired(message="Please confirm your password."), EqualTo("password", message="The two passwords do not match.")],
	)
	submit = SubmitField("Create account")


class TeamCreateForm(FlaskForm):
	name = StringField("Team name", validators=[DataRequired(message="Please enter the team name."), Length(min=2, max=120)])
	description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
	submit = SubmitField("Create team")


class TeamJoinForm(FlaskForm):
	code = StringField("Invite code", validators=[DataRequired(message="Please enter the invite code."), Length(min=4, max=32)])
	submit = SubmitField("Join team")


class ChangePasswordForm(FlaskForm):
	old_password = PasswordField("Current password", validators=[DataRequired(message="Please enter your current password.")])
	new_password = PasswordField(
		"New password",
		validators=[DataRequired(message="Please enter a new password."), Length(min=8, max=128)],
	)
	confirm_password = PasswordField(
		"Confirm new password",
		validators=[DataRequired(message="Please confirm your new password."), EqualTo("new_password", message="The two passwords do not match.")],
	)
	submit = SubmitField("Update password")


class ResetPasswordForm(FlaskForm):
	username_or_email = StringField(
		"Username or email",
		validators=[DataRequired(message="Please enter your username or email."), Length(min=3, max=120)],
	)
	new_password = PasswordField(
		"New password",
		validators=[DataRequired(message="Please enter a new password."), Length(min=8, max=128)],
	)
	confirm_password = PasswordField(
		"Confirm new password",
		validators=[DataRequired(message="Please confirm your new password."), EqualTo("new_password", message="The two passwords do not match.")],
	)
	submit = SubmitField("Reset password")