import os
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Get the secret key from the environment file
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-must-set-a-secret-key-in-.env'
    
    # Configure the database
    # It will use the 'DATABASE_URL' from the live server (like Render)
    # or default to our local 'agrilink.db' file if it's not set.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'agrilink.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

