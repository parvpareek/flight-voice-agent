import streamlit as st
from datetime import datetime
from dateutil import parser as date_parser
import pandas as pd
import time

# Import project modules
import voice_utils
import db_utils
import gemini_utils

# --- Page Configuration ---
st.set_page_config(page_title="Flight Voice Agent", layout="wide")
st.title("✈️ Flight Booking Voice Assistant")
st.caption(f"Today is: {datetime.now().strftime('%A, %B %d, %Y')}")

# --- Initialization ---
# Configure Gemini API (run once)
try:
    gemini_utils.configure_gemini()
except ValueError as e:
    st.error(f"Configuration Error: {e}. Please set your GEMINI_API_KEY in the .env file.")
    st.stop() # Stop execution if API key is missing

# Check and populate database (run once per session start/if needed)
with st.spinner("Initializing database..."):
    db_utils.check_and_populate_db()

# --- Session State Management ---
if 'stage' not in st.session_state:
    st.session_state.stage = 'INIT'
    st.session_state.user_data = {
        "name": None,
        "dob": None,
        "date": None,
        "origin": None,
        "destination": None,
        "class": None
    }
    st.session_state.last_speech_input = ""
    st.session_state.error_message = None
    st.session_state.sql_query = None
    st.session_state.flight_results = None
    st.session_state.processing = False # Flag to prevent multiple concurrent actions

# --- Helper Functions ---
def update_stage(new_stage):
    st.session_state.stage = new_stage
    st.session_state.processing = False # Reset processing flag when stage changes
    st.rerun() # Rerun the script to reflect the new stage

def handle_reset():
    print("Resetting session state.")
    st.session_state.stage = 'INIT'
    st.session_state.user_data = {
        "name": None, "dob": None, "date": None,
        "origin": None, "destination": None, "class": None
    }
    st.session_state.last_speech_input = ""
    st.session_state.error_message = None
    st.session_state.sql_query = None
    st.session_state.flight_results = None
    st.session_state.processing = False
    voice_utils.speak("Okay, let's start over.")
    st.rerun()

# *** NEW Refactored Date Parsing Function ***
def try_parse_date_string(text_input):
    """
    Attempts to parse a string into a date and returns it in 'YYYY-MM-DD' format.
    Returns (date_string, None) on success, (None, error_message) on failure.
    Does NOT apply future/past validation here.
    """
    try:
        # Use dateutil parser for flexible date parsing
        dt = date_parser.parse(text_input)
        # Format as YYYY-MM-DD for consistency and SQL
        return dt.strftime('%Y-%m-%d'), None
    except (ValueError, OverflowError):
        return None, f"I couldn't understand '{text_input}' as a date format. Please try saying it again (e.g., 'April 15th', 'Tomorrow', 'May 10 1990')."
    except Exception as e: # Catch any other potential parsing errors
         return None, f"An unexpected error occurred while parsing the date: {e}. Please try again."


def parse_class(text_input):
    text_input = text_input.lower()
    if "economy" in text_input or "coach" in text_input:
        return "Economy"
    elif "business" in text_input:
        return "Business"
    elif "first" in text_input or "1st" in text_input:
        return "First"
    else:
        return None # Indicate not recognized

# --- UI Layout ---
col1, col2 = st.columns([1, 1]) # Adjust column ratios as needed

with col1:
    st.subheader("Conversation")
    status_placeholder = st.empty()
    start_button_placeholder = st.empty()
    reset_button_placeholder = st.button("🔁 Reset Conversation", on_click=handle_reset, key="reset_button_main")

    if st.session_state.last_speech_input:
         st.write(f"**You said:** *{st.session_state.last_speech_input}*")
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
        st.session_state.error_message = None # Clear error after displaying

with col2:
    st.subheader("Collected Information")
    st.json(st.session_state.user_data) # Display collected data clearly

st.divider()

st.subheader("Flight Results")
results_placeholder = st.empty()
if st.session_state.sql_query:
     with st.expander("Generated SQL Query"):
          st.code(st.session_state.sql_query, language='sql')


