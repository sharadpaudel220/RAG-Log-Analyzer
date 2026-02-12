# Agentic RAG Log Analyzer - Web Application Guide

## 🚀 Application is Running!

**Access URLs:**
- **Dashboard**: http://localhost:5001
- **Chat Interface**: http://localhost:5001/chat

---

## ✨ Features

### 1. **Professional Dashboard**
- **Real-time Statistics**: Monitor total logs analyzed, anomalies detected, alerts generated, and knowledge base size
- **Interactive Log Analyzer**: Paste log entries and analyze them with 4 different systems:
  - Agentic RAG (Proposed)
  - Non-Agentic RAG
  - Rule-Based
  - Isolation Forest
- **Recent Alerts Feed**: View all recent anomaly detections with severity levels
- **Comparative Evaluation**: Run side-by-side comparison of all 4 systems
- **System Health Monitoring**: Real-time status indicator

### 2. **AI Chat Interface**
- **Conversational Analysis**: Chat with the AI assistant to analyze logs
- **Natural Language Queries**: Ask questions about log patterns and anomalies
- **Contextual Responses**: Get detailed explanations with reasoning steps
- **Quick Suggestions**: Pre-built prompts for common tasks

### 3. **Modern UI/UX**
- **Dark Theme**: Professional dark mode design
- **Responsive Layout**: Works on desktop and mobile
- **Real-time Updates**: Auto-refreshing statistics and alerts
- **Smooth Animations**: Polished transitions and interactions
- **Font Awesome Icons**: Beautiful iconography throughout

---

## 🎯 How to Use

### Dashboard Features:

1. **Analyze a Log Entry**:
   - Navigate to the "Log Analyzer" section
   - Paste your log entry in the text area
   - Select the system you want to use (Agentic RAG recommended)
   - Click "Analyze"
   - View detailed results including confidence, reasoning steps, and recommendations

2. **Run Comparative Evaluation**:
   - Click on "Evaluation" in the sidebar
   - Click "Run Comparative Evaluation"
   - Compare F1-Score, Precision, Recall, Accuracy, Latency, and Throughput across all systems

3. **Monitor Alerts**:
   - Recent alerts appear automatically in the "Recent Alerts" section
   - Each alert shows severity, timestamp, description, and analysis time
   - Alerts are color-coded by severity (High/Medium/Low)

### Chat Interface Features:

1. **Interactive Analysis**:
   - Type or paste a log entry
   - Ask questions like "Analyze this log: ERROR Connection timeout"
   - Get conversational responses with detailed analysis

2. **Quick Actions**:
   - Use suggestion chips for common queries
   - Press Enter to send messages (Shift+Enter for new line)
   - Clear chat history with the "Clear Chat" button

---

## 🔧 API Endpoints

The application exposes several REST API endpoints:

- `GET /api/health` - System health check
- `GET /api/stats` - Get system statistics
- `POST /api/analyze` - Analyze a single log entry
- `POST /api/chat` - Send chat message
- `GET /api/alerts` - Get recent alerts
- `POST /api/evaluate` - Run comparative evaluation

---

## 📊 System Architecture

```
Web Application (Flask)
├── Frontend (HTML/CSS/JS)
│   ├── Dashboard (Real-time stats, analyzer, alerts)
│   └── Chat Interface (Conversational AI)
├── Backend API
│   ├── Log Ingestion
│   ├── Preprocessing (Drain3)
│   ├── Knowledge Base (FAISS)
│   ├── Retrieval System
│   ├── LLM Engine (Ollama/Mistral)
│   ├── Agentic Controller (ReAct)
│   └── Alert Generator
└── Baseline Systems
    ├── Rule-Based
    ├── Isolation Forest
    └── Non-Agentic RAG
```

---

## 🎨 UI Components

