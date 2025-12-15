import streamlit as st
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Page Configuration ---
st.set_page_config(
    page_title="Knowledge Base",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
<style>
    .main-header {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2.5rem;
        background: -webkit-linear-gradient(45deg, #4285F4, #9B72CB, #D96570);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .stChatMessage {
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    .stButton>button {
        background: linear-gradient(90deg, #4285F4 0%, #9B72CB 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3);
    }
    div[data-testid="stFileUploader"] section {
        border: 1px dashed #4285F4;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Management ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_files_cache" not in st.session_state:
    st.session_state.uploaded_files_cache = {}
if "current_file_uri" not in st.session_state:
    st.session_state.current_file_uri = None

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    api_key_input = st.text_input("Enter Gemini API Key", type="password", help="Get your key from Google AI Studio")
    
    # Priority: Input > Environment Variable
    api_key = None
    if api_key_input:
        api_key = api_key_input
    # else:
    #     api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        genai.configure(api_key=api_key)
        st.success("API Key configured!", icon="✅")
    else:
        st.warning("Please enter your API Key to proceed.", icon="⚠️")
        st.stop() # Stop if no key is present to prevent errors downstream

    # --- Mode Selection ---
    st.markdown("### 🤖 Chat Mode")
    chat_mode = st.radio("Context:", ["Single Document", "All Documents"], index=0)
    
    if chat_mode == "Single Document":
        # Tabs for Upload vs Select (Existing Logic)
        tab1, tab2 = st.tabs(["Upload New", "Select Existing"])
        
        with tab1:
            uploaded_file = st.file_uploader("Upload a document", type=['pdf', 'txt', 'md', 'csv', 'json', 'py', 'js', 'html'])
            if uploaded_file:
                file_key = f"{uploaded_file.name}-{uploaded_file.size}"
                if st.button("Upload to Gemini", key="upload_btn"):
                    with st.spinner(f"Uploading {uploaded_file.name}..."):
                        try:
                            temp_filename = f"temp_{uploaded_file.name}"
                            with open(temp_filename, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            gemini_file = genai.upload_file(path=temp_filename, display_name=uploaded_file.name)
                            
                            # Wait for processing
                            while gemini_file.state.name == "PROCESSING":
                                time.sleep(2)
                                gemini_file = genai.get_file(gemini_file.name)
                                
                            if gemini_file.state.name == "FAILED":
                                st.error("File processing failed.")
                            else:
                                st.session_state.current_file_uri = gemini_file
                                st.success(f"Uploaded & Ready: {uploaded_file.name}")
                                time.sleep(1)
                                st.rerun()
                                
                            if os.path.exists(temp_filename):
                                os.remove(temp_filename)
                        except Exception as e:
                            st.error(f"Upload failed: {str(e)}")

        with tab2:
            if st.button("Refresh File List"):
                st.rerun()
                
            try:
                # List files from Gemini API
                remote_files = list(genai.list_files())
                if not remote_files:
                    st.info("No files found on Gemini server.")
                else:
                    file_options = {f.display_name or f.name: f for f in remote_files}
                    selected_file_name = st.selectbox("Select a file", options=list(file_options.keys()))
                    
                    if st.button("Load Selected File"):
                        st.session_state.current_file_uri = file_options[selected_file_name]
                        st.success(f"Loaded: {selected_file_name}")
                        st.rerun()
            except Exception as e:
                st.error(f"Could not list files: {str(e)}")

        if st.session_state.current_file_uri:
            st.markdown("---")
            st.info(f"**Active File:**\n{st.session_state.current_file_uri.display_name}")
            
    else: # All Documents
        st.info("📚 **Global Context**: The model will read ALL uploaded files to answer your questions.")
        st.markdown("*(Note: This uses the large context window of Gemini 2.5)*")
        if st.button("Refresh Available Files"):
            st.rerun()

    st.markdown("---")
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# --- Main Interface ---
st.markdown('<div class="main-header">Knowledge Base 🤖</div>', unsafe_allow_html=True)

if not api_key:
    st.info("👋 Welcome! Please configure your Gemini API Key in the sidebar to get started.")
    st.stop()

# Context Check
active_files = []
if chat_mode == "Single Document":
    if not st.session_state.current_file_uri:
        st.info("👆 Please upload or select a document in the sidebar to start chatting.")
        st.stop()
    active_files = [st.session_state.current_file_uri]
else:
    # All Documents Mode
    try:
        active_files = list(genai.list_files())
        if not active_files:
            st.warning("⚠️ No files found on the server. Please switch to 'Single Document' to upload some files first.")
            st.stop()
    except Exception as e:
        st.error(f"Failed to fetch files: {str(e)}")
        st.stop()

# Display Chat History
for role, message in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(message)

# Chat Input
if prompt := st.chat_input("Ask something about your document(s)..."):
    # User Message
    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Assistant Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")
        
        try:
            # Initialize model
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Context Preparation
            # We pass the list of file objects (or URIs) directly to the model
            # Note: active_files contains the file usage objects from list_files or upload
            
            system_prompt = """
            INSTRUCTIONS:
            1. You are a Knowledge Base Assistant.
            2. Answer the user's question STRICTLY based on the provided documents.
            3. Do NOT use outside knowledge or general training data.
            4. If the answer cannot be found in the documents, politely state that the information is not present in the files.
            5. Cite the document name if possible.
            """
            
            context_prompt = ""
            for role, msg in st.session_state.chat_history[:-1]:
                context_prompt += f"{role.upper()}: {msg}\n"
            
            final_prompt = f"{system_prompt}\n\n{context_prompt}\nUSER: {prompt}\nASSISTANT:"
            
            # Construct content list: [file1, file2, ..., prompt]
            request_content = active_files + [final_prompt]
            
            response = model.generate_content(request_content)
            
            full_response = response.text
            message_placeholder.markdown(full_response)
            st.session_state.chat_history.append(("assistant", full_response))
            
        except Exception as e:
            message_placeholder.error(f"An error occurred: {str(e)}")

