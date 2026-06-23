import sqlite3

conn = sqlite3.connect('ecommerce.db')
c = conn.cursor()

# Create Products table
c.execute('''CREATE TABLE IF NOT EXISTS products
             (id INTEGER PRIMARY KEY, name TEXT, price REAL, category TEXT, description TEXT)''')

# Insert some mock data
c.execute("INSERT INTO products (name, price, category, description) VALUES ('Gaming Mouse', 45.0, 'Electronics', 'High precision sensor.')")
c.execute("INSERT INTO products (name, price, category, description) VALUES ('Mechanical Keyboard', 89.0, 'Electronics', 'RGB backlit, silent switches.')")
c.execute("INSERT INTO products (name, price, category, description) VALUES ('Coffee Mug', 12.0, 'Home', 'Ceramic, heat resistant.')")

conn.commit()
conn.close()