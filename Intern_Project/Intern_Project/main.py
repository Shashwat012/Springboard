from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from flask_mail import Mail, Message
from functools import wraps
from flask_cors import CORS
from datetime import datetime, timedelta,timezone
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Expense, Category, Budget, User,  SavingCategory, SavingsTarget, Savings
from io import BytesIO
import random, string, os,re, calendar
import io
import numpy as np
from graph import *
import base64
import pandas as pd
import plotly.graph_objects as go 


app = Flask(__name__)
app.secret_key = "unifiedfamilyfinancetracker"
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False 

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///ufft_database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

db.init_app(app)



# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'thariqali142@gmail.com'
app.config['MAIL_PASSWORD'] = 'vheo bjfy yppk tyiu'  # Use App Password
mail = Mail(app)

# Function to strip emojis from a string
def strip_emojis(text):
    emoji_pattern = re.compile(
        "[" 
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def attach_emojis(category_name):
    emoji_map = {
        "Food": "🍕",
        "Transport": "🚂",
        "Bills": "💸",
        "Entertainment": "🤡",
        "Shopping": "🛍️",
        "Therapy": "🩺",
        "Others": ""
    }
    for key, emoji in emoji_map.items():
        if key in category_name:
            return f"{category_name}{emoji}"
    return category_name

# Function to generate OTP
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))  # 6-digit OTP

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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            flash("You must be logged in to access this page.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        family_name = request.form['family_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        
        # Check if email already exists
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            flash("Email or username already exists. Please use a different email or username.", "error")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, family_name=family_name, email=email, password=hashed_password, phone=phone, address=address)
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
            if user.role == "super_user" and user.status != "approved":
                flash("Your account is pending approval. Please contact the admin.")
                return redirect(url_for('login'))
            elif user.role == "family_member" and user.status != "approved":
                flash("Your account is pending approval. Please wait for the super user to approve it.")
                return redirect(url_for('login'))

            session["user_id"] = user.id
            session["role"] = user.role
            session["email"] = email

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))

            elif user.role == "super_user" or user.role == "family_member":
                otp = generate_otp()
                session['otp'] = otp  
                send_otp(email, otp)
                return redirect(url_for('verify'))
            
        flash('Invalid email or password')
    
    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        user = User.query.filter_by(email=email).first()

        if user:
            otp = generate_otp()
            session['reset_otp'] = otp
            session['reset_email'] = email
            session['reset_otp_expiry'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

            try:
                send_otp(email, otp)
                flash('An OTP has been sent to your email.', 'success')
                return redirect(url_for('verify_reset_otp'))
            except Exception as e:
                flash(f'Failed to send OTP: {str(e)}', 'error')
                return redirect(url_for('forgot_password'))
        else:
            flash('Email not found.', 'error')
    return render_template('forgot_password.html')
    
@app.route('/verify_reset_otp', methods=['GET', 'POST'])
def verify_reset_otp():
    if 'reset_otp' not in session or 'reset_email' not in session:
        flash('Invalid request. Please try again.', 'error')
        return redirect(url_for('forgot_password'))

    if datetime.now(timezone.utc) > datetime.fromisoformat(session['reset_otp_expiry']):
        flash('OTP has expired. Please request a new OTP.', 'error')
        session.pop('reset_otp', None)
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        entered_otp = ''.join([request.form.get(f'otp{i}') for i in range(1, 7)])
        actual_otp = session.get('reset_otp')

        if entered_otp == actual_otp:
            return redirect(url_for('reset_password'))
        else:
            flash('Invalid OTP. Please try again.', 'error')
    return render_template('verify_otp.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_otp' not in session or 'reset_email' not in session:
        flash('Invalid request. Please try again.', 'error')
        return redirect(url_for('forgot_password'))

    if datetime.now(timezone.utc) > datetime.fromisoformat(session['reset_otp_expiry']):
        flash('OTP has expired. Please request a new OTP.', 'error')
        session.pop('reset_otp', None)
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_password'))
        
        user = User.query.filter_by(email=session['reset_email']).first()
        if user:
            user.password = generate_password_hash(password)
            db.session.commit()

            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('reset_otp_expiry', None)

            return redirect(url_for('login'))
        else:
            flash('User not found.', 'error')
    return render_template('reset_password.html')

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))
    
    page = request.args.get('page', 1, type=int)
    users = User.query.filter_by(role="super_user").paginate(page=page, per_page=4, error_out=False)

    return render_template("admin_dashboard.html", users=users)

@app.route('/verify', methods=['GET', 'POST'])
@login_required
def verify():
    if request.method == 'POST':
        entered_otp = ''.join([request.form.get(f'otp{i}') for i in range(1, 7)])
        actual_otp = session.get('otp')

        if entered_otp == actual_otp:
            session.pop('otp', None)
            role = session.get('role')

            if role == "super_user":
                return redirect(url_for('super_user_dashboard'))
            elif role == "family_member":
                user_id = session.get('user_id')
                user = User.query.get(user_id)

                if user:
                    if user.privilege == "view":
                        return redirect(url_for('view_dash'))
                    elif user.privilege == "edit":
                        return redirect(url_for('dashboard'))

        flash("Invalid OTP, Please Try Again!")

    return render_template('verification.html')


