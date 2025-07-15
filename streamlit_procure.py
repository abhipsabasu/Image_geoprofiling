import streamlit as st
import os
import json
import tempfile
import pandas as pd
from PIL import Image
from io import BytesIO
from io import StringIO
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore, storage
import requests
import uuid

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


# ---- SESSION STATE ----
if "index" not in st.session_state:
    st.session_state.index = 0
    
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

def reset_selections():
    st.session_state.pop("q1", None)

# ---- UI ----
st.title("Image Collection from India")
st.markdown("""
We are collecting a dataset of images from **India** to assess the knowledge of modern-day AI technologies about Indian surroundings. With your consent, we request you to upload images that you have clicked, but *not posted online*.

The images can depict historical sites, common buildings and houses, roads, highways, post offices, shopping malls, courthouses, markets, shops, etc.

Thus, they can depict any scene (preferrably outdoor), which is clear, properly lighted.

In case of privacy concerns, kindly refrain from uploading images with recognizable faces.

You are requested to upload **30** images one by one, and answer a few questions regarding the same.

NOTE: The images should only be from **India**, and not uploaded on any social media.

For each image:
- Rate how strongly the image supports the stated country.
- Mention any clues you used to make your judgment.

After uploading and answering the questions corresponding to an image, click on *Submit and Next* for the next image upload.
""")
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

if "birth_country" not in st.session_state:
    st.session_state.birth_country = None

if "residence" not in st.session_state:
    st.session_state.residence = None

if "privacy" not in st.session_state:
    st.session_state.privacy = None

if not st.session_state.prolific_id:
    with st.form("prolific_form"):
        st.write("## Please enter your Prolific ID to begin:")
        pid = st.text_input("Prolific ID", max_chars=24)
        st.write("## Please enter your country of birth")
        birth = st.text_input("Birth country", max_chars=24)
        st.write("## Please enter your country of residence")
        res = st.text_input("Residence country", max_chars=24)
        privacy = st.radio(
            "Do you permit us to release your images publically as a dataset, or strictly use them for our research purpose?",
            options=["Make them public", "Only use them for your research"],
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            if pid.strip() and birth.strip() and res.strip():
                st.session_state.prolific_id = pid.strip()
                st.session_state.birth_country = birth.strip()
                st.session_state.residence = res.strip()
                st.session_state.privacy = privacy
                st.success("Thank you! You may now begin.")
                st.rerun()
            else:
                st.error("Please enter a valid Prolific ID, birth country or residence country.")
    st.stop()  # Stop further execution until ID is entered

# --- SESSION STATE ---

if "responses" not in st.session_state:
    st.session_state.responses = []

if 'q1_index' not in st.session_state:
    st.session_state.q1_index = 0

# Current image
if st.session_state.index < 30:
    uploaded_file = st.file_uploader(f"Upload image {st.session_state.index + 1}", type=["jpg", "jpeg", "png"], key=st.session_state.index)
    if uploaded_file:
        st.image(uploaded_file, use_container_width=True)
    
    about = st.text_area("What does the image primarily depict? (e.g., building, monument, market, etc)", height=100, key='q1')
    st.markdown(f"Given that this image is from **India**, how much visual evidence (e.g., specific architecture, writing, landmarks, vegetations, etc) is present in the image to indicate the same?")
    
    rating = st.radio(
        "Select a score:",
        options=["Choose an option", 0, 1, 2, 3],
        format_func=lambda x: f"{x} . {'No evidence at all' if x==0 else 'A few evidence that may indicate the continent of the mentioned country, but not the country itself' if x==2 else 'Enough evidence to indicate the country' if x==3 else 'There are visual indications like architectural style, vegetations, etc, but I do not know if they indicate the mentioned country' if x==1 else ''}",
        index=st.session_state.q1_index,
        key='q2'
    )
    if rating in [2, 3]:
        clue_text = st.text_area("What visual clues or indicators helped you make this judgment?", height=100, key='q3')
    if st.button("Submit and Next"):
        if ((rating == 'Choose an option') or (rating in [2, 3] and clue_text in [None, ''])):
            st.error('Answer the questions')
        else:
        # Save response
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(uploaded_file.read())
            temp_file.flush()

            # Upload image to Firebase
            image_id = str(uuid.uuid4())
            blob = bucket.blob(f"procured_images_India/{st.session_state.prolific_id}/{image_id}_{uploaded_file.name}")
            blob.upload_from_filename(temp_file.name)
            blob.make_public()
            image_url = blob.public_url
            st.session_state.responses.append({
                "name": st.session_state.prolific_id,
                "birth_country": st.session_state.birth_country,
                "residence": st.session_state.residence,
                "privacy": st.session_state.privacy,
                "image_url": image_url,
                "rating": rating,
                "clues": clue_text,
                "description": about,
            })
            reset_selections()
            
            st.session_state.index += 1
            print(st.session_state.index)
            st.session_state.q2_index = 0
            
            st.rerun()
else:
    doc_ref = db.collection("Image_procurement").document(st.session_state.prolific_id)
    doc_ref.set({
        "prolific_id": st.session_state.prolific_id,
        "birth_country": st.session_state.birth_country,
        "country_of_residence": st.session_state.residence,
        "privacy": st.session_state.privacy,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "responses": st.session_state.responses
    })
    st.session_state.submitted_all = True
    st.success("Survey complete. Thank you!")
    st.write("✅ Survey complete! Thank you.")
