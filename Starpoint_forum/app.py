from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_restful import Api, Resource
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests


app = Flask(__name__, static_url_path='/static')
api = Api(app)
app.secret_key = 'fire_host'  # Change this to a different secret key for security purposes
posts = []

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Using SQLite database for demonstraion purposes
app.config['SQLALCHEMYst_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define User model and create database, this sets the user, post and reply variables and gives replies a relationship to posts
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    replies = db.relationship('Reply', backref='author', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    replies = db.relationship('Reply', backref='post', lazy=True)

class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


#api integration
exchange_rate = "https://api.exchangerate-api.com/v4/latest/USD"
api_key = 'a37107f693c4eb8abbed9710'




#Initializes login
login_manager = LoginManager(app)

#login manager that is used to give information about users
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Returns the homepage
@app.route('/')
def index():
    return render_template('index.html')

#Login method that is connected to the database, searches and matches password and username, while returning a 404 error if needed
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('404login.html')
    return render_template('login.html')

#Gives access to a personal user dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    forum_post_href = url_for('forum_post')
    return render_template('dashboard.html', forum_post_href=forum_post_href)

#Logs out users by popping the current session and returning users to the homepage
@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('logged_in', None)
    return redirect(url_for('index'))

#Method for signing users up, checks for username, email, password and hashes the password for security purposes
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hash = generate_password_hash(password)
        # Check if username or email already exists
        existing_user: User = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            return 'Username or email already exists!'
        # Create new user
        new_user: User = User(username=username, email=email, password=hash)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('signup_success'))
    return render_template('signup.html')

@app.route('/signup_success')
def signup_success():
    return 'Sign up complete, proceed to login from here <a href="/login">Log in</a>'

@app.route('/exchange_rates')
def get_exchange_rates():
    try:
        response = requests.get(exchange_rate, params={'access_key': api_key})
        data = response.json()
        if response.status_code == 200:
            # Check if 'rates' key exists in the response data
            if 'rates' in data:
                exchange_rates = data['rates']

                # Sort exchange rate data by currency code
                sorted_exchange_rates = dict(sorted(exchange_rates.items()))

                # Format exchange rate data with currency code as key and exchange rate as value
                format = [{'currency_code': currency, 'exchange_rate': rate} for currency, rate in sorted_exchange_rates.items()]

                return render_template('exchange_rates.html', exchange_rates=format)
            else:
                return jsonify({"error": "No exchange rates data found"}), 404
        else:
            return jsonify({"error": "Failed to fetch exchange rates"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Search method for exchange rates, currently only usable in url with special characters
@app.route('/search')
def search_exchange_rate():
    currency_code = request.args.get('currency_code')
    if currency_code:
        try:
            response = requests.get(exchange_rate, params={'access_key': api_key})
            data = response.json()
            if response.status_code == 200:
                # Check if 'rates' key exists in the response data
                if 'rates' in data:
                    exchange_rates = data['rates']
                    if currency_code.upper() in exchange_rates:
                        searched_exchange_rate = exchange_rates[currency_code.upper()]
                        return jsonify({currency_code.upper(): searched_exchange_rate})
                    else:
                        return jsonify({"error": "Exchange rate not found for the specified currency code"}), 404
                else:
                    return jsonify({"error": "No exchange rates data found"}), 404
            else:
                return jsonify({"error": "Failed to fetch exchange rates"}), response.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Currency code parameter is required"}), 400
      
#Post functionality, will require user input
@app.route('/forum_post', methods=['GET', 'POST'])
@login_required
def forum_post():
    if request.method == 'POST':
        post_content = request.form['post_content']
        new_post = Post(content=post_content, author=current_user)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('display_post', post_id=new_post.id))
    try:
        posts = Post.query.all()
    except Exception as e:
        # Handle the exception (e.g., log the error, display a user-friendly message)
        posts = []
    return render_template('post.html', posts=posts)

#Reply to messages
@app.route('/reply/<int:post_id>', methods=['GET', 'POST'])
@login_required
def reply_to_post(post_id):
    if request.method == 'POST':
        # Handle POST request to submit a reply
        post = Post.query.get_or_404(post_id)  # Retrieve the post from the database
        reply_content = request.form['reply_content']
        new_reply = Reply(content=reply_content, post=post, author=current_user)  # Create a new reply associated with the post
        db.session.add(new_reply)  # Add the new reply to the database
        db.session.commit()  # Commit the transaction
        return redirect(url_for('display_post', post_id=post_id))  # Redirect to the post page after replying
    else:
        # Handle GET request to display the reply form
        post = Post.query.get_or_404(post_id)  # Retrieve the post from the database
        return render_template('reply.html', post=post, post_id=post_id)  # Render the reply form

#Shows information on specific posts, as well as replies to the post
@app.route('/post/<int:post_id>')
def display_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('display_post.html', post=post, post_id=post_id)

#Used to run the app, for demonstration purposes a db is created, in deployment a new db will not be created each time
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host = '0.0.0.0', port=81, debug=True)