@app.route("/update_approved_by", methods=["POST"])
def update_approved_by():
    user_id = request.form.get("user_id")
    approve = request.form.get("approve")  
    admin_id = session.get("user_id")

    user = User.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if approve:
        user.approved_by = admin_id
        user.status = "approved"
        flash(f"User {user.username} has been approved.", "success")
    else:
        user.approved_by = None
        user.status = "pending"

        # **Check if the user is a super user**
        family_members = User.query.filter_by(approved_by=user.id).all()
        
        if family_members:
            for member in family_members:
                member.status = "pending"
            
            flash(f"Super user {user.username} and all family members have been disapproved.", "warning")
        else:
            flash(f"User {user.username} has been disapproved.", "warning")

    db.session.commit()

    return redirect(url_for("admin_dashboard"))


@app.route("/super_user_dashboard")
@login_required
def super_user_dashboard():
    if "user_id" not in session or session["role"] != "super_user":
        return redirect(url_for("login"))
    family_members = User.query.filter_by(approved_by=session["user_id"]).all()
    return render_template("super_user_dash.html",family_members=family_members)


@app.route("/create_subaccount", methods=["POST"])
def create_subaccount():
    if "user_id" not in session or session["role"] != "super_user":
        return redirect(url_for("login"))

    # Get the form data
    username = request.form.get("username")  # Get the username from the form
    email = request.form.get("email")
    password = request.form.get("password")
    phone_number = request.form.get("phone_number")

    # Fetch the superuser's details
    superuser = User.query.get(session["user_id"])
    if not superuser:
        flash("Superuser not found.", "error")
        return redirect(url_for("super_user_dashboard"))

    # Check if the username already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Username already exists. Please choose a different username.", "error")
        return redirect(url_for("super_user_dashboard"))

    # Create the family member account
    hashed_password = generate_password_hash(password)
    new_user = User(
        username=username,  # Use the provided username
        family_name=superuser.family_name,  # Inherit family name from superuser
        address=superuser.address,  # Inherit address from superuser
        email=email,
        password=hashed_password,
        phone=phone_number,
        role="family_member",
        privilege="view",
        approved_by=session["user_id"]
    )

    # Add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    flash("Subaccount created successfully!","success")
    return redirect(url_for("super_user_dashboard"))

@app.route("/update_approval", methods=["POST"])
def update_approval():
    if "user_id" not in session or session["role"] != "super_user":
        return redirect(url_for("login"))

    user_id = request.form.get("user_id")
    action = request.form.get("approve")  # "approve" or "disapprove"

    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("super_user_dashboard"))

    if action:
        user.status = "approved"
        flash(f"User {user.username} has been approved.", "success")
    else:
        user.status = "pending"
        flash(f"User {user.username} has been disapproved.", "warning")

    db.session.commit()
    return redirect(url_for("super_user_dashboard"))

@app.route('/update_privilege', methods=['POST'])
def update_privilege():
    user_id = request.form.get('user_id')
    new_privilege = request.form.get('new_privilege')
    user = User.query.get(user_id)
   
    if user:
        user.privilege = new_privilege

        db.session.commit()  # Commit both updates together

        flash("Privilege updated successfully!", "success")
    else:
        flash("User not found!", "error")

    return redirect(url_for("super_user_dashboard"))  # Redirect to avoid form resubmission issues


@app.route('/dashboard')
@login_required
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    today = datetime.today()
    default_year = today.year
    default_month = today.month

    all_users = []  
    if user.role == "super_user":
        all_users.append(user.username)  
        family_members = User.query.filter(User.approved_by == user.id).order_by(User.id).all()
        all_users.extend([member.username for member in family_members]) 
    elif user.role == "family_member":
        superuser = User.query.get(user.approved_by)
        if superuser:
            all_users.append(superuser.username)  
        all_users.append(user.username)

    default_user= all_users[0] if all_users else None 


    # Generate plots
    monthly_plot = generate_monthly_expenses_plot(user_id=user.id)
    category_plot = generate_category_expenses_plot(default_year, default_month,user_id=user.id)
    pie_chart = generate_pie_chart(user_id=user.id, month=default_month, year=default_year)
    bar_chart = generate_bar_chart(user_id=user.id, month=default_month, year=default_year)
    stacked_bar_chart = generate_stacked_bar_chart(user_id=user.id,month=default_month, year=default_year)
    line_chart = generate_line_chart(year=default_year,user_id=user.id)
    
    return render_template('dashboard_edit.html',
                        username=user.username,
                        users=all_users,
                        default_user=default_user,  
                        monthly_plot=monthly_plot,
                        category_plot=category_plot,                      
                        pie_chart=pie_chart,
                        bar_chart=bar_chart,
                        stacked_bar_chart=stacked_bar_chart,
                        line_chart=line_chart,
                        
                        default_year=default_year,
                        default_month=default_month)

@app.route('/view_dash')
@login_required
def view_dash():
    role = session.get('role')
    user = User.query.get(session.get('user_id'))
    
    current_year = datetime.now().year
    current_month = datetime.now().month

    monthly_plot = generate_monthly_expenses_plot(user_id=user.id)
    category_plot = generate_category_expenses_plot(year=current_year, month=current_month, user_id=user.id)
    pie_chart = generate_pie_chart(user_id=user.id, month=current_month, year=current_year)
    bar_chart = generate_bar_chart(user_id=user.id, month=current_month, year=current_year)
    stacked_bar_chart = generate_stacked_bar_chart(user_id=user.id, month=current_month, year=current_year)
    line_chart = generate_line_chart(year=current_year, user_id=user.id)
    return render_template("dashboard_view.html",
                            username=user.username,
                            users=all_users,
                            default_user=default_user,  
                            monthly_plot=monthly_plot, 
                            category_plot=category_plot, 
                            pie_chart=pie_chart, 
                            bar_chart=bar_chart,
                            stacked_bar_chart=stacked_bar_chart, 
                            line_chart=line_chart, 
                            
                            default_year=current_year, 
                            default_month=current_month)


