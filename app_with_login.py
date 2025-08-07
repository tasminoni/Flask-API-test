from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config.from_object('config.Config')
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with posts
    posts = db.relationship('Post', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Post model
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Notification model
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    post = db.relationship('Post', backref='notifications')

# Create database tables
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    # Get user's posts
    user_posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', user=user, posts=user_posts)

@app.route('/posts')
def posts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get all posts with author information
    all_posts = Post.query.join(User).order_by(Post.created_at.desc()).all()
    return render_template('posts.html', posts=all_posts)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        if not title or not content:
            flash('Title and content are required', 'error')
            return render_template('create_post.html')
        
        # Create new post
        post = Post(title=title, content=content, user_id=session['user_id'])
        
        try:
            db.session.add(post)
            db.session.commit()
            flash('Post created successfully!', 'success')
            return redirect(url_for('posts'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to create post. Please try again.', 'error')
    
    return render_template('create_post.html')

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    user_notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', user=user, notifications=user_notifications)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/api/users')
def api_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = User.query.all()
    return jsonify({
        'users': [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat()
            }
            for user in users
        ]
    })

@app.route('/api/public/users')
def api_public_users():
    users = User.query.all()
    return jsonify({
        'users': [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat()
            }
            for user in users
        ]
    })

@app.route('/api/public/notifications/<username>')
def api_public_notifications(username):
    """Get notifications for a specific user"""
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    
    return jsonify({
        'notifications': [
            {
                'id': notif.id,
                'message': notif.message,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat(),
                'post_id': notif.post_id
            }
            for notif in notifications
        ]
    })

@app.route('/api/public/notifications_21201532/<username>')
def api_public_notifications_21201532(username):
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    
    return jsonify({
        'notifications': [
            {
                'id': notif.id,
                'message': notif.message,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat(),
                'post_id': notif.post_id
            }
            for notif in notifications
        ]
    })

@app.route('/api/public/notifications/<username>/mark-read', methods=['POST'])
def api_mark_notifications_read(username):
    """Mark all notifications as read for a user"""
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Mark all unread notifications as read
    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    for notif in unread_notifications:
        notif.is_read = True
    
    db.session.commit()
    
    return jsonify({'message': 'Notifications marked as read'})

@app.route('/api/public/notifications_21201532/<username>/mark-read', methods=['POST'])
def api_mark_notifications_read_21201532(username):
    """Mark all notifications as read for a user with custom endpoint"""
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Mark all unread notifications as read
    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    for notif in unread_notifications:
        notif.is_read = True
    
    db.session.commit()
    
    return jsonify({'message': 'Notifications marked as read'})

@app.route('/api/posts')
def api_posts():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    posts = Post.query.join(User).order_by(Post.created_at.desc()).all()
    return jsonify({
        'posts': [
            {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author': post.author.username,
                'created_at': post.created_at.isoformat()
            }
            for post in posts
        ]
    })

@app.route('/api/public/posts_21201532')
def api_public_posts():
   
    posts = Post.query.join(User).order_by(Post.created_at.desc()).all()
    return jsonify({
        'posts': [
            {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author': post.author.username,
                'created_at': post.created_at.isoformat()
            }
            for post in posts
        ]
    })

@app.route('/api/public/posts_21201532', methods=['GET', 'POST'])
def api_posts_21201532():
    
    if request.method == 'GET':
        # GET method - return all posts
        posts = Post.query.join(User).order_by(Post.created_at.desc()).all()
        return jsonify({
            'posts': [
                {
                    'id': post.id,
                    'title': post.title,
                    'content': post.content,
                    'author': post.author.username,
                    'created_at': post.created_at.isoformat()
                }
                for post in posts
            ]
        })
    
    elif request.method == 'POST':
        # POST method - create new post
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            title = data.get('title')
            content = data.get('content')
            username = data.get('username')
            
            if not title or not content or not username:
                return jsonify({'error': 'Title, content, and username are required'}), 400
            
            # Find the user by username
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Create new post
            post = Post(title=title, content=content, user_id=user.id)
            
            db.session.add(post)
            db.session.commit()
            
            # Create notifications for all other users
            all_users = User.query.filter(User.id != user.id).all()
            for other_user in all_users:
                notification = Notification(
                    user_id=other_user.id,
                    post_id=post.id,
                    message=f"New post by {user.username}: {title}"
                )
                db.session.add(notification)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Post created successfully',
                'post': {
                    'id': post.id,
                    'title': post.title,
                    'content': post.content,
                    'author': user.username,
                    'created_at': post.created_at.isoformat()
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': 'Failed to create post', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000) 