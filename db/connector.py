import sqlite3
import os

class DatabaseConnector:
    def __init__(self, db_config, logger):
        self.db_config = db_config
        self.logger = logger
        self.connection = None
    
    def connect(self):
        db_type = self.db_config.get('type', 'sqlite')
        
        if db_type == 'sqlite':
            db_path = self.db_config.get('path')
            
            if not os.path.exists(db_path):
                self.logger.log_system(f"Database not found at {db_path}, creating sample database")
                self._create_sample_database(db_path)
            
            self.connection = sqlite3.connect(db_path)
            self.connection.execute("PRAGMA query_only = ON")
            
            self.logger.log_system(f"Connected to SQLite database: {db_path}")
            
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        return self.connection
    
    def execute_query(self, query):
        if not self.connection:
            return {
                'status': 'error',
                'error': 'No database connection',
                'data': [],
                'columns': []
            }
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            
            self.logger.log_system(f"Query executed: {len(data)} rows returned")
            
            return {
                'status': 'success',
                'data': data,
                'columns': columns,
                'error': None
            }
            
        except Exception as e:
            self.logger.log_system(f"Query execution error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'data': [],
                'columns': []
            }
    
    def close(self):
        if self.connection:
            self.connection.close()
            self.logger.log_system("Database connection closed")
    
    def _create_sample_database(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                city TEXT,
                country TEXT,
                signup_date TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TEXT,
                total_amount REAL,
                status TEXT,
                salesman TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                price REAL,
                stock_quantity INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE order_items (
                item_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')
        
        customers_data = [
            (1, 'John Smith', 'john@example.com', 'New York', 'USA', '2024-01-15'),
            (2, 'Emma Wilson', 'emma@example.com', 'London', 'UK', '2024-02-20'),
            (3, 'Michael Brown', 'michael@example.com', 'Toronto', 'Canada', '2024-03-10'),
            (4, 'Sarah Davis', 'sarah@example.com', 'Sydney', 'Australia', '2024-04-05'),
            (5, 'James Johnson', 'james@example.com', 'Berlin', 'Germany', '2024-05-12')
        ]
        cursor.executemany('INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)', customers_data)
        
        orders_data = [
            (1, 1, '2024-06-01', 150.00, 'completed', 'Alice Thompson'),
            (2, 1, '2024-06-15', 200.00, 'completed', 'Bob Martinez'),
            (3, 2, '2024-06-10', 75.00, 'completed', 'Alice Thompson'),
            (4, 3, '2024-06-20', 300.00, 'pending', 'Carol Chen'),
            (5, 4, '2024-07-01', 125.00, 'completed', 'David Rodriguez'),
            (6, 5, '2024-07-05', 400.00, 'completed', 'Eve Johnson'),
            (7, 1, '2024-07-10', 180.00, 'pending', 'Bob Martinez')
        ]
        cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)', orders_data)
        
        products_data = [
            (1, 'Laptop', 'Electronics', 999.99, 50),
            (2, 'Mouse', 'Electronics', 25.99, 200),
            (3, 'Keyboard', 'Electronics', 75.99, 150),
            (4, 'Monitor', 'Electronics', 299.99, 80),
            (5, 'Desk Chair', 'Furniture', 199.99, 40)
        ]
        cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', products_data)
        
        order_items_data = [
            (1, 1, 2, 2, 25.99),
            (2, 1, 3, 1, 75.99),
            (3, 2, 4, 1, 299.99),
            (4, 3, 2, 3, 25.99),
            (5, 4, 1, 1, 999.99),
            (6, 5, 5, 1, 199.99),
            (7, 6, 1, 1, 999.99),
            (8, 7, 3, 2, 75.99)
        ]
        cursor.executemany('INSERT INTO order_items VALUES (?, ?, ?, ?, ?)', order_items_data)
        
        conn.commit()
        conn.close()
        
        self.logger.log_system(f"Sample database created at {db_path}")