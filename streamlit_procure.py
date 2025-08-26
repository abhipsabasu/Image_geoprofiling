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

def create_google_maps_embed():
    """
    Create Google Maps embed with coordinate extraction functionality
    """
    # Get the Google Maps API key from Streamlit secrets
    api_key = st.secrets["firebase"]["GOOGLE_MAPS_API_KEY"]
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Maps Location Picker</title>
        <style>
            #map {{
                height: 400px;
                width: 100%;
                border-radius: 10px;
                border: 2px solid #ddd;
            }}
            .search-container {{
                margin-bottom: 15px;
            }}
            #search-input {{
                width: 70%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
            }}
            #search-button {{
                width: 25%;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }}
            #search-button:hover {{
                background-color: #45a049;
            }}
            .coordinates-display {{
                margin-top: 15px;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 5px;
                font-family: monospace;
            }}
            .instructions {{
                margin-bottom: 15px;
                color: #666;
                font-size: 14px;
            }}
            .loading {{
                color: #666;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="instructions">
            <strong>Instructions:</strong> Search for a location or click anywhere on the map to select coordinates.
        </div>
        
        <div class="search-container">
            <input type="text" id="search-input" placeholder="Search for a location in India...">
            <button id="search-button" onclick="searchLocation()">Search</button>
        </div>
        
        <div id="map"></div>
        
        <div class="coordinates-display" id="coordinates-display">
            <strong>Selected Coordinates:</strong> None selected
        </div>
        
        <!-- Hidden input fields for Streamlit to read -->
        <input type="hidden" id="lat-input" value="">
        <input type="hidden" id="lng-input" value="">
        <input type="hidden" id="address-input" value="">
        
        <!-- Easy copy section -->
        <div style="margin-top: 15px; padding: 10px; background-color: #e8f5e8; border-radius: 5px; border: 1px solid #4CAF50;">
            <strong>📋 Easy Copy:</strong><br>
            <div id="easy-copy" style="font-family: monospace; margin: 10px 0; padding: 10px; background-color: white; border-radius: 3px;">
                Click on the map or search for a location to see coordinates here
            </div>
        </div>
        
        <script>
            let map;
            let marker;
            let geocoder;
            let searchBox;
            
            function initMap() {{
                // Center map on India
                const india = {{ lat: 20.5937, lng: 78.9629 }};
                
                map = new google.maps.Map(document.getElementById("map"), {{
                    zoom: 5,
                    center: india,
                    mapTypeId: google.maps.MapTypeId.ROADMAP,
                    styles: [
                        {{
                            featureType: "poi",
                            elementType: "labels",
                            stylers: [{{ visibility: "off" }}]
                        }}
                    ]
                }});
                
                geocoder = new google.maps.Geocoder();
                
                // Add click listener to map
                map.addListener("click", function(event) {{
                    placeMarker(event.latLng);
                    updateCoordinates(event.latLng);
                }});
                
                // Initialize search box
                const input = document.getElementById("search-input");
                searchBox = new google.maps.places.SearchBox(input);
                
                // Bias search results to India
                map.addListener("bounds_changed", function() {{
                    searchBox.setBounds(map.getBounds());
                }});
                
                // Listen for search results
                searchBox.addListener("places_changed", function() {{
                    const places = searchBox.getPlaces();
                    if (places.length === 0) return;
                    
                    const place = places[0];
                    if (!place.geometry) return;
                    
                    // Center map on search result
                    if (place.geometry.viewport) {{
                        map.fitBounds(place.geometry.viewport);
                    }} else {{
                        map.setCenter(place.geometry.location);
                        map.setZoom(15);
                    }}
                    
                    // Place marker and update coordinates
                    placeMarker(place.geometry.location);
                    updateCoordinates(place.geometry.location);
                    
                    // Update search input with formatted address
                    document.getElementById("search-input").value = place.formatted_address;
                }});
                
                // Handle Enter key in search input
                input.addEventListener("keypress", function(event) {{
                    if (event.key === "Enter") {{
                        searchLocation();
                    }}
                }});
            }}
            
            function placeMarker(latLng) {{
                if (marker) {{
                    marker.setMap(null);
                }}
                marker = new google.maps.Marker({{
                    position: latLng,
                    map: map,
                    title: "Selected Location",
                    animation: google.maps.Animation.DROP
                }});
            }}
            
            function updateCoordinates(latLng) {{
                const display = document.getElementById("coordinates-display");
                display.innerHTML = `
                    <strong>Selected Coordinates:</strong><br>
                    Latitude: ${{latLng.lat().toFixed(6)}}°N<br>
                    Longitude: ${{latLng.lng().toFixed(6)}}°E<br>
                    <button onclick="copyCoordinates(${{latLng.lat()}}, ${{latLng.lng()}})" style="margin-top: 10px; padding: 5px 10px; background-color: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">
                        Copy Coordinates
                    </button>
                `;
                
                // Update hidden input fields for Streamlit
                document.getElementById("lat-input").value = latLng.lat();
                document.getElementById("lng-input").value = latLng.lng();
                
                // Update easy copy section
                document.getElementById("easy-copy").innerHTML = `
                    <strong>Latitude:</strong> ${{latLng.lat().toFixed(6)}}°N<br>
                    <strong>Longitude:</strong> ${{latLng.lng().toFixed(6)}}°E<br>
                    <button onclick="copyToClipboard('${{latLng.lat().toFixed(6)}}, ${{latLng.lng().toFixed(6)}}')" style="margin-top: 5px; padding: 5px 10px; background-color: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">
                        📋 Copy to Clipboard
                    </button>
                `;
                
                // Send coordinates to Streamlit
                if (window.parent && window.parent.postMessage) {{
                    window.parent.postMessage({{
                        type: 'coordinates',
                        lat: latLng.lat(),
                        lng: latLng.lng()
                    }}, '*');
                }}
            }}
            
            function searchLocation() {{
                const input = document.getElementById("search-input");
                const query = input.value.trim();
                
                if (!query) {{
                    alert("Please enter a location to search for.");
                    return;
                }}
                
                // Show loading state
                const searchBtn = document.getElementById("search-button");
                const originalText = searchBtn.textContent;
                searchBtn.textContent = "Searching...";
                searchBtn.disabled = true;
                
                // Use Google Places API for search
                const service = new google.maps.places.PlacesService(map);
                const request = {{
                    query: query + ", India",
                    fields: ['name', 'geometry', 'formatted_address']
                }};
                
                service.findPlaceFromQuery(request, function(results, status) {{
                    if (status === google.maps.places.PlacesServiceStatus.OK && results.length > 0) {{
                        const place = results[0];
                        map.setCenter(place.geometry.location);
                        map.setZoom(15);
                        placeMarker(place.geometry.location);
                        updateCoordinates(place.geometry.location);
                        input.value = place.formatted_address;
                        
                        // Show success message
                        const display = document.getElementById("coordinates-display");
                        display.innerHTML += `<br><span style="color: green;">✅ Location found: ${{place.formatted_address}}</span>`;
                        
                        // Update hidden address field
                        document.getElementById("address-input").value = place.formatted_address;
                    }} else {{
                        alert("Location not found. Please try a different search term or be more specific.");
                    }}
                    
                    // Reset button state
                    searchBtn.textContent = originalText;
                    searchBtn.disabled = false;
                }});
            }}
            
            function copyCoordinates(lat, lng) {{
                const text = `${{lat.toFixed(6)}}, ${{lng.toFixed(6)}}`;
                navigator.clipboard.writeText(text).then(function() {{
                    alert("Coordinates copied to clipboard!");
                }});
            }}
            
            function copyToClipboard(text) {{
                navigator.clipboard.writeText(text).then(function() {{
                    alert("Coordinates copied to clipboard!");
                }});
            }}
        </script>
        
        <script async defer
            src="https://maps.googleapis.com/maps/api/js?key={api_key}&libraries=places&callback=initMap">
        </script>
    </body>
    </html>
    """
    return html_code

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
        
        # Google Maps Location Picker
        st.markdown("**🗺️ Google Maps Location Picker:**")
        st.info("💡 **Instructions:** Search for a location or click anywhere on the map to select coordinates. The map will automatically extract the latitude and longitude.")
        
        # Create Google Maps embed
        google_maps_html = create_google_maps_embed()
        
        # Display the Google Maps embed
        components.html(google_maps_html, height=500, scrolling=False)
        
        # Coordinate capture system
        st.markdown("**📍 Coordinate Capture:**")
        st.info("💡 **How it works:** Search for a location or click on the map, then copy the coordinates from the green box above and paste them below.")
        
        # Manual coordinate input
        with st.form("coordinate_capture"):
            coord_col1, coord_col2, coord_col3 = st.columns([2, 2, 1])
            
            with coord_col1:
                lat_input = st.text_input("Latitude", placeholder="e.g., 19.0760", key="lat_input")
            
            with coord_col2:
                lng_input = st.text_input("Longitude", placeholder="e.g., 72.8777", key="lng_input")
            
            with coord_col3:
                st.markdown("**Action:**")
                capture_button = st.form_submit_button("📍 Capture Coordinates", type="primary")
            
            if capture_button and lat_input and lng_input:
                try:
                    lat = float(lat_input)
                    lng = float(lng_input)
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        st.session_state.coords = {"lat": lat, "lng": lng}
                        st.success(f"✅ Coordinates captured: {lat:.6f}°N, {lng:.6f}°E")
                        st.rerun()
                    else:
                        st.error("❌ Invalid coordinates. Latitude must be between -90 and 90, Longitude between -180 and 180.")
                except ValueError:
                    st.error("❌ Please enter valid numbers for coordinates.")
        
        # Show coordinate status
        if not st.session_state.coords:
            st.error("❌ **No coordinates selected.** Please select a location above to proceed.")
        else:
            st.markdown(f"**📍 Selected Location:** {st.session_state.coords['lat']:.6f}°N, {st.session_state.coords['lng']:.6f}°E")
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
