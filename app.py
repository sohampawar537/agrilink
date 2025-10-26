# --- Imports ---
from flask import Flask, render_template, url_for, flash, redirect, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from sqlalchemy import or_, func
from datetime import datetime, timedelta
import random
import os
import secrets
import hashlib
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Local Imports ---
from config import Config
from models import db, User, Crop, Message, Order, Transaction, LogisticsPartner, Block
from forms import RegistrationForm, LoginForm, CropForm, MessageForm

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
db.init_app(app)

# --- Flask-Login Configuration ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Seeding Function ---
def seed_logistics_partners():
    # Check if partners already exist
    if LogisticsPartner.query.count() == 0:
        partners = [
            LogisticsPartner(name='AgriConnect Logistics', contact_email='contact@agriconnect.com', phone='9876543210', rating=4.7),
            LogisticsPartner(name='FarmHaul', contact_email='support@farmhaul.com', phone='8765432109', rating=4.5),
            LogisticsPartner(name='Rural Transport Co.', contact_email='info@ruraltransport.com', phone='7654321098', rating=4.2)
        ]
        db.session.bulk_save_objects(partners)
        db.session.commit()
        print("Logistics partners seeded.")
# ------------------------------------

# --- Helper Function to Save Picture ---
def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/uploads', picture_fn)
    
    # In a real app, you'd add image resizing here
    form_picture.save(picture_path)
    
    return picture_fn

# --- Helper Classes & Services ---
class Conversation:
    def __init__(self, crop, company):
        self.crop = crop
        self.company = company

class MarketDataService:
    @staticmethod
    def get_crop_prices():
        prices = {
            'Wheat': {'price': 2150, 'trend': random.choice(['up', 'down'])},
            'Paddy (Rice)': {'price': 2040, 'trend': random.choice(['up', 'down'])},
            'Maize': {'price': 1980, 'trend': random.choice(['up', 'down'])},
            'Cotton': {'price': 6025, 'trend': random.choice(['up', 'down'])},
            'Soybean': {'price': 4300, 'trend': random.choice(['up', 'down'])}
        }
        return prices
    
    @staticmethod
    def get_weather_forecast():
        today = datetime.now()
        forecast = [
            {
                'day': (today + timedelta(days=i)).strftime('%A'),
                'temp': random.randint(28, 35),
                'condition': random.choice(['Sunny', 'Partly Cloudy', 'Showers', 'Clear Skies'])
            } for i in range(5)
        ]
        return forecast

class PricePredictionService:
    @staticmethod
    def predict_price(crop_name):
        paid_orders = db.session.query(Order).join(Crop).filter(
            func.lower(Crop.name) == func.lower(crop_name),
            Order.status.in_(['Paid', 'Awaiting Pickup', 'Shipped', 'Delivered']) # Use all paid statuses
        ).all()
        
        if not paid_orders:
            return None
        
        # Calculate price per quintal for each order
        prices_per_quintal = []
        for order in paid_orders:
            if order.quantity > 0:
                # Assuming order.final_price is the *total* price
                prices_per_quintal.append(order.final_price / order.quantity)
        
        if not prices_per_quintal:
            return None

        predicted_price = sum(prices_per_quintal) / len(prices_per_quintal)
        return round(predicted_price, 2)

# --- Main Routes ---

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
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password, role=form.role.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
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
    logout_user()
    return redirect(url_for('home'))

# --- Dashboard Routes ---

@app.route("/farmer_dashboard")
@login_required
def farmer_dashboard():
    if current_user.role != 'farmer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.date_posted.desc()).all()
    farmer_crop_ids = [crop.id for crop in crops]
    
    # Find active conversations
    incoming_messages = Message.query.filter(Message.crop_id.in_(farmer_crop_ids)).all()
    convo_partners = {}
    for msg in incoming_messages:
        if msg.sender_id != current_user.id:
            convo_partners.setdefault(msg.crop_id, set()).add(msg.sender_id)
            
    conversations = []
    for crop_id, company_ids in convo_partners.items():
        crop = Crop.query.get(crop_id)
        for company_id in company_ids:
            conversations.append(Conversation(crop=crop, company=User.query.get(company_id)))
            
    # Get market data
    market_prices = MarketDataService.get_crop_prices()
    weather_forecast = MarketDataService.get_weather_forecast()
    
    return render_template('farmer_dashboard.html', 
                           title='Farmer Dashboard', 
                           crops=crops, 
                           conversations=conversations, 
                           market_prices=market_prices, 
                           weather_forecast=weather_forecast)

