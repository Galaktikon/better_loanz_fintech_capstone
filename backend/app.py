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
    
    # In production, hash the password
    users_db[username] = {
        'username': username,
        'password': password,  # Hash this in production!
        'created_at': datetime.now().isoformat()
    }
    
    # Initialize user loans
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
    
    # Create session token (simple implementation)
    import secrets
    session_token = secrets.token_urlsafe(32)
    sessions_db[session_token] = {
        'username': username,
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'message': 'Login successful',
        'token': session_token,
        'username': username
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token in sessions_db:
        del sessions_db[token]
    return jsonify({'message': 'Logged out successfully'}), 200

# ============ HELPER FUNCTIONS ============

def get_user_from_token():
    """Extract username from session token"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    session = sessions_db.get(token)
    if not session:
        return None
    return session['username']

def require_auth():
    """Decorator helper to require authentication"""
    username = get_user_from_token()
    if not username:
        return None, jsonify({'error': 'Unauthorized'}), 401
    return username, None, None

# ============ LOAN ENDPOINTS ============

@app.route('/api/loans', methods=['GET'])
def get_loans():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    # Get loans from database or Plaid
    loans = loans_db.get(username, [])
    
    # If no loans exist, return sample data (in production, fetch from Plaid)
    if not loans:
        loans = [
            {
                'id': 'LN-001',
                'title': 'Auto Loan',
                'balance': 25000,
                'apr': 5.5,
                'payment': 750,
                'endDate': '2026-02-15',
                'type': 'AUTO'
            },
            {
                'id': 'LN-002',
                'title': 'Home Mortgage',
                'balance': 85000,
                'apr': 4.8,
                'payment': 1200,
                'endDate': '2035-02-20',
                'type': 'MORTGAGE'
            },
            {
                'id': 'LN-003',
                'title': 'Personal Loan',
                'balance': 15000,
                'apr': 6.2,
                'payment': 500,
                'endDate': '2025-03-01',
                'type': 'PERSONAL'
            }
        ]
        loans_db[username] = loans
    
    return jsonify({'loans': loans}), 200

@app.route('/api/loans', methods=['POST'])
def add_loan():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    data = request.get_json()
    loan = {
        'id': f"LN-{len(loans_db.get(username, [])) + 1:03d}",
        'title': data.get('title', 'New Loan'),
        'balance': float(data.get('balance', 0)),
        'apr': float(data.get('apr', 0)),
        'payment': float(data.get('payment', 0)),
        'endDate': data.get('endDate', ''),
        'type': data.get('type', 'PERSONAL')
    }
    
    if username not in loans_db:
        loans_db[username] = []
    loans_db[username].append(loan)
    
    return jsonify({'loan': loan}), 201

@app.route('/api/loans/<loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    loans = loans_db.get(username, [])
    loans_db[username] = [loan for loan in loans if loan['id'] != loan_id]
    
    return jsonify({'message': 'Loan deleted successfully'}), 200

@app.route('/api/loans/sync', methods=['POST'])
def sync_plaid_loans():
    """Sync loans from Plaid Liabilities API"""
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    # TODO: Implement Plaid integration
    # This would:
    # 1. Get user's Plaid access token
    # 2. Call Plaid Liabilities API
    # 3. Parse and normalize loan data
    # 4. Update loans_db[username]
    
    # For now, return a placeholder response
    return jsonify({
        'message': 'Plaid sync not yet implemented. Add PLAID_CLIENT_ID and PLAID_SECRET to enable.',
        'loans': loans_db.get(username, [])
    }), 200

# ============ METRICS ENDPOINTS ============

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    loans = loans_db.get(username, [])
    
    if not loans:
        # Return default metrics if no loans
        return jsonify({
            'totalDebt': 125000,
            'avgInterest': 5.4,
            'monthlyPayment': 2450,
            'totalInterest': 0,
            'estimatedPayoff': ''
        }), 200
    
    total_debt = sum(loan['balance'] for loan in loans)
    avg_interest = sum(loan['apr'] for loan in loans) / len(loans) if loans else 0
    monthly_payment = sum(loan['payment'] for loan in loans)
    
    return jsonify({
        'totalDebt': total_debt,
        'avgInterest': round(avg_interest, 2),
        'monthlyPayment': monthly_payment,
        'totalInterest': 0,  # Calculate based on repayment schedule
        'estimatedPayoff': ''
    }), 200

# ============ REPAYMENT CALCULATION ENDPOINTS ============

@app.route('/api/repayment/calculate', methods=['POST'])
def calculate_repayment():
    """Calculate repayment schedule for a loan"""
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    data = request.get_json()
    principal = float(data.get('principal', 125000))
    apr = float(data.get('apr', 5.2))
    payment = float(data.get('payment', 2450))
    extra_payments = float(data.get('extraPayments', 0))
    
    monthly_rate = apr / 100 / 12
    schedule = []
    remaining_balance = principal
    current_date = datetime.now()
    total_interest = 0
    
    max_months = 600  # 50 years max
    month_count = 0
    
    while remaining_balance > 0.01 and month_count < max_months:
        interest_payment = remaining_balance * monthly_rate
        principal_payment = min(payment - interest_payment + extra_payments, remaining_balance)
        total_payment = payment + extra_payments
        
        if principal_payment < 0:
            # Payment is too small to cover interest
            break
        
        schedule.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'principal': round(remaining_balance, 2),
            'interest': round(interest_payment, 2),
            'payment': round(payment, 2),
            'extraPayment': round(extra_payments, 2),
            'totalPayment': round(total_payment, 2),
            'principalPayment': round(principal_payment, 2)
        })
        
        total_interest += interest_payment
        remaining_balance -= principal_payment
        current_date += timedelta(days=30)  # Approximate month
        month_count += 1
    
    return jsonify({
        'schedule': schedule,
        'totalInterest': round(total_interest, 2),
        'totalPayments': len(schedule),
        'payoffDate': schedule[-1]['date'] if schedule else None
    }), 200

# ============ AI ADVISOR ENDPOINTS ============

@app.route('/api/advisor/chat', methods=['POST'])
def chat_with_advisor():
    """Chat with AI advisor powered by OpenAI"""
    username, error_response, status_code = require_auth()
    if error_response:
        return error_response, status_code
    
    data = request.get_json()
    user_message = data.get('message', '')
    chat_history = data.get('history', [])
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get user's loan data for context
    loans = loans_db.get(username, [])
    
    # Build context for AI
    context = build_advisor_context(loans)
    
    # Try to use OpenAI if available
    if openai_client and OPENAI_API_KEY:
        try:
            response = get_openai_response(user_message, chat_history, context)
            return jsonify({'response': response}), 200
        except Exception as e:
            print(f"OpenAI error: {e}")
            # Fallback to rule-based responses
            response = generate_rule_based_response(user_message, loans)
            return jsonify({'response': response}), 200
    else:
        # Use rule-based responses
        response = generate_rule_based_response(user_message, loans)
        return jsonify({'response': response}), 200

def build_advisor_context(loans):
    """Build context string from user's loan data"""
    if not loans:
        return "The user has no loans currently."
    
    context = f"The user has {len(loans)} loan(s):\n"
    total_debt = sum(loan['balance'] for loan in loans)
    avg_apr = sum(loan['apr'] for loan in loans) / len(loans)
    monthly_payment = sum(loan['payment'] for loan in loans)
    
    context += f"- Total debt: ${total_debt:,.2f}\n"
    context += f"- Average APR: {avg_apr:.2f}%\n"
    context += f"- Total monthly payment: ${monthly_payment:,.2f}\n\n"
    
    for loan in loans:
        context += f"- {loan['title']}: Balance ${loan['balance']:,.2f}, APR {loan['apr']:.2f}%, Payment ${loan['payment']:,.2f}/month\n"
    
    return context

def get_openai_response(user_message, chat_history, context):
    """Get response from OpenAI API"""
    messages = [
        {
            'role': 'system',
            'content': f"""You are a helpful AI Loan Advisor. You provide personalized financial advice about loans, debt management, and repayment strategies.

Current user loan information:
{context}

Provide clear, actionable advice. Be concise but informative. Focus on:
- Debt repayment strategies (avalanche vs snowball method)
- Interest rate optimization
- Refinancing opportunities
- Extra payment strategies
- Budgeting and financial planning"""
        }
    ]
    
    # Add chat history
    for msg in chat_history[-5:]:  # Last 5 messages for context
        messages.append({
            'role': msg.get('role', 'user'),
            'content': msg.get('content', '')
        })
    
    # Add current message
    messages.append({
        'role': 'user',
        'content': user_message
    })
    
    response = openai_client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=messages,
        max_tokens=300,
        temperature=0.7
    )
    
    return response.choices[0].message.content.strip()

