import speech_recognition as sr
import pyttsx3
import time

# --- Initialize TTS Engine ---
try:
    tts_engine = pyttsx3.init()
    # Optional: Adjust voice properties if needed
    # voices = tts_engine.getProperty('voices')
    # tts_engine.setProperty('voice', voices[1].id) # Example: change voice
    # tts_engine.setProperty('rate', 180) # Example: adjust speed
except Exception as e:
    print(f"Error initializing TTS engine: {e}")
    tts_engine = None

# --- Initialize Recognizer ---
recognizer = sr.Recognizer()
microphone = sr.Microphone()

# Adjust for ambient noise once at the start
# Consider doing this calibration within the Streamlit app if noise levels vary
# with microphone as source:
#     print("Adjusting for ambient noise, please wait...")
#     recognizer.adjust_for_ambient_noise(source, duration=1)
#     print("Ready to listen.")


def speak(text):
    """Converts text to speech."""
    print(f"Agent: {text}") # Also print to console for debugging
    if tts_engine:
        try:
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")
    else:
        print("TTS Engine not available.")


def listen(prompt="Listening...", timeout_s=10, phrase_time_limit_s=5):
    """Listens for user input using the microphone."""
    print(prompt) # Indicate listening state
    with microphone as source:
        # Adjust for ambient noise dynamically (optional, can slow down)
        # recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout_s, phrase_time_limit=phrase_time_limit_s)
        except sr.WaitTimeoutError:
            print("No speech detected within timeout.")
            return None # Indicate timeout

    try:
        print("Recognizing...")
        # Use Google Web Speech API
        text = recognizer.recognize_google(audio)
        print(f"User said: {text}")
        return text.lower() # Return lowercase for easier processing
    except sr.UnknownValueError:
        print("Speech Recognition could not understand audio.")
        speak("Sorry, I didn't catch that. Could you please repeat?")
        return None # Indicate recognition failure
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        speak("Sorry, I'm having trouble connecting to the speech service right now.")
        return None # Indicate service error

# Example usage (for testing)
if __name__ == '__main__':
    speak("Hello! How can I help you find a flight today?")
    time.sleep(0.5)
    user_input = listen()
    if user_input:
        speak(f"You said: {user_input}")
    else:
        speak("I didn't get a response.")