#Team 2
@app.route("/get_categories")
def get_categories():
    categories = Category.query.all()
    return jsonify([{"name": cat.name, "description": cat.category_desc} for cat in categories])

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Consolidated user context logic
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by
        if not user_id:
            return jsonify({"message": "Not linked to any family"}), 400

    user = session['user_id']
    role = session['role']
    if user:
        if role == "family_member":
            user = User.query.get(session['user_id'])
            user_id = user.approved_by
        else:
            user_id = user

    data = request.form.to_dict()
    name = data.get("name")
    category_name = data.get("category")  # Category name comes with emoji already
    date_str = data.get("date")
    amount = data.get("amount")
    description = data.get("description", "")

    if not name or not category_name or not date_str or not amount:
        return jsonify({"message": "Missing required fields!"}), 400

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400

    category = Category.query.filter_by(name=category_name).first()
    if not category:
        category_desc = data.get("category-desc", "")
        category = Category(name=category_name, category_desc=category_desc)
        db.session.add(category)
        db.session.commit()

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format!"}), 400

    file = request.files.get("file-upload")
    
    if file and file.filename:
        file_data = file.read()
        file_type = file.mimetype
        new_expense = Expense(
            user_id=user_id,
            name=name,
            category_id=category.category_id,
            date=date,
            amount=amount,
            description=description,
            image_data=file_data,
            file_type=file_type
        )
    else:
        new_expense = Expense(
            user_id=user_id,
            name=name,
            category_id=category.category_id,
            date=date,
            amount=amount,
            description=description
        )
    db.session.add(new_expense)
    db.session.commit()

    return jsonify({"message": "Expense added successfully!"})
    

    
@app.route("/get_expenses")
def get_expenses():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Consolidated user context logic
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by
        if not user_id:
            return jsonify({"message": "Not linked to any family"}), 400

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Expense.query.filter_by(user_id=user_id)
    if from_date:
        query = query.filter(Expense.date >= from_date)
    if to_date:
        query = query.filter(Expense.date <= to_date)

    expenses = query.order_by(Expense.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "expenses": [{
            "id": exp.id,
            "name": exp.name,
            "category": exp.category.name if exp.category else "Unknown",
            "date": exp.date.strftime("%Y-%m-%d"),
            "amount": exp.amount,
            "description": exp.description,
            "image_url": f"/get_file/{exp.id}" if exp.image_data else None,
            "file_type": exp.file_type
        } for exp in expenses.items],
        "total_pages": expenses.pages,
        "current_page": expenses.page
    })

@app.route("/get_expense/<int:expense_id>")
def get_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        return jsonify({"message": "Expense not found"}), 404
    return jsonify({
        "id": expense.id,
        "name": expense.name,
        "category": expense.category.name if expense.category else "Unknown",
        "category_desc": expense.category.category_desc if expense.category else "",
        "date": expense.date.strftime("%Y-%m-%d"),
        "amount": expense.amount,
        "description": expense.description,
        "image_url": f"/get_file/{expense.id}" if expense.image_data else None,
        "file_type": expense.file_type
    })

@app.route("/get_file/<int:expense_id>")
def get_file(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense or not expense.image_data:
        return jsonify({"message": "File not found"}), 404
    return send_file(BytesIO(expense.image_data), mimetype=expense.file_type)

@app.route("/edit_expense/<int:expense_id>", methods=["PUT"])
def edit_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Consolidated user context logic
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by
        if not user_id:
            return jsonify({"message": "Not linked to any family"}), 400

    # Update query to use the resolved user_id
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    data = request.form.to_dict()
    expense.name = data.get("name", expense.name)
    category_name = data.get("category", expense.category.name)  # Use category name directly
    try:
        expense.amount = float(data.get("amount", expense.amount))
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400
    expense.description = data.get("description", expense.description)
    
    category = Category.query.filter_by(name=category_name).first()
    if not category:
        category_desc = data.get("category-desc", "")
        category = Category(name=category_name, category_desc=category_desc)
        db.session.add(category)
        db.session.commit()
    expense.category_id = category.category_id
    try:
        expense.date = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format!"}), 400
    file = request.files.get("file-upload")
    if file and file.filename:
        file_data = file.read()
        expense.image_data = file_data
        expense.file_type = file.mimetype
    db.session.commit()
    return jsonify({"message": "Expense updated successfully!"})

@app.route("/delete_expense/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Consolidated user context logic
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by
        if not user_id:
            return jsonify({"message": "Not linked to any family"}), 400

    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    category_id = expense.category_id
    db.session.delete(expense)
    db.session.commit()
    remaining_expenses = Expense.query.filter_by(category_id=category_id).count()
    if remaining_expenses == 0:
        category = Category.query.get(category_id)
        db.session.delete(category)
        db.session.commit()
    return jsonify({"message": "Expense deleted successfully!"})

@app.route("/get_stats")
def get_stats():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Get the correct user context
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by  # Use super user's ID for family members
        if not user_id:  # Handle unlinked family members
            return jsonify({"message": "Not linked to any family"}), 400
    else:
        user_id = user_id  # Use current user's ID directly for super users

    # Get filter parameters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    # Base query
    query = Expense.query.filter_by(user_id=user_id)
    
    # Date filtering
    try:
        if from_date:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date >= from_date)
        if to_date:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date <= to_date)
    except ValueError:
        return jsonify({"message": "Invalid date format! Use YYYY-MM-DD"}), 400

    # Rest of the calculations remain the same
    total_spent = query.with_entities(db.func.sum(Expense.amount)).scalar() or 0
    expense_count = query.with_entities(db.func.count(Expense.id)).scalar() or 0
    last_7days_spent = query.with_entities(db.func.sum(Expense.amount)).filter(
        Expense.date >= (datetime.now().date() - timedelta(days=7))
    ).scalar() or 0
    highest_category = query.with_entities(
        Category.name, db.func.sum(Expense.amount)
    ).join(Category).group_by(Category.name).order_by(db.func.sum(Expense.amount).desc()).first()
    highest_amount = query.with_entities(db.func.max(Expense.amount)).scalar() or 0
    # Using decimal Unicode instead of hex
    empty_face = chr(128566)  # Decimal Unicode for 😶
    highest_category_name = highest_category[0] if highest_category else f"Empty!{empty_face}"
    
    return jsonify({
        "total_spent": float(total_spent),
        "expense_count": expense_count,
        "last_7days_spent": float(last_7days_spent),
        "highest_category": highest_category_name,
        "highest_amount": float(highest_amount)
    })