def generate_rule_based_response(user_message, loans):
    """Generate rule-based response as fallback"""
    lower_message = user_message.lower()
    
    if not loans:
        return "You don't have any loans currently. I can help you understand loan management strategies, interest rates, and repayment plans for when you do have loans."
    
    total_debt = sum(loan['balance'] for loan in loans)
    avg_apr = sum(loan['apr'] for loan in loans) / len(loans)
    monthly_payment = sum(loan['payment'] for loan in loans)
    
    if 'interest' in lower_message or 'rate' in lower_message or 'apr' in lower_message:
        return f"Your average interest rate is {avg_apr:.2f}%. Consider consolidating high-interest loans to reduce overall interest payments. The debt avalanche method (paying highest interest loans first) can save you money over time."
    
    elif 'payment' in lower_message or 'pay' in lower_message:
        return f"Your total monthly payment is ${monthly_payment:,.2f}. Making extra payments can significantly reduce your loan term and total interest paid. Even small extra payments can make a big difference over time."
    
    elif 'debt' in lower_message or 'balance' in lower_message:
        return f"Your total debt is ${total_debt:,.2f}. I recommend focusing on paying off the highest interest loans first (debt avalanche method) to save money over time. You can also consider the debt snowball method (paying smallest balances first) for psychological wins."
    
    elif 'refinanc' in lower_message:
        return "Refinancing can help you get a lower interest rate or reduce monthly payments. Consider refinancing if you can get an APR that's at least 0.5-1% lower than your current rate, and if you plan to stay in the loan long enough to recoup any fees."
    
    elif 'extra' in lower_message or 'additional' in lower_message:
        return "Extra payments can dramatically reduce your loan term and total interest. Apply extra payments to the principal of your highest interest loan first. Even $50-100 extra per month can save thousands in interest over the life of the loan."
    
    elif 'help' in lower_message or 'advice' in lower_message or 'strategy' in lower_message:
        return "I can help you with loan management strategies, repayment plans, interest rate optimization, debt consolidation advice, refinancing opportunities, and extra payment strategies. What would you like to know more about?"
    
    else:
        return "Thank you for your message. I'm here to help you manage your loans better. You can ask me about interest rates, payments, debt strategies, repayment plans, refinancing, or extra payment strategies."

# ============ STATIC FILE SERVING ============

#@app.route('/')
#def index():
#    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from python backend")

# ============ RUN SERVER ============

if __name__ == '__main__':
    print("=" * 60)
    print("Better Loanz API Server")
    print("=" * 60)
    print(f"OpenAI Integration: {'Enabled' if OPENAI_API_KEY else 'Disabled (set OPENAI_API_KEY to enable)'}")
    print(f"Plaid Integration: {'Enabled' if PLAID_CLIENT_ID and PLAID_SECRET else 'Disabled (set PLAID_CLIENT_ID and PLAID_SECRET to enable)'}")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0" port=10000)

