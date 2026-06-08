import streamlit as st
from PIL import Image
from google import genai
from gtts import gTTS
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder
import os
import json
import io

# --- Page Setup ---
st.set_page_config(page_title="Cloud Audiobook Engine", page_icon="📖", layout="wide")
st.title("🎙️ Cloud-Safe Audio Engine")
st.write("Upload a page image, then use your browser microphone to query Gemini or interact.")

# --- Initialize Gemini Client ---
@st.cache_resource
def get_gemini_client():
    try:
        return genai.Client()
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client: {e}")
        return None

client = get_gemini_client()

# --- Initialize Session States ---
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'agent_reply_text' not in st.session_state:
    st.session_state.agent_reply_text = ""
if 'command_log' not in st.session_state:
    st.session_state.command_log = []

# --- Core Processing Functions ---

def extract_text(image):
    if not client: return "Gemini Client error."
    try:
        prompt = "Transcribe all text from this page exactly. No intro/outro commentary."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
        return response.text
    except Exception as e: return f"Error: {e}"

def generate_audio_bytes(text):
    """Generates audio completely in-memory without needing file writing or pygame players"""
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def ask_gemini_agent(question, context):
    if not client: return "Offline."
    try:
        prompt = f"Context from book page:\n{context}\n\nUser Question/Statement: {question}\n\nRespond concisely as a voice assistant. Do not use markdown tags."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt])
        return response.text
    except Exception as e: return f"Error: {e}"

def process_backend_audio(audio_bytes):
    """Processes the in-memory wav data bytes extracted directly from the frontend microphone widget."""
    rec = sr.Recognizer()
    audio_file = io.BytesIO(audio_bytes)
    
    with sr.AudioFile(audio_file) as source:
        audio_data = rec.record(source)
    try:
        # Works perfectly in cloud because it reads from data bytes, not a hardware microphone jack
        text = rec.recognize_google(audio_data).lower().strip()
        return text
    except Exception:
        return None

# --- UI Sidebar Layout ---
uploaded_file = st.sidebar.file_uploader("Upload Page Image", type=["jpg", "png", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.sidebar.image(img, caption="Target Page", use_column_width=True)
    if not st.session_state.extracted_text:
        with st.spinner("Extracting text contents..."):
            st.session_state.extracted_text = extract_text(img)
            st.rerun()

# --- Main App Dashboards ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Extracted Page Text")
    if st.session_state.extracted_text:
        st.text_area("Content:", st.session_state.extracted_text, height=300, disabled=True)
        
        st.write("### 🔊 Listen to full page")
        page_audio = generate_audio_bytes(st.session_state.extracted_text)
        if page_audio:
            st.audio(page_audio, format="audio/mp3")
    else:
        st.info("Upload an image in the sidebar to populate data matrices.")

with col2:
    st.subheader("⚙️ Voice Control Console")
    
    if st.session_state.extracted_text:
        st.write("Click **Start Recording**, ask a question about the text, then click **Stop**.")
        
        # Native Browser HTML5 Microphone Component
        audio_response = mic_recorder(
            start_prompt="🎤 Start Recording",
            stop_prompt="🛑 Stop & Process",
            key="cloud_mic", 
            format="wav"
        )

        if audio_response and "bytes" in audio_response:
            raw_audio_bytes = audio_response["bytes"]
            
            last_processed_sig = f"sig_{len(raw_audio_bytes)}"
            if last_processed_sig not in st.session_state:
                st.session_state[last_processed_sig] = True
                
                with st.spinner("Transcribing your voice..."):
                    transcribed_text = process_backend_audio(raw_audio_bytes)
                    if transcribed_text:
                        st.session_state.command_log.append(f"Heard: '{transcribed_text}'")
                        
                        # Process response
                        reply = ask_gemini_agent(transcribed_text, st.session_state.extracted_text)
                        st.session_state.agent_reply_text = reply
                        st.session_state.command_log.append(f"🤖 Agent: {reply}")
                        st.rerun()
                    else:
                        st.error("Could not capture clear speech. Please try again.")
                        
        if st.session_state.agent_reply_text:
            st.info(f"🤖 **Gemini Assistant:** {st.session_state.agent_reply_text}")
            agent_audio = generate_audio_bytes(st.session_state.agent_reply_text)
            if agent_audio:
                st.audio(agent_audio, format="audio/mp3", autoplay=True)
    else:
        st.info("Upload a book page to unlock voice operations.")
        
    st.write("---")
    st.write("**🗂️ Voice History Log:**")
    if st.session_state.command_log:
        for log in reversed(st.session_state.command_log[-5:]):
            st.caption(log)