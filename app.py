import os
import secrets
import hashlib
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import (
    Flask, render_template, url_for, flash, redirect, request, 
    abort, jsonify, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, current_user, logout_user, login_required, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- Configuration ---

# Load environment variables from .env file
# This needs to be done *before* importing Config
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

from config import Config
from models import (
    db, User, Crop, Message, Order, Transaction, 
    LogisticsPartner, Block
)
from forms import (
    RegistrationForm, LoginForm, CropForm, MessageForm, OrderForm
)

# --- Application Initialization ---

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Utility Functions ---

@login_manager.user_loader
def load_user(user_id):
    """Required by Flask-Login to load a user from session."""
    return User.query.get(int(user_id))

def allowed_file(filename):
    """Check if a file's extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_picture(form_picture):
    """Saves uploaded picture to the filesystem."""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_fn)
    
    # Ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    form_picture.save(picture_path)
    return picture_fn

# --- Mock Data Services ---

class MarketDataService:
    """A mock service to simulate fetching live market data."""
    
    @staticmethod
    def get_price_trends():
        """Returns fake price trend data."""
        return [
            {'name': 'Wheat', 'price': 2105.75, 'change': '+1.2%'},
            {'name': 'Rice', 'price': 3840.20, 'change': '-0.5%'},
            {'name': 'Cotton', 'price': 5800.00, 'change': '+2.1%'},
            {'name': 'Soybean', 'price': 4550.50, 'change': '+0.8%'},
        ]

    @staticmethod
    def get_weather_forecast():
        """Returns fake weather data."""
        return [
            {'day': 'Today', 'icon': '☀️', 'temp': '32°C'},
            {'day': 'Mon', 'icon': '🌤️', 'temp': '31°C'},
            {'day': 'Tue', 'icon': '☁️', 'temp': '29°C'},
            {'day': 'Wed', 'icon': '🌧️', 'temp': '28°C'},
            {'day': 'Thu', 'icon': '🌤️', 'temp': '30°C'},
        ]

class PricePredictionService:
    """A mock AI service to predict crop prices."""
    
    @staticmethod
    def get_predicted_price(crop_name):
        """
        Simulates an AI model.
        In a real app, this would query a model.
        Here, it calculates the average price from past "Delivered" orders.
        """
        # Find all delivered orders for this crop
        orders = db.session.query(Order).join(Crop).filter(
            Crop.name.ilike(crop_name),
            Order.status == 'Delivered'
        ).all()
        
        if not orders:
            return None # Not enough data

        # Calculate average price per quintal
        total_price = sum(o.total_price for o in orders)
        total_quantity = sum(o.quantity for o in orders)
        
        if total_quantity == 0:
            return None

        avg_price = total_price / total_quantity
        # Return a clean, rounded price
        return round(avg_price, 2)

class BlockchainService:
    """A mock service to simulate blockchain operations."""

    @staticmethod
    def get_last_block_hash():
        """Fetches the hash of the very last block in the ledger."""
        last_block = Block.query.order_by(Block.timestamp.desc()).first()
        if last_block:
            return last_block.block_hash
        # Return the "genesis block" hash if no blocks exist
        return hashlib.sha256("genesis_block".encode()).hexdigest()

    @staticmethod
    def create_hash(data_string, timestamp_str, previous_hash):
        """Creates a SHA-256 hash for a new block."""
        sha = hashlib.sha256()
        sha.update(f"{data_string}{timestamp_str}{previous_hash}".encode('utf-8'))
        return sha.hexdigest()

    @staticmethod
    def create_new_block(order):
        """Creates and saves a new block for a delivered order."""
        
        # 1. Get the previous block's hash
        previous_hash = BlockchainService.get_last_block_hash()
        
        # 2. Prepare transaction data
        timestamp = datetime.utcnow()
        transaction_data = {
            "order_id": order.id,
            "farmer": order.farmer.username,
            "company": order.company.username,
            "crop": order.crop.name,
            "quantity": order.quantity,
            "total_price": order.total_price,
            "delivered_on": timestamp.isoformat()
        }
        transaction_string = json.dumps(transaction_data, sort_keys=True)
        
        # 3. Create the new block's hash
        block_hash = BlockchainService.create_hash(
            transaction_string, 
            str(timestamp), 
            previous_hash
        )

        # 4. Create and save the new block
        block = Block(
            order_id=order.id,
            previous_hash=previous_hash,
            timestamp=timestamp,
            transaction_data=transaction_string,
            block_hash=block_hash
        )
        
        db.session.add(block)
        # We commit here because this runs *after* the order commit
        db.session.commit()
        return block

# --- Main Routes ---

@app.route("/")
@app.route("/home")
def home():
    """Renders the homepage."""
    return render_template('index.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    """Handles user registration."""
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
        try:
            db.session.commit()
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {e}', 'danger')
            app.logger.error(f"Error on registration: {e}")
            
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            
            # Redirect to the correct dashboard based on role
            if user.role == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            else:
                return redirect(url_for('company_dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
            
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    """Handles user logout."""
    logout_user()
    return redirect(url_for('home'))

# --- Farmer Routes ---

@app.route("/farmer_dashboard")
@login_required
def farmer_dashboard():
    """Displays the farmer's dashboard."""
    if current_user.role != 'farmer':
        abort(403) # Forbidden
    
    # Get market data
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()
    
    # Get crops listed by this farmer
    crops = Crop.query.filter_by(farmer_id=current_user.id)\
                .order_by(Crop.date_posted.desc()).all()
    
    # Find active chats (new messages)
    # This query finds messages sent by companies to this farmer
    active_chats_query = db.session.query(
        Message.crop_id,
        User.username.label('company_name'),
        Crop.name.label('crop_name'),
        User.id.label('company_id')
    ).join(
        User, User.id == Message.sender_id
    ).join(
        Crop, Crop.id == Message.crop_id
    ).filter(
        Message.recipient_id == current_user.id
    ).distinct()
    
    active_chats = active_chats_query.all()
    
    return render_template(
        'farmer_dashboard.html', 
        title='Farmer Dashboard',
        crops=crops,
        prices=prices,
        weather=weather,
        active_chats=active_chats
    )

@app.route("/crop/add", methods=['GET', 'POST'])
@login_required
def add_crop():
    """Handles adding a new crop for a farmer."""
    if current_user.role != 'farmer':
        abort(403)

    form = CropForm()
    if form.validate_on_submit():
        image_fn = 'default.jpg' # Default image
        if form.image.data:
            try:
                if not allowed_file(form.image.data.filename):
                    flash('Invalid file type. Please upload JPG or PNG.', 'danger')
                    return render_template('add_crop.html', title='Add Crop', form=form)
                
                image_fn = save_picture(form.image.data)
            except Exception as e:
                flash(f'Error saving image: {e}', 'danger')
                app.logger.error(f"Error saving image: {e}")

        crop = Crop(
            name=form.name.data,
            quantity=form.quantity.data,
            price=form.price.data,
            image_file=image_fn,
            author=current_user
        )
        db.session.add(crop)
        db.session.commit()
        flash('Your crop has been listed!', 'success')
        return redirect(url_for('farmer_dashboard'))
    
    return render_template('add_crop.html', title='Add Crop', form=form)

# --- Company Routes ---

@app.route("/company_dashboard")
@login_required
def company_dashboard():
    """Displays the company's dashboard (marketplace)."""
    if current_user.role != 'company':
        abort(403)
        
    # Get market data
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()

    # Get all crops from all farmers
    crops = Crop.query.order_by(Crop.date_posted.desc()).all()
    
    return render_template(
        'company_dashboard.html', 
        title='Marketplace',
        crops=crops,
        prices=prices,
        weather=weather
    )

# --- Shared Routes (Chat, Order, Logistics) ---

@app.route("/chat/<int:crop_id>/<int:other_user_id>", methods=['GET', 'POST'])
@login_required
def chat(crop_id, other_user_id):
    """Handles the real-time chat and order creation page."""
    crop = Crop.query.get_or_404(crop_id)
    other_user = User.query.get_or_404(other_user_id)

    # --- Security Check ---
    # This is the corrected security logic
    # Deny access if the current user is NOT the farmer
    # AND is NOT a company.
    if (current_user.id != crop.farmer_id and 
        current_user.role != 'company'):
        abort(403) # Forbidden
    
    # Determine who is who
    if current_user.role == 'farmer':
        farmer_id = current_user.id
        company_id = other_user.id
    else: # current_user is a company
        farmer_id = other_user.id
        company_id = current_user.id

    # --- Message Form Handling (Sending) ---
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            body=form.body.data,
            author=current_user,
            recipient=other_user,
            crop=crop
        )
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('chat', crop_id=crop_id, other_user_id=other_user_id))

    # --- Order Form (for display) ---
    order_form = OrderForm()

    # --- Load Chat History ---
    messages = Message.query.filter_by(crop_id=crop.id).filter(
        (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
    ).order_by(Message.timestamp.asc()).all()

    return render_template(
        'chat.html', 
        title=f'Chat for {crop.name}', 
        form=form,
        order_form=order_form,
        messages=messages, 
        crop=crop, 
        other_user=other_user,
        farmer_id=farmer_id,
        company_id=company_id
    )

@app.route("/order/create/<int:crop_id>/<int:farmer_id>/<int:company_id>", methods=['POST'])
@login_required
def create_order(crop_id, farmer_id, company_id):
    """Handles the creation of a new order from the chat."""
    if current_user.role != 'company' or current_user.id != company_id:
        abort(403)

    form = OrderForm()
    if form.validate_on_submit():
        crop = Crop.query.get_or_404(crop_id)
        
        # Check if quantity is available
        if form.quantity.data > crop.quantity:
            flash(f'Cannot order {form.quantity.data} quintals. Only {crop.quantity} available.', 'danger')
            return redirect(url_for('chat', crop_id=crop_id, other_user_id=farmer_id))
        
        total_price = form.quantity.data * form.price_per_quintal.data
        
        order = Order(
            company_id=company_id,
            farmer_id=farmer_id,
            crop_id=crop_id,
            quantity=form.quantity.data,
            total_price=total_price,
            status='Pending Payment' # Initial status
        )
        
        # Reduce crop quantity (or mark as sold if all is bought)
        crop.quantity -= form.quantity.data
        if crop.quantity < 0:
            crop.quantity = 0
            
        db.session.add(order)
        db.session.commit()
        flash('Order successfully created. Please proceed with payment.', 'success')
        return redirect(url_for('transaction_history'))
    else:
        flash('Error in order form. Please check quantity and price.', 'danger')
        return redirect(url_for('chat', crop_id=crop_id, other_user_id=farmer_id))

@app.route("/transactions")
@login_required
def transaction_history():
    """Displays all orders for the current user."""
    if current_user.role == 'farmer':
        orders = Order.query.filter_by(farmer_id=current_user.id)\
                    .order_by(Order.order_date.desc()).all()
    else: # Role is 'company'
        orders = Order.query.filter_by(company_id=current_user.id)\
                    .order_by(Order.order_date.desc()).all()
    
    return render_template('transaction_history.html', title='Transaction History', orders=orders)

@app.route("/payment/process/<int:order_id>", methods=['POST'])
@login_required
def process_payment(order_id):
    """(Mock) Processes a payment for an order."""
    order = Order.query.get_or_404(order_id)
    if current_user.role != 'company' or current_user.id != order.company_id:
        abort(403)
    
    # --- This is where a real payment gateway (e.g., Razorpay) would be called ---
    # We will simulate a successful payment.
    
    order.status = 'Paid'
    
    # Create a transaction record
    transaction = Transaction(
        order_id=order.id,
        payment_method='Mock Payment Gateway',
        payment_status='Completed'
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Payment successful! Order is now marked as Paid.', 'success')
    return redirect(url_for('transaction_history'))

@app.route("/order/<int:order_id>/assign-logistics", methods=['POST'])
@login_required
def assign_logistics(order_id):
    """Assigns a logistics partner to an order (Farmer action)."""
    order = Order.query.get_or_404(order_id)
    if current_user.role != 'farmer' or current_user.id != order.farmer_id:
        abort(403)
    
    data = request.get_json()
    partner_id = data.get('partner_id')
    
    if not partner_id:
        return jsonify({'success': False, 'error': 'Partner ID missing.'}), 400
    
    partner = LogisticsPartner.query.get(partner_id)
    if not partner:
        return jsonify({'success': False, 'error': 'Partner not found.'}), 404
        
    order.logistics_partner_id = partner.id
    order.status = 'Awaiting Pickup'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Partner assigned.'})

@app.route("/order/<int:order_id>/ship", methods=['POST'])
@login_required
def ship_order(order_id):
    """Marks an order as Shipped (Farmer action)."""
    order = Order.query.get_or_404(order_id)
    if current_user.role != 'farmer' or current_user.id != order.farmer_id:
        abort(403)
        
    order.status = 'Shipped'
    db.session.commit()
    flash('Order marked as Shipped.', 'info')
    return redirect(url_for('transaction_history'))

@app.route("/order/<int:order_id>/deliver", methods=['POST'])
@login_required
def deliver_order(order_id):
    """Confirms delivery of an order (Company action)."""
    order = Order.query.get_or_404(order_id)
    if current_user.role != 'company' or current_user.id != order.company_id:
        abort(403)
        
    order.status = 'Delivered'
    db.session.commit()
    
    # --- Create Blockchain Entry ---
    try:
        BlockchainService.create_new_block(order)
        flash('Delivery confirmed and transaction recorded on the ledger!', 'success')
    except Exception as e:
        flash('Delivery confirmed, but error recording to ledger.', 'warning')
        app.logger.error(f"Blockchain error: {e}")

    return redirect(url_for('transaction_history'))

@app.route("/ledger/<int:order_id>")
@login_required
def view_ledger(order_id):
    """Displays the secure blockchain ledger entry for an order."""
    order = Order.query.get_or_404(order_id)
    block = Block.query.filter_by(order_id=order.id).first()

    # Security: Only farmer or company from this order can view
    if (current_user.id != order.farmer_id and 
        current_user.id != order.company_id):
        abort(403) # Forbidden
        
    if not block:
        flash('This transaction has not been recorded on the ledger yet.', 'info')
        return redirect(url_for('transaction_history'))

    # Parse the JSON data for pretty display
    block_data = json.loads(block.transaction_data)
    block.transaction_data = json.dumps(block_data, indent=4)
        
    return render_template('ledger.html', title='Ledger Verification', block=block)

# --- API Routes ---

@app.route("/api/predict-price/<string:crop_name>")
@login_required
def api_predict_price(crop_name):
    """API endpoint for AI price prediction."""
    if current_user.role != 'farmer':
        return jsonify({'error': 'Unauthorized'}), 403
        
    predicted_price = PricePredictionService.get_predicted_price(crop_name)
    
    if predicted_price is None:
        return jsonify({'error': 'Not enough data to predict price. Please enter manually.'}), 404
    
    return jsonify({'crop_name': crop_name, 'predicted_price': predicted_price})

@app.route("/api/logistics-partners")
@login_required
def api_get_logistics_partners():
    """API endpoint to fetch all logistics partners."""
    if current_user.role != 'farmer':
        return jsonify({'error': 'Unauthorized'}), 403
        
    partners = LogisticsPartner.query.all()
    partners_list = [
        {
            'id': p.id,
            'name': p.name,
            'email': p.contact_email,
            'vehicles': p.vehicles_available
        } for p in partners
    ]
    return jsonify(partners_list)

# --- Database Seeding ---

def seed_logistics_partners():
    """Adds default logistics partners to the database if they don't exist."""
    with app.app_context():
        if LogisticsPartner.query.count() > 0:
            print("Logistics partners already exist.")
            return

        partners = [
            LogisticsPartner(name='AgriTrans Logistics', contact_email='info@agritrans.com', vehicles_available=50),
            LogisticsPartner(name='FarmFleet Carriers', contact_email='contact@farmfleet.com', vehicles_available=30),
            LogisticsPartner(name='QuickCrop Transport', contact_email='ops@quickcrop.com', vehicles_available=25)
        ]
        
        db.session.add_all(partners)
        db.session.commit()
        print("Logistics partners seeded.")

# --- Main Entry Point ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_logistics_partners()
    app.run(debug=True)


# --- NEW: Database Initialization Command for Deployment ---
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and seeds logistics partners."""
    db.create_all()
    seed_logistics_partners()
    print("Database initialized and partners seeded!")
# ---------------------------------------------