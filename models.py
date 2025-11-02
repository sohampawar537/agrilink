from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

# --- Database Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Updated from 128 to 256
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

