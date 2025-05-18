# ✈️ Airline Chat Assistant

A conversational AI assistant built with Flask, OpenAI's GPT API, and Firebase.
It acts as a gateway layer that interprets user messages and interacts with an internal Airline API.
Users can query flights, buy tickets, and check in through a chat interface, while all actual service calls are securely routed through this gateway.

---

## 🔗 Source Code

GitHub Repository: [https://github.com/dogasac/flight-assistant]()

---

## 🎥 Demo Video

Watch a short presentation of this project:
[Demo](https://drive.google.com/file/d/1bqTEtJunSfjpPdrt_beh2jb3Jq0o81RV/view?usp=drive_link)

---

## 🧠 System Design & Assumptions

- **Natural Language Interface**: The system uses OpenAI's GPT model to parse user messages and determine actions (query flight, buy ticket, check-in).
- **Backend**: Flask app that connects with a RESTful airline API and logs chat interactions into Firebase.
- **State Handling**: JWT-based auth token is cached and refreshed every 50 minutes for authenticated endpoints.
- **Message Logging**: All conversations are saved into Firebase Realtime Database.
- **Modular API Call Logic**: Separated into helper functions to handle headers, auth, and error handling.

---

## ⚙️ Tech Stack

- Python (Flask)
- OpenAI GPT-3.5 API
- Firebase Realtime Database

---
