# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import pandas as pd
import time
import requests
import re
from pyproj import Transformer
from datetime import datetime
from dateparser.search import search_dates

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable Cross-Origin Resource Sharing

# === CONFIGURATION ===
API_KEY = "AIzaSyAqU3mmXxK55y5yUQ7Di27-ngUFDWw1eSI"  # Replace with your Google Cloud key
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-001:generateContent?key={API_KEY}"
PLACES_RADIUS = 2000
SEARCH_TYPES = ["subway_station", "bus_station"]
INPUT_FILE = "static/Hiking_Trails.json"  # Move your GeoJSON file to the static folder
CACHE_FILE = "static/station_cache.json"
WEATHER_CACHE_FILE = "static/weather_cache.json"
RECOMMENDATIONS_CACHE_FILE = "static/recommendations_cache.json"

# Initialize transformer for coordinate conversion
transformer = Transformer.from_crs("EPSG:2326", "EPSG:4326", always_xy=True)

# === ENHANCED CACHING FOR TRAIL DATA ===
def load_trail_data():
    # Make sure the cache directory exists
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    
    # Load GeoJSON file
    with open(INPUT_FILE, "r") as f:
        geojson = json.load(f)
    
    # Load cache if it exists
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                cache_data = json.load(f)
                station_cache = cache_data.get("stations", {})
                cache_timestamp = cache_data.get("timestamp", 0)
                
                # If cache is recent (less than 7 days old), use it
                if time.time() - cache_timestamp < 7 * 24 * 60 * 60:
                    # Skip API calls if cache is valid
                    return geojson, station_cache, True
                else:
                    print("Cache expired, will refresh trail data")
            except json.JSONDecodeError:
                print("Cache file corrupted, creating new cache")
                station_cache = {}
    else:
        print("No cache file found, creating new cache")
        station_cache = {}
        
    return geojson, station_cache, False

# === ENHANCED WEATHER FORECAST CACHING ===
def get_cached_weather(prompt):
    # Initialize weather cache
    if os.path.exists(WEATHER_CACHE_FILE):
        with open(WEATHER_CACHE_FILE, "r") as f:
            try:
                weather_cache = json.load(f)
            except:
                weather_cache = {"data": {}, "timestamp": time.time()}
    else:
        weather_cache = {"data": {}, "timestamp": time.time()}
    
    # Check if cache is still valid (1 hour for current weather, 12 hours for forecasts)
    cache_age = time.time() - weather_cache.get("timestamp", 0)
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Simple key for weather cache based on date in prompt
    cache_key = prompt.lower().strip()
    
    # If we have cached data for this query and it's not too old
    if (cache_key in weather_cache["data"] and 
        ((cache_key.find("today") >= 0 and cache_age < 3600) or  # 1 hour for today
         (cache_age < 12 * 3600))):  # 12 hours for other forecasts
        print(f"Using cached weather for: {cache_key}")
        return weather_cache["data"][cache_key]
    
    # If not in cache or expired, get fresh data
    weather_info = get_forecast_for_day(prompt)
    
    # Update cache
    weather_cache["data"][cache_key] = weather_info
    weather_cache["timestamp"] = time.time()
    
    # Save updated cache
    os.makedirs(os.path.dirname(WEATHER_CACHE_FILE), exist_ok=True)
    with open(WEATHER_CACHE_FILE, "w") as f:
        json.dump(weather_cache, f, indent=2)
    
    return weather_info

