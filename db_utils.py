import sqlite3
import random
from datetime import datetime, timedelta
import os

DB_NAME = "flights.db"

# --- Sample Data ---
AIRLINES = ["Indigo", "Air India", "SpiceJet", "Vistara", "GoAir", "Emirates", "British Airways", "Lufthansa"]
CITIES = ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Ahmedabad", "Pune", "London", "New York", "Dubai", "Singapore"]
CLASSES = ["Economy", "Business", "First"]

def connect_db():
    """Connects to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

def create_table(conn):
    """Creates the flights table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flights (
            flight_id TEXT PRIMARY KEY,
            airline TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            departure_datetime TEXT NOT NULL, -- Store as ISO 8601 String
            arrival_datetime TEXT NOT NULL,   -- Store as ISO 8601 String
            travel_class TEXT NOT NULL,
            price REAL NOT NULL,
            seats_available INTEGER NOT NULL
        )
    ''')
    conn.commit()

def generate_random_flights(conn, num_flights=100):
    """Generates random flight data for the current month and inserts it."""
    cursor = conn.cursor()
    # Clear existing data for idempotency if regenerating
    cursor.execute("DELETE FROM flights")
    conn.commit()

    flights = []
    current_time = datetime.now()
    start_date = current_time.replace(day=1)
    # Ensure end_date doesn't go beyond the actual end of the month
    try:
        end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
    except ValueError: # Handles December
        end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)


    for i in range(num_flights):
        airline = random.choice(AIRLINES)
        origin = random.choice(CITIES)
        destination = random.choice([c for c in CITIES if c != origin]) # Ensure destination != origin
        travel_class = random.choice(CLASSES)

        # Generate random date within the current month
        random_day = random.randint(start_date.day, end_date.day)
        departure_date = start_date.replace(day=random_day)

        # Generate random time
        departure_hour = random.randint(0, 23)
        departure_minute = random.choice([0, 15, 30, 45])
        departure_dt = departure_date.replace(hour=departure_hour, minute=departure_minute, second=0, microsecond=0)

        # Calculate arrival time (add random duration)
        flight_duration_hours = random.uniform(1.5, 15.0) # Duration between 1.5 and 15 hours
        arrival_dt = departure_dt + timedelta(hours=flight_duration_hours)

        # Generate flight ID
        flight_num = random.randint(100, 999)
        # Basic airline code extraction (can be improved)
        airline_code = "".join([word[0] for word in airline.split() if word])[:2].upper()
        flight_id = f"{airline_code}{flight_num}-{travel_class[0]}" # e.g., BA234-E

        # Generate price based on class
        base_price = random.uniform(3000, 25000)
        if travel_class == "Business":
            price = base_price * random.uniform(1.8, 3.0)
        elif travel_class == "First":
            price = base_price * random.uniform(3.5, 6.0)
        else: # Economy
            price = base_price
        price = round(price, 2)

        seats = random.randint(5, 50)

        flights.append((
            flight_id + str(i), # Ensure uniqueness for demo
            airline,
            origin,
            destination,
            departure_dt.isoformat(sep=' '), # Format for SQLite TEXT
            arrival_dt.isoformat(sep=' '),   # Format for SQLite TEXT
            travel_class,
            price,
            seats
        ))

    try:
        cursor.executemany('''
            INSERT INTO flights (flight_id, airline, origin, destination, departure_datetime, arrival_datetime, travel_class, price, seats_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', flights)
        conn.commit()
        print(f"Successfully inserted {len(flights)} flights for {current_time.strftime('%B %Y')}.")
    except sqlite3.Error as e:
        print(f"Database error during insertion: {e}")
        conn.rollback() # Rollback changes on error


def check_and_populate_db():
    """Checks if DB exists and has data for the current month, populates if needed."""
    regenerate = False
    if not os.path.exists(DB_NAME):
        regenerate = True
        print(f"Database '{DB_NAME}' not found. Creating and populating...")
    else:
        # Optional: Check if data is for the current month (more complex check needed)
        # For simplicity, we'll just check if the table is empty
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM flights")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
           regenerate = True
           print("Flights table is empty. Populating...")
        # Add more sophisticated check here if needed based on dates in DB

    if regenerate:
        conn = connect_db()
        create_table(conn)
        generate_random_flights(conn)
        conn.close()
    else:
        print(f"Database '{DB_NAME}' found and appears populated.")


def execute_query(query, params=()):
    """Executes a given SQL query and returns results."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        # Convert Row objects to simple dictionaries for easier handling/display
        results_list = [dict(row) for row in results]
        return results_list
    except sqlite3.Error as e:
        print(f"Error executing query: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        return None # Indicate error
    finally:
        conn.close()