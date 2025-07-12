import streamlit as st
import os
import pandas as pd
from PIL import Image
from io import BytesIO
from io import StringIO
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

firebase_secrets = st.secrets["firebase"]

# Convert secrets to dict
cred_dict = {
    "type": firebase_secrets["type"],
    "project_id": firebase_secrets["project_id"],
    "private_key_id": firebase_secrets["private_key_id"],
    "private_key": firebase_secrets["private_key"].replace("\\n", "\n"),  # Fix multi-line key
    "client_email": firebase_secrets["client_email"],
    "client_id": firebase_secrets["client_id"],
    "auth_uri": firebase_secrets["auth_uri"],
    "token_uri": firebase_secrets["token_uri"],
    "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
    "universe_domain": firebase_secrets["universe_domain"],
}
cred = credentials.Certificate(json.loads(json.dumps(cred_dict)))
# Initialize Firebase (only if not already initialized)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

GITHUB = "https://raw.githubusercontent.com/abhipsabasu/Image_geoprofiling/main/"

# ---- CONFIG ----
@st.cache_data
def load_data():
    response_wiki = requests.get(GITHUB + 'wikimedia_geo_images_hs.csv')
    df = pd.read_csv(StringIO(response_wiki.text))
    df = df.sample(frac=1, replace=False)
    # IMAGE_FOLDER = "images"  # Folder with images
    image_files = list(df['file_path']) # sorted([f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    countries = list(df['country'])
    return image_files, countries

@st.cache_data
def get_responses():
    return []

image_files, countries = load_data()
responses = get_responses()

# CSV_PATH = "responses.csv"  # File to save responses

# ---- LOAD IMAGES ----


# ---- SESSION STATE ----
if "index" not in st.session_state:
    st.session_state.index = 0
    
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

# ---- UI ----
st.title("Image Origin Survey")
st.markdown("""
Please help us evaluate how well visual cues in each image indicate the mentioned country of origin.
For each image:
- Rate how strongly the image supports the stated country.
- Mention any clues you used to make your judgment.
""")
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

if not st.session_state.prolific_id:
    with st.form("prolific_form"):
        st.write("## Please enter your Prolific ID to begin:")
        pid = st.text_input("Prolific ID", max_chars=24)
        submitted = st.form_submit_button("Submit")
        if submitted:
            if pid.strip():
                st.session_state.prolific_id = pid.strip()
                st.success("Thank you! You may now begin the survey.")
                st.rerun()
            else:
                st.error("Please enter a valid Prolific ID.")
    st.stop()  # Stop further execution until ID is entered

# --- SESSION STATE ---

# Current image
if st.session_state.index < len(image_files):
    
    image_path = image_files[st.session_state.index]
    image_name = GITHUB + image_path
    # print(st.session_state.index, 'hello', image_name)
    # image_path = os.path.join(IMAGE_FOLDER, image_name)
    country = countries[st.session_state.index]

    # st.image(Image.open(image_path), caption=f"Image: {image_name}", use_container_width=True)
    try:
        img_data = requests.get(image_name).content
        image = Image.open(BytesIO(img_data))
        st.image(image, use_container_width=True)
    except:
        st.error("Could not load image.")
    
    st.markdown(f"Given that this image is from {country}, how much visual evidence (e.g., specific architecture, writing, landmarks, vegetations, etc), do you see that supports this?")
    rating = st.radio(
        "Select a score:",
        options=["Choose an option", -1, 0, 1, 2],
        format_func=lambda x: f"{x} . {'Enough evidence, but wrong country mentioned' if x==-1 else 'No evidence at all' if x==0 else 'A few evidence that might indicate the continent, but not the country' if x==1 else 'Enough features to indicate the country' if x==2 else ''}",
        # index=1
    )
    net_rating = None
    clue_text = None
    if rating in [0, 1]:
        st.markdown(f"If you are not confident, you can search about the image on the internet (using textual descriptions, reverse image search, etc), and respond accordingly")
        net_rating = st.radio(
            "Select a score:",
            options=["Choose an option", -1, 0, 1, 2],
            format_func=lambda x: f"{x} . {'No I could not find out even from the internet' if x==0 else 'I could only determine the continent' if x==1 else 'The mentioned country matches with the true country as per the internet' if x==-1 else 'The mentioned country does not match the true country as per the internet' if x==2 else ''}"
        )
    if rating in [-1, 1, 2]:
        clue_text = st.text_area("What visual clues or indicators helped you make this judgment?", height=100)
    st.markdown(f"To what extent are you aware of the country {country}?")
    awareness = st.radio(
        "Select a score:",
        options=["Choose an option", 0, 1, 2],
        format_func=lambda x: f"{x} . {'I am not aware about the country at all' if x==0 else 'I have some knowledge about the visuals present in the country' if x==1 else 'I am quite confident about the visuals present in the country' if x==2 else ''}",
        # index=1
    )
    if st.button("Submit and Next"):
        if awareness == 'Choose an option':
            st.error('Answer the questions')
        elif ((rating == 'Choose an option') or (rating in [0, 1] and net_rating == 'Choose an option') or (rating in [-1, 1, 2] and clue_text in [None, ''])):
            st.error('Answer the questions')
        else:
        # Save response
            responses.append({
                "name": st.session_state.user_name,
                "image": image_name,
                "rating": rating,
                "clues": clue_text,
                "net_rating": net_rating,
                "awareness": awareness
            })

            # if os.path.exists(CSV_PATH):
            #     df.to_csv(CSV_PATH, mode="a", header=False, index=False)
            # else:
            #     df.to_csv(CSV_PATH, index=False)

            # st.success("Response saved.")
            st.session_state.index += 1
            print(st.session_state.index)
            st.rerun()
else:
    doc_ref = db.collection("Image_geolocalization").document(st.session_state.prolific_id)
    doc_ref.set({
        "prolific_id": st.session_state.prolific_id,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "responses": responses
    })
    st.session_state.submitted_all = True
    st.success("Survey complete. Thank you!")
    st.write("✅ Survey complete! Thank you.")
