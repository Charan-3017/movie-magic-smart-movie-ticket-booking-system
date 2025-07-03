from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import boto3
import uuid
import json
import os
from botocore.exceptions import ClientError

app = Flask(__name__)
# Use a static secret key
app.secret_key = 'your_static_secret_key_here'  # Replace with your own secret string

# AWS Configuration - read from environment variables for security
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Fix the SNS_TOPIC_ARN assignment - this was the main issue
# Instead of using os.environ.get with the ARN as the key, set it directly
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:557690577200:MovieTicketNotifications'

# Initialize AWS services with proper credentials handling
# On EC2, this will use the instance profile/role automatically
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
sns = boto3.client('sns', region_name=AWS_REGION)

# DynamoDB tables
USERS_TABLE_NAME = os.environ.get('USERS_TABLE_NAME', 'MovieMagic_Users')
BOOKINGS_TABLE_NAME = os.environ.get('BOOKINGS_TABLE_NAME', 'MovieMagic_Bookings')

users_table = dynamodb.Table(USERS_TABLE_NAME)
bookings_table = dynamodb.Table(BOOKINGS_TABLE_NAME)

# Authentication Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Get user from DynamoDB
            response = users_table.get_item(Key={'email': email})
            
            if 'Item' in response:
                user = response['Item']
                if check_password_hash(user['password'], password):
                    session['user'] = {
                        'id': user['id'],
                        'name': user['name'],
                        'email': user['email']
                    }
                    return redirect(url_for('home1'))
            
            flash('Invalid email or password', 'danger')
        except ClientError as e:
            print(f"Error accessing DynamoDB: {e.response['Error']['Message']}")
            flash('An error occurred. Please try again later.', 'danger')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        try:
            # Check if user already exists
            response = users_table.get_item(Key={'email': email})
            if 'Item' in response:
                flash('Email already registered!', 'danger')
                return redirect(url_for('signup'))
            
            # Create new user in DynamoDB
            user_id = str(uuid.uuid4())
            users_table.put_item(
                Item={
                    'id': user_id,
                    'name': name,
                    'email': email,
                    'password': password,
                    'created_at': datetime.now().isoformat()
                }
            )
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except ClientError as e:
            print(f"Error accessing DynamoDB: {e.response['Error']['Message']}")
            flash('An error occurred during registration. Please try again.', 'danger')
            
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out!', 'info')
    return redirect(url_for('index'))

# Application Routes
@app.route('/home1')
def home1():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('home1.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact_us')
def contact():
    return render_template('contact_us.html')

# Booking page route
@app.route('/b1', methods=['GET'], endpoint='b1')  # Add explicit endpoint
def booking_page():
    if 'user' not in session:
        return redirect(url_for('login'))

    return render_template('b1.html',
        movie=request.args.get('movie'),
        theater=request.args.get('theater'),
        address=request.args.get('address'),
        price=request.args.get('price')
    )

@app.route('/tickets', methods=['POST'])
def tickets():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    try:
        # Extract booking details from form
        movie_name = request.form.get('movie')
        booking_date = request.form.get('date')  
        show_time = request.form.get('time')
        theater_name = request.form.get('theater')
        theater_address = request.form.get('address')
        selected_seats = request.form.get('seats')  # Changed from selected_seats
        amount_paid = request.form.get('amount')    # Changed from total_price
        
        # Generate a unique booking ID
        booking_id = f"MVM-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        
        # Store booking in DynamoDB
        booking_item = {
            'booking_id': booking_id,
            'movie_name': movie_name,
            'date': booking_date,
            'time': show_time,
            'theater': theater_name,
            'address': theater_address,
            'booked_by': session['user']['email'],
            'user_name': session['user']['name'],
            'seats': selected_seats,
            'amount_paid': amount_paid,
            'booking_time': datetime.now().isoformat()
        }
        
        bookings_table.put_item(Item=booking_item)
        
        # Send email notification via SNS
        notification_sent = send_booking_confirmation(booking_item)
        if notification_sent:
            flash('Booking confirmation has been sent to your email!', 'success')
        
        # Pass the booking details to the tickets template
        return render_template('tickets.html', booking=booking_item)
        
    except Exception as e:
        print(f"Error processing booking: {str(e)}")
        flash('Error processing booking', 'danger')
        return redirect(url_for('home1'))

def send_booking_confirmation(booking):
    """Send booking confirmation email using SNS"""
    # Check if SNS_TOPIC_ARN is set
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN is not set. Unable to send notification.")
        return False
        
    try:
        # Format email content
        email_subject = f"MovieMagic Booking Confirmation - {booking['booking_id']}"
        
        email_message = f"""
        Hello {booking['user_name']},
        
        Your movie ticket booking is confirmed!
        
        Booking Details:
        ----------------
        Booking ID: {booking['booking_id']}
        Movie: {booking['movie_name']}
        Date: {booking['date']}
        Time: {booking['time']}
        Theater: {booking['theater']}
        Location: {booking['address']}
        Seats: {booking['seats']}
        Amount Paid: ₹{booking['amount_paid']}
        
        Please show this confirmation at the theater to collect your tickets.
        
        Thank you for choosing MovieMagic!
        """
        
        # User email
        user_email = booking['booked_by']
        
        print(f"Attempting to send notification to {user_email} via SNS topic {SNS_TOPIC_ARN}")
        
        # Send directly to the email using SNS
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=email_subject,
            Message=email_message,
            MessageAttributes={
                'email': {
                    'DataType': 'String',
                    'StringValue': user_email
                }
            }
        )
        
        print(f"SNS publish response: {response}")
        print(f"Booking confirmation sent to {user_email}")
        return True
        
    except Exception as e:
        print(f"Error sending booking confirmation: {str(e)}")
        return False

# Error handlers - uncommented for better error handling
# @app.errorhandler(404)
# def page_not_found(e):
#     return render_template('404.html'), 404

# @app.errorhandler(500)
# def server_error(e):
#     return render_template('500.html'), 500

if __name__ == '__main__':
    # Using Flask's built-in server as requested
    port = int(os.environ.get('PORT', 5000))
    # You can set debug=False in production
    app.run(host='0.0.0.0', port=port, debug=True)