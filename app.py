import os
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, url_for, flash, redirect, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, RadioField, BooleanField, FloatField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from dotenv import load_dotenv

# --- Configuration ---

# Load environment variables from .env file
load_dotenv()

# Get the absolute path of the directory where this file is located
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-and-hard-to-guess-string'
    
    # Configure the database location
    # Use DATABASE_URL from environment if available (for production),
    # otherwise default to a local sqlite file (for development).
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'agrilink.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configure the upload folder
    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- Application and Database Initialization ---

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Database Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'farmer' or 'company'
    location = db.Column(db.String(100))
    
    # Relationships
    crops = db.relationship('Crop', backref='author', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='author', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)
    orders_placed = db.relationship('Order', foreign_keys='Order.company_id', backref='company', lazy=True)
    orders_received = db.relationship('Order', foreign_keys='Order.farmer_id', backref='farmer', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    messages = db.relationship('Message', backref='crop', lazy=True)
    orders = db.relationship('Order', backref='crop', lazy=True)

    def __repr__(self):
        return f'<Crop {self.name}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))

    def __repr__(self):
        return f'<Message {self.body}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)
    
    quantity = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending Payment') # e.g., Pending Payment, Paid, Awaiting Pickup, Shipped, Delivered
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Logistics
    logistics_partner_id = db.Column(db.Integer, db.ForeignKey('logistics_partner.id'), nullable=True)
    
    # Relationship
    transaction = db.relationship('Transaction', backref='order', uselist=False, lazy=True)
    block = db.relationship('Block', backref='order', uselist=False, lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False, default='Mock Payment')
    payment_status = db.Column(db.String(50), nullable=False, default='Completed')
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class LogisticsPartner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    contact_email = db.Column(db.String(120), unique=True, nullable=False)
    vehicles_available = db.Column(db.Integer, nullable=False)
    
    # Relationship
    orders = db.relationship('Order', backref='logistics_partner', lazy=True)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    transaction_data = db.Column(db.Text, nullable=False)
    block_hash = db.Column(db.String(64), unique=True, nullable=False)

    def __repr__(self):
        return f'<Block {self.block_hash}>'

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
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

class CropForm(FlaskForm):
    name = StringField('Crop Name', validators=[DataRequired()])
    quantity = FloatField('Quantity (in Quintals)', validators=[DataRequired()])
    price = FloatField('Expected Price (per Quintal)', validators=[DataRequired()])
    image = FileField('Crop Image', validators=[FileAllowed(Config.ALLOWED_EXTENSIONS, 'Images only!')])
    submit = SubmitField('List Crop')

class MessageForm(FlaskForm):
    body = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=1000)])
    submit = SubmitField('Send')

class OrderForm(FlaskForm):
    quantity = FloatField('Quantity (in Quintals)', validators=[DataRequired()])
    price_per_quintal = FloatField('Price per Quintal', validators=[DataRequired()])
    submit = SubmitField('Create Order')

# --- Helper Functions ---

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_fn)
    
    # Resize image if needed (optional)
    # output_size = (500, 500)
    # i = Image.open(form_picture)
    # i.thumbnail(output_size)
    # i.save(picture_path)
    
    # For now, just save
    form_picture.save(picture_path)
    
    return picture_fn

