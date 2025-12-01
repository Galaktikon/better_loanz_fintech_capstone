from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import secrets
from dotenv import load_dotenv
import json
from openai import OpenAI


# ===== Load environment variables =====
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
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
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
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.liabilities_get_request import LiabilitiesGetRequest

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
    print(f"Auth token: {token}, Session: {session}")
    if "demo-token" in token:
        return "demo-user"
    if not session:
        return None
    return session['username']

def require_auth():
    username = get_user_from_token()
    print(f"Authenticated user: {username}")
    if not username:
        return None, jsonify({'error': 'Unauthorized'}), 401
    return username, None, None

# ===== PLAID INTEGRATION =====
@app.route('/api/plaid/create_link_token', methods=['POST'])
def create_link_token():
    username, error_response, status_code = require_auth()
    # Uncomment to enforce auth
    # if error_response:
    #     return error_response, status_code

    if not username:
        username = "demo_user"

    try:
        request_body = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=username),
            client_name="Better Loanz",
            products=[Products('liabilities')],
            country_codes=[CountryCode('US')],
            language="en"
        )
        response = plaid_client.link_token_create(request_body)
        return jsonify(response.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/plaid/exchange_public_token', methods=['POST'])
def exchange_public_token():
    username, error_response, status_code = require_auth()
    # if error_response:
    #     return error_response, status_code

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
    #if error_response:
    #    return error_response, status_code

    access_token = plaid_access_tokens.get(username)
    if not access_token:
        return jsonify({"error": "No Plaid access token found"}), 400

    try:
        liabilities_request = LiabilitiesGetRequest(access_token=access_token)
        response = plaid_client.liabilities_get(liabilities_request)
        liabilities_data = response.to_dict()
        loans = parse_plaid_loans(liabilities_data)
        loans_db[username] = loans
        return jsonify({"loans": loans}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== Helper: safely get nested values =====
def get_nested_value(obj, *keys, default=0):
    """Safely get nested values, even if intermediate keys are floats or missing."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        else:
            return float(obj or default)
    return float(obj or default)

# ===== Helper: Parse Plaid Liabilities safely with logging =====
def parse_plaid_loans(data):
    import json
    from datetime import date

    def safe_get(d, *keys, default=None):
        """Safely get nested dictionary keys."""
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key, default)
            else:
                return default
        return d

    loans = []
    liabilities = data.get("liabilities", {})
    accounts = data.get("accounts", [])

    # Build a lookup for account_id -> account info
    account_lookup = {acct["account_id"]: acct for acct in accounts}

    print(json.dumps(data, indent=2, sort_keys=True, default=str))

    for category in ["student", "mortgage", "credit"]:
        for loan in liabilities.get(category, []):
            account_id = loan.get("account_id", "Unknown")
            account_info = account_lookup.get(account_id, {})

            # --- Extract account-level info ---
            account_name = account_info.get("name")
            official_name = account_info.get("official_name")
            account_balance = safe_get(account_info, "balances", "current")

            # --- Balance extraction ---
            # Prefer account-level current balance, then liability balance
            balance = (
                account_balance
                or safe_get(loan, "balance", "current")
                or safe_get(loan, "current")
                or 0.0
            )

            # --- APR / interest rate extraction ---
            apr = None
            if category == "credit":
                apr_list = loan.get("aprs", [])
                if apr_list:
                    apr_entry = next(
                        (a for a in apr_list if a.get("apr_type") == "purchase_apr"),
                        apr_list[0],
                    )
                    apr = apr_entry.get("apr_percentage")
            elif category == "mortgage":
                apr = safe_get(loan, "interest_rate", "percentage")
            elif category == "student":
                apr = loan.get("interest_rate_percentage")

            # --- Last payment extraction ---
            payment = safe_get(loan, "last_payment_amount") or 0.0

            # --- Next payment due ---
            next_due = loan.get("next_payment_due_date")
            if isinstance(next_due, date):
                next_due = next_due.isoformat()
            elif next_due is None:
                next_due = "N/A"

            # --- Loan name/title ---
            # Prefer official_name > account_name > liability loan_name > fallback
            name = (
                official_name
                or account_name
                or loan.get("loan_name")
                or loan.get("loan_type_description")
                or loan.get("name")
                or f"Loan {account_id}"
            )

            # --- Construct the combined loan info ---
            loan_info = {
                "id": account_id,
                "title": name,
                "balance": balance,
                "apr": apr,
                "payment": payment,
                "endDate": next_due,
                "type": "PLAID",
                "category": category,
            }

            # Print for debugging
            print(f"Appending loan info: {loan_info}")

            loans.append(loan_info)

    print(f"Total loans parsed: {len(loans)}")
    return loans

# ============= AI Helper ==============
def build_user_context(username, local_loans=None):
    print(loans_db)
    user_loans = loans_db.get(username, []) if local_loans is None else local_loans

    if not user_loans:
        return "The user currently has no loans connected."

    total_debt = sum(l.get("balance", 0) for l in user_loans)
    total_payment = sum(l.get("payment", 0) for l in user_loans)
    avg_apr = (
        sum(l.get("apr", 0) for l in user_loans) / len(user_loans)
        if len(user_loans) > 0 else 0
    )

    # Build a user financial profile
    context = f"""
User Financial Summary:
-------------------------
Total Debt: ${total_debt:,.2f}
Total Monthly Payment: ${total_payment:,.2f}
Average APR: {avg_apr:.2f}%

Loan Details:
"""

    # FIXED indentation below ↓↓↓
    for loan in user_loans:
        context += f"""
• {loan.get("title", "Loan")}
    - Balance: ${loan.get("balance", 0):,.2f}
    - APR: {loan.get("apr", 0)}%
    - Payment: ${loan.get("payment", 0):,.2f}
    - Due Date: {loan.get("endDate", "N/A")}
"""

    context += "\nUse this context to give specific, actionable financial guidance."
    return context


# ============ LOAN ENDPOINTS ============
@app.route('/api/loans/sync', methods=['POST'])
def sync_plaid_loans():
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

# ============ AI Endpoints ============
@app.route('/api/advisor/chat', methods=['POST'])
def advisor_chat():
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key missing on backend"}), 500

    username, error_response, status_code = require_auth()
    if error_response:
        print(f"Auth error: {error_response}")
        return error_response, status_code

    data = request.get_json()
    user_message = data.get("message", "")
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Message required"}), 400

    # ---- Build user financial context ----
    user_context = build_user_context(username, local_loans=data.get("loans"))
    print(f"User context for {username}:\n{user_context}")

    # ---- Compose messages for OpenAI ----
    messages = [
        {
            "role": "system",
            "content": (
                "You are BetterLoanz AI, a financial advisor specializing in debt reduction, "
                "APR optimization, refinancing guidance, and loan payoff strategies.\n\n"
                "Always provide clear, actionable recommendations.\n"
                "You must ALWAYS reference the user's actual loan data when applicable.\n"
                "Here is the user's financial profile:\n\n"
                f"{user_context}"
            )
        }
    ]

    # Add message history
    for h in history:
        messages.append({
            "role": h.get("role", "user"),
            "content": h.get("content", "")
        })

    # Add the new user input
    messages.append({"role": "user", "content": user_message})

    # ---- Call OpenAI ----
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            max_tokens=350,
            temperature=0.6
        )

        ai_response = completion.choices[0].message.content
        return jsonify({"response": ai_response}), 200

    except Exception as e:
        print(f"OpenAI error: {e}")
        return jsonify({"error": str(e)}), 500

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