### Color Scheme:
- **Primary**: Indigo (#6366f1)
- **Secondary**: Purple (#8b5cf6)
- **Success**: Green (#10b981)
- **Warning**: Yellow (#f59e0b)
- **Danger**: Red (#ef4444)
- **Info**: Blue (#3b82f6)

### Key Elements:
- **Stat Cards**: Real-time metrics with icons
- **Alert Items**: Color-coded severity badges
- **Message Bubbles**: Chat-style interface
- **Loading Indicators**: Smooth animations
- **Status Dots**: Pulsing health indicators

---

## 🔥 Example Usage

### Analyze a Log:
```
1. Go to Dashboard (http://localhost:5001)
2. Scroll to "Log Analyzer" section
3. Paste: "2024-01-15 10:23:47 ERROR [DataNode] Exception in receiveBlock"
4. Select "Agentic RAG (Proposed)"
5. Click "Analyze"
6. View results with confidence score and reasoning
```

### Chat with AI:
```
1. Go to Chat Interface (http://localhost:5001/chat)
2. Type: "Analyze this log: FATAL Out of memory error"
3. Press Enter
4. Get conversational analysis with recommendations
```

### Run Evaluation:
```
1. Go to Dashboard
2. Click "Evaluation" in sidebar
3. Click "Run Comparative Evaluation"
4. View comparison table with all metrics
```

---

## 📈 Performance

- **Dashboard Load Time**: < 1 second
- **Log Analysis**: 2-5 seconds (with Ollama/Mistral)
- **Chat Response**: 3-8 seconds (with LLM)
- **Stats Refresh**: Every 10 seconds
- **Health Check**: Every 30 seconds

---

## 🛠️ Technologies Used

### Backend:
- **Flask 3.1.2**: Web framework
- **Flask-CORS**: Cross-origin support
- **Python 3.9+**: Core language

### Frontend:
- **HTML5**: Structure
- **CSS3**: Modern styling with CSS Grid/Flexbox
- **Vanilla JavaScript**: Interactive features
- **Font Awesome 6.4**: Icons

### AI/ML:
- **Ollama**: LLM inference
- **Mistral 7B**: Language model
- **FAISS**: Vector search
- **Sentence Transformers**: Embeddings
- **Drain3**: Log parsing
- **Scikit-learn**: ML baselines

---

## 🔒 Security Notes

- **Development Server**: Current setup is for development only
- **Production Deployment**: Use Gunicorn or uWSGI for production
- **API Authentication**: Not implemented (add JWT/OAuth for production)
- **CORS**: Currently allows all origins (restrict in production)

---

## 🐛 Troubleshooting

### Port Already in Use:
```bash
# Change port in web_app.py (line 355)
app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)
```

### Ollama Not Connected:
```bash
# Start Ollama service
ollama serve

# Pull Mistral model
ollama pull mistral:7b-instruct
```

### System Not Initializing:
```bash
# Check logs
tail -f logs/web_app.log

# Verify dependencies
python3 -m pip install -r requirements.txt
```

---

## 📝 Future Enhancements

- [ ] User authentication and sessions
- [ ] File upload for batch log analysis
- [ ] Real-time log streaming
- [ ] Custom alert rules configuration
- [ ] Export reports to PDF/CSV
- [ ] Dark/Light theme toggle
- [ ] Multi-language support
- [ ] WebSocket for real-time updates
- [ ] Docker containerization
- [ ] Kubernetes deployment

---

## 🎓 For Your Dissertation

This web interface demonstrates:
- **Practical Application**: Real-world usability of the Agentic RAG system
- **User Experience**: Professional UI for system interaction
- **Comparative Analysis**: Side-by-side system evaluation
- **Explainability**: Transparent reasoning steps in chat interface
- **Scalability**: RESTful API design for future extensions

You can include screenshots of:
1. Dashboard with real-time statistics
2. Log analyzer with reasoning steps
3. Chat interface showing conversational analysis
4. Comparative evaluation results
5. Alert monitoring feed

---

## 📞 Support

For issues or questions:
- Check logs: `logs/web_app.log`
- Review API responses in browser DevTools
- Test endpoints with curl or Postman

---

**Enjoy your professional Agentic RAG Log Analyzer! 🚀**
