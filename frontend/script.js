// API Configuration
const API_BASE_URL = 'https://better-loanz-fintech-capstone.onrender.com/api';
let useBackend = false; // Will be set based on API availability
let authToken = null;
let currentUser = null;
let loans = [];
let chatHistory = [];
let repaymentChart = null; // Chart.js instance

// ============ API HELPERS ============

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    try {
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Request failed');
        }
        
        return await response.json();
    } catch (error) {
        // If API fails, fall back to standalone mode
        if (!useBackend) {
            throw error;
        }
        useBackend = false;
        throw error;
    }
}

// Check if backend is available
async function checkBackendAvailable() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: 'test', password: 'test' })
        });
        useBackend = true;
        console.log("Using backend");
        return true;
    } catch (error) {
        useBackend = false;
        console.log(error);
        return false;
    }
}

// ============ STANDALONE MODE FUNCTIONS ============

// Local storage keys
const STORAGE_USERS = 'betterloanz_users';
const STORAGE_LOANS = 'betterloanz_loans';
const STORAGE_CURRENT_USER = 'betterloanz_current_user';

function getLocalUsers() {
    const stored = localStorage.getItem(STORAGE_USERS);
    return stored ? JSON.parse(stored) : {};
}

function saveLocalUsers(users) {
    localStorage.setItem(STORAGE_USERS, JSON.stringify(users));
}

function getLocalLoans() {
    const user = localStorage.getItem(STORAGE_CURRENT_USER);
    if (!user) return [];
    const stored = localStorage.getItem(`${STORAGE_LOANS}_${user}`);
    return stored ? JSON.parse(stored) : getDefaultLoans();
}

function saveLocalLoans(loanList) {
    const user = localStorage.getItem(STORAGE_CURRENT_USER);
    if (user) {
        localStorage.setItem(`${STORAGE_LOANS}_${user}`, JSON.stringify(loanList));
    }
    loans = loanList;
    
}

function getDefaultLoans() {
    return [
    {
        id: 'LN-001',
        title: 'Auto Loan',
        balance: 25000,
        apr: 5.5,
        payment: 750,
        endDate: '2026-02-15'
    },
    {
        id: 'LN-002',
        title: 'Home Mortgage',
        balance: 85000,
        apr: 4.8,
        payment: 1200,
        endDate: '2035-02-20'
    },
    {
        id: 'LN-003',
        title: 'Personal Loan',
        balance: 15000,
        apr: 6.2,
        payment: 500,
        endDate: '2025-03-01'
    }
];
}

function calculateRepaymentLocal(principal, apr, payment, extraPayments) {
    const monthlyRate = apr / 100 / 12;
    const schedule = [];
    let remainingBalance = principal;
    let currentDate = new Date();
    let totalInterest = 0;
    const maxMonths = 600;
    let monthCount = 0;
    
    while (remainingBalance > 0.01 && monthCount < maxMonths) {
        const interestPayment = remainingBalance * monthlyRate;
        const principalPayment = Math.min(payment - interestPayment + extraPayments, remainingBalance);
        const totalPayment = payment + extraPayments;
        
        if (principalPayment < 0) break;
        
        schedule.push({
            date: new Date(currentDate.getTime()).toISOString().split('T')[0],
            principal: Math.round(remainingBalance * 100) / 100,
            interest: Math.round(interestPayment * 100) / 100,
            payment: Math.round(payment * 100) / 100,
            extraPayment: Math.round(extraPayments * 100) / 100,
            totalPayment: Math.round(totalPayment * 100) / 100,
            principalPayment: Math.round(principalPayment * 100) / 100
        });
        
        totalInterest += interestPayment;
        remainingBalance -= principalPayment;
        currentDate.setMonth(currentDate.getMonth() + 1);
        monthCount++;
    }
    
    return {
        schedule,
        totalInterest: Math.round(totalInterest * 100) / 100,
        totalPayments: schedule.length,
        payoffDate: schedule.length > 0 ? schedule[schedule.length - 1].date : null
    };
}

