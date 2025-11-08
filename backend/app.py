from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import json
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for front-end communication

# In-memory storage (in production, use a database)
users_db = {}
loans_db = {}
sessions_db = {}

# Configuration
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID', '')
PLAID_SECRET = os.getenv('PLAID_SECRET', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Initialize OpenAI client (will be None if no key provided)
openai_client = None
try:
    import openai
    if OPENAI_API_KEY:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
except ImportError:
    pass


# ===== PLAID INTEGRATION START =====
# Install plaid: pip install plaid-python
from plaid.api import plaid_api
from plaid.model import *
from plaid import Configuration, ApiClient, PlaidEnvironments

PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # sandbox | development | production
PLAID_REDIRECT_URI = os.getenv("PLAID_REDIRECT_URI", None)

# Configure Plaid client
configuration = Configuration(
    host=PlaidEnvironments[PLAID_ENV],
    api_key={
        "clientId": PLAID_CLIENT_ID,
        "secret": PLAID_SECRET,
    }
)
api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

# Temporary access token storage (replace with DB in production)
plaid_access_tokens = {}
# ===== PLAID INTEGRATION END =====


# ============ AUTHENTICATION ENDPOINTS ============
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if username in users_db:
        return jsonify({'error': 'Username already exists'}), 400
    
    users_db[username] = {
        'username': username,
        'password': password,
        'created_at': datetime.now().isoformat()
    }
    loans_db[username] = []
    
    return jsonify({'message': 'Account created successfully', 'username': username}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = users_db.get(username)
    if not user or user['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    import secrets
    session_token = secrets.token_urlsafe(32)
    sessions_db[session_token] = {'username': username, 'created_at': datetime.now().isoformat()}
    
    return jsonify({'message': 'Login successful', 'token': session_token, 'username': username}), 200


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token in sessions_db:
        del sessions_db[token]
    return jsonify({'message': 'Logged out successfully'}), 200


# ============ HELPER FUNCTIONS ============
def get_user_from_token():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    session = sessions_db.get(token)
    if not session:
        return None
    return session['username']

def require_auth():
    username = get_user_from_token()
    if not username:
        return None, jsonify({'error': 'Unauthorized'}), 401
    return username, None, None


# ===== PLAID INTEGRATION START =====
@app.route('/api/plaid/create_link_token', methods=['POST'])
def create_link_token():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    try:
        request_body = LinkTokenCreateRequest(
            products=["liabilities"],
            client_name="Better Loanz",
            country_codes=["US"],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=username)
        )
        response = plaid_client.link_token_create(request_body)
        return jsonify(response.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/plaid/exchange_public_token', methods=['POST'])
def exchange_public_token():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    data = request.get_json()
    public_token = data.get("public_token")
    if not public_token:
        return jsonify({"error": "Missing public_token"}), 400
    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        access_token = exchange_response.to_dict().get("access_token")
        plaid_access_tokens[username] = access_token
        return jsonify({"message": "Plaid access token stored"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/plaid/get_liabilities', methods=['GET'])
def get_liabilities():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    access_token = plaid_access_tokens.get(username)
    if not access_token:
        return jsonify({"error": "No Plaid access token found"}), 400
    try:
        liabilities_request = LiabilitiesGetRequest(access_token=access_token)
        response = plaid_client.liabilities_get(liabilities_request)
        liabilities_data = response.to_dict()
        loans = parse_plaid_loans(liabilities_data)
        loans_db[username] = loans
        return jsonify(liabilities_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def parse_plaid_loans(data):
    """Convert Plaid liabilities data into Better Loanz format"""
    loans = []
    liabilities = data.get("liabilities", {})
    student = liabilities.get("student", [])
    mortgage = liabilities.get("mortgage", [])
    credit = liabilities.get("credit", [])
    for loan in student + mortgage + credit:
        account_id = loan.get("account_id", "Unknown")
        balance = loan.get("balance", {}).get("current", 0)
        apr = loan.get("interest_rate_percentage", 0)
        payment = loan.get("last_payment_amount", {}).get("amount", 0)
        next_due = loan.get("next_payment_due_date", "N/A")
        loans.append({
            "id": account_id,
            "title": f"Loan {account_id}",
            "balance": float(balance or 0),
            "apr": float(apr or 0),
            "payment": float(payment or 0),
            "endDate": next_due,
            "type": "PLAID"
        })
    return loans
# ===== PLAID INTEGRATION END =====


# ============ LOAN ENDPOINTS ============
@app.route('/api/loans/sync', methods=['POST'])
def sync_plaid_loans():
    """Sync loans from Plaid Liabilities API"""
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    access_token = plaid_access_tokens.get(username)
    if not access_token:
        return jsonify({'error': 'No Plaid access token found for user'}), 400
    try:
        liabilities_request = LiabilitiesGetRequest(access_token=access_token)
        response = plaid_client.liabilities_get(liabilities_request)
        liabilities_data = response.to_dict()
        loans = parse_plaid_loans(liabilities_data)
        loans_db[username] = loans
        return jsonify({'message': 'Loans synced successfully', 'loans': loans}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# (The rest of your endpoints — metrics, advisor, repayment — remain unchanged)

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from python backend")

if __name__ == '__main__':
    print("=" * 60)
    print("Better Loanz API Server")
    print("=" * 60)
    print(f"OpenAI Integration: {'Enabled' if OPENAI_API_KEY else 'Disabled'}")
    print(f"Plaid Integration: {'Enabled' if PLAID_CLIENT_ID and PLAID_SECRET else 'Disabled'}")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=10000)