# --- User Loader ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route("/")
@app.route("/home")
def home():
    return render_template('index.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            role=form.role.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            
            # Redirect to the 'next' page if it exists (e.g., if user was trying to access a protected page)
            next_page = request.args.get('next')
            
            if next_page:
                return redirect(next_page)
            
            # Otherwise, redirect to the appropriate dashboard
            if user.role == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            else:
                return redirect(url_for('company_dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

# --- Mock Data Services ---

class MarketDataService:
    @staticmethod
    def get_price_trends():
        # In a real app, this would call an external API
        return [
            {"name": "Wheat", "price": 2050.00, "change": "+1.5%"},
            {"name": "Rice (Paddy)", "price": 1940.00, "change": "-0.5%"},
            {"name": "Cotton", "price": 6025.00, "change": "+2.0%"}
        ]
    
    @staticmethod
    def get_weather_forecast():
        # In a real app, this would call a weather API with user's location
        return [
            {"day": "Today", "icon": "☀️", "temp": "31°C"},
            {"day": "Mon", "icon": "☀️", "temp": "32°C"},
            {"day": "Tue", "icon": "⛅", "temp": "30°C"},
            {"day": "Wed", "icon": "🌧️", "temp": "28°C"},
            {"day": "Thu", "icon": "⛅", "temp": "29°C"},
        ]

class PricePredictionService:
    @staticmethod
    def predict_price(crop_name):
        # Simple AI model: Calculate average price from past "Paid" or "Delivered" orders
        orders = db.session.query(Order).join(Crop).filter(
            Crop.name == crop_name,
            Order.status.in_(['Paid', 'Awaiting Pickup', 'Shipped', 'Delivered'])
        ).all()
        
        if not orders:
            return None # Not enough data
            
        total_price = sum(o.total_price for o in orders)
        total_quantity = sum(o.quantity for o in orders)
        
        if total_quantity == 0:
            return None
            
        avg_price_per_quintal = total_price / total_quantity
        return round(avg_price_per_quintal, 2)

# --- Farmer Routes ---

@app.route("/farmer_dashboard")
@login_required
def farmer_dashboard():
    if current_user.role != 'farmer':
        abort(403)
    
    # Market Data
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()
    
    # Farmer's Crops
    crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.date_posted.desc()).all()
    
    # Farmer's Active Negotiations
    # Find all unique conversations (crop_id, company_id)
    conversations = db.session.query(Message.crop_id, Crop.name, Message.sender_id, User.username)\
        .join(Crop, Message.crop_id == Crop.id)\
        .join(User, Message.sender_id == User.id)\
        .filter(Message.recipient_id == current_user.id)\
        .distinct().all()
        
    # Reformat for template
    active_chats = [
        {"crop_id": c[0], "crop_name": c[1], "company_id": c[2], "company_name": c[3]}
        for c in conversations
    ]

    return render_template('farmer_dashboard.html', 
                           crops=crops, 
                           active_chats=active_chats, 
                           prices=prices, 
                           weather=weather)

@app.route("/crop/add", methods=['GET', 'POST'])
@login_required
def add_crop():
    if current_user.role != 'farmer':
        abort(403)
    form = CropForm()
    if form.validate_on_submit():
        image_filename = "default.jpg"
        if form.image.data:
            image_filename = save_picture(form.image.data)
        
        crop = Crop(name=form.name.data, 
                    quantity=form.quantity.data, 
                    price=form.price.data, 
                    image_file=image_filename,
                    author=current_user)
        db.session.add(crop)
        db.session.commit()
        flash('Your crop has been listed!', 'success')
        return redirect(url_for('farmer_dashboard'))
    return render_template('add_crop.html', title='Add Crop', form=form)

# --- Company Routes ---

@app.route("/company_dashboard")
@login_required
def company_dashboard():
    if current_user.role != 'company':
        abort(403)
    
    # Market Data
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()
    
    # All Crops from all farmers
    crops = Crop.query.order_by(Crop.date_posted.desc()).all()
    return render_template('company_dashboard.html', crops=crops, prices=prices, weather=weather)

# --- Chat & Negotiation Routes ---

@app.route("/chat/<int:crop_id>/<int:other_user_id>", methods=['GET', 'POST'])
@login_required
def chat(crop_id, other_user_id):
    crop = Crop.query.get_or_404(crop_id)
    other_user = User.query.get_or_404(other_user_id)
    
    # Security check: Ensure current user is part of this transaction
    if current_user.id != crop.farmer_id and current_user.id != other_user_id:
        abort(403)
    
    # Determine sender and recipient for this chat
    if current_user.role == 'farmer':
        farmer_id = current_user.id
        company_id = other_user_id
    else:
        farmer_id = other_user_id
        company_id = current_user.id
        
    form = MessageForm()
    order_form = OrderForm()

    if form.validate_on_submit() and form.submit.data:
        msg = Message(body=form.body.data,
                      author=current_user,
                      recipient=other_user,
                      crop_id=crop.id)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('chat', crop_id=crop_id, other_user_id=other_user_id))

    messages = Message.query.filter_by(crop_id=crop.id).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    return render_template('chat.html', 
                           title=f'Chat for {crop.name}', 
                           form=form, 
                           order_form=order_form,
                           messages=messages, 
                           crop=crop, 
                           other_user=other_user,
                           farmer_id=farmer_id,
                           company_id=company_id)

# --- Order & Transaction Routes ---

@app.route("/order/create/<int:crop_id>/<int:farmer_id>/<int:company_id>", methods=['POST'])
@login_required
def create_order(crop_id, farmer_id, company_id):
    if current_user.role != 'company' or current_user.id != company_id:
        abort(403)
    
    form = OrderForm()
    if form.validate_on_submit():
        crop = Crop.query.get_or_404(crop_id)
        quantity = form.quantity.data
        price_per_quintal = form.price_per_quintal.data
        total_price = quantity * price_per_quintal

        if quantity > crop.quantity:
            flash(f'Error: Farmer only has {crop.quantity} quintals available.', 'danger')
            return redirect(url_for('chat', crop_id=crop_id, other_user_id=farmer_id))
            
        order = Order(
            company_id=company_id,
            farmer_id=farmer_id,
            crop_id=crop_id,
            quantity=quantity,
            total_price=total_price,
            status='Pending Payment'
        )
        db.session.add(order)
        db.session.commit()
        flash('Order created! Please proceed to payment.', 'success')
        return redirect(url_for('transaction_history'))
    else:
        flash('There was an error with your order form.', 'danger')
        return redirect(url_for('chat', crop_id=crop_id, other_user_id=farmer_id))


@app.route("/transactions")
@login_required
def transaction_history():
    if current_user.role == 'farmer':
        orders = Order.query.filter_by(farmer_id=current_user.id).order_by(Order.order_date.desc()).all()
    else:
        orders = Order.query.filter_by(company_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('transaction_history.html', title='Transaction History', orders=orders)

@app.route("/payment/process/<int:order_id>", methods=['POST'])
@login_required
def process_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.company_id:
        abort(403)
    
    # --- Mock Payment Logic ---
    # In a real app, this would integrate with Razorpay, Stripe, etc.
    # For now, we'll just create a transaction record and update the order.
    
    transaction = Transaction(order_id=order.id)
    order.status = 'Paid'
    
    # Update crop quantity
    if order.crop:
        order.crop.quantity -= order.quantity
        if order.crop.quantity < 0:
            order.crop.quantity = 0 # Ensure it doesn't go negative
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Payment Successful! The farmer has been notified.', 'success')
    return redirect(url_for('transaction_history'))

# --- Logistics Routes ---

@app.route("/order/ship/<int:order_id>", methods=['POST'])
@login_required
def ship_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.farmer_id:
        abort(403)
    
    order.status = 'Shipped'
    db.session.commit()
    flash(f'Order #{order.id} marked as Shipped.', 'success')
    return redirect(url_for('transaction_history'))

@app.route("/order/deliver/<int:order_id>", methods=['POST'])
@login_required
def deliver_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.company_id:
        abort(403)
        
    order.status = 'Delivered'
    
    # --- Create Blockchain Entry ---
    try:
        # 1. Get the last block's hash (or a genesis hash)
        last_block = Block.query.order_by(Block.timestamp.desc()).first()
        previous_hash = last_block.block_hash if last_block else '0' * 64
        
        # 2. Prepare transaction data
        data = f"OrderID: {order.id}, " \
               f"Farmer: {order.farmer.username}, " \
               f"Company: {order.company.username}, " \
               f"Crop: {order.crop.name}, " \
               f"Quantity: {order.quantity}, " \
               f"Price: {order.total_price}"
        
        # 3. Create the hash for the new block
        timestamp = datetime.utcnow()
        block_header = f"{previous_hash}{timestamp}{data}"
        block_hash = hashlib.sha256(block_header.encode()).hexdigest()
        
        # 4. Create and save the new block
        new_block = Block(
            order_id=order.id,
            previous_hash=previous_hash,
            timestamp=timestamp,
            transaction_data=data,
            block_hash=block_hash
        )
        db.session.add(new_block)
        
    except Exception as e:
        # Don't fail the delivery if blockchain write fails
        print(f"Error creating block: {e}")
        
    db.session.commit()
    flash(f'Order #{order.id} marked as Delivered and verified on ledger.', 'success')
    return redirect(url_for('transaction_history'))


# --- Blockchain/Ledger Route ---

@app.route("/ledger/<int:order_id>")
@login_required
def view_ledger(order_id):
    order = Order.query.get_or_404(order_id)
    block = Block.query.filter_by(order_id=order.id).first()
    
    if not block:
        abort(404) # No block found for this order
        
    # Security check: Only farmer or company involved can view
    if current_user.id != order.farmer_id and current_user.id != order.company_id:
        abort(403)
        
    return render_template('ledger.html', title='Ledger Verification', block=block)

# --- API Routes (for JavaScript) ---

@app.route("/api/predict-price/<string:crop_name>")
@login_required
def predict_price_api(crop_name):
    if not crop_name:
        return jsonify({"error": "Crop name required"}), 400
        
    predicted_price = PricePredictionService.predict_price(crop_name)
    
    if predicted_price is None:
        return jsonify({"error": "Not enough data to predict price."}), 404
        
    return jsonify({"crop_name": crop_name, "predicted_price": predicted_price})

@app.route("/api/logistics-partners")
@login_required
def get_logistics_partners():
    partners = LogisticsPartner.query.all()
    partners_list = [
        {"id": p.id, "name": p.name, "email": p.contact_email, "vehicles": p.vehicles_available}
        for p in partners
    ]
    return jsonify(partners_list)

@app.route("/order/<int:order_id>/assign-logistics", methods=['POST'])
@login_required
def assign_logistics(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.farmer_id:
        abort(403)
        
    data = request.get_json()
    partner_id = data.get('partner_id')
    
    if not partner_id:
        return jsonify({"error": "Partner ID is required"}), 400
        
    partner = LogisticsPartner.query.get(partner_id)
    if not partner:
        return jsonify({"error": "Partner not found"}), 404
        
    order.logistics_partner_id = partner.id
    order.status = 'Awaiting Pickup'
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": f"Order assigned to {partner.name}.",
        "new_status": "Awaiting Pickup"
    })

# --- Database Seeding Function ---

def seed_logistics_partners():
    # Check if partners already exist
    if LogisticsPartner.query.count() > 0:
        return # Already seeded

    # Create mock partners
    p1 = LogisticsPartner(name="AgriFast Transport", contact_email="contact@agrifast.com", vehicles_available=50)
    p2 = LogisticsPartner(name="QuickCrop Logistics", contact_email="info@quickcrop.com", vehicles_available=30)
    p3 = LogisticsPartner(name="Rural Express", contact_email="dispatch@ruralexpress.in", vehicles_available=75)

    db.session.add_all([p1, p2, p3])
    db.session.commit()
    print("Logistics partners seeded.")

# --- Main Run ---

# This block is for local development only.
# Gunicorn will not run this.
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_logistics_partners()
    app.run(debug=True)


# --- NEW: Database Initialization Command ---
# This command is for deployment (e.g., on Render)
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and seeds logistics partners."""
    db.create_all()
    seed_logistics_partners()
    print("Database initialized and partners seeded!")
# ---------------------------------------------

