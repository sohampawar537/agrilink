from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
import hashlib
import json

db = SQLAlchemy()

# --- User Model ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'farmer' or 'company'
    location = db.Column(db.String(100))
    
    # Relationships
    crops = db.relationship('Crop', backref='author', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    orders = db.relationship('Order', foreign_keys='Order.company_id', backref='buyer', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

# --- Crop Model ---
class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    image_file = db.Column(db.String(20), nullable=False, default='default_crop.jpg')
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    messages = db.relationship('Message', backref='crop', lazy=True)
    orders = db.relationship('Order', backref='crop', lazy=True)

    def __repr__(self):
        return f'<Crop {self.name}>'

# --- Message Model ---
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)

    def __repr__(self):
        return f'<Message {self.id}>'

# --- Order Model ---
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    final_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Logistics Fields
    status = db.Column(db.String(30), nullable=False, default='Pending Payment') 
    # Statuses: 'Pending Payment', 'Paid', 'Awaiting Pickup', 'Shipped', 'Delivered'
    logistics_partner_id = db.Column(db.Integer, db.ForeignKey('logistics_partner.id'), nullable=True)
    
    # Relationships
    transaction = db.relationship('Transaction', backref='order', uselist=False, lazy=True)
    logistics_partner = db.relationship('LogisticsPartner', backref='orders', lazy=True)
    block = db.relationship('Block', backref='order', uselist=False, lazy=True)

    def __repr__(self):
        return f'<Order {self.id}>'

# --- Transaction Model ---
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    payment_id = db.Column(db.String(100), nullable=False) # From payment gateway
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Transaction {self.payment_id}>'

# --- LogisticsPartner Model ---
class LogisticsPartner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    rating = db.Column(db.Float, default=4.5)

    def __repr__(self):
        return f'<LogisticsPartner {self.name}>'

# --- Block Model (Blockchain Ledger) ---
class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction_data = db.Column(db.Text, nullable=False) # JSON of the transaction
    block_hash = db.Column(db.String(64), nullable=False, unique=True) # SHA-256

    def __init__(self, order_id, transaction_data):
        self.order_id = order_id
        self.transaction_data = json.dumps(transaction_data) # Store data as a JSON string
        self.block_hash = self.compute_hash()

    def compute_hash(self):
        """Creates a SHA-256 hash for the block's data."""
        # We use a static timestamp from the transaction data for a consistent hash
        block_string = f"{self.order_id}{self.transaction_data}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def __repr__(self):
        return f'<Block {self.block_hash}>'

