from flask import Flask, request, jsonify, render_template
import openai
import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

FIREBASE_CREDENTIAL_PATH = os.getenv("FIREBASE_CREDENTIAL_PATH", "firebase-service-account.json")

cred = credentials.Certificate(FIREBASE_CREDENTIAL_PATH)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://airline-chat-app-default-rtdb.firebaseio.com/' 
})

# Load environment variables
load_dotenv()

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

AIRLINE_API_BASE = os.getenv("AIRLINE_API_URL", "https://airline-api-m1vn.onrender.com")
AIRLINE_API_URL = f"{AIRLINE_API_BASE}/api/v1/"

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "doga")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "1234")

cached_token = {"value": None, "expires_at": None}

with open("systemPrompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_MESSAGE = f.read()
    
def log_to_firebase(user_message, system_response):
    try:
        ref = db.reference("/chat_logs")
        log = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_message": user_message,
            "system_response": system_response
        }
        ref.push(log)
    except Exception as e:
        print(f"Firebase log error: {e}")

# Get authorization token
def get_auth_token():
    now = datetime.utcnow()
    if cached_token["value"] and cached_token["expires_at"] and now < cached_token["expires_at"]:
        return cached_token["value"]

    login_url = f"{AIRLINE_API_URL}auth/login"
    payload = {
        "username": AUTH_USERNAME,
        "password": AUTH_PASSWORD
    }
    try:
        response = requests.post(login_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            print("Token:", token)

            if token:
                cached_token["value"] = token
                cached_token["expires_at"] = now + timedelta(minutes=50)
                return token
    except Exception as e:
        print(f"Failed to retrieve token: {e}")
    return None

# Make API request
def call_airline_api(endpoint, method="GET", params=None, json_data=None, use_auth=False):
    url = f"{AIRLINE_API_URL}{endpoint.lstrip('/')}"
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    if use_auth:
        token = get_auth_token()
        if not token:
            return {"error": "Failed to get token. Authentication failed."}
        headers["Authorization"] = f"Bearer {token}"  

    try:
        response = requests.request(
            method.upper(),
            url,
            params=params,
            json=json_data,
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"API Error {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        return {"error": str(e)}

# OpenAI call to interpret message
def parse_user_query(user_query):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": user_query}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {str(e)}")
        return None

# Response formatting functions
def format_flight_response(api_response):
    if not api_response or "flights" not in api_response or not api_response["flights"]:
        return "No flights found matching your criteria."

    formatted = []
    for flight in api_response["flights"]:
        info = [
            f"✈️ Flight No: {flight.get('flight_number', 'N/A')}",
            f"📍 From: {flight.get('airport_from', 'N/A')} → To: {flight.get('airport_to', 'N/A')}",
            f"🗓️ Date: {flight.get('date_from', 'N/A')} - {flight.get('date_to', 'N/A')}",
        ]
        formatted.append("\n".join(info))

    return "\n\n".join(formatted)

def format_buy_ticket_response(api_response):
    if "error" in api_response:
        return f"Ticket purchase failed: {api_response['error']}"
    return "✅ Ticket successfully purchased. Have a nice flight!"

def format_checkin_response(api_response):
    if "error" in api_response:
        return f"Check-in failed: {api_response['error']}"
    
    return (
        f"✅ Check-in successful!\n"
        f"💺 Seat Number: {api_response.get('seat_number', 'Not assigned')}\n"
        f"🛫 You're ready to fly!"
    )


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').strip()

    if not user_message:
        return jsonify({"response": "Please enter a valid message."})

    try:
        parsed = parse_user_query(user_message)
        if not parsed:
            return jsonify({"response": "Could not understand your request. Please rephrase it."})

        action = parsed["action"]
        params = parsed["parameters"]

        if action == "query_flight":
            query_params = {
                "date_from": params.get("date_from", datetime.now().strftime("%Y-%m-%d")),
                "date_to": params.get("date_to", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
                "airport_from": params["airport_from"],
                "airport_to": params["airport_to"],
                "number_of_people": params.get("number_of_people", 1)
            }
            result = call_airline_api("flight/query-flight", "GET", params=query_params)
            suggestion_message = "\n\n✈️ Would you like to book a ticket?\nYou can purchase it by specifying the date, flight number, and passenger name.\n\nExample: Book a ticket for flight 8 on 2025-05-20. My name is Doga."
            log_to_firebase(user_message, format_flight_response(result))
            return jsonify({
                "response": format_flight_response(result),
                "suggestion": suggestion_message,
                "raw_data": result
            })

        elif action == "buy_ticket":
            json_data = {
                "date": params["date"],
                "flight_number": params["flight_number"],
                "passenger_names": params["passenger_names"]
            }
            
            result = call_airline_api("ticket/buy-ticket", "POST", json_data=json_data, use_auth=True)
            checkin_suggestion_message = "\n\n🛂 Would you like to check in?\nYou can do so by specifying the flight number, date, and your name.\n\nExample: Check in for flight (flight number) on 2025-05-19. My name is Doga."
            log_to_firebase(user_message, format_buy_ticket_response(result))
            return jsonify({
                "response": format_buy_ticket_response(result),
                "suggestion": checkin_suggestion_message,
                "raw_data": result
            })

        elif action == "checkin":
            json_data = {
                "date": params["date"],
                "flight_number": params["flight_number"],
                "passenger_name": params["passenger_names"][0]
            }
            result = call_airline_api("checkin", "POST", json_data=json_data)
            log_to_firebase(user_message, format_checkin_response(result))
            return jsonify({
                "response": format_checkin_response(result),
                "raw_data": result
            })

        else:
            return jsonify({"response": "Unrecognized action type."})

    except Exception as e:
        return jsonify({"response": f"System error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