@app.route("/company_dashboard")
@login_required
def company_dashboard():
    if current_user.role != 'company':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
        
    all_crops = Crop.query.order_by(Crop.date_posted.desc()).all()
    market_prices = MarketDataService.get_crop_prices()
    weather_forecast = MarketDataService.get_weather_forecast()
    
    return render_template('company_dashboard.html', 
                           title='Marketplace', 
                           crops=all_crops, 
                           market_prices=market_prices, 
                           weather_forecast=weather_forecast)

# --- Core Feature Routes ---

@app.route("/crop/add", methods=['GET', 'POST'])
@login_required
def add_crop():
    if current_user.role != 'farmer':
        flash('Only farmers can add crops.', 'danger')
        return redirect(url_for('home'))
        
    form = CropForm()
    if form.validate_on_submit():
        image_file = 'default_crop.jpg' # Default
        if form.image.data:
            image_file = save_picture(form.image.data)
        
        crop = Crop(name=form.name.data, 
                    quantity=form.quantity.data, 
                    price=form.price.data, 
                    author=current_user,
                    image_file=image_file)
        db.session.add(crop)
        db.session.commit()
        flash('Your crop has been listed successfully!', 'success')
        return redirect(url_for('farmer_dashboard'))
        
    return render_template('add_crop.html', title='Add Crop', form=form)

@app.route("/chat/<int:crop_id>/with/<int:interlocutor_id>", methods=['GET', 'POST'])
@login_required
def chat(crop_id, interlocutor_id):
    crop = Crop.query.get_or_404(crop_id)
    interlocutor = User.query.get_or_404(interlocutor_id)

    # Security check: only farmer or involved company can view
    if not (current_user.id == crop.farmer_id or current_user.id == interlocutor_id):
         flash('You do not have permission to view this chat.', 'danger')
         return redirect(url_for('home'))
         
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(content=form.content.data, 
                          sender_id=current_user.id, 
                          receiver_id=interlocutor.id, 
                          crop_id=crop.id)
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('chat', crop_id=crop.id, interlocutor_id=interlocutor.id))
        
    messages = Message.query.filter_by(crop_id=crop.id).filter(
        or_(
            (Message.sender_id == current_user.id, Message.receiver_id == interlocutor.id),
            (Message.sender_id == interlocutor.id, Message.receiver_id == current_user.id)
        )
    ).order_by(Message.date_sent.asc()).all()
    
    return render_template('chat.html', 
                           title='Chat', 
                           form=form, 
                           crop=crop, 
                           interlocutor=interlocutor, 
                           messages=messages)

# --- Transaction & Order Routes ---

@app.route('/order/create/<int:crop_id>/for/<int:company_id>', methods=['POST'])
@login_required
def create_order(crop_id, company_id):
    # Security check
    if not (current_user.role == 'company' and current_user.id == company_id):
        flash('Only companies can create orders.', 'danger')
        return redirect(url_for('home'))
        
    crop = Crop.query.get_or_404(crop_id)
    quantity = request.form.get('quantity', type=float)
    total_price = request.form.get('price', type=float) # Form field is named 'price' but it's total price

    if not all([quantity, total_price]) or not (quantity > 0 and total_price > 0):
        flash('Invalid quantity or price provided.', 'danger')
        return redirect(url_for('chat', crop_id=crop_id, interlocutor_id=crop.author.id))

    order = Order(crop_id=crop.id, 
                  company_id=company_id, 
                  final_price=total_price, 
                  quantity=quantity, 
                  buyer=current_user,
                  status='Pending Payment')
    db.session.add(order)
    db.session.commit()
    
    flash('Order created successfully! Please proceed with the payment.', 'success')
    return redirect(url_for('transaction_history'))

@app.route('/transactions')
@login_required
def transaction_history():
    if current_user.role == 'farmer':
        orders = Order.query.join(Crop).filter(Crop.farmer_id == current_user.id).order_by(Order.order_date.desc()).all()
    else: # Company
        orders = Order.query.filter_by(company_id=current_user.id).order_by(Order.order_date.desc()).all()
        
    return render_template('transaction_history.html', title='Transaction History', orders=orders)

