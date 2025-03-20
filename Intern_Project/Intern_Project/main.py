from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from flask_mail import Mail, Message
from functools import wraps
from flask_cors import CORS
from datetime import datetime, timedelta,timezone
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Expense, Category, Budget, User
from io import BytesIO
import random, string, os,re
import io
import base64
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd


app = Flask(__name__)
app.secret_key = "unifiedfamilyfinancetracker"
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False 

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///ufft_database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

db.init_app(app)

matplotlib.use('Agg')

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

def generate_monthly_expenses_plot():
    # Query to get monthly expenses
    monthly_expenses = db.session.query(
        db.func.strftime('%Y-%m', Expense.date).label('month'),
        db.func.sum(Expense.amount).label('total_expense')
    ).group_by('month').order_by('month').all()

    # Extract data for plotting
    months = [row.month for row in monthly_expenses]
    expenses = [float(row.total_expense) for row in monthly_expenses]

    # Generate the plot
    plt.figure(figsize=(8, 5))
    plt.plot(months, expenses, marker='o', linestyle='-', color='b')
    plt.xlabel('Month')
    plt.ylabel('Total Expense')
    plt.title('Monthly Expenses')
    plt.xticks(rotation=45)
    plt.grid()

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    # Return the plot as a base64-encoded string
    return base64.b64encode(img.getvalue()).decode()

def generate_category_expenses_plot(year, month):
    # Query to get expenses by category for a specific month and year
    category_expenses = db.session.query(
        Category.name,
        db.func.sum(Expense.amount).label('total_expense')
    ).join(Expense, Category.category_id == Expense.category_id).filter(db.func.strftime('%Y', Expense.date) == str(year)).filter(db.func.strftime('%m', Expense.date) == f'{month:02d}').group_by(Category.name).all()

    # Extract data for plotting
    categories = [row.name for row in category_expenses]
    expenses = [float(row.total_expense) for row in category_expenses]

    # Generate the plot
    plt.figure(figsize=(8, 5))
    plt.bar(categories, expenses, color='orange')
    plt.xlabel('Category')
    plt.ylabel('Total Expense')
    plt.title(f'Expenses by Category for {year}-{month:02d}')
    plt.xticks(rotation=45)

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    # Return the plot as a base64-encoded string
    return base64.b64encode(img.getvalue()).decode()


def generate_pie_chart(user=None, month=None, year=None):
    if month is None or year is None:
        today = datetime.today()
        month, year = today.month, today.year

    # Query for budget data
    budget_data = db.session.query(
        Category.name,
        db.func.sum(Budget.amount).label('total_budget')
    ).join(Budget, Category.category_id == Budget.category_id).filter(Budget.month == month).filter(Budget.year == year).group_by(Category.name).all()

    # Query for expense data
    expense_data = db.session.query(
        Category.name,
        db.func.sum(Expense.amount).label('total_expense')
    ).join(Expense, Category.category_id == Expense.category_id).filter(db.func.strftime('%m', Expense.date) == f'{month:02d}').filter(db.func.strftime('%Y', Expense.date) == str(year)).group_by(Category.name).all()

    # Extract data for plotting
    categories_budget = [row.name for row in budget_data]
    budget_amounts = [float(row.total_budget) for row in budget_data]

    categories_expense = [row.name for row in expense_data]
    expense_amounts = [float(row.total_expense) for row in expense_data]

    # Generate the plot
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))

    if budget_amounts:
        axs[0].pie(budget_amounts, labels=categories_budget, autopct='%1.1f%%', startangle=140)
        axs[0].set_title('Planned Budget')
    else:
        axs[0].text(0.5, 0.5, "No Data", fontsize=15, ha='center')

    if expense_amounts:
        axs[1].pie(expense_amounts, labels=categories_expense, autopct='%1.1f%%', startangle=140)
        axs[1].set_title('Actual Expenses')
    else:
        axs[1].text(0.5, 0.5, "No Data", fontsize=15, ha='center')

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    return base64.b64encode(img.getvalue()).decode()


