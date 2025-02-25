from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import random, string, os

app = Flask(__name__)
app.secret_key = "unifiedfamilyfinancetracker"

# Configure database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'loginDB.db')
db = SQLAlchemy(app)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'thariqali142@gmail.com'
app.config['MAIL_PASSWORD'] = 'vheo bjfy yppk tyiu'  
mail = Mail(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hashed password

# Function to generate OTP
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))  

# Function to send OTP
def send_otp(email, otp):
    msg = Message("Your OTP for Unified Family Finance Tracker", sender="your_email@gmail.com", recipients=[email])
    msg.body = f"""
                Dear User,

                Your One-Time Password (OTP) for verifying your Unified Family Finance Tracker account is: {otp}

                This OTP is valid for a limited time. Please do not share it with anyone for security reasons.

                If you did not request this, please ignore this message.

                Best regards,  
                Unified Family Finance Tracker Team """
    mail.send(msg)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return redirect(url_for('login'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            otp = generate_otp()
            session['otp'] = otp  
            session['email'] = email
            send_otp(email, otp)
            return redirect(url_for('verify'))
        
        flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        entered_otp = ''.join([request.form.get(f'otp{i}') for i in range(1, 7)])
        actual_otp = session.get('otp')

        if entered_otp == actual_otp:
            session.pop('otp', None)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid OTP, Please Try Again!")

    return render_template('verification_page.html')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            flash("You must be logged in to access this page.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