function generateAIResponse(userMessage, loans) {
    const lowerMessage = userMessage.toLowerCase();
    
    if (!loans || loans.length === 0) {
        return "You don't have any loans currently. I can help you understand loan management strategies, interest rates, and repayment plans for when you do have loans.";
    }
    
    const totalDebt = loans.reduce((sum, loan) => sum + loan.balance, 0);
    const avgApr = loans.reduce((sum, loan) => sum + loan.apr, 0) / loans.length;
    const monthlyPayment = loans.reduce((sum, loan) => sum + loan.payment, 0);
    
    if (lowerMessage.includes('interest') || lowerMessage.includes('rate') || lowerMessage.includes('apr')) {
        return `Your average interest rate is ${avgApr.toFixed(2)}%. Consider consolidating high-interest loans to reduce overall interest payments. The debt avalanche method (paying highest interest loans first) can save you money over time.`;
    } else if (lowerMessage.includes('payment') || lowerMessage.includes('pay')) {
        return `Your total monthly payment is ${formatCurrency(monthlyPayment)}. Making extra payments can significantly reduce your loan term and total interest paid. Even small extra payments can make a big difference over time.`;
    } else if (lowerMessage.includes('debt') || lowerMessage.includes('balance')) {
        return `Your total debt is ${formatCurrency(totalDebt)}. I recommend focusing on paying off the highest interest loans first (debt avalanche method) to save money over time. You can also consider the debt snowball method (paying smallest balances first) for psychological wins.`;
    } else if (lowerMessage.includes('refinanc')) {
        return "Refinancing can help you get a lower interest rate or reduce monthly payments. Consider refinancing if you can get an APR that's at least 0.5-1% lower than your current rate, and if you plan to stay in the loan long enough to recoup any fees.";
    } else if (lowerMessage.includes('extra') || lowerMessage.includes('additional')) {
        return "Extra payments can dramatically reduce your loan term and total interest. Apply extra payments to the principal of your highest interest loan first. Even $50-100 extra per month can save thousands in interest over the life of the loan.";
    } else if (lowerMessage.includes('help') || lowerMessage.includes('advice') || lowerMessage.includes('strategy')) {
        return "I can help you with loan management strategies, repayment plans, interest rate optimization, debt consolidation advice, refinancing opportunities, and extra payment strategies. What would you like to know more about?";
    } else {
        return "Thank you for your message. I'm here to help you manage your loans better. You can ask me about interest rates, payments, debt strategies, repayment plans, refinancing, or extra payment strategies.";
    }
}

// ============ VIEW MANAGEMENT ============

function showView(viewId) {
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(viewId).classList.add('active');
    
    if (viewId === 'dashboardView') {
        loadDashboard();
    } else if (viewId === 'repaymentView') {
        loadRepaymentChart();
    } else if (viewId === 'advisorView') {
        loadAdvisor();
    }
}

function showLogin() {
    showView('loginView');
}

function showSignup() {
    showView('signupView');
}

function showForgotPassword() {
    alert('Forgot Password: Please contact support at support@betterloanz.com');
}

// ============ AUTHENTICATION ============

async function handleLogin() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        alert('Please enter username and password');
                return;
            }
            
    if (useBackend) {
        try {
            const response = await apiRequest('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            authToken = response.token;
            currentUser = response.username;
            console.log(authToken);
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', currentUser);
            
            showView('dashboardView');
            return;
        } catch (error) {
            useBackend = false;
        }
    }
    
    // Standalone mode
    const users = getLocalUsers();
    if (users[username] && users[username].password === password) {
        authToken = "demo-token";
    currentUser = username;
        localStorage.setItem(STORAGE_CURRENT_USER, username);
    showView('dashboardView');
    } else {
        alert('Invalid username or password');
    }
}