def generate_bar_chart(user=None, month=None, year=None):
    if month is None or year is None:
        today = datetime.today()
        month, year = today.month, today.year

    # Query to get budget and expense data for the user
    data = db.session.query(
        Category.name,
        db.func.sum(Budget.amount).label('total_budget'),
        db.func.sum(Expense.amount).label('total_expense')
    ).join(Budget, Category.category_id == Budget.category_id, isouter=True).join(Expense, Category.category_id == Expense.category_id, isouter=True).filter(Budget.user_id == User.id).filter(db.func.strftime('%m', Expense.date) == f'{month:02d}').filter(db.func.strftime('%Y', Expense.date) == str(year)).group_by(Category.name).all()

    total_budget = sum(row[1] for row in data)
    total_expense = sum(row[2] for row in data)
    fig, ax = plt.subplots(figsize=(12, 6))  #  Make it WIDER
    if not data or all(row[1] == 0 and row[2] == 0 for row in data):
        ax.text(0.5, 0.5, "No Data Available", fontsize=15, ha='center', va='center')
    else:
        categories = [row[0] for row in data]
        budgets = [row[1] for row in data]
        expenses = [row[2] for row in data]
        x_indexes = range(len(categories))
        ax.barh(x_indexes, budgets, height=0.8, color='aqua', label="Budget", alpha=0.6)
        ax.barh(x_indexes, expenses, height=0.8, color='red', label="Expense", alpha=0.6)
        ax.set_yticks(x_indexes)
        ax.set_yticklabels(categories)
        ax.set_xlabel("Amount")
        ax.set_title(f"Spending Progress by Category ({month}/{year})")
        ax.legend()
        legend_text = f"Total Budget: Rs.{total_budget:,.2f}\nTotal Spent: Rs.{total_expense:,.2f}"  #  Keep Total Budget and Total Spent Label
        ax.text(1.05, 0.98, legend_text, transform=ax.transAxes, fontsize=12, verticalalignment='top', 
                bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=0.5'))
    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plt.close()

    # Return the plot as a base64-encoded string
    return base64.b64encode(img.getvalue()).decode()

def generate_stacked_bar_chart(month=None, year=None):
    if month is None or year is None:
        today = datetime.today()
        month, year = today.month, today.year

    # Query to get expenses by family members and categories
    data = db.session.query(
        User.username,
        Category.name,
        db.func.sum(Expense.amount).label('total_expense')
    ).join(Expense, User.id == Expense.user_id).join(Category, Expense.category_id == Category.category_id).filter(
        db.func.strftime('%m', Expense.date) == f'{month:02d}'
    ).filter(
        db.func.strftime('%Y', Expense.date) == str(year)
    ).group_by(User.username, Category.name).all()

    # Convert to a DataFrame
    df = pd.DataFrame(data, columns=['username', 'category', 'total_expense'])

    if df.empty:
        print("❗ No expense data found for this month and year. Returning empty plot.")
        return None  # Return None to indicate no data

    df_pivot = df.pivot(index='username', columns='category', values='total_expense').fillna(0)

    df_pivot = df_pivot.apply(pd.to_numeric, errors='coerce').fillna(0)



    # Generate the plot
    plt.figure(figsize=(12, 6))
    df_pivot.plot(kind='bar', stacked=True, colormap='Set2', edgecolor='black')
    plt.xlabel('Family Members')
    plt.ylabel('Total Expense')
    plt.title(f'Family Members\' Expenses by Category for {month}/{year}')
    plt.xticks(rotation=0)
    plt.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left')

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close()

    # Return the plot as a base64-encoded string
    return base64.b64encode(img.getvalue()).decode()


def generate_line_chart(year):
    # Query to get budget and expense data for the year
    data = db.session.query(
        db.func.strftime('%m', Expense.date).label('month'),
        db.func.sum(Budget.amount).label('total_budget'),
        db.func.sum(Expense.amount).label('total_expense')
    ).join(Budget, (Budget.category_id == Expense.category_id) & 
                   (Budget.month == db.func.strftime('%m', Expense.date)), isouter=True
    ).filter(db.func.strftime('%Y', Expense.date) == str(year)
    ).group_by('month').order_by('month').all()

    # Convert data into lists
    months = [row.month for row in data]
    total_budget = [float(row.total_budget) if row.total_budget else 0 for row in data]
    total_expense = [float(row.total_expense) if row.total_expense else 0 for row in data]
    
    plt.figure(figsize=(10, 5))
    plt.plot(months, total_budget, label='Budget', marker='o', linestyle='-')
    plt.plot(months, total_expense, label='Expense', marker='o', linestyle='-')
    plt.xlabel('Month')
    plt.ylabel('Amount')
    plt.title(f'Budget vs. Expense by Month ({year})')
    plt.legend()
    plt.grid()
    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    # Return the plot as a base64-encoded string
    return base64.b64encode(img.getvalue()).decode()


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
    monthly_plot = generate_monthly_expenses_plot()
    category_plot = generate_category_expenses_plot(default_year, default_month)
    pie_chart = generate_pie_chart(user=default_user, month=default_month, year=default_year)
    bar_chart = generate_bar_chart(user=default_user, month=default_month, year=default_year)
    stacked_bar_chart = generate_stacked_bar_chart(month=default_month, year=default_year)
    line_chart = generate_line_chart(default_year)
    
    return render_template('dashboard.html',
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
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    return render_template('view_dash.html',username=user.username)


#Team 2
@app.route("/get_categories")
def get_categories():
    categories = Category.query.all()
    return jsonify([{"name": cat.name, "description": cat.category_desc} for cat in categories])

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(session['user_id'])
    username = user.username  # Get the logged-in user's username
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Determine the correct user_id based on role
    if user.role == "family_member":
        user_id = user.approved_by  # Use the super_user's ID
    else:
        user_id = user.id  # Use the logged-in user's ID

    data = request.form.to_dict()
    name = data.get("name")
    category_name = data.get("category")
    date_str = data.get("date")
    amount = data.get("amount")
    description = data.get("description", "")

    if not name or not category_name or not date_str or not amount:
        return jsonify({"message": "Missing required fields!"}), 400

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400

    # Handle "Others" category input
    if category_name == "Others":
        category_name = data.get("custom-category")
        if not category_name:
            return jsonify({"message": "Custom category name is required!"}), 400

    # Remove emojis for internal storage
    category_stripped = strip_emojis(category_name)
    category = Category.query.filter_by(name=category_stripped).first()
    if not category:
        category_desc = data.get("category-desc", "")
        category = Category(name=category_stripped, category_desc=category_desc)
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
            username=username,  
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
            username=username,  
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

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Determine the correct user_id based on role
    if user.role == "family_member":
        user_id = user.approved_by  # Use the super_user's ID
    else:
        user_id = user.id  # Use the logged-in user's ID
            
    
    
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    
    query = Expense.query.filter_by(user_id=user_id)
    if from_date:
        query = query.filter(Expense.date >= from_date)
    if to_date:
        query = query.filter(Expense.date <= to_date)
    expenses = query.order_by(Expense.date.desc()).all()
    return jsonify([{
        "id": exp.id,
        "username": exp.username,
        "name": exp.name,
        "category": attach_emojis(exp.category.name) if exp.category else "Unknown",
        "date": exp.date.strftime("%Y-%m-%d"),
        "amount": exp.amount,
        "description": exp.description,
        "image_url": f"/get_file/{exp.id}" if exp.image_data else None,
        "file_type": exp.file_type
    } for exp in expenses])

@app.route("/get_expense/<int:expense_id>")
def get_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        return jsonify({"message": "Expense not found"}), 404
    return jsonify({
        "id": expense.id,
        "username": expense.username,
        "name": expense.name,
        "category": attach_emojis(expense.category.name) if expense.category else "Unknown",
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

    user_id = session['user_id']
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    data = request.form.to_dict()
    expense.name = data.get("name", expense.name)
    category_name = data.get("category", expense.category.name)
    try:
        expense.amount = float(data.get("amount", expense.amount))
    except ValueError:
        return jsonify({"message": "Invalid amount!"}), 400
    expense.description = data.get("description", expense.description)
    if category_name == "Others":
        category_name = data.get("custom-category")
        if not category_name:
            return jsonify({"message": "Custom category name is required!"}), 400
    category = Category.query.filter_by(name=strip_emojis(category_name)).first()
    if not category:
        category_desc = data.get("category-desc", "")
        category = Category(name=strip_emojis(category_name), category_desc=category_desc)
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

    user_id = session['user_id']
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

    user_id = session['user_id']
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = Expense.query.filter_by(user_id=user_id)
    if from_date:
        query = query.filter(Expense.date >= from_date)
    if to_date:
        query = query.filter(Expense.date <= to_date)

    total_spent = query.with_entities(db.func.sum(Expense.amount)).scalar() or 0
    expense_count = query.with_entities(db.func.count(Expense.id)).scalar() or 0
    last_7days_spent = query.with_entities(db.func.sum(Expense.amount)).filter(
        Expense.date >= (datetime.now().date() - timedelta(days=7))
    ).scalar() or 0
    highest_category = query.with_entities(
        Category.name, db.func.sum(Expense.amount)
    ).join(Category).group_by(Category.name).order_by(db.func.sum(Expense.amount).desc()).first()
    highest_amount = query.with_entities(db.func.max(Expense.amount)).scalar() or 0
    highest_category_name = attach_emojis(highest_category[0]) if highest_category else "Empty!😶"
    return jsonify({
        "total_spent": float(total_spent),
        "expense_count": expense_count,
        "last_7days_spent": float(last_7days_spent),
        "highest_category": highest_category_name,
        "highest_amount": float(highest_amount)
    })

@app.route('/set_period', methods=['POST'])
def set_period():
    try:
        data = request.get_json()
        if not data or 'year' not in data or 'month' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        year = int(data['year'])
        month = int(data['month'])
        if not (1 <= month <= 12):
            return jsonify({'error': 'Invalid month'}), 400
        if year < 2000 or year > 2100:
            return jsonify({'error': 'Invalid year'}), 400
        session['current_year'] = year
        session['current_month'] = month
        return jsonify({'message': 'Period set successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/add_budget', methods=['POST'])
def add_budget():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

   
    if user.role == "family_member":
        user_id = user.approved_by  # Use the super_user's ID
    else:
        user_id = user.id  # Use the logged-in user's ID

    try:
        data = request.get_json()
        if not data or 'category' not in data or 'amount' not in data:
            return jsonify({'error': 'Missing category or amount'}), 400

        # Get period from session
        year = session.get('current_year')
        month = session.get('current_month')
        if not year or not month:
            return jsonify({'error': 'Period not set'}), 400

        # Process category
        category_name = strip_emojis(data['category'].split(' ')[0])  # Remove emoji and any trailing space
        amount = float(data['amount'])

        # Find or create category
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.commit()

        # Create budget entry
        new_budget = Budget(
            user_id=user_id,  
            category_id=category.category_id,
            amount=amount,
            month=month,
            year=year
        )

        db.session.add(new_budget)
        db.session.commit()

        return jsonify({'message': 'Budget saved successfully'}), 200

    except ValueError as ve:
        return jsonify({'error': f'Invalid data format: {str(ve)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
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

    # Fetch budgets for the correct user_id
    budgets = Budget.query.filter_by(user_id=user_id).join(Category).add_columns(
        Budget.budget_id,
        Budget.year,
        Budget.month,
        Category.name,
        Budget.amount
    ).all()

    return jsonify([{
        "budget_id": b.budget_id,
        "year": b.year,
        "month": b.month,
        "category": attach_emojis(b.name),
        "amount": float(b.amount)
    } for b in budgets])

@app.route("/get_budget/<int:budget_id>")
def get_budget(budget_id):
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

    # Fetch budget for the correct user_id
    budget = Budget.query.filter_by(budget_id=budget_id, user_id=user_id).first()
    if not budget:
        return jsonify({"message": "Budget not found"}), 404

    return jsonify({
        "budget_id": budget.budget_id,
        "category": budget.category.name,
        "amount": float(budget.amount),
        "month": budget.month,
        "year": budget.year
    })

@app.route("/delete_budget/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
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

    # Fetch budget for the correct user_id
    budget = Budget.query.filter_by(budget_id=budget_id, user_id=user_id).first()
    if not budget:
        return jsonify({"message": "Budget not found"}), 404

    db.session.delete(budget)
    db.session.commit()
    return jsonify({"message": "Budget deleted successfully"})

@app.route("/edit_budget/<int:budget_id>", methods=["PUT"])
def edit_budget(budget_id):
    budget = Budget.query.get(budget_id)
    if not budget:
        return jsonify({"message": "Budget not found"}), 404
    
    data = request.get_json()
    category_name = strip_emojis(data['category'].split(' ')[0])
    category = Category.query.filter_by(name=category_name).first()
    
    if not category:
        return jsonify({"message": "Category not found"}), 404
    
    budget.category_id = category.category_id
    budget.amount = data['amount']
    db.session.commit()
    
    return jsonify({"message": "Budget updated successfully"})
   

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

#Team 4
@app.route('/plot/category_data/<int:year>/<int:month>')
def get_category_plot(year, month):
    category_plot = generate_category_expenses_plot(year, month)
    return jsonify({'category_plot': category_plot})

@app.route('/plot/pie_chart/<int:year>/<int:month>')
def get_pie_chart(year, month):
    user = request.args.get('user')
    if user == "All Users":
        user = None
    pie_chart = generate_pie_chart(user=user, month=month, year=year)
    return jsonify({'pie_chart': pie_chart})

@app.route('/plot/bar_chart/<int:year>/<int:month>')
def get_bar_chart(year, month):
    user = request.args.get('user')
    if user == "All Users":
        user = None
    bar_chart = generate_bar_chart(user=user, month=month, year=year)
    return jsonify({'bar_chart': bar_chart})

@app.route('/plot/stacked_bar_chart/<int:year>/<int:month>')
def get_stacked_bar_chart(year, month):
    stacked_bar_chart = generate_stacked_bar_chart(month=month, year=year)
    return jsonify({'stacked_bar_chart': stacked_bar_chart})

@app.route('/plot/line_chart/<int:year>')
def get_line_chart(year):
    line_chart = generate_line_chart(year)
    return jsonify({'line_chart': line_chart})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