# --- Core Logic based on Stage ---

current_stage = st.session_state.stage
print(f"Current Stage: {current_stage}, Processing: {st.session_state.processing}")

# Disable buttons while processing speech or backend tasks
button_disabled = st.session_state.processing

# --- INIT Stage ---
if current_stage == 'INIT':
    status_placeholder.info("Click 'Start Booking' to begin.")
    start_button_placeholder.button("🎙️ Start Booking", on_click=update_stage, args=('ASK_DATE',), key="start_btn", disabled=button_disabled)

# --- Conversation Flow ---
elif not st.session_state.processing: # Only proceed if not already processing
    st.session_state.processing = True # Set processing flag

    if current_stage == 'ASK_DATE':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("What date would you like to depart?")
        update_stage('GET_DATE')

    # *** UPDATED GET_DATE Stage ***
    elif current_stage == 'GET_DATE':
        status_placeholder.warning("Listening for departure date...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                # Step 1: Try parsing the date string
                parsed_date_str, parse_error = try_parse_date_string(user_input)

                if parse_error:
                    # Parsing failed
                    st.session_state.error_message = parse_error
                    voice_utils.speak(parse_error)
                    update_stage('GET_DATE') # Ask again
                else:
                    # Step 2: Parsing succeeded, now validate for DEPARTURE context
                    departure_date = datetime.strptime(parsed_date_str, '%Y-%m-%d').date()
                    today_date = datetime.now().date()

                    if departure_date < today_date:
                        # Validation Failed: Departure date cannot be in the past
                        error_msg = "Departure date cannot be in the past. Please provide a date from today onwards."
                        st.session_state.error_message = error_msg
                        voice_utils.speak(error_msg)
                        update_stage('GET_DATE') # Ask again
                    else:
                        # Validation Succeeded
                        st.session_state.user_data['date'] = parsed_date_str
                        voice_utils.speak(f"Okay, departing on {departure_date.strftime('%B %d, %Y')}.")
                        update_stage('ASK_ORIGIN')
        else:
            # Handling listen timeout or error (message spoken in listen())
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_DATE') # Ask again

    elif current_stage == 'ASK_ORIGIN':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("Which city are you departing from?")
        update_stage('GET_ORIGIN')

    elif current_stage == 'GET_ORIGIN':
        status_placeholder.warning("Listening for origin city...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                st.session_state.user_data['origin'] = user_input.strip().title()
                voice_utils.speak(f"Got it, departing from {st.session_state.user_data['origin']}.")
                update_stage('ASK_DESTINATION')
        else:
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_ORIGIN')

    elif current_stage == 'ASK_DESTINATION':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("And where are you flying to?")
        update_stage('GET_DESTINATION')

    elif current_stage == 'GET_DESTINATION':
        status_placeholder.warning("Listening for destination city...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                st.session_state.user_data['destination'] = user_input.strip().title()
                voice_utils.speak(f"Okay, flying to {st.session_state.user_data['destination']}.")
                update_stage('ASK_CLASS')
        else:
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_DESTINATION')

    elif current_stage == 'ASK_CLASS':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("Which class would you like to fly? (Economy, Business, or First)?")
        update_stage('GET_CLASS')

    elif current_stage == 'GET_CLASS':
        status_placeholder.warning("Listening for flight class...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                parsed_class = parse_class(user_input)
                if parsed_class:
                    st.session_state.user_data['class'] = parsed_class
                    voice_utils.speak(f"Alright, {parsed_class} class.")
                    update_stage('ASK_NAME') # Move to ask name
                else:
                    st.session_state.error_message = "I didn't recognize that class. Please say Economy, Business, or First."
                    voice_utils.speak(st.session_state.error_message)
                    update_stage('GET_CLASS') # Ask again
        else:
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_CLASS')

    elif current_stage == 'ASK_NAME':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("What is the full name of the passenger?")
        update_stage('GET_NAME')

    elif current_stage == 'GET_NAME':
        status_placeholder.warning("Listening for passenger name...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                st.session_state.user_data['name'] = user_input.strip().title()
                voice_utils.speak(f"Thank you, {st.session_state.user_data['name']}.")
                update_stage('ASK_DOB')
        else:
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_NAME')

    elif current_stage == 'ASK_DOB':
        status_placeholder.info("Agent is speaking...")
        voice_utils.speak("And what is the passenger's date of birth?")
        update_stage('GET_DOB')

    # *** UPDATED GET_DOB Stage ***
    elif current_stage == 'GET_DOB':
        status_placeholder.warning("Listening for date of birth...")
        user_input = voice_utils.listen()
        st.session_state.last_speech_input = user_input
        if user_input:
            if "reset" in user_input: handle_reset()
            else:
                # Step 1: Try parsing the date string
                parsed_dob_str, parse_error = try_parse_date_string(user_input)

                if parse_error:
                    # Parsing failed
                    st.session_state.error_message = parse_error
                    voice_utils.speak(parse_error)
                    update_stage('GET_DOB') # Ask again
                else:
                    # Step 2: Parsing succeeded, now validate for DATE OF BIRTH context
                    dob_date = datetime.strptime(parsed_dob_str, '%Y-%m-%d').date()
                    today_date = datetime.now().date()

                    if dob_date >= today_date:
                        # Validation Failed: DOB cannot be today or in the future
                        error_msg = "Date of birth cannot be today or in the future. Please state the correct date of birth."
                        st.session_state.error_message = error_msg
                        voice_utils.speak(error_msg)
                        update_stage('GET_DOB') # Ask again
                    else:
                        # Validation Succeeded
                        st.session_state.user_data['dob'] = parsed_dob_str
                        voice_utils.speak(f"Got it, date of birth {dob_date.strftime('%B %d, %Y')}.")
                        update_stage('CONFIRM') # Move to confirmation
        else:
            st.session_state.error_message = "Listening failed. Please try again."
            update_stage('GET_DOB')

    elif current_stage == 'CONFIRM':
         status_placeholder.info("Agent is speaking...")
         # Check if all data needed for confirmation is present (robustness)
         required_keys = ['origin', 'destination', 'date', 'class', 'name', 'dob']
         if all(st.session_state.user_data.get(key) for key in required_keys):
            # Summarize details before querying
            summary = (
                f"Okay, let me confirm: You want to fly from {st.session_state.user_data['origin']} "
                f"to {st.session_state.user_data['destination']} on "
                f"{datetime.strptime(st.session_state.user_data['date'], '%Y-%m-%d').strftime('%B %d, %Y')} in "
                f"{st.session_state.user_data['class']} class. "
                f"The passenger's name is {st.session_state.user_data['name']} with date of birth "
                f"{datetime.strptime(st.session_state.user_data['dob'], '%Y-%m-%d').strftime('%B %d, %Y')}. "
                f"Is this correct?"
            )
            voice_utils.speak(summary)
            update_stage('GET_CONFIRMATION')
         else:
             missing_data = [key for key in required_keys if not st.session_state.user_data.get(key)]
             error_msg = f"Something went wrong, I seem to be missing some details ({', '.join(missing_data)}). Let's start over."
             st.session_state.error_message = error_msg
             voice_utils.speak(error_msg)
             handle_reset() # Reset if essential data is missing before confirmation

    elif current_stage == 'GET_CONFIRMATION':
         status_placeholder.warning("Listening for confirmation (Yes/No)...")
         user_input = voice_utils.listen()
         st.session_state.last_speech_input = user_input
         if user_input:
             if "reset" in user_input: handle_reset()
             elif "yes" in user_input or "correct" in user_input or "yeah" in user_input:
                 voice_utils.speak("Great! Searching for flights now.")
                 update_stage('QUERYING')
             elif "no" in user_input or "incorrect" in user_input:
                 voice_utils.speak("Okay, let's start over to correct the details.")
                 handle_reset() # Simple reset for now, could implement targeted correction
             else:
                 voice_utils.speak("Sorry, I didn't understand if that was a yes or no. Please say 'Yes' to confirm or 'No' to restart.")
                 update_stage('GET_CONFIRMATION') # Ask again
         else:
             st.session_state.error_message = "Listening failed. Please try again."
             update_stage('GET_CONFIRMATION')

    # --- Querying and Results ---
    elif current_stage == 'QUERYING':
        status_placeholder.info("Generating SQL query and searching database...")
        with st.spinner("Finding suitable flights..."):
            # Prepare details for Gemini (only relevant flight info)
            flight_details = {
                'origin': st.session_state.user_data['origin'],
                'destination': st.session_state.user_data['destination'],
                'date': st.session_state.user_data['date'],
                'class': st.session_state.user_data['class']
            }
            sql_query = gemini_utils.generate_sql_query(flight_details)
            st.session_state.sql_query = sql_query # Store for display

            if sql_query:
                results = db_utils.execute_query(sql_query)
                st.session_state.flight_results = results
                if results is not None: # Check if query execution was successful
                    update_stage('SHOW_RESULTS')
                else:
                    st.session_state.error_message = "There was an error querying the database."
                    voice_utils.speak(st.session_state.error_message)
                    update_stage('ERROR') # Go to error state
            else:
                st.session_state.error_message = "Could not generate the flight search query using the AI model."
                voice_utils.speak(st.session_state.error_message)
                update_stage('ERROR') # Go to error state

    elif current_stage == 'SHOW_RESULTS':
        status_placeholder.success("Found Flights!")
        results = st.session_state.flight_results
        if results:
            num_flights = len(results)
            voice_utils.speak(f"Okay, I found {num_flights} flight{'s' if num_flights != 1 else ''} matching your criteria. Please see the details on screen.")
            # Display results in a table/dataframe
            df = pd.DataFrame(results)
            # Format columns for better readability
            if 'price' in df.columns:
                 df['price'] = df['price'].map('₹{:.2f}'.format) # Example currency format
            if 'departure_datetime' in df.columns:
                 df['departure_datetime'] = pd.to_datetime(df['departure_datetime']).dt.strftime('%Y-%m-%d %H:%M')
            if 'arrival_datetime' in df.columns:
                 df['arrival_datetime'] = pd.to_datetime(df['arrival_datetime']).dt.strftime('%Y-%m-%d %H:%M')

            results_placeholder.dataframe(df)
        else:
            voice_utils.speak("Sorry, I couldn't find any flights matching your exact criteria for that date.")
            results_placeholder.warning("No flights found matching your criteria.")

        # Optionally offer to start a new search or end
        voice_utils.speak("Would you like to search again?")
        # For simplicity, we just end here. Button allows manual reset.
        update_stage('DONE')


    elif current_stage == 'ERROR':
        # Error message already set and potentially spoken
        status_placeholder.error(f"An error occurred: {st.session_state.error_message}")
        # Reset might be appropriate here or allow user to trigger reset
        st.session_state.processing = False # Allow reset button

    elif current_stage == 'DONE':
         status_placeholder.success("Process complete. You can start a new search using the 'Reset Conversation' button.")
         st.session_state.processing = False # Allow reset

else:
    # This block runs if st.session_state.processing is True, typically showing a spinner
    # or just preventing further actions until the current step completes.
    status_placeholder.info("Processing...") # General processing message


# Display final results if available (persists after stage moves to DONE)
if st.session_state.flight_results is not None and current_stage == 'DONE':
     if st.session_state.flight_results:
         df = pd.DataFrame(st.session_state.flight_results)
         # Re-apply formatting if needed when displaying persistent results
         if 'price' in df.columns: df['price'] = df['price'].map('₹{:.2f}'.format)
         if 'departure_datetime' in df.columns: df['departure_datetime'] = pd.to_datetime(df['departure_datetime']).dt.strftime('%Y-%m-%d %H:%M')
         if 'arrival_datetime' in df.columns: df['arrival_datetime'] = pd.to_datetime(df['arrival_datetime']).dt.strftime('%Y-%m-%d %H:%M')
         results_placeholder.dataframe(df)
     else:
          results_placeholder.warning("No flights found matching your criteria.")