async function handleSignup() {
    const username = document.getElementById('signup-username').value;
    const password = document.getElementById('signup-password').value;
    const confirm = document.getElementById('signup-confirm').value;
    
    if (!username || !password) {
        alert('Please fill in all fields');
                return;
            }
            
    if (password !== confirm) {
        alert('Passwords do not match');
        return;
    }
    
    if (useBackend) {
        try {
            const response = await apiRequest('/auth/signup', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            alert('Account created successfully! Please login.');
            showView('loginView');
            return;
        } catch (error) {
            useBackend = false;
        }
    }
    
    // Standalone mode
    const users = getLocalUsers();
    if (users[username]) {
        alert('Username already exists');
        return;
    }
    
    users[username] = { username, password, created_at: new Date().toISOString() };
    saveLocalUsers(users);
    alert('Account created successfully! Please login.');
    showView('loginView');
}

async function handleLogout() {
    if (useBackend) {
        try {
            await apiRequest('/auth/logout', { method: 'POST' });
        } catch (error) {
            // Ignore errors
        }
    }
    
    authToken = null;
    currentUser = null;
    loans = [];
    chatHistory = [];
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    localStorage.removeItem(STORAGE_CURRENT_USER);
    
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    showView('loginView');
}

// ============ DASHBOARD FUNCTIONS ============

async function loadDashboard() {
    updateUserName();
    await loadLoans();
    await loadMetrics();
    displayLoanList();
}

function updateUserName() {
    const nameElements = document.querySelectorAll('#userName, #repaymentUserName, #advisorUserName');
    nameElements.forEach(el => {
        if (el) el.textContent = currentUser || 'User';
    });
}

async function loadLoans() {
    if (useBackend) {
        try {
            const response = await apiRequest('/loans');
            loans = response.loans || [];
            return;
        } catch (error) {
            useBackend = false;
        }
    }
    
    // Standalone mode
    loans = getLocalLoans();
}

async function loadMetrics() {
    if (useBackend) {
        try {
            const response = await apiRequest('/metrics');
            const metrics = response;
            
            document.getElementById('totalDebt').textContent = formatCurrency(metrics.totalDebt);
            document.getElementById('avgInterest').textContent = metrics.avgInterest.toFixed(1) + '%';
            document.getElementById('monthlyPayment').textContent = formatCurrency(metrics.monthlyPayment);
            return;
        } catch (error) {
            useBackend = false;
        }
    }
    
    // Standalone mode
    if (loans.length === 0) {
        loans = getDefaultLoans();
    }
    
    const totalDebt = loans.reduce((sum, loan) => sum + loan.balance, 0);
    const avgInterest = loans.reduce((sum, loan) => sum + loan.apr, 0) / loans.length;
    const monthlyPayment = loans.reduce((sum, loan) => sum + loan.payment, 0);
    
    document.getElementById('totalDebt').textContent = formatCurrency(totalDebt);
    document.getElementById('avgInterest').textContent = avgInterest.toFixed(1) + '%';
    document.getElementById('monthlyPayment').textContent = formatCurrency(monthlyPayment);
}

function displayLoanList() {
    const loanList = document.getElementById('loanList');
    loanList.innerHTML = '';
    
    if (loans.length === 0) {
        loanList.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;">No loans found. Sample loans are displayed when in standalone mode.</div>';
        loans = getDefaultLoans();
        displayLoanList();
        return;
    }
    
    loans.forEach(loan => {
        const loanItem = document.createElement('div');
        loanItem.className = 'loan-item';
        loanItem.innerHTML = `
            <div class="loan-field loan-title">${loan.title}</div>
            <div class="loan-field loan-value">${formatCurrency(loan.balance)}</div>
            <div class="loan-field loan-value">${loan.apr}%</div>
            <div class="loan-field loan-value">${formatCurrency(loan.payment)}</div>
            <div class="loan-field">${formatDate(loan.endDate)}</div>
        `;
        loanList.appendChild(loanItem);
    });
}

// ============ REPAYMENT CHART FUNCTIONS ============

async function loadRepaymentChart() {
    updateUserName();
    await updateChart();
}

async function updateChart() {
    const principal = parseFloat(document.getElementById('principal').value) || 125000;
    const apr = parseFloat(document.getElementById('apr').value) || 5.2;
    const payment = parseFloat(document.getElementById('payment').value) || 2450;
    const extraPayments = parseFloat(document.getElementById('extraPayments').value) || 0;
    
    let schedule = [];
    
    if (useBackend) {
        try {
            const response = await apiRequest('/repayment/calculate', {
                method: 'POST',
                body: JSON.stringify({
                    principal,
                    apr,
                    payment,
                    extraPayments
                })
            });
            
            schedule = response.schedule;
        } catch (error) {
            useBackend = false;
            // Fall through to local calculation
        }
    }
    
    // Standalone mode or fallback
    if (schedule.length === 0) {
        const result = calculateRepaymentLocal(principal, apr, payment, extraPayments);
        schedule = result.schedule;
    }
    
    // Calculate and display first month interest
    if (schedule.length > 0) {
        document.getElementById('interest').value = formatCurrency(schedule[0].interest);
    }
    
    displayChartTable(schedule);
    drawRepaymentChart(schedule);
}

function displayChartTable(schedule) {
    const tableBody = document.getElementById('chartTableBody');
    tableBody.innerHTML = '';
    
    if (schedule.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">No schedule data available</td></tr>';
        return;
    }
    
    schedule.slice(0, 12).forEach(payment => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formatDate(payment.date)}</td>
            <td>${formatCurrency(payment.principal)}</td>
            <td>${formatCurrency(payment.interest)}</td>
            <td>${formatCurrency(payment.payment)}</td>
            <td>${formatCurrency(payment.extraPayment)}</td>
        `;
        tableBody.appendChild(row);
    });
}

function drawRepaymentChart(schedule) {
    const canvas = document.getElementById('repaymentChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Destroy existing chart if it exists
    if (repaymentChart) {
        repaymentChart.destroy();
    }
    
    if (!schedule || schedule.length === 0) {
        return;
    }
    
    // Prepare data for Chart.js
    const months = schedule.slice(0, 60).map((_, index) => `Month ${index + 1}`);
    const principalData = schedule.slice(0, 60).map(p => p.principal);
    const interestData = schedule.slice(0, 60).map(p => p.interest);
    
    // Create Chart.js chart
    repaymentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Principal Balance',
                    data: principalData,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Interest Payment',
                    data: interestData,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                },
                x: {
                    ticks: {
                        maxTicksLimit: 12
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// ============ AI ADVISOR FUNCTIONS ============

function loadAdvisor() {
    updateUserName();
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to UI
    addChatMessage(message, 'user');
    chatHistory.push({ role: 'user', content: message });
    input.value = '';
    
    // Show loading indicator
    const loadingId = addChatMessage('Thinking...', 'bot');
    
    let response = '';
    
    try {
        console.log(localStorage.getItem("authToken"))

        const apiResponse = await apiRequest('/advisor/chat', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem("authToken")}`
            },
            body: JSON.stringify({
                message,
                history: chatHistory.slice(-10)
            })
        });
        response = apiResponse.response;
    } catch (error) {
        useBackend = false;
        // Fall through to local response
        response = generateAIResponse(message, loans);
    }
    
    // Remove loading message
    const messagesContainer = document.getElementById('chatMessages');
    const loadingMsg = document.getElementById(loadingId);
    if (loadingMsg) {
        loadingMsg.remove();
    }
    
    // Add bot response
        addChatMessage(response, 'bot');
    chatHistory.push({ role: 'assistant', content: response });
}

