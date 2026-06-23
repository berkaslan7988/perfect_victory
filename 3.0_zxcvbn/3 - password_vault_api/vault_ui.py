import streamlit as st
import requests

# FastAPI Backend URL configuration
BACKEND_URL = "http://127.0.0.1:8000"

# Page configuration for a sleek cyber-security themed UI
st.set_page_config(
    page_title="CipherVault | Military-Grade Pass Manager",
    page_icon="🔐",
    layout="centered"
)

# Application Title and Styling
st.title("🔐 CipherVault")
st.subheader("DevSecOps Grade Password Management System")
st.write("Securely encrypting and storing credentials on-the-fly using AES-256.")
st.markdown("---")

# Create two distinct tabs for UI organization: Save vs Retrieve
tab1, tab2 = st.tabs(["📥 Save New Credential", "🔑 Retrieve Password"])

# --- TAB 1: SAVE CREDENTIALS ---
with tab1:
    st.header("Secure Vault Ingestion")
    
    # Form input fields with clean placeholders
    platform = st.text_input("Platform / Website Name", placeholder="e.g., netflix, github, binance").lower().strip()
    username = st.text_input("Username / Email Address", placeholder="e.g., alex@security.com").strip()
    password = st.text_input("Account Password", type="password", placeholder="••••••••••••")
    
    if st.button("Encrypt & Save to DB", type="primary"):
        if platform and username and password:
            # Construct the JSON payload to send to our FastAPI backend
            payload = {
                "platform": platform,
                "username": username,
                "password": password
            }
            
            try:
                # Send HTTP POST request to backend API
                response = requests.post(f"{BACKEND_URL}/secrets/save", json=payload)
                
                if response.status_code == 200:
                    st.success(f"✔️ AES-256 Encryption Successful! Credential stored for **{platform}**.")
                else:
                    st.error(f"❌ Backend Error: {response.json().get('detail')}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Connection Refused: Is your FastAPI server running on port 8000?")
        else:
            st.warning("⚠️ Please fill in all fields before injecting to database.")

# --- TAB 2: RETRIEVE CREDENTIALS ---
with tab2:
    st.header("Decryption & Retrieval Center")
    
    search_platform = st.text_input("Enter Target Platform to Decrypt", placeholder="e.g., netflix").lower().strip()
    
    if st.button("Fetch & Decrypt Ciphertext", type="secondary"):
        if search_platform:
            try:
                # Send HTTP GET request to backend API with dynamic URL path parameters
                response = requests.get(f"{BACKEND_URL}/secrets/retrieve/{search_platform}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Display retrieved data in clean UI cards
                    st.info(f"📍 **Platform Matched:** {data['platform'].upper()}")
                    st.success(f"👤 **Decrypted Username:** {data['username']}")
                    
                    # Using streamlit status block to show military-grade decryption note
                    with st.status("Performing Cryptographic Decryption...", expanded=True):
                        st.code(f"Decrypted Plaintext Password: {data['decrypted_password']}", language="text")
                        st.caption(f"Security Engine Log: {data['security_note']}")
                else:
                    st.error(f"🔍 Not Found: {response.json().get('detail')}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Connection Refused: Is your FastAPI server running on port 8000?")
        else:
            st.warning("⚠️ Please specify a platform to trigger cryptographic decryption.")