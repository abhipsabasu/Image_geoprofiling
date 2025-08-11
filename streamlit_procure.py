import streamlit as st
import streamlit.components.v1 as components
import os
import json
import pandas as pd
from streamlit_js_eval import streamlit_js_eval
from PIL import Image
import io
import base64
import time
from io import BytesIO
from io import StringIO
from github import Github
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
import uuid

country = 'India'
continent = 'Asia'

firebase_secrets = st.secrets["firebase"]
token = firebase_secrets["github_token"]
repo_name = firebase_secrets["github_repo"]
owner, repo_name = repo_name.split('/')
Maps_API_KEY = firebase_secrets["GOOGLE_MAPS_API_KEY"]
# Convert secrets to dict
cred_dict = {
    "type": firebase_secrets["type"],
    "project_id": firebase_secrets["project_id"],
    "private_key_id": firebase_secrets["private_key_id"],
    "private_key": firebase_secrets["private_key"].replace("\\n", "\n"),
    "client_email": firebase_secrets["client_email"],
    "client_id": firebase_secrets["client_id"],
    "auth_uri": firebase_secrets["auth_uri"],
    "token_uri": firebase_secrets["token_uri"],
    "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
    "universe_domain": firebase_secrets["universe_domain"]
}
cred = credentials.Certificate(json.loads(json.dumps(cred_dict)))
# Initialize Firebase (only if not already initialized)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

# ---- HTML for the Google Maps Component ----
# This HTML stores coordinates in localStorage on user interaction.
html_code = f"""
<!DOCTYPE html>
<html>
  <head>
    <title>Pick a Location</title>
    <script src="https://maps.googleapis.com/maps/api/js?key={Maps_API_KEY}&libraries=places"></script>
    <script>
      let map;
      let marker;
      
      function initMap() {{
        localStorage.removeItem('coords');
        const defaultLoc = {{ lat: 20.5937, lng: 78.9629 }};
        map = new google.maps.Map(document.getElementById("map"), {{
          zoom: 4,
          center: defaultLoc,
        }});

        marker = new google.maps.Marker({{
          position: defaultLoc,
          map: map,
          draggable: true
        }});

        const input = document.getElementById("pac-input");
        const searchBox = new google.maps.places.SearchBox(input);
        map.controls[google.maps.ControlPosition.TOP_LEFT].push(input);

        map.addListener("bounds_changed", () => {{
          searchBox.setBounds(map.getBounds());
        }});

        searchBox.addListener("places_changed", () => {{
          const places = searchBox.getPlaces();
          if (places.length === 0) return;
          const place = places[0];
          if (!place.geometry) return;

          marker.setPosition(place.geometry.location);
          map.panTo(place.geometry.location);
          map.setZoom(12);

          localStorage.setItem('coords', JSON.stringify({{
            lat: place.geometry.location.lat(),
            lng: place.geometry.location.lng()
          }}));
        }});

        map.addListener("click", (event) => {{
          marker.setPosition(event.latLng);
          localStorage.setItem('coords', JSON.stringify({{
            lat: event.latLng.lat(),
            lng: event.latLng.lng()
          }}));
        }});
        
        marker.addListener('dragend', (event) => {{
          localStorage.setItem('coords', JSON.stringify({{
            lat: event.latLng.lat(),
            lng: event.latLng.lng()
          }}));
        }});
      }}
    </script>
    <style>
      #pac-input {{
        margin: 10px;
        padding: 5px;
        width: 250px;
        z-index: 5;
      }}
    </style>
  </head>
  <body onload="initMap()">
    <input id="pac-input" type="text" placeholder="Search for a location" />
    <div id="map" style="height: 500px; width: 100%;"></div>
  </body>
</html>
"""

# ---- SESSION STATE ----
if "index" not in st.session_state:
    st.session_state.index = 0
    
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

# Correctly initialize the session state variable for coordinates
if 'coords' not in st.session_state:
    st.session_state.coords = None

def reset_selections():
    st.session_state.pop("q1", None)
    st.session_state.pop("q4", None)
    st.session_state.pop("coords", None)

# ---- UI ----
st.title(f"Image Collection from {country}")
st.markdown("""
<div style='text-align: justify;'>
We are collecting a dataset of images from **India** to assess the knowledge of modern-day AI technologies about surroundings within the country. With your consent, we request you to upload photos that you have taken but have **not shared online**.
<br><br>
**What kind of images to upload**:
<ul>
<li>The images can show a variety of environments such as:
    <ul>
        <li>Historical Monuments</li>
        <li>Residential buildings or houses</li>
        <li>Roads, Streets, or highways</li>
        <li>Markets, shops, post offices, courthouses, malls, etc.</li>
    </ul>
</li>
<li>Ensure the images are clear and well-lit.</li>
<li>Outdoor scenes are preferred.</li>
<li>Avoid uploading images with identifiable faces to protect privacy.</li>
</ul>
<br>
**Image Requirements**:
<ul>
<li>All images must be from **within India**.</li>
<li>Do **not** upload images already posted on social media.</li>
<li>Try to upload images that represent diverse locations or settings.</li>
</ul>
<br>
**What to do:**
<ol>
<li>**Upload 30 images**, one at a time.</li>
<li>For each image:
    <ul>
        <li>**Rate** how clearly the image suggests it was taken in India.</li>
        <li>**List the clues** that helped you make that judgment.</li>
        <li>**Click** "Submit and Next" to move to the next image.</li>
    </ul>
</li>
</ol>
You have *30* minutes to upload the photos and answer the questions surrounding them. After you upload the photo, wait for the photo to be visible on screen, then answer the questions.
</div>
""", unsafe_allow_html=True)

