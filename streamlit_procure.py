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
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

country = 'India'
continent = 'Asia'

firebase_secrets = st.secrets["firebase"]
token = firebase_secrets["github_token"]
repo_name = firebase_secrets["github_repo"]
owner, repo_name = repo_name.split('/')

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

# ---- SESSION STATE ----
if "index" not in st.session_state:
    st.session_state.index = 0
    st.session_state.responses = []
    
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

if 'coords' not in st.session_state:
    st.session_state.coords = None

if 'q1_index' not in st.session_state:
    st.session_state.q1_index = 0

def reset_selections():
    st.session_state.pop("q1", None)
    st.session_state.pop("q4", None)
    st.session_state.pop("coords", None)
    st.session_state.q1_index = 0

def geocode_location(location_text):
    """
    Convert location text to coordinates using Nominatim geocoding service
    """
    try:
        # Add "India" to the search query to improve accuracy for Indian locations
        search_query = f"{location_text}, India"
        
        # Initialize geocoder
        geolocator = Nominatim(user_agent="streamlit_app")
        
        # Geocode the location
        location = geolocator.geocode(search_query, timeout=10)
        
        if location:
            return {
                "lat": location.latitude,
                "lng": location.longitude,
                "name": location.address,
                "success": True
            }
        else:
            return {
                "lat": None,
                "lng": None,
                "name": None,
                "success": False,
                "error": "Location not found"
            }
            
    except GeocoderTimedOut:
        return {
            "lat": None,
            "lng": None,
            "name": None,
            "success": False,
            "error": "Geocoding service timed out. Please try again."
        }
    except GeocoderUnavailable:
        return {
            "lat": None,
            "lng": None,
            "name": None,
            "success": False,
            "error": "Geocoding service unavailable. Please try again later."
        }
    except Exception as e:
        return {
            "lat": None,
            "lng": None,
            "name": None,
            "success": False,
            "error": f"Error: {str(e)}"
        }

