from flask import Flask, render_template, request, redirect, url_for, session 
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24)) 

def get_db():
    conn = sqlite3.connect('ecommerce.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def products():
    db = get_db()
    items = db.execute('SELECT * FROM products').fetchall()
    return render_template('products.html', items=items)

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    
    if isinstance(cart, list):
        new_cart = {}
        for item_id in cart:
            str_id = str(item_id)
            new_cart[str_id] = new_cart.get(str_id, 0) + 1
        session['cart'] = new_cart
        cart = new_cart

    db = get_db()
    cart_items = []
    total = 0
    
    for id, qty in cart.items():
        item = db.execute('SELECT * FROM products WHERE id = ?', (int(id),)).fetchone()
        if item:
            item_dict = dict(item)
            item_dict['quantity'] = qty
            item_dict['subtotal'] = item['price'] * qty
            cart_items.append(item_dict)
            total += item_dict['subtotal']
            
    return render_template('cart.html', items=cart_items, total=total)

@app.route('/cart/remove/<int:id>')
def remove_from_cart(id):
    cart = session.get('cart', {})
    str_id = str(id)
    if str_id in cart:
        cart[str_id] -= 1
        if cart[str_id] <= 0:
            del cart[str_id]
    session['cart'] = cart
    return redirect(url_for('cart'))

def admin_required(f):
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return "You don't have access to this page!"
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    items = db.execute('SELECT * FROM products').fetchall()
    return render_template('admin.html', items=items)

@app.route('/admin/delete/<int:id>')
@admin_required
def delete_product(id):
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add', methods=('GET', 'POST'))
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        cat = request.form['category'] 
        desc = request.form['description']
        
        db = get_db()
        db.execute('INSERT INTO products (name, price, category, description) VALUES (?, ?, ?, ?)',
                   (name, price, cat, desc))
        db.commit()
        return redirect(url_for('admin'))
    return render_template('add_product.html')

@app.route('/add/<int:id>')
def add_to_cart(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {}) 
    
    if isinstance(cart, list):
        new_cart = {}
        for item_id in cart:
            new_cart[str(item_id)] = new_cart.get(str(item_id), 0) + 1
        cart = new_cart

    str_id = str(id)
    cart[str_id] = cart.get(str_id, 0) + 1 
    session['cart'] = cart

    return redirect(url_for('cart'))

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password']) 
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            db.commit()
            return redirect(url_for('login'))
        except:
            return "This username is already exists!"
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if 'user_id' in session:
        return redirect(url_for('products'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin'] 
            return redirect(url_for('products'))
        return "Wrong username or password!"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('products'))

if __name__ == '__main__':
    app.run(debug=True)