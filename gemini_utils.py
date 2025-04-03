import google.generativeai as genai
import os
from dotenv import load_dotenv
import re # For cleaning up the response

def configure_gemini():
    """Configures the Gemini API with the key from environment variables."""
    load_dotenv() # Load variables from .env file
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables or .env file.")
    genai.configure(api_key=api_key)
    print("Gemini API configured.")

def generate_sql_query(user_details):
    """
    Generates an SQLite query using Gemini based on user flight requirements.

    Args:
        user_details (dict): A dictionary containing keys like
                             'origin', 'destination', 'date', 'class'.
                             Date should ideally be in 'YYYY-MM-DD' format.

    Returns:
        str: The generated SQL query string, or None if generation fails.
    """
    if not user_details.get('origin') or not user_details.get('destination') or \
       not user_details.get('date') or not user_details.get('class'):
        print("Error: Missing required details for SQL generation.")
        return None

    # Define the database schema clearly for the model
    schema_description = """
    You are interacting with an SQLite database containing flight information in a table named 'flights'.
    The table has the following columns:
    - flight_id (TEXT, Primary Key): Unique identifier for the flight (e.g., 'BA234-E').
    - airline (TEXT): Name of the airline (e.g., 'British Airways').
    - origin (TEXT): Departure city/airport (e.g., 'London Heathrow').
    - destination (TEXT): Arrival city/airport (e.g., 'New York JFK').
    - departure_datetime (TEXT): Departure date and time in 'YYYY-MM-DD HH:MM:SS' format.
    - arrival_datetime (TEXT): Arrival date and time in 'YYYY-MM-DD HH:MM:SS' format.
    - travel_class (TEXT): Cabin class ('Economy', 'Business', 'First').
    - price (REAL): Price of the flight ticket.
    - seats_available (INTEGER): Number of seats remaining.
    """

    # Construct the prompt
    prompt = f"""
    {schema_description}

    User wants to find flights based on the following criteria:
    - Origin: {user_details['origin']}
    - Destination: {user_details['destination']}
    - Departure Date: {user_details['date']} (This is the specific date, format YYYY-MM-DD)
    - Travel Class: {user_details['class']}

    Generate an SQLite SELECT query to retrieve all matching flights from the 'flights' table.
    The query should filter based on:
    1. Exact match for 'origin' (case-insensitive).
    2. Exact match for 'destination' (case-insensitive).
    3. The departure date must match the given date. Use the `date()` function on the 'departure_datetime' column for comparison (e.g., `date(departure_datetime) = '{user_details['date']}'`).
    4. Exact match for 'travel_class' (case-insensitive).

    Return ONLY the SQL query string, without any explanation, comments, markdown formatting (like ```sql), or introductory text.
    Example format: SELECT * FROM flights WHERE ...;
    """

    try:
        # Select the appropriate model
        # Use a model known for code/SQL generation if available, otherwise a general text model
        model = genai.GenerativeModel('gemini-2.0-flash') # Or a newer/more specific model if applicable

        print("\n--- Sending Prompt to Gemini ---")
        # print(prompt) # Uncomment to debug the prompt
        print("-------------------------------\n")

        response = model.generate_content(prompt)

        print("\n--- Received Response from Gemini ---")
        print(response.text)
        print("------------------------------------\n")

        # Clean the response to extract only the SQL query
        sql_query = response.text.strip()
        # Remove potential markdown code blocks
        sql_query = re.sub(r'```sql\n(.*)\n```', r'\1', sql_query, flags=re.DOTALL | re.IGNORECASE)
        sql_query = re.sub(r'```(.*)```', r'\1', sql_query, flags=re.DOTALL | re.IGNORECASE)
        # Remove leading/trailing whitespace and semicolons (optional, execute might handle it)
        sql_query = sql_query.strip().rstrip(';')

        # Basic validation (check if it looks like a SELECT query)
        if not sql_query.upper().startswith("SELECT"):
            print(f"Error: Gemini response doesn't look like a valid SELECT query: {sql_query}")
            return None

        print(f"Generated SQL Query: {sql_query}")
        return sql_query

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

# Example usage (for testing)
if __name__ == '__main__':
    configure_gemini()
    test_details = {
        'origin': 'Mumbai',
        'destination': 'Delhi',
        'date': '2025-04-15', # Replace with a date within the current month for testing
        'class': 'Economy'
    }
    query = generate_sql_query(test_details)
    if query:
        print(f"\nSuccessfully generated query:\n{query}")
    else:
        print("\nFailed to generate query.")