# ---- UI ----
st.title(f"Image Collection from {country}")
st.markdown(f"""
We are collecting a dataset of images from **{country}** to assess the knowledge of modern-day AI technologies about surroundings within the country. With your consent, we request you to upload photos that you have taken but have **not shared online**.

Following are the instructions for the same.

**What kind of images to upload**:

- Photos should depict a variety of surroundings within {country}.
- Avoid uploading duplicate/near-duplicate photos that you have already uploaded.
- Ensure the images are clear and well-lit.
- Outdoor scenes are preferred.
- Avoid uploading images with identifiable faces and license plates to protect privacy. 

**Image Requirements**:

-   All images must be from **within {country}**.
-   Do **not** upload images already posted on social media.
-   Try to upload images that represent diverse locations or settings.

**What to do:**
1.  **Upload 10 images**, one at a time.
2.  For each image:
    -   **Rate** how clearly the photo suggests it was taken in India.
    -   **Select the location** where the photo was taken using the search box or map.
    -   **List the clues** that helped you make that judgment.
    -   **Rate the photo** on the popularity of the location captured.
    -   **Click** "Submit and Next" to move to the next image.

You have *20* minutes to upload the photos and answer the questions surrounding them. After you upload the photo, wait for the photo to be visible on screen, then answer the questions.
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
    if st.session_state.index < 10:
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
        st.markdown("**Use the search box or map below to select the location where the photo was taken:**")
        
        # Warning that coordinates are required
        if not st.session_state.coords:
            st.error("🚨 **COORDINATES REQUIRED:** You must select a location to proceed with the survey!")
        else:
            st.success("✅ **Location selected successfully!**")
            
        st.info("💡 **Tip:** You can search for locations or use the map to find coordinates. **Coordinates are required** to proceed.")
        
        # Location search functionality
        st.markdown("**🔍 Search for a location:**")
        search_col1, search_col2 = st.columns([3, 1])
        
        with search_col1:
            location_search = st.text_input(
                "Enter location name (e.g., 'Taj Mahal, Agra', 'Gateway of India, Mumbai')",
                placeholder="Type location name here...",
                help="Search for any location in India. Try: Taj Mahal, Red Fort, Golden Temple, Goa, etc."
            )
        
        with search_col2:
            search_button = st.button("🔍 Search", type="primary")
        
        # Show popular search suggestions
        if not location_search:
            st.markdown("**💡 Popular searches:** Taj Mahal, Red Fort, Golden Temple, Goa, Kerala, Darjeeling, Shimla")
        
        # Handle location search
        if search_button and location_search:
            with st.spinner("🔍 Searching for location..."):
                # Use geocoding service to find any location
                geocode_result = geocode_location(location_search)
                
                if geocode_result["success"]:
                    st.session_state.coords = {
                        "lat": geocode_result["lat"], 
                        "lng": geocode_result["lng"]
                    }
                    st.session_state.location_name = geocode_result["name"]
                    
                    st.success(f"✅ **Location Found!**")
                    st.info(f"📍 **Address:** {geocode_result['name']}")
                    st.info(f"📍 **Coordinates:** {geocode_result['lat']:.6f}°N, {geocode_result['lng']:.6f}°E")
                    
                    # Clear the search input by rerunning
                    st.rerun()
                else:
                    st.error(f"❌ **Location not found:** {geocode_result['error']}")
                    st.info("💡 **Try:** Being more specific (e.g., 'Taj Mahal, Agra' instead of just 'Taj Mahal')")
                    st.info("💡 **Or:** Use the manual coordinate inputs below")
        
        # Create a map centered around India
        st.markdown("**🗺️ Location Map:**")
        
        # Create map data with proper column names
        if st.session_state.coords:
            # Show selected location on map
            map_data = pd.DataFrame({
                'latitude': [st.session_state.coords['lat']],  # Use 'latitude' instead of 'lat'
                'longitude': [st.session_state.coords['lng']]  # Use 'longitude' instead of 'lon'
            })
            st.map(map_data)
            st.info(f"📍 Map centered on selected location: {st.session_state.coords['lat']:.6f}, {st.session_state.coords['lng']:.6f}")
        else:
            # Show warning that no location is selected
            st.warning("⚠️ **No location selected!** Please use the search box above or enter coordinates manually to select a location.")
            st.info("💡 **Tip:** You can search for locations like 'Taj Mahal', 'Mumbai', 'Goa', etc., or use the coordinate inputs below.")
            
            # Show a basic map of India without centering on any specific location
            map_data = pd.DataFrame({
                'latitude': [20.5937, 19.0760, 28.7041, 12.9716],  # India center + major cities
                'longitude': [78.9629, 72.8777, 77.1025, 77.5946]
            })
            st.map(map_data)
        
        # Show coordinate status
        if not st.session_state.coords:
            st.error("❌ **No coordinates selected.** Please select a location above to proceed.")
        else:
            st.markdown(f"**📍 Selected Location:** {st.session_state.coords['lat']:.6f}°N, {st.session_state.coords['lng']:.6f}°E")
        
        # Show current coordinates if set
        if st.session_state.coords:
            # Try to identify the location name
            location_name = "Selected Location"
            if abs(st.session_state.coords['lat'] - 19.0760) < 0.1 and abs(st.session_state.coords['lng'] - 72.8777) < 0.1:
                location_name = "Mumbai"
            elif abs(st.session_state.coords['lat'] - 28.7041) < 0.1 and abs(st.session_state.coords['lng'] - 77.1025) < 0.1:
                location_name = "Delhi"
            elif abs(st.session_state.coords['lat'] - 12.9716) < 0.1 and abs(st.session_state.coords['lng'] - 77.5946) < 0.1:
                location_name = "Bangalore"
            elif abs(st.session_state.coords['lat'] - 13.0827) < 0.1 and abs(st.session_state.coords['lng'] - 80.2707) < 0.1:
                location_name = "Chennai"
            
            st.success(f"✅ {location_name}: Latitude: {st.session_state.coords['lat']:.6f}, Longitude: {st.session_state.coords['lng']:.6f}")

        if st.session_state.coords:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Current Selected Location:** Latitude: {st.session_state.coords['lat']:.6f}, Longitude: {st.session_state.coords['lng']:.6f}")
            with col2:
                if st.button("🗑️ Clear Location", type="secondary"):
                    st.session_state.coords = None
                    st.rerun()
        
        # st.markdown(f"To what extent does this image contain visual cues (e.g., local architecture, language, or scenery) that identify it as being from {country}?")
        clue_text = None
        rating = st.radio(
            f"**To what extent does this image contain visual cues (e.g., local architecture, language, or scenery) that identify it as being from {country}?**",
            options=["Choose an option", 0, 1, 2, 3],
            format_func=lambda x: f"{'No evidence at all' if x==0 else f'A few features that are shared by multiple countries within {continent}, but not fully specific to {country}' if x==2 else f'Enough evidence specific to {country}' if x==3 else f'There are visual indications like architectural style, vegetations, etc, but I do not know if they are specific to {country} or {continent}' if x==1 else ''}",
            index=st.session_state.q1_index,
            key='q2'
        )
        if rating in [2, 3]:
            clue_text = st.text_area("What visual clues or indicators helped you make this judgment?", height=100, key='q3')
        popularity = st.radio(
            "**How would you rate the popularity of the location depicted in the photo you uploaded?**",
            options=["Choose an option", 0, 1, 2],
            format_func=lambda x: f"{'The location depicts only a regular scene' if x==0 else f'The location may be locally popular, but not country-wide' if x==1 else f'The location is popular country-wide' if x==2 else 'Choose an option'}",
            index=st.session_state.q1_index,
            key='q5'
        )

        if st.button("Submit and Next"):
            if not uploaded_file or about in ['', None] or ((rating == 'Choose an option') or (rating in [2, 3] and clue_text in [None, ''])):
                st.error('Please answer all the questions and upload a file.')
            elif not st.session_state.coords:
                st.error('Please select a location on the map first.')
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
                st.session_state.q1_index = 0
                
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