@app.route('/add_budget', methods=['POST'])
def add_budget():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    # Consolidated user context logic
    user_id = session['user_id']
    role = session['role']
    
    if role == "family_member":
        user = User.query.get(user_id)
        user_id = user.approved_by
        if not user_id:
            return jsonify({"message": "Not linked to any family"}), 400

    user_id = session['user_id']
    data = request.form.to_dict()
    year = data.get("year")
    month = data.get("month")
    category_name = data.get("budget-category")  # Remove conversion
    amount = data.get("budget-amount")

    if not year or not month or not category_name or not amount:
        return jsonify({"message": "Missing required fields!"}), 400

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400

    category = Category.query.filter_by(name=category_name).first()
    if not category:
        category = Category(name=category_name)
        db.session.add(category)
        db.session.commit()

    # Check if budget already exists for the given year, month, and category
    existing_budget = Budget.query.filter_by(user_id=user_id, year=year, month=month, category_id=category.category_id).first()
    if existing_budget:
        return jsonify({"message": "Budget already set for this year, month, and category!"}), 400

    new_budget = Budget(
        user_id=user_id,
        category_id=category.category_id,
        amount=amount,
        month=int(month),
        year=int(year)
    )
    db.session.add(new_budget)
    db.session.commit()

    return jsonify({"message": "Budget added successfully!"})
    
@app.route("/get_budgets")
def get_budgets():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Determine the correct user_id based on role
    if user.role == "family_member":
        user_id = user.approved_by  # Use the super_user's ID
    else:
        user_id = user.id  # Use the logged-in user's ID

    page = request.args.get("page", 1, type=int)
    per_page = 10
    budgets = Budget.query.filter_by(user_id=user_id).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "budgets": [{
            "id": budget.budget_id,
            "year": budget.year,
            "month": budget.month,
            "category": budget.category.name if budget.category else "Unknown",
            "amount": budget.amount,
            "recurring": budget.recurring
        } for budget in budgets.items],
        "total_pages": budgets.pages,
        "current_page": budgets.page
    })

@app.route("/get_budget/<int:budget_id>")
def get_budget(budget_id):
    budget = Budget.query.get(budget_id)
    if not budget:
        return jsonify({"message": "Budget not found"}), 404
        
    # Add privilege check for family members
    if session.get('role') == "family_member":
        user = User.query.get(session['user_id'])
        if user.privilege not in ['view', 'edit']:
            return jsonify({"message": "Insufficient privileges"}), 403

    return jsonify({
        "id": budget.budget_id,
        "year": budget.year,
        "month": budget.month,
        "category": budget.category.name if budget.category else "Unknown",
        "amount": budget.amount,
        "recurring": budget.recurring
    })

