from flask import Flask, render_template, request, redirect, url_for, session
import random
import boto3
import uuid

app = Flask(__name__)
app.secret_key = '9a4f90b2b6df594f2e16f6c1f3d9e0ab0cd431c0f0176a2544e740c94cb75a0e'

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

users_table = dynamodb.Table('MovieMagic_Users')
bookings_table = dynamodb.Table('MovieMagic_Bookings')

SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:841162686181:MovieShows'  # Replace this

# Movie list
movies = [
    {"id": 2, "name": "Avengers: Endgame", "time": "6:00 PM", "price": 150, "rating": 4.8, "image": "avengers.jpeg"},
    {"id": 7, "name": "Leo", "time": "3:30 PM", "price": 180, "rating": 4.7, "image": "leo.jpeg"},
    {"id": 10, "name": "RRR", "time": "1:00 PM", "price": 160, "rating": 4.6, "image": "rrr.jpeg"},
    {"id": 4, "name": "Inception", "time": "5:00 PM", "price": 200, "rating": 4.9, "image": "inception.jpeg"},
    {"id": 9, "name": "Pushpa", "time": "11:00 AM", "price": 140, "rating": 4.5, "image": "pushpa.jpeg"},
    {"id": 1, "name": "Animal", "time": "8:00 PM", "price": 190, "rating": 4.4, "image": "animal.jpeg"},
    {"id": 6, "name": "KGF", "time": "2:30 PM", "price": 170, "rating": 4.6, "image": "kgf.jpeg"},
    {"id": 8, "name": "Pathaan", "time": "10:00 AM", "price": 160, "rating": 4.3, "image": "pathaan.jpeg"},
    {"id": 3, "name": "mi", "time": "4:30 PM", "price": 130, "rating": 4.2, "image": "mi.jpeg"},
    {"id": 5, "name": "Jawan", "time": "7:00 PM", "price": 175, "rating": 4.4, "image": "jawan.jpeg"},
]

@app.route('/')
def index():
    return render_template('welcome.html')  # ✅ Renders the welcome page

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        response = users_table.get_item(Key={'Email': email})
        user = response.get('Item')
        if user and user['Password'] == password:
            session['user'] = email
            if remember:
                session.permanent = True
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        response = users_table.get_item(Key={'Email': email})
        if 'Item' in response:
            return render_template('register.html', error='User already exists')
        users_table.put_item(Item={'Email': email, 'Password': password, 'Phone': phone})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('home1.html')

@app.route('/movies')
def movies_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    query = request.args.get('q', '')
    filtered = [m for m in movies if query.lower() in m['name'].lower()]
    return render_template('movies.html', movies=filtered)

@app.route('/book/<int:id>', methods=['GET', 'POST'])
def book_ticket(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    movie = next((m for m in movies if m['id'] == id), None)
    if not movie:
        return "Movie not found.", 404

    if request.method == 'POST':
        name = request.form.get('name')
        tickets = request.form.get('tickets')
        if not name or not tickets:
            return render_template("book.html", movie=movie, error="Please fill all fields")
        try:
            tickets = int(tickets)
            booking_id = f"BK{random.randint(1000,9999)}"
            bookings_table.put_item(Item={
                'Bookingid': booking_id,
                'Email': session['user'],
                'Movie': movie['name'],
                'User': name,
                'Tickets': tickets
            })
            return render_template('success.html', movie=movie, name=name, tickets=tickets)
        except ValueError:
            return render_template("book.html", movie=movie, error="Invalid ticket number")
    return render_template('book.html', movie=movie)

@app.route('/admin')
def admin():
    response = bookings_table.scan()
    all_bookings = response.get('Items', [])
    return render_template('admin.html', bookings=all_bookings)

@app.route('/contact')
def contact():
    return render_template('contact_us.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('email')
        response = users_table.get_item(Key={'Email': email})
        user = response.get('Item')
        if user:
            code = random.randint(1000, 9999)
            session['reset_code'] = code
            session['reset_email'] = email
            print(f"Verification code sent to {email}: {code}")
            return redirect(url_for('verify_code'))
        else:
            return render_template('forgot_password.html', error="Email not registered.")
    return render_template('forgot_password.html')

@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered = request.form.get('code')
        if 'reset_code' in session and entered == str(session['reset_code']):
            return redirect(url_for('reset_password'))
        else:
            return render_template('verify_code.html', error="Invalid code. Try again.")
    return render_template('verify_code.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_pass = request.form.get('password')
        email = session.get('reset_email')
        users_table.update_item(
            Key={'Email': email},
            UpdateExpression='SET Password = :p',
            ExpressionAttributeValues={':p': new_pass}
        )
        session.pop('reset_email', None)
        session.pop('reset_code', None)
        return redirect(url_for('login'))
    return render_template('reset_password.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)