if not st.session_state.prolific_id:
    with st.form("prolific_form"):
        pid = st.text_input("Please enter your Prolific ID to begin:", max_chars=24)
        birth = st.text_input("Please enter your country of birth", max_chars=24)
        res = st.text_input("Please enter your country of residence", max_chars=24)
        privacy = st.radio(
            "Do you permit us to release your images publically as a dataset, or strictly use them for our research purpose?",
            options=["You can make them public", "Only use them for your research"],
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
else:
    # --- MAIN APP LOGIC (This section runs only after Prolific ID is submitted) ---
    if st.session_state.index < 30:
        uploaded_file = st.file_uploader(f"Upload image {st.session_state.index + 1}", type=["jpg", "jpeg", "png"], key=st.session_state.index)
        if uploaded_file:
            file_bytes = uploaded_file.read() 
            if len(file_bytes) < 100:
                st.error("⚠️ File seems too small. Possible read error.")
            encoded_content = base64.b64encode(file_bytes).decode("utf-8")
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True)
        
        about = st.text_area("What does the photo primarily depict (e.g., building, monument, market, etc)? In case there are multiple descriptors, write them in a comma-separated manner", height=100, key='q1')
        st.markdown(f"Where in {country} was the photo taken?")
        
        # Render the map component
        components.html(html_code, height=600, width=1200)

        # A button to trigger the coordinate retrieval. This is the most reliable way.
        if st.button("Read Coordinates from Map"):
            coords_str = streamlit_js_eval(
                js_expressions="localStorage.getItem('coords')",
                key=f"coords_read_button_{st.session_state.index}" # Use a unique key
            )
            if coords_str:
                coords_dict = json.loads(coords_str)
                st.session_state.coords = coords_dict
                st.success(f"✅ Coordinates captured: Latitude: {coords_dict['lat']:.6f}, Longitude: {coords_dict['lng']:.6f}")
            else:
                st.warning("⚠️ No coordinates found. Please click or search on the map first.")

        # Display the stored coordinates if they exist
        if st.session_state.coords:
            st.write(f"**Current Selected Location:** Latitude: {st.session_state.coords['lat']:.6f}, Longitude: {st.session_state.coords['lng']:.6f}")
        
        st.markdown(f"To what extent does this image contain visual cues (e.g., local architecture, language, or scenery) that identify it as being from {country}?")
        clue_text = None
        rating = st.radio(
            "Select a score:",
            options=["Choose an option", 0, 1, 2, 3],
            format_func=lambda x: f"{'No evidence at all' if x==0 else f'A few features that are shared by multiple countries within {continent}, but not fully specific to {country}' if x==2 else f'Enough evidence specific to {country}' if x==3 else f'There are visual indications like architectural style, vegetations, etc, but I do not know if they are specific to {country} or {continent}' if x==1 else ''}",
            index=st.session_state.q1_index,
            key='q2'
        )
        if rating in [2, 3]:
            clue_text = st.text_area("What visual clues or indicators helped you make this judgment?", height=100, key='q3')
        popularity = st.radio(
            "How would you rate the popularity of the location depicted in the photo you uploaded?",
            options=["Choose an option", 0, 1, 2],
            format_func=lambda x: f"{'The location depicts only a regular scene' if x==0 else f'The location may be locally popular, but not country-wide' if x==1 else f'The location is popular country-wide' if x==2 else 'Choose an option'}",
            index=st.session_state.q1_index,
            key='q5'
        )

        if st.button("Submit and Next"):
            if not uploaded_file or about in ['', None] or ((rating == 'Choose an option') or (rating in [2, 3] and clue_text in [None, ''])):
                st.error('Please answer all the questions and upload a file.')
            elif not st.session_state.coords:
                st.error('Please select a location on the map and click "Read Coordinates from Map" first.')
            else:
                # Submission logic...
                image_id = str(uuid.uuid4())
                file_name = f"{st.session_state.prolific_id}_{st.session_state.index}.png"
                file_path = f"{country}_images/{file_name}"
                api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}"

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                payload = {
                    "message": f"Upload {file_path}",
                    "content": encoded_content,
                    "branch": "main"
                }

                response = requests.put(api_url, headers=headers, json=payload)
                if response.status_code in [200, 201]:
                    st.success("✅ Image uploaded to GitHub successfully.")
                else:
                    st.error(f"❌ Upload failed: {response.status_code}")
                    st.text(response.json())
                
                st.session_state.responses.append({
                    "name": st.session_state.prolific_id,
                    "birth_country": st.session_state.birth_country,
                    "residence": st.session_state.residence,
                    "privacy": st.session_state.privacy,
                    "image_url": file_path,
                    "rating": rating,
                    "coords": st.session_state.coords,
                    "popularity": popularity,
                    "clues": clue_text,
                    "description": about,
                })
                reset_selections()
                
                st.session_state.index += 1
                st.session_state.q2_index = 0
                
                # Reset coords for the next image
                st.session_state.coords = None
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