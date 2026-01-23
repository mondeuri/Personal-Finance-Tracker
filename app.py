from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return UserSettings.query.get(int(user_id))



class UserSettings(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="User")
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    currency_symbol = db.Column(db.String(10), default="₱")
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    accounts = db.relationship('Account', backref='user', lazy=True)
    savings = db.relationship('SavingsAccount', backref='user', uselist=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_settings.id'))
    name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    category = db.Column(db.String(50))
    date = db.Column(db.String(20))
    type = db.Column(db.String(10))

class SavingsAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_settings.id'))
    total_amount = db.Column(db.Float, default=0.0)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_settings.id'))
    name = db.Column(db.String(100))
    type = db.Column(db.String(50))
    balance = db.Column(db.Float)
    icon = db.Column(db.String(10))

with app.app_context():
    db.create_all()
    db.session.commit()


def get_finance_data():
    total_inc = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'Income').scalar() or 0.0
    total_exp = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'Expense').scalar() or 0.0
    
    current_balance = total_inc - total_exp
    total_saved = current_user.savings.total_amount if current_user.savings else 0.0
    
    return {
        "name": current_user.name,
        "email": current_user.email,
        "symbol": current_user.currency_symbol,
        "balance": "{:,.2f}".format(current_balance),
        "income": "{:,.2f}".format(total_inc),
        "expense": "{:,.2f}".format(total_exp),
        "savings": "{:,.2f}".format(total_saved),
        "raw_balance": current_balance
    }


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = UserSettings.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Invalid email or password", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name') or "User"
        password = generate_password_hash(request.form.get('password'))

        if UserSettings.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for('register'))

        new_user = UserSettings(email=email, name=name, password=password)
        db.session.add(new_user)
        db.session.commit()

        db.session.add(SavingsAccount(user_id=new_user.id, total_amount=0.0))
        db.session.commit()

        flash("Account created! Please login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    data = get_finance_data()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(
        Transaction.id.desc()).limit(5).all()
    budget_q = db.session.query(Transaction.category, func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'Expense').group_by(Transaction.category).all()
    
    return render_template('dashboard.html', data=data, transactions=transactions,
                           budget_categories=[r[0] for r in budget_q],
                           budget_values=[float(r[1]) for r in budget_q], active_page='Dashboard')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        current_user.currency_symbol = request.form.get('currency')
        db.session.commit()
        flash("Settings updated successfully!", "success")
        return redirect(url_for('settings'))
    return render_template('settings.html', data=get_finance_data(), active_page='Settings')

@app.route('/wallet')
@login_required
def wallet():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('wallet.html', data=get_finance_data(), accounts=accounts, active_page='Wallet')

@app.route('/budget')
@login_required
def budget():
    data = get_finance_data()
    budget_q = db.session.query(Transaction.category, func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'Expense').group_by(Transaction.category).all()
    return render_template('budget.html', data=data,
                           budget_categories=[r[0] for r in budget_q],
                           budget_values=[float(r[1]) for r in budget_q], active_page='Budget')

@app.route('/analytics')
@login_required
def analytics():
    data = get_finance_data()
    budget_q = db.session.query(Transaction.category, func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'Expense').group_by(Transaction.category).all()
    return render_template('analytics.html', data=data,
                           budget_categories=[r[0] for r in budget_q],
                           budget_values=[float(r[1]) for r in budget_q], active_page='Analytics')

@app.route('/savings')
@login_required
def savings():
    return render_template('savings.html', data=get_finance_data(), active_page='Savings')

@app.route('/transactions')
@login_required
def transactions():
    all_t = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.id.desc()).all()
    return render_template('transactions.html', data=get_finance_data(), transactions=all_t, active_page='Transactions')


@app.route('/add_account', methods=['POST'])
@login_required
def add_account():
    new_acc = Account(
        user_id=current_user.id,
        name=request.form.get('name'),
        type=request.form.get('type'),
        balance=float(request.form.get('balance') or 0),
        icon=request.form.get('icon', '💰')
    )
    db.session.add(new_acc)
    db.session.commit()
    return redirect(url_for('wallet'))

@app.route('/adjust_account/<int:id>', methods=['POST'])
@login_required
def adjust_account(id):
    account = Account.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    amount = float(request.form.get('amount') or 0)
    action = request.form.get('action')
    if action == 'plus':
        account.balance += amount
    elif action == 'minus':
        account.balance = max(0, account.balance - amount)
    db.session.commit()
    return redirect(url_for('wallet'))

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    db.session.add(Transaction(
        user_id=current_user.id,
        name=request.form.get('name'),
        amount=float(request.form.get('amount') or 0),
        category=request.form.get('category'),
        date=request.form.get('date'),
        type=request.form.get('type')
    ))
    db.session.commit()
    flash("Transaction recorded!", "success")
    return redirect(url_for('dashboard'))

@app.route('/update_savings', methods=['POST'])
@login_required
def update_savings():
    amount = float(request.form.get('amount') or 0)
    action = request.form.get('action')
    savings_rec = current_user.savings
    symbol = current_user.currency_symbol

    if amount <= 0:
        flash("Please enter an amount greater than zero.", "error")
        return redirect(url_for('savings'))

    current_data = get_finance_data()
    current_balance = float(current_data['balance'].replace(',', ''))

    if action == 'deposit':
        if current_balance <= 0 or amount > current_balance:
            flash(f"Oops! Insufficient balance to deposit this amount.", "error")
        else:
            db.session.add(Transaction(user_id=current_user.id, name="Transfer to Savings", amount=amount,
                           category="Salary", date=datetime.now().strftime('%Y-%m-%d'), type="Expense"))
            savings_rec.total_amount += amount
            flash(f"Successfully deposited {symbol}{amount:,.2f}!", "success")
    else:
        if amount > savings_rec.total_amount:
            flash(f"Oops! You only have {symbol}{savings_rec.total_amount:,.2f} in savings.", "error")
        else:
            db.session.add(Transaction(user_id=current_user.id, name="Withdraw from Savings", amount=amount,
                           category="Salary", date=datetime.now().strftime('%Y-%m-%d'), type="Income"))
            savings_rec.total_amount -= amount
            flash(f"Successfully transferred back {symbol}{amount:,.2f}!", "success")

    db.session.commit()
    return redirect(url_for('savings'))

@app.route('/clear_history')
@login_required
def clear_history():
    Transaction.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(url_for('transactions'))

if __name__ == '__main__':
    app.run(debug=True)