@app.route('/payment/process/<int:order_id>')
@login_required
def process_payment(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Security check
    if current_user.id != order.company_id:
        flash('You are not authorized to pay for this order.', 'danger')
        return redirect(url_for('transaction_history'))
        
    # Mock Payment
    order.status = 'Paid'
    payment_id = f'mock_pay_{order.id}_{int(datetime.utcnow().timestamp())}'
    
    if not Transaction.query.filter_by(order_id=order.id).first():
        db.session.add(Transaction(order_id=order.id, payment_id=payment_id, amount=order.final_price))
        
    db.session.commit()
    flash(f'Payment for Order #{order.id} was successful!', 'success')
    return redirect(url_for('transaction_history'))

# --- Logistics & Blockchain Routes ---

@app.route('/order/<int:order_id>/assign-logistics', methods=['POST'])
@login_required
def assign_logistics(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Security check: only the farmer of this crop can assign logistics
    if current_user.id != order.crop.farmer_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    partner_id = request.json.get('partner_id')
    if not partner_id:
        return jsonify({'error': 'Partner ID is required'}), 400
        
    partner = LogisticsPartner.query.get(partner_id)
    if not partner:
        return jsonify({'error': 'Logistics partner not found'}), 404
        
    order.logistics_partner_id = partner.id
    order.status = 'Awaiting Pickup'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Logistics partner {partner.name} assigned.',
        'new_status': 'Awaiting Pickup'
    })

@app.route('/order/<int:order_id>/ship')
@login_required
def ship_order(order_id):
    order = Order.query.get_or_404(order_id)
    # Security: only farmer can mark as shipped
    if current_user.id != order.crop.farmer_id or order.status != 'Awaiting Pickup':
        flash('You cannot perform this action.', 'danger')
        return redirect(url_for('transaction_history'))
    
    order.status = 'Shipped'
    db.session.commit()
    flash(f'Order #{order.id} marked as Shipped.', 'success')
    return redirect(url_for('transaction_history'))
    
@app.route('/order/<int:order_id>/deliver')
@login_required
def deliver_order(order_id):
    order = Order.query.get_or_404(order_id)
    # Security: only company can mark as delivered
    if current_user.id != order.company_id or order.status != 'Shipped':
        flash('You cannot perform this action.', 'danger')
        return redirect(url_for('transaction_history'))
        
    order.status = 'Delivered'
    db.session.commit()
    
    # --- Create Blockchain Record ---
    # Check if block already exists
    if not Block.query.filter_by(order_id=order.id).first():
        # Create a secure record of the transaction
        transaction_data = {
            'order_id': order.id,
            'crop': order.crop.name,
            'quantity': order.quantity,
            'total_price': order.final_price,
            'farmer_id': order.crop.farmer_id,
            'company_id': order.company_id,
            'delivery_date': datetime.utcnow().isoformat()
        }
        # Create and save the new block
        new_block = Block(order_id=order.id, transaction_data=transaction_data)
        db.session.add(new_block)
        db.session.commit()
        flash(f'Order #{order.id} marked as Delivered and secured on the ledger.', 'success')
    else:
        flash(f'Order #{order.id} marked as Delivered.', 'success')
        
    return redirect(url_for('transaction_history'))

@app.route('/ledger/<int:block_id>')
@login_required
def view_ledger_block(block_id):
    block = Block.query.get_or_404(block_id)
    order = Order.query.get_or_404(block.order_id)
    
    # Security: Only involved parties can view the block
    if current_user.id not in [order.company_id, order.crop.farmer_id]:
        flash('You do not have permission to view this record.', 'danger')
        return redirect(url_for('home'))
        
    # Parse the JSON data to display it
    transaction_data = json.loads(block.transaction_data)
    
    return render_template('ledger.html', 
                           title='Ledger Record', 
                           block=block, 
                           data=transaction_data)

# --- API Routes ---

@app.route('/api/predict-price')
@login_required
def predict_price_api():
    crop_name = request.args.get('crop', '', type=str)
    if not crop_name:
        return jsonify({'error': 'Crop name is required.'}), 400
        
    predicted_price = PricePredictionService.predict_price(crop_name)
    
    if predicted_price is None:
        return jsonify({'error': f'Not enough historical data to predict a price for {crop_name}.'})
        
    return jsonify({'predicted_price': predicted_price})

@app.route('/api/logistics-partners')
@login_required
def get_logistics_partners():
    partners = LogisticsPartner.query.all()
    partners_list = [
        {'id': p.id, 'name': p.name, 'phone': p.phone, 'rating': p.rating}
        for p in partners
    ]
    return jsonify(partners_list)

# --- Main Entry Point ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_logistics_partners() # Seed the DB with logistics partners
    # This host/port is compatible with production servers
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

