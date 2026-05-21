import streamlit as st
import os
from google import genai
from google.genai import types
from gtts import gTTS
import io

# 1. Setup Page Configuration
st.set_page_config(
    page_title="Raw Image OCR to Audio", 
    page_icon="🔍", 
    layout="centered"
)

st.title("🔍 Raw Image OCR to Audio Converter")

# 2. Resilient API Key Validation
api_key = None

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif os.environ.get("GEMINI_API_KEY"):
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error(
        "❌ **No API Key Found!**\n\n"
        "Please add your `GEMINI_API_KEY` to your `.streamlit/secrets.toml` file or "
        "export it as an environment variable in your terminal window."
    )
    st.stop()

# Initialize the GenAI Client explicitly with the discovered key string
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"❌ Client Initialization Error: {e}")
    st.stop()

# 3. File Uploader UI
uploaded_file = st.file_uploader("Upload an Image (JPG, JPEG, PNG):", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Read file directly into bytes for uncompressed transfer
    bytes_data = uploaded_file.getvalue()
    
    # Display the uploaded image to the user
    st.image(bytes_data, caption="Uploaded Image", use_container_width=True)
    
    # 4. Pure OCR System Prompt (Forcing string-only plain prose response)
    pure_ocr_prompt = (
        "You are a strict, precise OCR engine. Your sole job is to extract and transcribe "
        "every piece of visible text inside this image word-for-word. "
        "Do not describe the scene, do not add commentary, do not format it as a poem, "
        "and do not explain anything. Provide only the raw extracted text as standard prose sentences. "
        "If absolutely no text is found, output exactly: [No text detected]"
    )
    
    # 5. Execution Button
    if st.button("🔍 Extract Text & Convert to Audio", type="primary"):
        detected_text = ""
        
        # Step A: Image Content Processing via Gemini
        with st.spinner("Processing image and performing OCR..."):
            try:
                # Wrap bytes into the expected SDK structural object type
                image_part = types.Part.from_bytes(
                    data=bytes_data,
                    mime_type=uploaded_file.type,
                )

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[image_part, pure_ocr_prompt]
                )
                detected_text = response.text.strip()
                
                # Display output string
                st.markdown("---")
                st.subheader("📝 Extracted Text:")
                st.info(detected_text)
                
            except Exception as e:
                st.error(
                    f"❌ **Google API Communication Failed!**\n\n"
                    f"Please confirm your key tier is valid and copied accurately.\n\n"
                    f"**Details:** {e}"
                )
                st.stop()
        
        # Step B: Audio Generation Stream
        if detected_text and detected_text != "[No text detected]":
            with st.spinner("Converting text sequence into speech..."):
                try:
                    # Feed raw string directly into the voice engine
                    tts = gTTS(text=detected_text, lang='en', slow=False)
                    
                    audio_buffer = io.BytesIO()
                    tts.write_to_fp(audio_buffer)
                    audio_buffer.seek(0)
                    
                    # Display the native HTML audio block
                    st.subheader("🔊 Audio Player")
                    st.audio(audio_buffer, format="audio/mp3")
                    st.success("🎉 Audio track compiled successfully! Press play to hear the text.")
                    
                except Exception as e:
                    st.error(f"Failed to compile text-to-speech audio stream: {e}")
        else:
            st.warning("No text components were extracted from this image to convert into audio.")