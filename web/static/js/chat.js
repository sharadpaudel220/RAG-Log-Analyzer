// Chat Interface JavaScript

let conversationHistory = [];
let analysisContext = null;
let prefillQuestion = null;
let currentSessionId = null;
let sessionData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    checkHealth();
    hydrateFromAnalysisContext();
    setInterval(checkHealth, 30000);
    
    analysisContext = sessionStorage.getItem('analysisChatContext');
    prefillQuestion = sessionStorage.getItem('analysisChatPrefill');
    currentSessionId = sessionStorage.getItem('analysisSessionId');
    
    if (currentSessionId) {
        await loadAnalysisSession(currentSessionId);
    } else if (analysisContext) {
        addMessage('assistant', 'I have your file analysis context loaded. Ask anything you want about the results.');
    }
    
    if (prefillQuestion) {
        const input = document.getElementById('chatInput');
        if (input) {
            input.value = prefillQuestion;
            input.focus();
            sessionStorage.removeItem('analysisChatPrefill');
        }
    }
});

async function loadAnalysisSession(sessionId) {
    try {
        const response = await fetch(`/api/analysis-sessions/${sessionId}`);
        const data = await response.json();
        
        if (data.success) {
            sessionData = data.session;
            const msg = `Loaded analysis session: ${sessionData.filename} (${sessionData.total_logs} logs, ${sessionData.anomalies_detected} anomalies detected)`;
            addMessage('assistant', msg);
        }
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

// Check system health
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        if (data.status === 'healthy') {
            statusDot.style.background = '#10b981';
            statusText.textContent = 'System Healthy';
        } else {
            statusDot.style.background = '#f59e0b';
            statusText.textContent = 'Initializing...';
        }
    } catch (error) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'System Error';
    }
}

// Send message
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    const analysisContext = sessionStorage.getItem('analysisChatContext');
    const includeContext = !!analysisContext;

    // Add user message to chat
    addMessage('user', message);
    input.value = '';
    
    // Show typing indicator
    const typingId = addTypingIndicator();
    
    try {
        const payloadMessage = includeContext
            ? `Context from uploaded log analysis:\n${analysisContext}\n\nUser question:\n${message}`
            : message;

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: payloadMessage })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator(typingId);
        
        if (data.success) {
            addMessage('assistant', data.response, data.is_anomaly);
        } else {
            addMessage('assistant', `Error: ${data.error}`, false);
        }

        if (includeContext) {
            sessionStorage.removeItem('analysisChatContext');
            sessionStorage.removeItem('analysisChatPrefill');
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage('assistant', `Error: ${error.message}`, false);
    }
}

// Add message to chat
function addMessage(role, content, isAnomaly = null) {
    const chatMessages = document.getElementById('chatMessages');
    const time = new Date().toLocaleTimeString();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatarIcon = role === 'assistant' ? 'fa-robot' : 'fa-user';
    const authorName = role === 'assistant' ? 'AI Assistant' : 'You';
    
    // Format content with markdown-like styling
    let formattedContent = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas ${avatarIcon}"></i>
        </div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">${authorName}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-text">
                ${formattedContent}
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add typing indicator
function addTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    const id = 'typing-' + Date.now();
    typingDiv.id = id;
    typingDiv.className = 'message assistant';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="message-text">
                <div class="loading"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

// Remove typing indicator
function removeTypingIndicator(id) {
    const typingDiv = document.getElementById(id);
    if (typingDiv) {
        typingDiv.remove();
    }
}

// Handle keyboard shortcuts
function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Use suggestion
function useSuggestion(text) {
    document.getElementById('chatInput').value = text;
    sendMessage();
}

// Clear chat
function clearChat() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = `
        <div class="message assistant">
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-author">AI Assistant</span>
                    <span class="message-time">Just now</span>
                </div>
                <div class="message-text">
                    <p>👋 Hello! I'm your Agentic RAG Log Analyzer assistant.</p>
                    <p>I can help you:</p>
                    <ul>
                        <li>Analyze system logs for anomalies</li>
                        <li>Explain error patterns and root causes</li>
                        <li>Provide recommendations for issues</li>
                        <li>Compare different detection systems</li>
                    </ul>
                    <p>Just paste a log entry or ask me a question!</p>
                </div>
            </div>
        </div>
    `;
}
