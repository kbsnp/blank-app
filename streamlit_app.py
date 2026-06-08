import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from google import genai
from gtts import gTTS
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder
import os
import time
import json
import io

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# --- Page Setup ---
st.set_page_config(page_title="Streamlit Mic Audiobook Engine", page_icon="📖", layout="wide")
st.title("🎙️ Frontend Mic Recording Audio Engine")
st.write("Upload or snap a page image, then use the browser microphone button below to control playback or query Gemini.")

# --- Initialize Gemini Client ---
@st.cache_resource
def get_gemini_client():
    try:
        return genai.Client()
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client: {e}")
        return None

client = get_gemini_client()

# --- Initialize Audio Engine ---
if not pygame.mixer.get_init():
    pygame.mixer.init()

# --- Initialize Session States ---
if 'playback_status' not in st.session_state:
    st.session_state.playback_status = "idle"  # idle, ready, playing, paused
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'command_log' not in st.session_state:
    st.session_state.command_log = []
if 'previous_source' not in st.session_state:
    st.session_state.previous_source = None

# --- Core Processing Functions ---

def extract_text(image):
    if not client: return "Gemini Client error."
    try:
        prompt = "Transcribe all text from this page exactly. No intro/outro commentary."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
        return response.text
    except Exception as e: return f"Error: {e}"

def generate_audio_file(text, filename="book_page.mp3"):
    try:
        if os.path.exists(filename):
            pygame.mixer.music.unload()
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        return filename
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def speak_agent_response(text):
    try:
        agent_audio = "agent_response.mp3"
        generate_audio_file(text, filename=agent_audio)
        agent_sound = pygame.mixer.Sound(agent_audio)
        agent_sound.play()
        while pygame.mixer.get_busy():
            time.sleep(0.1)
    except Exception as e:
        st.session_state.command_log.append(f"Audio Error: {e}")

def ask_gemini_agent(question, context):
    if not client: return "Offline."
    try:
        prompt = f"Context from book page:\n{context}\n\nUser Question/Statement: {question}\n\nRespond concisely as a voice assistant. Do not use markdown tags."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt])
        return response.text
    except Exception as e: return f"Error: {e}"

def parse_intent_with_gemini(raw_input):
    if not client: return "question"
    try:
        prompt = f"Analyze this audiobook voice command: \"{raw_input}\". Categorize into exactly one: 'play', 'pause', 'resume', 'stop', or 'question'. Return a raw JSON block with the key 'intent'."
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt],
            config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        return data.get("intent", "question")
    except:
        return "question"

def process_backend_audio(audio_bytes):
    """Processes the in-memory wav data bytes extracted directly from the frontend microphone widget."""
    rec = sr.Recognizer()
    audio_file = io.BytesIO(audio_bytes)
    
    with sr.AudioFile(audio_file) as source:
        audio_data = rec.record(source)
    try:
        text = rec.recognize_google(audio_data).lower().strip()
        return text
    except Exception:
        return None

def process_command(raw_input):
    if not raw_input:
        return

    st.session_state.command_log.append(f"Heard: '{raw_input}'")
    
    if any(word in raw_input for word in ["play", "start", "begin", "read"]):
        if os.path.exists("book_page.mp3"):
            pygame.mixer.music.load("book_page.mp3")
            pygame.mixer.music.play()
            st.session_state.playback_status = "playing"
            
    elif "pause" in raw_input:
        pygame.mixer.music.pause()
        st.session_state.playback_status = "paused"
        
    elif "resume" in raw_input:
        pygame.mixer.music.unpause()
        st.session_state.playback_status = "playing"
        
    elif "stop" in raw_input:
        pygame.mixer.music.stop()
        st.session_state.playback_status = "ready"
        
    else:
        intent = parse_intent_with_gemini(raw_input)
        if intent in ["play", "pause", "resume", "stop"]:
            if intent == "play": 
                pygame.mixer.music.load("book_page.mp3")
                pygame.mixer.music.play()
            elif intent == "pause": pygame.mixer.music.pause()
            elif intent == "resume": pygame.mixer.music.unpause()
            elif intent == "stop": pygame.mixer.music.stop()
            st.session_state.playback_status = intent if intent != "stop" else "ready"
        else:
            st.session_state.command_log.append("🤖 Routing question to Gemini...")
            agent_reply = ask_gemini_agent(raw_input, st.session_state.extracted_text)
            st.session_state.command_log.append(f"🤖 Agent: {agent_reply}")
            speak_agent_response(agent_reply)

