# === app.py ===
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.pdfgen import canvas
import qrcode
import boto3
from botocore.exceptions import ClientError
import uuid
import os

# === Flask App Setup ===
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# === AWS DynamoDB Setup ===
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
users_table = dynamodb.Table('MovieMagic_Users')
movies_table = dynamodb.Table('MovieMagic_Movies')
bookings_table = dynamodb.Table('MovieMagic_Bookings')

# === Helper Functions ===

def load_movies():
    response = movies_table.scan()
    return response.get('Items', [])

def get_movie_by_id(movie_id):
    response = movies_table.get_item(Key={'id': movie_id})
    return response.get('Item')

def save_movie(movie):
    movies_table.put_item(Item=movie)

def generate_qr_code(data, filename):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    img.save(filename)

# === Routes ===

@app.route('/')
def landing():
    return render_template('welcome.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].lower()
        response = users_table.get_item(Key={'email': email})
        if 'Item' in response:
            flash("Account already exists.")
            return redirect(url_for('login'))

        users_table.put_item(Item={
            'email': email,
            'id': str(uuid.uuid4()),
            'name': request.form['name'],
            'password': generate_password_hash(request.form['password'])
        })
        flash("Registered successfully. Please login.")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid credentials.")
            return redirect(url_for('login'))
        session['user'] = user
        return redirect(url_for('home1'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out.")
    return redirect(url_for('login'))

@app.route('/home1')
def home1():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('home1.html', movies=load_movies())

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/select_datetime/<int:movie_id>')
def select_datetime(movie_id):
    movie = get_movie_by_id(movie_id)
    return render_template('select_datetime.html', movie=movie, now=datetime.now(), timedelta=timedelta)

@app.route('/show_times/<int:movie_id>', methods=['POST'])
def show_times(movie_id):
    selected_date = request.form.get('date')
    movie = get_movie_by_id(movie_id)
    return render_template('show_times.html', movie=movie, selected_date=selected_date, current_time=datetime.now(), datetime=datetime)

@app.route('/b1/<int:movie_id>')
def b1(movie_id):
    movie = get_movie_by_id(movie_id)
    selected_date = request.args.get('selected_date')
    selected_time = request.args.get('selected_time')
    if not selected_date or not selected_time:
        flash("Please select both date and time.")
        return redirect(url_for('select_datetime', movie_id=movie_id))

    key = f"{selected_date}_{selected_time}"
    booked_seats = movie.get('booked_seats', {}).get(key, [])
    return render_template('b1.html', movie=movie, selected_date=selected_date, selected_time=selected_time, booked_seats=booked_seats)

@app.route('/tickets', methods=['POST'])
def tickets():
    if 'user' not in session:
        return redirect(url_for('login'))

    selected_seats = request.form.get('seats')
    if not selected_seats:
        flash("Please select at least one seat.")
        return redirect(url_for('home1'))

    seat_list = selected_seats.split(',')
    movie_id = int(request.form['movie_id'])
    selected_date = request.form['selected_date']
    selected_time = request.form['selected_time']
    user_name = request.form['full_name']
    user_email = request.form['email']
    user_phone = request.form['phone']

    movie = get_movie_by_id(movie_id)
    key = f"{selected_date}_{selected_time}"
    if 'booked_seats' not in movie:
        movie['booked_seats'] = {}
    if key not in movie['booked_seats']:
        movie['booked_seats'][key] = []
    for seat in seat_list:
        if seat in movie['booked_seats'][key]:
            flash(f"Seat {seat} is already booked.")
            return redirect(url_for('b1', movie_id=movie_id, selected_date=selected_date, selected_time=selected_time))
    movie['booked_seats'][key].extend(seat_list)
    save_movie(movie)

    total_price = 0
    seat_prices = []
    for seat in seat_list:
        row = int(seat.split('-')[0])
        price = movie['price'] + (50 if 4 <= row <= 6 else 100 if row > 6 else 0)
        seat_prices.append(price)
    total_price = sum(seat_prices)

    booking_id = f"B{int(datetime.now().timestamp())}"
    booking = {
        'booking_id': booking_id,
        'user_id': session['user']['id'],
        'movie': movie['title'],
        'movie_id': movie['id'],
        'theater': movie['location'],
        'seats': seat_list,
        'seat_prices': seat_prices,
        'total_price': total_price,
        'date': selected_date,
        'time': selected_time,
        'name': user_name,
        'email': user_email,
        'phone': user_phone,
        'payment_method': 'UPI',
        'booking_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    bookings_table.put_item(Item=booking)

    qr_text = f"""🎟 Movie Magic Ticket 🎟
Name: {user_name}
Movie: {movie['title']}
Date: {selected_date}
Time: {selected_time}
Theater: {movie['location']}
Seats: {', '.join(seat_list)}
Booking ID: {booking_id}"""
    qr_filename = f"static/qr/booking_{booking_id}.png"
    generate_qr_code(qr_text, qr_filename)

    return render_template('ticket.html', booking=booking, movie=movie, qr_image=qr_filename)

@app.route('/user_bookings')
def user_bookings():
    if 'user' not in session:
        flash("Please log in.")
        return redirect(url_for('login'))
    response = bookings_table.scan()
    all_bookings = response.get('Items', [])
    user_bookings = [b for b in all_bookings if b['user_id'] == session['user']['id']]
    if not user_bookings:
        flash("No bookings found.")
    return render_template('user_bookings.html', bookings=user_bookings)

@app.route('/download_ticket/<booking_id>')
def download_pdf(booking_id):
    response = bookings_table.get_item(Key={'booking_id': booking_id})
    booking = response.get('Item')
    if not booking:
        return "Booking not found", 404
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "🎟 Movie Magic Ticket 🎟")
    p.setFont("Helvetica", 12)
    y = 770
    for label, value in [
        ("Name", booking['name']),
        ("Email", booking['email']),
        ("Movie", booking['movie']),
        ("Theater", booking['theater']),
        ("Date", booking['date']),
        ("Time", booking['time']),
        ("Payment", booking['payment_method']),
        ("Seats", ', '.join(booking['seats'])),
        ("Total Price", f"₹{booking['total_price']}"),
        ("Booking ID", booking['booking_id'])
    ]:
        p.drawString(100, y, f"{label}: {value}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"ticket_{booking['booking_id']}.pdf", mimetype='application/pdf')

# Run App
if __name__ == '__main__':
    app.run(debug=True)