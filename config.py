"""
Configuration file for Smart Clothesline System Application
Contains all configuration parameters and settings
"""

import os
import psycopg2
from psycopg2 import sql
import time
import platform
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file if exists
load_dotenv()

# Flask configuration
class Config:
    CORS_ALLOWED_ORIGINS = "*"
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    # HTTP polling configuration
    POLLING_ENABLED = True
    POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', '5'))  # seconds

# Check if we're running on a production environment (Render)
IS_PRODUCTION = os.environ.get('RENDER', False)

# Database configuration
if IS_PRODUCTION:
    # Use PostgreSQL in production (Render)
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://clothesline_user:HEnc7bShp1X3Q4nSCB2s8RMeO7lMas3c@dpg-d0q7k87diees738q5tcg-a.oregon-postgres.render.com/clothesline_data')
    USE_POSTGRESQL = True
else:
    # Keep SQLite for local development
    DATABASE = 'data/sensor_data.db'
    USE_POSTGRESQL = False
    # Make sure the data directory exists for SQLite
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

# NodeMCU Configuration
NODEMCU_CONFIG = {
    'base_url': os.environ.get('NODEMCU_BASE_URL', 'http://192.168.8.137/'),
    'timeout': float(os.environ.get('NODEMCU_TIMEOUT', '10'))
}

# Auto mode settings
AUTO_SETTINGS = {
    'enabled': os.environ.get('AUTO_ENABLED', 'False').lower() == 'true',
    'lightThreshold': int(os.environ.get('LIGHT_THRESHOLD', '500')),
    'rainThreshold': int(os.environ.get('RAIN_THRESHOLD', '500'))
}

# Model information
MODEL_INFO = {
    'trained': False,
    'lastTraining': None,
    'accuracy': None
}

# Additional configuration
APP_CONFIG = {
    'polling_interval': int(os.environ.get('POLLING_INTERVAL', '10')),
    'training_interval': int(os.environ.get('TRAINING_INTERVAL', '3600')),
    'command_cooldown': int(os.environ.get('COMMAND_COOLDOWN', '60')),  # Seconds between auto commands
    'max_retries': int(os.environ.get('MAX_RETRIES', '3')),  # Max retries for HTTP requests
    'retry_delay': int(os.environ.get('RETRY_DELAY', '2'))   # Seconds between retries
}

# Thread control variables
threads_running = True
last_auto_command_time = 0
last_poll_time = 0

# Database connection function
def get_db_connection():
    """Get database connection based on environment"""
    if USE_POSTGRESQL:
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect(DATABASE)

# Database functions
def init_db():
    """Initialize database tables if they don't exist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRESQL:
            # PostgreSQL table creation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    ldr INTEGER,
                    rain INTEGER,
                    status TEXT,
                    rotation INTEGER
                )
            ''')
            
            # Create settings table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id SERIAL PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT
                )
            ''')
            
            # Create polling_log table to track HTTP polling
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS polling_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    success BOOLEAN,
                    response_time FLOAT,
                    message TEXT
                )
            ''')
        else:
            # SQLite table creation (for local development)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    ldr INTEGER,
                    rain INTEGER,
                    status TEXT,
                    rotation INTEGER
                )
            ''')
            
            # Create settings table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT
                )
            ''')
            
            # Create polling_log table to track HTTP polling
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS polling_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    success BOOLEAN,
                    response_time FLOAT,
                    message TEXT
                )
            ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

def save_setting(key, value):
    """Save a setting to the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRESQL:
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            ''', (key, str(value)))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, str(value)))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Setting saved: {key}={value}")
        return True
    except Exception as e:
        print(f"Error saving setting: {str(e)}")
        return False

def load_setting(key, default=None):
    """Load a setting from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRESQL:
            cursor.execute('SELECT value FROM settings WHERE key = %s', (key,))
        else:
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            print(f"Setting loaded: {key}={row[0]}")
            return row[0]
        return default
    except Exception as e:
        print(f"Error loading setting: {str(e)}")
        return default

def load_all_settings():
    """Load all settings from the database"""
    global NODEMCU_CONFIG, AUTO_SETTINGS, MODEL_INFO
    
    try:
        # Load NodeMCU config
        base_url = load_setting('nodemcu_base_url', NODEMCU_CONFIG['base_url'])
        timeout = float(load_setting('nodemcu_timeout', NODEMCU_CONFIG['timeout']))
        
        NODEMCU_CONFIG['base_url'] = base_url
        NODEMCU_CONFIG['timeout'] = timeout
        
        # Load auto settings
        AUTO_SETTINGS['enabled'] = load_setting('auto_enabled', 'False') == 'True'
        AUTO_SETTINGS['lightThreshold'] = int(load_setting('light_threshold', AUTO_SETTINGS['lightThreshold']))
        AUTO_SETTINGS['rainThreshold'] = int(load_setting('rain_threshold', AUTO_SETTINGS['rainThreshold']))
        
        # Load model info
        MODEL_INFO['trained'] = load_setting('model_trained', 'False') == 'True'
        MODEL_INFO['lastTraining'] = load_setting('model_last_training')
        accuracy = load_setting('model_accuracy')
        MODEL_INFO['accuracy'] = float(accuracy) if accuracy else None
        
        # Load polling settings
        Config.POLLING_ENABLED = load_setting('polling_enabled', 'True') == 'True'
        Config.POLLING_INTERVAL = int(load_setting('polling_interval', Config.POLLING_INTERVAL))
        
        print("All settings loaded successfully")
    except Exception as e:
        print(f"Error loading settings: {str(e)}")

def log_polling_event(success, response_time, message=""):
    """Log HTTP polling events to the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRESQL:
            cursor.execute('''
                INSERT INTO polling_log (timestamp, success, response_time, message) 
                VALUES (%s, %s, %s, %s)
            ''', (datetime.now(), success, response_time, message))
        else:
            cursor.execute('''
                INSERT INTO polling_log (timestamp, success, response_time, message) 
                VALUES (?, ?, ?, ?)
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), success, response_time, message))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging polling event: {str(e)}")

# Print system info
print(f"System: {platform.system()} {platform.release()}")
print(f"Python: {platform.python_version()}")
if USE_POSTGRESQL:
    print(f"Database: PostgreSQL (Production)")
    print(f"Database URL: {DATABASE_URL}")
else:
    print(f"Database path: {os.path.abspath(DATABASE)}")
print(f"Production mode: {IS_PRODUCTION}")
print(f"Polling mode: HTTP polling (interval: {Config.POLLING_INTERVAL}s)")

# Initialize the database and load settings when this module is imported
init_db()
load_all_settings()