@app.route("/delete_budget/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user_id = session['user_id']
    budget = Budget.query.filter_by(budget_id=budget_id, user_id=user_id).first()
    if not budget:
        return jsonify({"message": "Budget not found"}), 404

    db.session.delete(budget)
    db.session.commit()
    return jsonify({"message": "Budget deleted successfully!"})

@app.route("/edit_budget/<int:budget_id>", methods=["PUT"])
def edit_budget(budget_id):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user_id = session['user_id']
    budget = Budget.query.filter_by(budget_id=budget_id, user_id=user_id).first()
    if not budget:
        return jsonify({"message": "Budget not found"}), 404

    data = request.form.to_dict()
    year = data.get("year", budget.year)
    month = data.get("month", budget.month)
    category_name = data.get("budget-category", budget.category.name)  # Remove conversion
    try:
        amount = float(data.get("budget-amount", budget.amount))
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400

    category = Category.query.filter_by(name=category_name).first()
    if not category:
        category = Category(name=category_name)
        db.session.add(category)
        db.session.commit()

    # Check if budget already exists for the given year, month, and category
    existing_budget = Budget.query.filter_by(user_id=user_id, year=year, month=month, category_id=category.category_id).first()
    if existing_budget and existing_budget.budget_id != budget_id:
        return jsonify({"message": "Budget already set for this year, month, and category!"}), 400

    budget.year = year
    budget.month = month
    budget.amount = amount
    budget.category_id = category.category_id
    db.session.commit()
    return jsonify({"message": "Budget updated successfully!"})
   
@app.route("/toggle_recurring/<int:budget_id>", methods=["PUT"])
def toggle_recurring(budget_id):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json()
    recurring = data.get("recurring", False)

    budget = Budget.query.get(budget_id)
    if not budget:
        return jsonify({"message": "Budget not found"}), 404

    budget.recurring = recurring
    db.session.commit()
    return jsonify({"message": "Budget updated successfully!"})

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

#Team 4
@app.route('/plot/category_data/<int:year>/<int:month>')
def get_category_plot(year, month):
    user_id = session.get('user_id')
    category_plot = generate_category_expenses_plot(month=month, year=year,user_id=user_id)
    return jsonify({'category_plot': category_plot})

@app.route('/plot/pie_chart/<int:year>/<int:month>')
def get_pie_chart(year, month):
    user_id = session.get('user_id')
    pie_chart = generate_pie_chart(user_id=user_id, month=month, year=year)
    return jsonify({'pie_chart': pie_chart})

@app.route('/plot/bar_chart/<int:year>/<int:month>')
def get_bar_chart(year, month):
    user_id = session.get('user_id')
    bar_chart = generate_bar_chart(user_id=user_id, month=month, year=year)
    return jsonify({'bar_chart': bar_chart})

@app.route('/plot/stacked_bar_chart/<int:year>/<int:month>')
def get_stacked_bar_chart(year, month):
    user_id = session.get('user_id')
    stacked_bar_chart = generate_stacked_bar_chart(user_id=user_id, month=month, year=year)
    return jsonify({'stacked_bar_chart': stacked_bar_chart})

@app.route('/plot/line_chart/<int:year>')
def get_line_chart(year):
    user_id = session.get('user_id')
    line_chart = generate_line_chart(user_id=user_id,year=year)
    return jsonify({'line_chart': line_chart})


#Team 3
@app.route('/saving_page')
def saving_page():
    bar_chart = plot_savings_progress()  # Main bar graph
    gauge_chart = plot_gauge_charts()    #gauge chart for 1st load
    return render_template('savings.html', bar_chart=bar_chart,gauges=gauge_chart)

@app.route('/get_savings_data', methods=['GET'])
def get_savings_data():  # For Plotly.js graph
    user_id = session.get('user_id', None)

    if not user_id:
        return jsonify([])  # Empty response

    user = User.query.get(user_id)
    if not user:
        return jsonify([])  # Empty response

    # Get family group user IDs
    if user.role == "family_member":
        superuser_id = user.approved_by
        family_members = User.query.filter_by(approved_by=superuser_id).all()
        family_group_user_ids = [fm.id for fm in family_members] + [superuser_id]
    else:
        family_members = User.query.filter_by(approved_by=user.id).all()
        family_group_user_ids = [fm.id for fm in family_members] + [user.id]

    if not family_group_user_ids:
        return jsonify([])  # Empty response

    # Build query
    query = db.session.query(
        User.username,
        db.func.coalesce(db.func.sum(SavingsTarget.amount), 0).label('Total_Target_Savings'),
        db.func.coalesce(db.func.sum(Savings.amount), 0).label('Total_Achieved_Savings')
    ).outerjoin(SavingsTarget, User.id == SavingsTarget.user_id)\
     .outerjoin(Savings, SavingsTarget.id == Savings.target_id)\
     .filter(User.id.in_(family_group_user_ids))

    # Group by username to aggregate savings properly
    data = query.group_by(User.username).all()

    # Prepare result
    result = [
        {
            "username": row[0],
            "Achieved_Savings": float(row[2]),
            "Target_Savings": float(row[1])
        } for row in data
    ]
    return jsonify(result)

def generate_no_data_image():#Function for returning no data image when no data found
    fig = go.Figure()
    fig.add_annotation(
        text="No Data Available",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=24, color="grey")
    )
    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=0, b=0, l=0, r=0),
        height=300  # You can adjust height/width if needed
    )

    img_io = BytesIO()
    fig.write_image(img_io, format='png', scale=3)
    img_io.seek(0)
    return Response(img_io.getvalue(), mimetype='image/png') 