# --- UI Sidebar Layout ---
st.sidebar.subheader("📥 Target Document Input")
input_method = st.sidebar.radio("Choose Input Method:", ["Upload File", "Take a Photo with Camera"])

target_image = None
current_source_key = None

if input_method == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload Page Image", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        target_image = Image.open(uploaded_file)
        current_source_key = f"upload_{uploaded_file.name}"
else:
    camera_file = st.sidebar.camera_input("Snap a picture of the page")
    if camera_file:
        target_image = Image.open(camera_file)
        # Generate a unique key using the current timestamp to detect a fresh snap
        current_source_key = f"camera_{camera_file.size}"

# --- Handle Image processing & resets if the document changes ---
if target_image:
    st.sidebar.image(target_image, caption="Target Page", use_column_width=True)
    
    # If a brand new image is uploaded or snapped, clear old states and process it
    if st.session_state.previous_source != current_source_key:
        st.session_state.previous_source = current_source_key
        with st.spinner("Extracting text contents..."):
            st.session_state.extracted_text = extract_text(target_image)
            generate_audio_file(st.session_state.extracted_text)
            st.session_state.playback_status = "ready"
            st.rerun()

# --- Main App Dashboards ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Extracted Page Text")
    if st.session_state.extracted_text:
        st.text_area("Content:", st.session_state.extracted_text, height=450, disabled=True)
    else:
        st.info("Upload an image or take a snapshot in the sidebar to populate data matrices.")

with col2:
    st.subheader("⚙️ System Processing Console")
    
    state_mapping = {
        "idle": "Awaiting Document",
        "ready": "Ready to Stream",
        "playing": "Reading Book Aloud",
        "paused": "Audio Paused"
    }
    st.metric(label="Current Audio State", value=state_mapping.get(st.session_state.playback_status, "Unknown"))
    
    st.write("---")
    
    if st.session_state.playback_status != "idle":
        st.write("Click **Start Recording**, speak your command or question, then click **Stop**.")
        
        # --- Native Browser Button Click Interceptor ---
        if st.query_params.get("action") == ["stop_audio"]:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                st.session_state.playback_status = "paused"
                st.session_state.command_log.append("🔇 Mic opened. Audio auto-paused.")
            st.query_params.clear()
            st.rerun()

        # HTML/JS bridge code to detect frontend mic interactions
        components.html("""
            <script>
                const parentDoc = window.parent.document;
                const checkExist = setInterval(function() {
                    const buttons = parentDoc.querySelectorAll('button');
                    buttons.forEach(btn => {
                        if (btn.innerText.includes("Start Recording") && !btn.dataset.hooked) {
                            btn.dataset.hooked = "true";
                            btn.addEventListener('click', function() {
                                const url = new URL(window.parent.location.href);
                                url.searchParams.set('action', 'stop_audio');
                                window.parent.location.href = url.href;
                            });
                        }
                    });
                }, 500);
            </script>
        """, height=0)

        # Native Browser-safe HTML5 Microphone Widget Component
        audio_response = mic_recorder(
            start_prompt="🎤 Start Recording",
            stop_prompt="🛑 Stop & Process",
            key=f"mic_{st.session_state.playback_status}", 
            format="wav"
        )

        if audio_response and "bytes" in audio_response:
            raw_audio_bytes = audio_response["bytes"]
            
            last_processed_sig = f"sig_{len(raw_audio_bytes)}"
            if last_processed_sig not in st.session_state:
                st.session_state[last_processed_sig] = True
                
                with st.spinner("Processing speech stream inside backend..."):
                    transcribed_text = process_backend_audio(raw_audio_bytes)
                    if transcribed_text:
                        process_command(transcribed_text)
                        st.rerun()
                    else:
                        st.error("Could not capture clear speech vectors. Click start and try again.")
    else:
        st.info("Provide a book page using the options on the left to unlock the voice operations panel.")
        
    st.write("---")
    st.write("**🗂️ Front-End Voice Log Display:**")
    if st.session_state.command_log:
        for log in reversed(st.session_state.command_log[-5:]):
            st.caption(log)
    else:
        st.caption("No operations logged yet.")