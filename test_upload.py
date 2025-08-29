import streamlit as st

st.title("File Upload Test")

st.write("This is a simple test to see if file upload works.")

# Test file uploader
uploaded_file = st.file_uploader("Choose a file", type=["jpg", "jpeg", "png", "txt"])

if uploaded_file is not None:
    st.write(f"File uploaded: {uploaded_file.name}")
    st.write(f"File size: {uploaded_file.size} bytes")
    
    # Try to read the file
    try:
        file_bytes = uploaded_file.read()
        st.write(f"File read successfully, length: {len(file_bytes)} bytes")
        
        # Reset file pointer for further use
        uploaded_file.seek(0)
        
    except Exception as e:
        st.error(f"Error reading file: {e}")
else:
    st.write("No file uploaded yet")

# Test button
if st.button("Test Button"):
    st.write("Button works!")

# Show session state
st.write("Session state:", st.session_state)
