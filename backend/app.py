from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for frontend communication

# ===== In-memory storage (replace with database in production) =====
users_db = {}
loans_db = {}
sessions_db = {}
plaid_access_tokens = {}

# ===== Configuration =====
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.getenv("PLAID_SECRET", "")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # sandbox | development | production
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PLAID_REDIRECT_URI = os.getenv("PLAID_REDIRECT_URI")

# ===== Initialize OpenAI client =====
openai_client = None
try:
    import openai
    if OPENAI_API_KEY:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
except ImportError:
    pass

# ===== Initialize Plaid client (v9+) =====
from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid import ApiClient
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products

# Map environment to URL manually (PlaidEnvironments removed in v9)
PLAID_ENV_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

configuration = Configuration(
    host=PLAID_ENV_URLS.get(PLAID_ENV, "https://sandbox.plaid.com"),
    api_key={
        "clientId": PLAID_CLIENT_ID,
        "secret": PLAID_SECRET,
    },
)
api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

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

    session_token = secrets.token_urlsafe(32)
    sessions_db[session_token] = {
        'username': username,
        'created_at': datetime.now().isoformat()
    }

    return jsonify({'message': 'Login successful', 'token': session_token, 'username': username}), 200


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token in sessions_db:
        del sessions_db[token]
    return jsonify({'message': 'Logged out successfully'}), 200


# ============ AUTH HELPERS ============
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


# ===== PLAID INTEGRATION =====
@app.route('/api/plaid/create_link_token', methods=['POST'])
def create_link_token():
    # ========== DEMO MODE (commented auth check for demo) ==========
    username, error_response, status_code = require_auth()
    # Uncomment below line to enforce auth
    # if error_response:
    #     return error_response, status_code

    # If no user is logged in, use a default demo user ID
    if not username:
        username = "demo_user"

    try:
        request_body = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=username),
            client_name="Better Loanz",
            products=[Products.LIABILITIES],       # or the correct enum value
            country_codes=[CountryCode.US],
            language="en"
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


# ===== Helper: Parse Plaid Liabilities =====
def parse_plaid_loans(data):
    """Convert Plaid liabilities data into Better Loanz format"""
    loans = []
    liabilities = data.get("liabilities", {})
    for category in ["student", "mortgage", "credit"]:
        for loan in liabilities.get(category, []):
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


# ====== BASIC ENDPOINTS ======
@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Python backend")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory('.', path)


if __name__ == "__main__":
    print("=" * 60)
    print("Better Loanz API Server")
    print("=" * 60)
    print(f"OpenAI Integration: {'Enabled' if OPENAI_API_KEY else 'Disabled'}")
    print(f"Plaid Integration: {'Enabled' if PLAID_CLIENT_ID and PLAID_SECRET else 'Disabled'}")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