# Original weather forecast function
# Updated weather forecast function with no caching and improved date handling
def get_forecast_for_day(prompt):
    today = datetime.now()
    
    # Step 1: Try using dateparser for natural language input
    results = search_dates(prompt, settings={"PREFER_DATES_FROM": "future"})
    if results:
        # Extract the date string and parsed date
        date_string, parsed_date = results[0]
        
        # Debug the parsed date
        print(f"Parsed date from '{date_string}': {parsed_date}")
        
        # Format the date for API request
        date_requested = parsed_date.strftime("%Y%m%d")
        readable_date = parsed_date.strftime("%A, %Y-%m-%d")
        
        # Check if the parsed date is today
        is_today = (parsed_date.year == today.year and 
                   parsed_date.month == today.month and 
                   parsed_date.day == today.day)
        
        if is_today:
            # If it's today, use current weather
            date_requested = None
            readable_date = "Today"
    else:
        date_requested = None
        readable_date = "Today"
    
    
    # If no date found or date is today, use current weather
    if not date_requested:
        url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=en"
        try:
            response = requests.get(url).json()

            temp_data = response.get("temperature", {}).get("data", [{}])[0]
            temp = temp_data.get("value", "?")
            warnings = response.get("warningMessage", [])
            rain_data = response.get("rainfall", {}).get("data", [{}])[0]
            rain = rain_data.get("max", 0)

            weather_icon_map = {
                50: "Sunny", 51: "Sunny intervals", 52: "Sunny periods", 60: "Cloudy",
                61: "Overcast", 62: "Mist", 63: "Rainy", 64: "Heavy rain",
                65: "Thunderstorms", 70: "Hazy", 71: "Very hot", 72: "Cold",
                73: "Dry", 74: "Humid"
            }

            icon_codes = response.get("icon", [])
            weather_text = weather_icon_map.get(icon_codes[0], "Weather condition unknown") if icon_codes else "Unknown"

            alert = ""
            if "rain" in " ".join(warnings).lower() or (isinstance(rain, (int, float)) and rain > 0):
                alert = "Rain is expected. Consider rescheduling your hike."

            return {
                "date": readable_date,
                "condition": weather_text,
                "temp": f"{temp}°C",
                "humidity": None,
                "alert": alert
            }
        except Exception as e:
            return {
                "date": readable_date,
                "condition": "Unable to fetch current weather",
                "temp": "?°C",
                "humidity": None,
                "alert": f"Weather data fetch error: {str(e)}"
            }

    # For future forecasts
    url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=en"
    try:
        response = requests.get(url)
        forecast = response.json().get("weatherForecast", [])

        for entry in forecast:
            if entry["forecastDate"] == date_requested:
                weather = entry["forecastWeather"]
                maxtemp = entry["forecastMaxtemp"]["value"]
                mintemp = entry["forecastMintemp"]["value"]
                maxrh = entry["forecastMaxrh"]["value"]
                minrh = entry["forecastMinrh"]["value"]
                alert = "Rain is expected. Consider rescheduling your hike." if "rain" in weather.lower() or "showers" in weather.lower() else ""
                
                return {
                    "date": readable_date,
                    "condition": weather,
                    "temp": f"{mintemp}–{maxtemp}°C",
                    "humidity": f"{minrh}–{maxrh}%",
                    "alert": alert
                }
    except Exception as e:
        return {
            "date": readable_date,
            "condition": "Forecast unavailable",
            "temp": "?°C",
            "humidity": None,
            "alert": f"Weather forecast error: {str(e)}"
        }

    return {
        "date": readable_date,
        "condition": "Forecast not found",
        "temp": "?°C",
        "humidity": None,
        "alert": "No weather data available for this date."
    }

# === ENHANCED AI RECOMMENDATIONS CACHING ===
def get_cached_recommendations(user_preference, trail_data):
    # Initialize recommendations cache
    if os.path.exists(RECOMMENDATIONS_CACHE_FILE):
        with open(RECOMMENDATIONS_CACHE_FILE, "r") as f:
            try:
                recommendations_cache = json.load(f)
            except:
                recommendations_cache = {"data": {}, "timestamp": time.time()}
    else:
        recommendations_cache = {"data": {}, "timestamp": time.time()}
    
    # Simple key for recommendations cache
    cache_key = user_preference.lower().strip()
    
    # Cache is valid for 24 hours
    cache_age = time.time() - recommendations_cache.get("timestamp", 0)
    if cache_key in recommendations_cache["data"] and cache_age < 24 * 3600:
        print(f"Using cached recommendations for: {cache_key}")
        return recommendations_cache["data"][cache_key]
    
    # Not in cache or expired, get fresh recommendations
    recommendations = get_recommendations(user_preference, trail_data)
    
    # Update cache
    recommendations_cache["data"][cache_key] = recommendations
    recommendations_cache["timestamp"] = time.time()
    
    # Save updated cache
    os.makedirs(os.path.dirname(RECOMMENDATIONS_CACHE_FILE), exist_ok=True)
    with open(RECOMMENDATIONS_CACHE_FILE, "w") as f:
        json.dump(recommendations_cache, f, indent=2)
    
    return recommendations

