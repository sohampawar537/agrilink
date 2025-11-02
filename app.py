import os
import secrets
import hashlib
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Import Config and db/models
from config import Config
from models import db, User, Crop, Message, Order, Transaction, LogisticsPartner, Block
from forms import RegistrationForm, LoginForm, CropForm, MessageForm, OrderForm

# --- Application and Database Initialization ---

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- Helper Functions ---

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_fn)
    
    # Create the uploads directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Save the picture
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
            
            next_page = request.args.get('next')
            
            if next_page:
                return redirect(next_page)
            
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
        return [
            {"name": "Wheat", "price": 2050.00, "change": "+1.5%"},
            {"name": "Rice (Paddy)", "price": 1940.00, "change": "-0.5%"},
            {"name": "Cotton", "price": 6025.00, "change": "+2.0%"}
        ]
    
    @staticmethod
    def get_weather_forecast():
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
        orders = db.session.query(Order).join(Crop).filter(
            Crop.name == crop_name,
            Order.status.in_(['Paid', 'Awaiting Pickup', 'Shipped', 'Delivered'])
        ).all()
        
        if not orders:
            return None
            
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
    
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()
    
    crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.date_posted.desc()).all()
    
    conversations = db.session.query(Message.crop_id, Crop.name, Message.sender_id, User.username)\
        .join(Crop, Message.crop_id == Crop.id)\
        .join(User, Message.sender_id == User.id)\
        .filter(Message.recipient_id == current_user.id)\
        .distinct().all()
        
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
    
    prices = MarketDataService.get_price_trends()
    weather = MarketDataService.get_weather_forecast()
    
    crops = Crop.query.order_by(Crop.date_posted.desc()).all()
    return render_template('company_dashboard.html', crops=crops, prices=prices, weather=weather)

# --- Chat & Negotiation Routes ---

@app.route("/chat/<int:crop_id>/<int:other_user_id>", methods=['GET', 'POST'])
@login_required
def chat(crop_id, other_user_id):
    crop = Crop.query.get_or_404(crop_id)
    other_user = User.query.get_or_404(other_user_id)
    
    if current_user.id != crop.farmer_id and current_user.id != other_user_id:
        abort(403)
    
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
    
    transaction = Transaction(order_id=order.id)
    order.status = 'Paid'
    
    if order.crop:
        order.crop.quantity -= order.quantity
        if order.crop.quantity < 0:
            order.crop.quantity = 0
    
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
    
    try:
        last_block = Block.query.order_by(Block.timestamp.desc()).first()
        previous_hash = last_block.block_hash if last_block else '0' * 64
        
        data = f"OrderID: {order.id}, " \
               f"Farmer: {order.farmer.username}, " \
               f"Company: {order.company.username}, " \
               f"Crop: {order.crop.name}, " \
               f"Quantity: {order.quantity}, " \
               f"Price: {order.total_price}"
        
        timestamp = datetime.utcnow()
        block_header = f"{previous_hash}{timestamp}{data}"
        block_hash = hashlib.sha256(block_header.encode()).hexdigest()
        
        new_block = Block(
            order_id=order.id,
            previous_hash=previous_hash,
            timestamp=timestamp,
            transaction_data=data,
            block_hash=block_hash
        )
        db.session.add(new_block)
        
    except Exception as e:
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
        abort(404)
        
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
    if LogisticsPartner.query.count() > 0:
        return

    try:
        p1 = LogisticsPartner(name="AgriFast Transport", contact_email="contact@agrifast.com", vehicles_available=50)
        p2 = LogisticsPartner(name="QuickCrop Logistics", contact_email="info@quickcrop.com", vehicles_available=30)
        p3 = LogisticsPartner(name="Rural Express", contact_email="dispatch@ruralexpress.in", vehicles_available=75)

        db.session.add_all([p1, p2, p3])
        db.session.commit()
        print("Logistics partners seeded.")
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding logistics partners: {e}")


# --- Main Run ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_logistics_partners()
    app.run(debug=True)


# --- NEW: Database Initialization Command ---
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and seeds logistics partners."""
    db.create_all()
    seed_logistics_partners()
    print("Database initialized and partners seeded!")