#Bar graph
def plot_savings_progress(user_id=None):  # Main bar graph
    family_group_user_ids = []  # To hold all user_ids to filter on

    # Check if user is logged in
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

        if not user:
            return "<div style='text-align:center;'><h3>No Data Available</h3></div>"

        if user.role == "family_member":
            # Family member: include self + their superuser + other family members under same superuser
            superuser_id = user.approved_by
            family_members = User.query.filter_by(approved_by=superuser_id).all()
            family_group_user_ids = [fm.id for fm in family_members] + [superuser_id]
        else:
            # Superuser: include self + family members they approved
            family_members = User.query.filter_by(approved_by=user.id).all()
            family_group_user_ids = [fm.id for fm in family_members] + [user.id]
    else:
        # If not logged in, return 'no data'
        return "<div style='text-align:center;'><h3>No Data Available</h3></div>"

    # Now apply filter to query only for these user IDs
    query = db.session.query(
        SavingCategory.name.label('category'),
        db.func.coalesce(db.func.sum(SavingsTarget.amount), 0).label('target_savings'),
        db.func.coalesce(db.func.sum(Savings.amount), 0).label('actual_savings')
    ).outerjoin(SavingsTarget, SavingCategory.id == SavingsTarget.category_id)\
     .outerjoin(Savings, SavingsTarget.id == Savings.target_id)\
     .filter(SavingsTarget.user_id.in_(family_group_user_ids))  # Filter for family group

    # Group and execute query
    data = query.group_by(SavingCategory.name).all()

    # If no data found, return 'no data' image
    if not data:
        return "<div style='text-align:center;'><h3>No Data Available</h3></div>"

    # Extract data for plotting
    categories = [row.category for row in data]
    target_savings = [row.target_savings for row in data]
    actual_savings = [row.actual_savings for row in data]

    # Plotting
    x = np.arange(len(categories))
    width = 0.35

    plt.figure(figsize=(10, 6))
    bars1 = plt.bar(x - width/2, target_savings, width, color='gray', label='Target Savings')
    bars2 = plt.bar(x + width/2, actual_savings, width, color='blue', label='Actual Savings')

    plt.xlabel('Savings Goals')
    plt.ylabel('Amount ($)')
    plt.title('Savings Target vs. Actual')
    plt.xticks(x, categories, rotation=45, ha='right')
    plt.legend()

    # Annotate bar values
    for bar in bars1 + bars2:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval + 50, f"${yval:.2f}", ha='center', va='bottom')

    plt.tight_layout()

    # Save plot as base64-encoded PNG
    img_io = BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.read()).decode('utf-8')
    plt.close()
    return img_base64

