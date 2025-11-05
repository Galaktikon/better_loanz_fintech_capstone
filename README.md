# Better Loanz - Intelligent Loan Management Platform

Better Loanz is an intelligent loan management and visualization platform designed to help users take control of their debt and make smarter financial decisions. The dashboard provides a clear overview of key loan metrics and a detailed list of all active loans, enabling users to easily track their financial standing.

## Features

- **Interactive Dashboard**: View total debt, average interest rates, and monthly payments at a glance
- **Loan Management**: Track multiple loans with detailed information (balance, APR, payments, end dates)
- **Repayment Calculator**: Interactive repayment chart that visualizes how extra payments or APR adjustments affect your repayment timeline
- **AI-Powered Advisor**: Get personalized financial insights and recommendations powered by OpenAI
- **Real-time Data**: Integration with Plaid Liabilities API for secure, real-time loan data retrieval (optional)
- **Beautiful Visualizations**: Powered by Chart.js for interactive, responsive charts

## Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Backend**: Python 3.x with Flask
- **Data Visualization**: Chart.js
- **AI Integration**: OpenAI API (GPT-3.5-turbo)
- **Financial Data**: Plaid Liabilities API (optional)

## Project Structure

```
my-web-app/
├── app.py                 # Flask backend server
├── index.html            # Main HTML file
├── script.js             # Frontend JavaScript
├── styles.css            # Stylesheet
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A modern web browser

### Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd my-web-app
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables (optional)**
   
   Create a `.env` file in the project root (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   PLAID_CLIENT_ID=your_plaid_client_id_here
   PLAID_SECRET=your_plaid_secret_here
   PLAID_ENV=sandbox
   ```
   
   **Note**: The application will work without API keys, but certain features will be limited:
   - Without OpenAI API key: AI advisor will use rule-based responses
   - Without Plaid credentials: Loan data will use sample/mock data

6. **Start the Flask server**
   ```bash
   python app.py
   ```

   The server will start on `http://localhost:5000`

7. **Open in your browser**
   
   Navigate to `http://localhost:5000` in your web browser.

## Usage

### Getting Started

1. **Sign Up**: Create a new account with a username and password
2. **Login**: Use your credentials to log in
3. **View Dashboard**: See your loan overview and metrics
4. **Explore Repayment Chart**: Navigate to the Repayment Chart view to visualize loan payoff scenarios
5. **Chat with AI Advisor**: Ask questions about your loans, repayment strategies, and financial planning

### Features Overview

#### Dashboard
- View total debt across all loans
- See average interest rate
- Monitor total monthly payments
- Browse detailed loan list

#### Repayment Chart
- Adjust principal, APR, payment amount, and extra payments
- See real-time calculations of repayment schedule
- Visualize principal balance and interest payments over time
- View detailed payment schedule table

#### AI Advisor
- Ask questions about your loans
- Get personalized repayment strategies
- Receive advice on debt consolidation
- Learn about refinancing opportunities

## API Endpoints

The backend provides the following REST API endpoints:

### Authentication
- `POST /api/auth/signup` - Create a new account
- `POST /api/auth/login` - Login and get session token
- `POST /api/auth/logout` - Logout and invalidate session

### Loans
- `GET /api/loans` - Get all loans for the current user
- `POST /api/loans` - Add a new loan
- `DELETE /api/loans/<loan_id>` - Delete a loan
- `POST /api/loans/sync` - Sync loans from Plaid (when implemented)

### Metrics
- `GET /api/metrics` - Get aggregated loan metrics

### Repayment
- `POST /api/repayment/calculate` - Calculate repayment schedule

### AI Advisor
- `POST /api/advisor/chat` - Chat with AI advisor

## Configuration

### OpenAI Integration

To enable the AI advisor with OpenAI:
1. Get an API key from [OpenAI](https://platform.openai.com/)
2. Add it to your `.env` file as `OPENAI_API_KEY`
3. Restart the Flask server

### Plaid Integration

To enable Plaid Liabilities integration:
1. Sign up for a [Plaid](https://plaid.com/) account
2. Get your Client ID and Secret from the Plaid Dashboard
3. Add them to your `.env` file
4. Restart the Flask server

**Note**: Plaid integration requires additional implementation. The current code provides the structure for integration.

## Development

### Running in Development Mode

The Flask server runs in debug mode by default when you run `python app.py`. This enables:
- Automatic reloading on code changes
- Detailed error messages
- Development-friendly logging

### Adding New Features

1. **Backend**: Add new routes in `app.py`
2. **Frontend**: Update `script.js` to call new endpoints
3. **UI**: Modify `index.html` and `styles.css` as needed

## Security Notes

⚠️ **Important**: This is a development/demo application. For production use:

- Implement proper password hashing (e.g., bcrypt)
- Use a real database instead of in-memory storage
- Add proper session management with secure tokens
- Implement HTTPS
- Add rate limiting for API endpoints
- Validate and sanitize all user inputs
- Use environment variables for all sensitive data
- Implement proper CORS policies

## Troubleshooting

### Server won't start
- Make sure Python 3.8+ is installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Ensure port 5000 is not in use by another application

### API calls failing
- Verify the Flask server is running on `http://localhost:5000`
- Check browser console for CORS errors
- Ensure you're logged in (check for auth token in localStorage)

### Chart not displaying
- Check browser console for JavaScript errors
- Verify Chart.js is loaded (check Network tab)
- Ensure repayment data is being calculated correctly

### AI Advisor not responding
- Check if OpenAI API key is set in `.env`
- Verify the API key is valid
- Check server logs for API errors
- The advisor will fall back to rule-based responses if OpenAI is unavailable

## License

This project is provided as-is for educational and demonstration purposes.

## Support

For issues or questions, please check the troubleshooting section or review the code comments for implementation details.

