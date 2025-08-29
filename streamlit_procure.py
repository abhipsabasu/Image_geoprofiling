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

if 'location_text' not in st.session_state:
    st.session_state.location_text = None

if 'q1_index' not in st.session_state:
    st.session_state.q1_index = 0
    
if 'temp_images' not in st.session_state:
    st.session_state.temp_images = []

def reset_selections():
    # Clear all form selections for the next image using a more robust method
    
    # Method 1: Try to clear specific keys
    keys_to_clear = ["q1", "q2", "q3", "q5", "q6_month", "q6_year", "location_text"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Method 2: Reset question index
    st.session_state.q1_index = 0
    
    # Method 3: Force rerun to clear form state
    # This is more reliable than trying to clear individual keys

def geocode_location(location_text):
    """
    Convert location text to coordinates using Nominatim geocoding service
    """
    try:
        # Add "India" to the search query to improve accuracy for Indian locations
        search_query = f"{location_text}, {country}"
        
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

# Show instructions only before Prolific ID is submitted
if not st.session_state.prolific_id:
    st.markdown(f"""
We are collecting a dataset of images from **{country}** to assess the knowledge of modern-day AI technologies about surroundings within the country. With your consent, we request you to upload photos that you have taken but have **not shared online**.

Following are the instructions for the same.

**What kind of images to upload**:

- Photos should depict a variety of surroundings within {country}.
- Avoid uploading similar photos to the ones that you have already uploaded.
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
    -   **Select the location** where the photo was taken using the search box or map.
    -   **Rate** how clearly the photo suggests it was taken in {country}, and **list the clues** that helped you make that judgment.
    -   **Rate the photo** on the popularity of the location captured.
    -   **Enter the month and year** when the photo was taken.
    -   **Click** "Submit and Next" to move to the next image.
3. If the screen freezes, do **NOT** refresh the page. Instead, wait for a few seconds for the internet connectivity to stabilize.
4. After uploading all the photos, wait till you get a message saying 'Survey Complete'.

You have *20* minutes to upload the photos and answer the questions surrounding them. After you upload the photo, wait for the photo to be visible on screen, then answer the questions.
""", unsafe_allow_html=True)
else:
    # Show View Instructions expander after Prolific ID is submitted
    with st.expander("📋 View Instructions", expanded=False):
        st.markdown(f"""
We are collecting a dataset of images from **{country}** to assess the knowledge of modern-day AI technologies about surroundings within the country. With your consent, we request you to upload photos that you have taken but have **not shared online**.

Following are the instructions for the same.

**What kind of images to upload**:

- Photos should depict a variety of surroundings within {country}. Try to avoid sharing images of well-known, highly-recognizable tourist attractions.
- Upload a diverse and distinct set of images in terms of content.
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
    -   **Select the location** where the photo was taken using the search box or map.
    -   **Rate** how clearly the photo suggests it was taken in {country}, and **list the clues** that helped you make that judgment.
    -   **Rate the photo** on the popularity of the location captured.
    -   **Enter the month and year** when the photo was taken.
    -   **Click** "Submit and Next" to move to the next image.
3. If the screen freezes, do **NOT** refresh the page. Instead, wait for a few seconds for the internet connectivity to stabilize.
4. After uploading all the photos, wait till you get a message saying 'Survey Complete'.

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
        # Show progress
        st.markdown(f"**📸 Progress: {st.session_state.index}/10 images completed**")
        progress_bar = st.progress(st.session_state.index / 10)
        st.markdown("Answer all questions (marked with <span style='color: red;'>*</span>)", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='margin-bottom: 5px; padding-bottom: 0px;'>
            <strong>Upload image {st.session_state.index + 1}</strong> 
            <span style='color: red;'>*</span>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], key=st.session_state.index)
        if uploaded_file:
            file_bytes = uploaded_file.read() 
            if len(file_bytes) < 100:
                st.error("⚠️ File seems too small. Possible read error.")
            encoded_content = base64.b64encode(file_bytes).decode("utf-8")
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True)
        

        st.markdown(f"**Where in {country} was the photo taken? Use the search box within map below to select the location where the photo was taken:** <span style='color: red;'>*</span>", unsafe_allow_html=True)
        
        # Warning that coordinates are required
        if not hasattr(st.session_state, 'location_text') or not st.session_state.location_text:
            st.error("🚨 **Search for the location where the photo was taken in the map text box below**")
        else:
            st.success("✅ **Location selected successfully!**")
            
        
        

        
        # Create a Google Map with search functionality
        st.markdown("**🗺️ Location Map:**")
        
        # Get Google Maps API key from firebase_secrets
        google_maps_api_key = firebase_secrets.get("GOOGLE_MAPS_API_KEY", "")
        
        if google_maps_api_key:
            # Google Maps with search functionality
            # Create Google Maps component with integrated search
            components.html(
                f"""
                                    <div style="margin-bottom: 10px;">
                        <input id="pac-input" type="text" placeholder="Search for a location in {country}..." 
                               style="width: 95%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 10px; margin: 0 auto;">
                    </div>
                <div id="map" style="height: 400px; width: 95%; margin: 0 auto;"></div>
                <script>
                    function initMap() {{
                        const map = new google.maps.Map(document.getElementById("map"), {{
                            zoom: 5,
                            center: {{ lat: 20.5937, lng: 78.9629 }}, // India center
                            mapTypeId: google.maps.MapTypeId.ROADMAP
                        }});
                        
                        // Add markers for major cities
                        const cities = [
                            {{ lat: 19.0760, lng: 72.8777, name: "Mumbai" }},
                            {{ lat: 28.7041, lng: 77.1025, name: "Delhi" }},
                            {{ lat: 12.9716, lng: 77.5946, name: "Bangalore" }},
                            {{ lat: 13.0827, lng: 80.2707, name: "Chennai" }}
                        ];
                        
                        cities.forEach(city => {{
                            new google.maps.Marker({{
                                position: {{ lat: city.lat, lng: city.lng }},
                                map: map,
                                title: city.name
                            }});
                        }});
                        
                        // Add search box functionality
                        const input = document.getElementById("pac-input");
                        const searchBox = new google.maps.places.SearchBox(input);
                        
                        // Bias the SearchBox results towards current map's viewport
                        map.addListener("bounds_changed", () => {{
                            searchBox.setBounds(map.getBounds());
                        }});
                        
                        // Listen for the event fired when the user selects a prediction
                        searchBox.addListener("places_changed", () => {{
                            const places = searchBox.getPlaces();
                            
                            if (places.length === 0) {{
                                return;
                            }}
                            
                            // For each place, get the icon, name and location
                            const bounds = new google.maps.LatLngBounds();
                            
                            places.forEach((place) => {{
                                if (!place.geometry || !place.geometry.location) {{
                                    console.log("Returned place contains no geometry");
                                    return;
                                }}
                                
                                // Create a marker for the selected place
                                const marker = new google.maps.Marker({{
                                    map,
                                    title: place.name,
                                    position: place.geometry.location,
                                }});
                                
                                if (place.geometry.viewport) {{
                                    bounds.union(place.geometry.viewport);
                                }} else {{
                                    bounds.extend(place.geometry.location);
                                }}
                            }});
                            
                            map.fitBounds(bounds);
                            
                            // Update coordinates in Streamlit
                            const selectedPlace = places[0];
                            if (selectedPlace.geometry && selectedPlace.geometry.location) {{
                                const lat = selectedPlace.geometry.location.lat();
                                const lng = selectedPlace.geometry.location.lng();
                                
                                // Automatically capture the location text
                                const locationText = selectedPlace.formatted_address || selectedPlace.name;
                                
                                // Send location data back to Streamlit
                                window.parent.postMessage({{
                                    type: 'location_selected',
                                    lat: lat,
                                    lng: lng,
                                    name: selectedPlace.name,
                                    formatted_address: selectedPlace.formatted_address,
                                    location_text: locationText
                                }}, '*');
                                
                                // Update the search input with the selected location
                                document.getElementById('pac-input').value = locationText;
                                
                                // Show success message
                                const successDiv = document.createElement('div');
                                successDiv.innerHTML = `<div style="background: #d4edda; color: #155724; padding: 10px; border-radius: 4px; margin: 10px 0; border: 1px solid #c3e6cb;">✅ Location captured: ${{locationText}}</div>`;
                                document.getElementById('map').parentNode.insertBefore(successDiv, document.getElementById('map').nextSibling);
                                
                                // Remove success message after 5 seconds
                                setTimeout(() => {{
                                    if (successDiv.parentNode) {{
                                        successDiv.parentNode.removeChild(successDiv);
                                    }}
                                }}, 5000);
                            }}
                        }});
                    }}
                </script>
                <script async defer src="https://maps.googleapis.com/maps/api/js?key={google_maps_api_key}&libraries=places&callback=initMap"></script>
                """,
                height=450
            )
            
            # Show captured location if available
            if hasattr(st.session_state, 'location_text') and st.session_state.location_text:
                st.success(f"✅ **Location Captured:** {st.session_state.location_text}")
            else:
                st.info("Once you have selected the correct location on the map, **paste the location string you used in the text box below**. If you are unable to find the location, please select the nearest location from the map.")
                # st.info("💡 **Tip:** Use the search box in the map above to find and select a location. The location will be automatically captured when you select it.")
                
                # Add a text input for manual location entry
                st.markdown("<div style='margin-bottom: 0px; padding-bottom: 0px;'><strong>Enter the location you selected on the map:</strong> <span style='color: red;'>*</span></div>", unsafe_allow_html=True)
                
                manual_location = st.text_input(
                    "",
                    placeholder="e.g., Taj Mahal, Agra, Uttar Pradesh, India",
                    key=f"manual_location_{st.session_state.index}"
                )
                
                if manual_location:
                    st.session_state.location_text = manual_location
                    st.success(f"✅ **Location set:** {manual_location}")
                
                
        else:
            # Fallback to Streamlit map if no Google Maps API key
            st.warning("⚠️ Google Maps API key not configured. Using default map.")
            # Show a basic map of India
            map_data = pd.DataFrame({
                'latitude': [20.5937, 19.0760, 28.7041, 12.9716],
                'longitude': [78.9629, 72.8777, 77.1025, 77.5946]
            })
            st.map(map_data)
            st.info("💡 **Tip:** Use the search functionality above to select a location.")
        
        # Show location status
        if not hasattr(st.session_state, 'location_text') or not st.session_state.location_text:
            st.error("❌ **No location selected.** Please select a location above to proceed.")
        else:
            st.markdown(f"**📍 Selected Location:** {st.session_state.location_text}")
        
        # Show current location if set
        if hasattr(st.session_state, 'location_text') and st.session_state.location_text:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Current Selected Location:** {st.session_state.location_text}")
            with col2:
                if st.button("🗑️ Clear Location", type="secondary"):
                    st.session_state.location_text = None
                    st.rerun()
        
        # st.markdown(f"To what extent does this image contain visual cues (e.g., local architecture, language, or scenery) that identify it as being from {country}?")
        clue_text = None
        st.markdown(f"""
        <div style='margin-bottom: 0px; padding-bottom: 0px;'>
            <strong>To what extent does this image contain visual cues (e.g., local architecture, language, or scenery) that identify it as being from {country}?</strong> 
            <span style='color: red;'>*</span>
        </div>
        """, unsafe_allow_html=True)
        rating = st.selectbox(
            f"",
            options=["Choose an option", 0, 1, 2, 3],
            format_func=lambda x: f"{'Strong evidence specific to the country' if x==3 else f'Clear cues, but not typically associated with {country}' if x==2 else f'Some visual indications, but not sure if they are specific to {country}' if x==1 else f'No visual indicators visible in the photo' if x==0 else 'Choose an option'}",
            index=st.session_state.q1_index,
            key=f'q2_{st.session_state.index}',
            # unsafe_allow_html=True
        )
        if rating in [2, 3]:
            clue_text = st.text_area("What visual clues or indicators helped you make this judgment?", height=100, key=f'q3_{st.session_state.index}')
        st.markdown(f"""
        <div style='margin-bottom: 0px; padding-bottom: 0px;'>
            <strong>How would you rate the popularity of the location depicted in the photo you uploaded?</strong> 
            <span style='color: red;'>*</span>
        </div>
        """, unsafe_allow_html=True)
        popularity = st.selectbox(
            "",
            options=["Choose an option", 1, 2, 3],
            format_func=lambda x: f"{'1 - Not Popular' if x==1 else f'2 - Locally Popular' if x==2 else f'3 - Country-wide Popular' if x==3 else 'Choose an option'}",
            index=st.session_state.q1_index,
            key=f'q5_{st.session_state.index}',
            # unsafe_allow_html=True
        )

        # Month and Year questions
        st.markdown("""
        <div style='margin-bottom: 0px; padding-bottom: 0px;'>
            <strong>📅 When was this photo taken?</strong> 
            <span style='color: red;'>*</span>
        </div>
        """, unsafe_allow_html=True)
        month_col, year_col = st.columns(2)
        
        with month_col:
            month = st.selectbox(
                "**Month:**",
                options=["Choose an option", "January", "February", "March", "April", "May", "June", 
                        "July", "August", "September", "October", "November", "December", "Cannot recall"],
                key=f'q6_month_{st.session_state.index}'
            )
        
        with year_col:
            year = st.selectbox(
                "**Year:**",
                options=["Choose an option"] + [str(i) for i in range(2025, 1999, -1)] + ["Cannot recall"],
                key=f'q6_year_{st.session_state.index}'
            )

        if st.button("Submit and Next"):
            if not uploaded_file or ((rating == 'Choose an option') or (rating in [2, 3] and clue_text in [None, ''])) or month == "Choose an option" or year == "Choose an option":
                st.error('Please answer all the questions and upload a file.')
            elif not hasattr(st.session_state, 'location_text') or not st.session_state.location_text:
                st.error('Please select a location on the map first and capture the location description.')
            else:
                # Store image temporarily instead of uploading immediately
                image_data = {
                    "file_name": f"{st.session_state.prolific_id}_{st.session_state.index}.png",
                    "file_path": f"{country}_images/{f'{st.session_state.prolific_id}_{st.session_state.index}.png'}",
                    "encoded_content": encoded_content,
                    "index": st.session_state.index
                }
                
                # Add to temporary storage
                st.session_state.temp_images.append(image_data)
                
                # Store response data (without uploading image yet)
                st.session_state.responses.append({
                    "name": st.session_state.prolific_id,
                    "birth_country": st.session_state.birth_country,
                    "residence": st.session_state.residence,
                    "privacy": st.session_state.privacy,
                    "image_url": image_data["file_path"],  # Will be updated after upload
                    "rating": rating,
                    "location_text": st.session_state.location_text,
                    "popularity": popularity,
                    "clues": clue_text,
                    "month": month,
                    "year": year,
                })
                
                st.success("✅ Image and responses saved!")
                st.toast("Saved successfully!", icon="✅")
                # Clear location and reset index
                st.session_state.location_text = None
                st.session_state.index += 1
                st.session_state.q1_index = 0
                
                # Force rerun to get fresh forms with new keys
                st.rerun()
    else:
        # Upload all images to GitHub at once
        st.markdown("**📤 Uploading all images...**")
        
        upload_progress = st.progress(0)
        upload_status = st.empty()
        
        successful_uploads = 0
        failed_uploads = 0
        
        for i, image_data in enumerate(st.session_state.temp_images):
            try:
                # Update progress
                progress = (i + 1) / len(st.session_state.temp_images)
                upload_progress.progress(progress)
                upload_status.text(f"Uploading image {i + 1} of {len(st.session_state.temp_images)}...")
                
                # Upload to GitHub
                api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{image_data['file_path']}"
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                payload = {
                    "message": f"Upload {image_data['file_path']}",
                    "content": image_data['encoded_content'],
                    "branch": "main"
                }

                response = requests.put(api_url, headers=headers, json=payload)
                if response.status_code in [200, 201]:
                    successful_uploads += 1
                    # Update the response with actual GitHub URL
                    st.session_state.responses[image_data['index']]['image_url'] = f"https://github.com/{owner}/{repo_name}/blob/main/{image_data['file_path']}"
                else:
                    failed_uploads += 1
                    st.error(f"❌ Failed to upload {image_data['file_name']}: {response.status_code}")
                    
            except Exception as e:
                failed_uploads += 1
                st.error(f"❌ Error uploading {image_data['file_name']}: {str(e)}")
        
        # Show final upload results
        upload_progress.progress(1.0)
        if failed_uploads == 0:
            upload_status.success(f"✅ All {successful_uploads} images uploaded successfully!")
        else:
            upload_status.warning(f"⚠️ {successful_uploads} images uploaded, {failed_uploads} failed")
        
        # Save to Firebase
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
        st.success("🎉 Survey complete! Thank you!")
        st.write(f"✅ **Survey Results:**")
        st.write(f"📸 **Images:** {successful_uploads} uploaded successfully")
        st.write(f"📊 **Responses:** {len(st.session_state.responses)} recorded")
        st.write(f"🗺️ **Locations:** All location descriptions captured")
        st.write(f"📅 **Timestamps:** Month/year data collected")
        st.write(f"📧 **Note**: If you wish to revoke your consent, please contact us at <a href='mailto:abhipsabasu@iisc.ac.in'>abhipsabasu@iisc.ac.in</a>.")