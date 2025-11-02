from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, RadioField, BooleanField, FloatField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User

# --- Forms ---

class RegistrationForm(FlaskForm):
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    role = RadioField('I am a:', choices=[('farmer', 'Farmer'), ('company', 'Company')],
                      validators=[DataRequired()])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already in use. Please choose a different one.')

class LoginForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

def allowed_file(filename):
    # This function is now part of Config, but we'll define it here
    # for simplicity in the form. A better approach would be to import Config
    # but that might create circular imports.
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class CropForm(FlaskForm):
    name = StringField('Crop Name', validators=[DataRequired()])
    quantity = FloatField('Quantity (in Quintals)', validators=[DataRequired()])
    price = FloatField('Expected Price (per Quintal)', validators=[DataRequired()])
    image = FileField('Crop Image', validators=[FileAllowed(['png', 'jpg', 'jpeg'], 'Images only!')])
    submit = SubmitField('List Crop')

class MessageForm(FlaskForm):
    body = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=1000)])
    submit = SubmitField('Send')

class OrderForm(FlaskForm):
    quantity = FloatField('Quantity (in Quintals)', validators=[DataRequired()])
    price_per_quintal = FloatField('Price per Quintal', validators=[DataRequired()])
    submit = SubmitField('Create Order')