# Process trail and find nearest stations
def process_trails(geojson, station_cache):
    trail_data = []
    cache_updated = False

    for i, feature in enumerate(geojson["features"]):
        props = feature["properties"]
        geometry = feature["geometry"]
        coords = geometry.get("coordinates")

        if not coords:
            continue

        if geometry["type"] == "LineString":
            first_coord = coords[0]
        elif geometry["type"] == "MultiLineString":
            first_coord = coords[0][0]
        else:
            continue

        easting, northing = first_coord
        lon, lat = transformer.transform(easting, northing)

        # Use trail name as unique ID, or fallback to index
        trail_id = props.get("Trail_name_En") or f"trail_{i}"

        # If in cache, load it and skip API calls
        if trail_id in station_cache:
            trail_data.append(station_cache[trail_id])
            continue

        print(f"Finding nearest station for trail: {trail_id}")
        cache_updated = True
        best_station = None
        best_distance = float('inf')
        best_type = None

        for place_type in SEARCH_TYPES:
            places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            places_params = {
                "location": f"{lat},{lon}",
                "radius": PLACES_RADIUS,
                "type": place_type,
                "key": API_KEY
            }

            try:
                response = requests.get(places_url, params=places_params)
                candidates = response.json().get("results", [])
            except Exception as e:
                print(f"Places API failed: {e}")
                continue

            for place in candidates:
                dest_lat = place['geometry']['location']['lat']
                dest_lon = place['geometry']['location']['lng']
                dest_name = place.get("name")

                matrix_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                matrix_params = {
                    "origins": f"{lat},{lon}",
                    "destinations": f"{dest_lat},{dest_lon}",
                    "mode": "walking",
                    "key": API_KEY
                }

                try:
                    dist_response = requests.get(matrix_url, params=matrix_params).json()
                    dist_value = dist_response['rows'][0]['elements'][0]['distance']['value'] / 1000
                    if dist_value < best_distance:
                        best_distance = dist_value
                        best_station = dest_name
                        best_type = place_type
                except Exception:
                    continue

            # Add a small delay to avoid API rate limits
            time.sleep(0.2)

        trail_result = {
            "name": props.get("Trail_name_En"),
            "startLocation": props.get("Startpt_En"),
            # Ensure length doesn't already have "km" suffix
            "length": round(props.get("Shape_Length", 0) / 1000, 2),  # Just the number
            "difficulty": props.get("Difficult_En"),
            "station": best_station,
            "stationType": best_type,
            "distance": round(best_distance, 2) if best_station else None,
            "website": props.get("Webpage_En")
        }

        trail_data.append(trail_result)
        station_cache[trail_id] = trail_result

    # Save updated cache with timestamp
    if cache_updated:
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "stations": station_cache,
                "timestamp": time.time()
            }, f, indent=2)
        
    return trail_data

# Get AI recommendations based on user preferences
def get_recommendations(user_preference, trail_data):
    trail_lines = []
    for t in trail_data:
        if not t["name"]: 
            continue
            
        desc = (
            f"- {t['name']} — {t['length']} km, Difficulty: {t['difficulty']}, "
            f"Nearest Station: {t['station']} ({t['distance']} km)"
        )
        if t.get("website"):
            desc += f", Website: {t['website']}"
        trail_lines.append(desc)

    trail_text = "\n".join(trail_lines)

    full_prompt = f"""
    {user_preference}

    Use only the provided list of trails below.
    Do not assume or invent anything that is not explicitly stated in the trail list.
    Be concise. Always include walking distance, difficulty and website link if available.
    Return results in JSON format with fields: name, length, difficulty, station, distance, website.

    Available Trails:
    {trail_text}
    """

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=data)
        result = response.json()
        response_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # Try to extract JSON if Gemini returns it properly formatted
        try:
            # Find JSON in the response (may be surrounded by markdown code blocks)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|^\s*(\[[\s\S]*\])\s*$|^\s*(\{[\s\S]*\})\s*$', response_text)
            if json_match:
                json_str = next(group for group in json_match.groups() if group)
                recommendations = json.loads(json_str)
                return recommendations
            else:
                # Parse the text response to extract trail data
                trails = []
                for line in response_text.split('\n'):
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        trails.append({"description": line.strip('- *')})
                return trails
        except Exception as e:
            return [{"description": response_text}]
            
    except Exception as e:
        return [{"error": f"Failed to get recommendations: {str(e)}"}]

# === API ROUTES ===
@app.route('/api/ready', methods=['GET'])
def ready():
    return jsonify({"status": "ready"})

@app.route('/api/weather', methods=['POST'])
def weather():
    data = request.get_json()
    prompt = data.get('prompt', '')
    # Get weather directly without caching
    weather_info = get_forecast_for_day(prompt)
    return jsonify(weather_info)

@app.route('/api/trails', methods=['GET'])
def trails():
    geojson, station_cache, _ = load_trail_data()
    trail_data = process_trails(geojson, station_cache)
    return jsonify(trail_data)

@app.route('/api/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    preference = data.get('preference', '')
    
    # Get weather directly without caching
    weather_info = get_forecast_for_day(preference)
    
    # Get trail data (using cache if available)
    geojson, station_cache, _ = load_trail_data()
    trail_data = process_trails(geojson, station_cache)
    
    # Get recommendations (using cache if available)
    recommendations = get_cached_recommendations(preference, trail_data)
    
    return jsonify({
        "weather": weather_info,
        "recommendations": recommendations
    })

@app.route('/', methods=['GET'])
def index():
    return send_from_directory('static', 'index.html')

# === PRELOAD DATA ON SERVER START ===
if __name__ == '__main__':
    print("Preloading trail data...")
    # Initial load of trail data to warm up the cache
    geojson, station_cache, cache_valid = load_trail_data()
    if not cache_valid:
        print("Processing trails and creating cache...")
        _ = process_trails(geojson, station_cache)
        print("Trail cache created!")
    else:
        print("Using existing trail cache.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)