#Pie chart
@app.route('/savings_chart')
def plot_savings_by_category():
    if 'user_id' not in session:
        return generate_no_data_image()
    
    user_id = session['user_id']

    selected_month = request.args.get('month')
    selected_year = request.args.get('year')

    # Start base query with outer joins to include all categories
    query = db.session.query(
        SavingCategory.name.label('category'),
        db.func.coalesce(db.func.sum(Savings.amount), 0).label('total_savings')
    ).outerjoin(SavingsTarget, SavingCategory.id == SavingsTarget.category_id)\
     .outerjoin(Savings, SavingsTarget.id == Savings.target_id)\
     .filter(SavingsTarget.user_id == user_id)

    # Apply filters only if selected
    if selected_month:
        query = query.filter(db.extract('month', Savings.date) == int(selected_month))
    if selected_year:
        query = query.filter(db.extract('year', Savings.date) == int(selected_year))

    # Group by category
    data = query.group_by(SavingCategory.name).all()

    if not data: #Retun no data image if there is no data
        return generate_no_data_image()
    
    # Ensure all categories are displayed (even if no savings)
    all_categories = db.session.query(SavingCategory.name).all()
    category_dict = {cat[0]: 0 for cat in all_categories}  # Default all categories to 0

    # Update with actual data
    for row in data:
        category_dict[row.category] = row.total_savings

    # Extract data for the plot
    categories = list(category_dict.keys())
    amounts = list(category_dict.values())

    # Prevent division by zero
    total = sum(amounts) if sum(amounts) != 0 else 1
    percentages = [f'{(amt / total) * 100:.1f}%' for amt in amounts]

    # Custom labels
    custom_labels = [f"{cat}" for cat, perc in zip(categories, percentages)]

    # Color palette
    colors = ['blue', 'green', 'red', 'purple', 'orange']
    colors = (colors * ((len(amounts) // len(colors)) + 1))[:len(amounts)]  # Extend colors if needed

    # Create donut chart
    fig = go.Figure(data=[go.Pie(
        labels=categories,
        values=amounts,
        hole=0.6,  # Donut effect
        marker=dict(colors=colors, line=dict(color='white', width=3)),  # White border
        hoverinfo='label+percent',
        text=custom_labels,  # Show category + percentage
        textposition='outside',
        pull=[0.05] * len(categories),  # Pull-out effect
    )])

    fig.update_layout(
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent
        plot_bgcolor='rgba(0,0,0,0)',   # Transparent
        margin=dict(t=50, b=0, l=0, r=0)
    )

    # Save as transparent PNG
    img_io = BytesIO()
    fig.write_image(img_io, format='png', scale=3)
    img_io.seek(0)
    return Response(img_io.getvalue(), mimetype='image/png') 

# Gauge chart
@app.route('/gauge_chart')
def plot_gauge_charts():
    if 'user_id' not in session:
        return "<div style='text-align:center;'><h3>No Data Available</h3></div>"

    user_id = session['user_id']
    selected_month = request.args.get('month')
    selected_year = request.args.get('year')

    # Base query with user filter
    query = db.session.query(
        SavingCategory.name.label('category'),
        SavingsTarget.amount.label('target'),
        db.func.coalesce(db.func.sum(Savings.amount), 0).label('saved')
    ).join(SavingsTarget, SavingCategory.id == SavingsTarget.category_id)\
     .outerjoin(Savings, SavingsTarget.id == Savings.target_id)\
     .filter(SavingsTarget.user_id == user_id)

    # Apply month and year filters
    if selected_month:
        query = query.filter(db.extract('month', Savings.date) == int(selected_month))
    if selected_year:
        query = query.filter(db.extract('year', Savings.date) == int(selected_year))

    # Group data
    data = query.group_by(SavingCategory.name, SavingsTarget.amount).all()

    if not data:
        return "<div style='text-align:center;'><h3>No Data Available</h3></div>"

    # Create figure
    fig = go.Figure()
    buttons = []

    for idx, (cat, target, saved) in enumerate(data):
        progress = (float(saved) / float(target)) * 100 if target else 0

        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=progress,
                title={'text': f"{cat}"},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': 'blue'}},
                visible=True if idx == 0 else False
            )
        )

        buttons.append(
            dict(
                label=cat,
                method="update",
                args=[
                    {"visible": [i == idx for i in range(len(data))]},
                    {"title": f"Savings Progress: {cat}"}
                ]
            )
        )

    # Dropdown for categories
    fig.update_layout(
        updatemenus=[
            dict(
                active=0,
                buttons=buttons,
                x=1.15,
                y=1,
                xanchor='right',
                yanchor='top'
            )
        ],
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig.to_html(full_html=False, config={'displayModeBar': False})

# get_category_savings is for gauge chart
@app.route('/get_category_savings')
def get_category_savings():  # Using for gauge chart to filter category
    # Get user_id from session if logged in
    user_id = session.get('user_id')
    selected_month = request.args.get('month')
    selected_year = request.args.get('year')

    # Base query
    query = db.session.query(
        SavingCategory.name.label('category'),
        db.func.coalesce(db.func.sum(Savings.amount), 0).label('total_saved')
    ).outerjoin(SavingsTarget, SavingCategory.id == SavingsTarget.category_id)\
     .outerjoin(Savings, SavingsTarget.id == Savings.target_id)

    # Apply user filter if user_id is available
    if user_id:
        query = query.filter(SavingsTarget.user_id == user_id)

    # Apply month and year filters
    if selected_month:
        query = query.filter(db.extract('month', Savings.date) == int(selected_month))
    if selected_year:
        query = query.filter(db.extract('year', Savings.date) == int(selected_year))

    # Group data
    data = query.group_by(SavingCategory.name).all()

    # Preparing data to return as JSON
    result = [{'category': row.category, 'saved_amount': row.total_saved} for row in data]
    return jsonify(result)

#get_savings_filters is for the filters for gauge and pie chart for monthyears
@app.route('/get_savings_filters', methods=['GET'])  #For filters according to month and year
def get_savings_filters():
    user_id = session.get('user_id')  # Get the logged-in user's ID

    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    # Fetch unique months and years
    filters = db.session.query(
        db.func.extract('month', Savings.date).label('month'),
        db.func.extract('year', Savings.date).label('year')
    ).filter(Savings.user_id == user_id).distinct().all()

    # Format response
    months_years = [{"month": int(m), "year": int(y)} for m, y in filters]

    return jsonify(months_years)

# get_filters_for_table is updated with session id and filters(user,monthyear,role)
@app.route('/get_filters_for_table', methods=['GET']) #for month and year filter for tables
def get_filters_for_table():
    user_id = session.get('user_id')  # Get the logged-in user's ID

    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    # Fetch unique months and years from SavingsTarget table
    filters = db.session.query(
        db.func.extract('month', SavingsTarget.target_date).label('month'),
        db.func.extract('year', SavingsTarget.target_date).label('year')
    ).filter(SavingsTarget.user_id == user_id).distinct().order_by(
        db.func.extract('month', SavingsTarget.target_date).asc(),
        db.func.extract('year', SavingsTarget.target_date).asc()
    ).all()

    # Format response
    months_years = [{"month": int(m), "year": int(y)} for m, y in filters]

    return jsonify(months_years)

@app.route('/add_saving_target', methods=['POST'])
def add_saving_target():
    data = request.json
    print("Received data for saving target:", data)

    # Find or create the saving category
    category = SavingCategory.query.filter_by(name=data['saving_category_name']).first()
    if not category:
        category = SavingCategory(
            name=data['saving_category_name'],
            description=data.get('saving_category_description', '')  # Use default if description is not provided
        )
        db.session.add(category)
        db.session.commit()

    # Create a new savings target
    target = SavingsTarget(
        user_id=data.get('user_id', 1),  # Use user_id from request or default to 1
        category_id=category.id,
        name=data['savings_goal_name'],
        amount=data['savings_target_amount'],
        target_date=datetime.strptime(data['savings_target_date'], '%Y-%m-%d').date()
    )
    db.session.add(target)
    db.session.commit()

    # Optionally add an initial savings entry
    if data.get('initial_saving_amount', 0) > 0:
        savings = Savings(
            user_id=data.get('user_id', 1),  # Use user_id from request or default to 1
            target_id=target.id,
            amount=data['initial_saving_amount'],
            date=datetime.utcnow()
        )
        db.session.add(savings)
        db.session.commit()

    return jsonify({"message": "Savings target and (optional) initial savings entry added successfully"}), 201

@app.route('/update_saving_target/<int:id>', methods=['PUT'])
def update_saving_target(id):
    data = request.json
    target = SavingsTarget.query.get(id)  # Get the savings target by ID
    if target:
        # Find or create the saving category
        category = SavingCategory.query.filter_by(name=data['saving_category_name']).first()
        if not category:
            category = SavingCategory(
                name=data['saving_category_name'],
                description=data.get('saving_category_description', '')  # Use default empty description
            )
            db.session.add(category)
            db.session.commit()

        # Update target fields
        target.category_id = category.id
        target.name = data['savings_goal_name']
        target.amount = data['savings_target_amount']
        target.target_date = datetime.strptime(data['savings_target_date'], '%Y-%m-%d').date()

        db.session.commit()
        return jsonify({"message": "Savings target updated successfully"}), 200

    return jsonify({"message": "Savings target not found"}), 404

@app.route('/delete_saving_target/<int:id>', methods=['DELETE'])
def delete_saving_target(id):
    target = SavingsTarget.query.get(id)  # Get the savings target by ID
    if target:
        # Delete all associated savings
        savings = Savings.query.filter_by(target_id=id).all()
        for saving in savings:
            db.session.delete(saving)

        db.session.delete(target)  # Delete the target itself
        db.session.commit()
        return jsonify({"message": "Savings target and corresponding savings deleted successfully"}), 200

    return jsonify({"message": "Savings target not found"}), 404

@app.route('/add_savings', methods=['POST'])
def add_savings():
    data = request.json
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"message": "User not authenticated"}), 401

    # Check if savings entry exists for this target and user
    savings = Savings.query.filter_by(target_id=data['savings_target_id'], user_id=user_id).first()

    if savings:
        # Update the existing savings entry
        savings.amount = data['savings_amount_saved']
        savings.mode = data['savings_payment_mode']
        savings.date = datetime.strptime(data['savings_date_saved'], '%Y-%m-%d').date()
        db.session.commit()
        return jsonify({"message": "Savings updated successfully"}), 200
    else:
        # Add new savings entry
        new_savings = Savings(
            user_id=user_id,
            target_id=data['savings_target_id'],  # ✅ Correct column name
            amount=data['savings_amount_saved'],
            mode=data['savings_payment_mode'],
            date=datetime.strptime(data['savings_date_saved'], '%Y-%m-%d').date()  # ✅ Correct column name
        )
        db.session.add(new_savings)
        db.session.commit()
        return jsonify({"message": "Savings added successfully"}), 201