function addChatMessage(text, sender) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    const messageId = 'msg-' + Date.now();
    messageDiv.id = messageId;
    messageDiv.className = `chat-message ${sender}`;
    messageDiv.innerHTML = `<p>${text}</p>`;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return messageId;
}

// ============ UTILITY FUNCTIONS ============

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// ============ INITIALIZATION ============

function checkAuth() {
    // Restore token and user if available
    authToken = localStorage.getItem('authToken');
    currentUser = localStorage.getItem('currentUser');

    if (authToken && currentUser) {
        useBackend = true; // Assume backend mode if token exists
        showView('dashboardView');
    } else {
        // Default to guest or login view
        currentUser = 'Guest User';
        showView('loginView');
    }
}

// ===== PLAID INTEGRATION START =====
async function initPlaidLink() {
    try {
        // Use the correct auth token key
        //const authToken = localStorage.getItem('authToken');
        if (!authToken) {
            alert('Please log in first.');
            return;
        }

        // Create a Plaid link token from backend
        const tokenRes = await fetch(`${API_BASE_URL}/plaid/create_link_token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (!tokenRes.ok) {
            const errText = await tokenRes.text();
            console.error('Plaid link token error:', errText);
            throw new Error(`Plaid create_link_token failed (${tokenRes.status})`);
        }

        const data = await tokenRes.json();
        if (!data.link_token) {
            throw new Error('No link_token returned from Plaid backend');
        }

        // Initialize Plaid Link with the token
        const handler = Plaid.create({
            token: data.link_token,
            onSuccess: async (public_token, metadata) => {
                console.log('Plaid link success:', metadata.institution);

                // Exchange the public token for an access token
                const exchangeRes = await fetch(`${API_BASE_URL}/plaid/exchange_public_token`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ public_token })
                });

                if (!exchangeRes.ok) {
                    const errText = await exchangeRes.text();
                    console.error('Plaid exchange error:', errText);
                    alert('Error exchanging Plaid public token.');
                    return;
                }

                // Fetch liabilities data (parsed loans)
                const liabRes = await fetch(`${API_BASE_URL}/plaid/get_liabilities`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });

                if (!liabRes.ok) {
                    const errText = await liabRes.text();
                    console.error('Plaid liabilities error:', errText);
                    alert('Error fetching liabilities.');
                    return;
                }

                const liabData = await liabRes.json();
                console.log('Parsed loans received:', liabData);
                displayPlaidLoans(liabData); 

            },
            onExit: (err, metadata) => {
                if (err) {
                    console.error('Plaid exited with error:', err);
                } else {
                    console.log('Plaid exited:', metadata.status);
                }
            }
        });

        handler.open();
    } catch (error) {
        console.error('Error initializing Plaid Link:', error);
        alert('Unable to initialize Plaid Link. Please check your backend connection.');
    }
}

function displayPlaidLoans(data) {
    const loanList = document.getElementById('loanList');
    loanList.innerHTML = '';

    const loans = data.loans;
    if (!loans || loans.length === 0) {
        loanList.innerHTML = '<p>No loans found.</p>';
        return;
    }

    saveLocalLoans(loans);
    loadMetrics();

    loans.forEach((loan) => {
        const div = document.createElement('div');
        div.className = 'loan-item';
        div.innerHTML = `
            <div class="loan-field loan-title">${loan.title || 'Unnamed Loan'}</div>
            <div class="loan-field loan-value">${formatCurrency(loan.balance)}</div>
            <div class="loan-field loan-value">${loan.apr ? loan.apr + '%' : 'N/A'}</div>
            <div class="loan-field loan-value">${formatCurrency(loan.payment || 0)}</div>
            <div class="loan-field">${loan.endDate ? formatDate(loan.endDate) : 'N/A'}</div>
        `;
        loanList.appendChild(div);
    });

    setTimeout(() => {
        loadMetrics();
    }, 50);
}

// Attach Plaid button event listener
document.addEventListener('DOMContentLoaded', () => {
    const linkBtn = document.getElementById('linkButton');
    if (linkBtn) linkBtn.addEventListener('click', initPlaidLink);
});
// ===== PLAID INTEGRATION END =====




// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});
