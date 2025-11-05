# Quick Start Guide

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. (Optional) Set Up API Keys

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_key_here
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_secret
```

**Note**: The app works without API keys! It will use:
- Rule-based AI advisor responses (no OpenAI needed)
- Sample loan data (no Plaid needed)

## 3. Start the Server

```bash
python app.py
```

## 4. Open in Browser

Navigate to: `http://localhost:5000`

## 5. Create an Account & Start Using

1. Click "Signup" to create an account
2. Login with your credentials
3. Explore the dashboard, repayment charts, and AI advisor!

## That's it! 🎉

The app is now running and ready to use. Check the main README.md for more detailed information.