@app.route('/get_savings/<int:id>', methods=['GET'])
def get_savings(id):
    # Fetch savings entry by target_id
    savings = Savings.query.filter_by(target_id=id).first()
    if savings:
        # Retrieve the associated category through the savings target
        category = SavingCategory.query.get(savings.savings_target.category_id)
        return jsonify({"savings": {
            "savings_target_id": savings.target_id,
            "saving_category_name": category.name,
            "saving_category_description": category.description,
            "savings_goal_name": savings.savings_target.name,
            "savings_target_amount": float(savings.savings_target.amount),
            "savings_target_date": str(savings.savings_target.target_date),
            "savings_amount_saved": float(savings.amount or 0),
            "savings_payment_mode": savings.mode,
            "savings_date_saved": str(savings.date)
        }}), 200

    # If no savings exist, retrieve the target instead
    target = SavingsTarget.query.get(id)
    if target:
        category = SavingCategory.query.get(target.category_id)
        return jsonify({"savings": {
            "savings_target_id": target.id,
            "saving_category_name": category.name,
            "saving_category_description": category.description,
            "savings_goal_name": target.name,
            "savings_target_amount": float(target.amount),
            "savings_target_date": str(target.target_date),
            "savings_amount_saved": 0,
            "savings_payment_mode": '',
            "savings_date_saved": str(datetime.today().date())
        }}), 200

    # If neither savings nor target is found, return None
    return jsonify({"savings": None}), 200

@app.route('/update_savings/<int:id>', methods=['PUT'])
def update_savings(id):
    data = request.json
    savings = Savings.query.filter_by(Sav_Target_id=id).first()
    if savings:
        savings.Amount = data['savings_amount_saved']
        savings.Mode = data['savings_payment_mode']
        savings.Date = datetime.strptime(data['savings_date_saved'], '%Y-%m-%d').date()
        db.session.commit()
        return jsonify({"message": "Savings updated successfully"}), 200
    return jsonify({"message": "Savings not found"}), 404

@app.route('/delete_savings/<int:id>', methods=['DELETE'])
def delete_savings(id):
    # Retrieve the savings entry by ID
    savings = Savings.query.get(id)
    if savings:
        db.session.delete(savings)  # Delete the entry
        db.session.commit()
        return jsonify({"message": "Savings deleted successfully"}), 200

    # If the savings entry is not found
    return jsonify({"message": "Savings not found"}), 404

# get_all_data_ is updated with session id and filters(user,monthyear,role)
@app.route('/get_all_data', methods=['GET'])
def get_all_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    month = request.args.get("month")
    year = request.args.get("year")

    # Start base query
    query = SavingsTarget.query.join(User, SavingsTarget.user_id == User.id)

    # Role-based filtering
    if user.role == "family_member":
        query = query.filter(SavingsTarget.user_id == user.id)
    elif user.role == "super_user":
        family_members = User.query.filter_by(approved_by=user.id).all()  # Assuming this exists
        family_member_ids = [member.id for member in family_members]
        query = query.filter(SavingsTarget.user_id.in_([user.id] + family_member_ids))

    # Apply month/year filters if provided
    if month:
        query = query.filter(db.extract("month", SavingsTarget.target_date) == int(month))
    if year:
        query = query.filter(db.extract("year", SavingsTarget.target_date) == int(year))

    targets = query.all()
    data = []

    for target in targets:
        savings = Savings.query.filter_by(target_id=target.id).first()
        category = SavingCategory.query.get(target.category_id)

        data.append({
            "savings_target_id": target.id,
            "saving_category_name": category.name,
            "saving_category_description": category.description,
            "savings_goal_name": target.name,
            "savings_target_amount": float(target.amount),
            "savings_target_date": str(target.target_date),
            "savings_amount_saved": float(savings.amount or 0) if savings else 0,
            "savings_payment_mode": savings.mode if savings else '',
            "savings_date_saved": str(savings.date) if savings else str(datetime.today().date()),
            "savings_updated_date": str(savings.date) if savings else None
        })
    return jsonify(data)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
