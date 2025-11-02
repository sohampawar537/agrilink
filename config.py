import os
from dotenv import load_dotenv

# Get the absolute path of the directory where this file is located
basedir = os.path.abspath(os.path.dirname(__file__))
# Load environment variables from .env file
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # A secret key is needed for session security and forms
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

