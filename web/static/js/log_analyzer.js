// Log Analyzer JavaScript

let uploadedFile = null;
let analysisResults = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    setupFileUpload();
    setInterval(checkHealth, 30000);
});

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

// Setup file upload
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary-color)';
        uploadArea.style.background = 'rgba(99, 102, 241, 0.1)';
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--border-color)';
        uploadArea.style.background = 'var(--dark-bg)';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--border-color)';
        uploadArea.style.background = 'var(--dark-bg)';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

// Handle file selection
function handleFile(file) {
    const allowedTypes = ['.log', '.txt', '.json', '.csv'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(fileExt)) {
        alert('Invalid file type. Please upload .log, .txt, .json, or .csv files.');
        return;
    }
    
    uploadedFile = file;
    
    // Show file info
    document.getElementById('uploadArea').style.display = 'none';
    document.getElementById('uploadInfo').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
}

// Remove file
function removeFile() {
    uploadedFile = null;
    document.getElementById('uploadArea').style.display = 'flex';
    document.getElementById('uploadInfo').style.display = 'none';
    document.getElementById('fileInput').value = '';
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

// Analyze manual log
async function analyzeManualLog() {
    const logInput = document.getElementById('logInput').value.trim();
    const systemType = document.getElementById('systemSelect').value;
    
    if (!logInput) {
        alert('Please enter a log entry to analyze');
        return;
    }
    
    showProgress('Analyzing log entry...');
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                log_content: logInput,
                system: systemType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displaySingleResult(data);
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error analyzing log: ' + error.message);
    } finally {
        hideProgress();
    }
}

// Analyze uploaded file
async function analyzeFile() {
    if (!uploadedFile) {
        alert('Please upload a log file first');
        return;
    }
    
    const systemType = document.getElementById('batchSystemSelect').value;
    const maxLogs = parseInt(document.getElementById('maxLogs').value);
    
    showProgress('Uploading and analyzing file...');
    
    try {
        // Upload file
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('source_id', 'file-upload');
        formData.append('source_type', 'application');
        formData.append('system_type', systemType);
        formData.append('max_logs', maxLogs);
        
        updateProgress(20, 'Uploading file...');
        
        const uploadResponse = await fetch('/api/analyze-file', {
            method: 'POST',
            body: formData
        });
        
        const uploadData = await uploadResponse.json();
        
        if (uploadData.success) {
            updateProgress(100, 'Analysis complete!');
            displayBatchResults(uploadData);
        } else {
            alert('Error: ' + uploadData.error);
        }
    } catch (error) {
        alert('Error analyzing file: ' + error.message);
    } finally {
        setTimeout(hideProgress, 1000);
    }
}

// Display single result
function displaySingleResult(data) {
    const resultsSection = document.getElementById('resultsSection');
    const reportSummary = document.getElementById('reportSummary');
    const reportDetails = document.getElementById('reportDetails');
    
    analysisResults = data;
    
    // Summary
    reportSummary.innerHTML = `
        <div class="summary-cards">
            <div class="summary-card ${data.is_anomaly ? 'anomaly' : 'normal'}">
                <div class="summary-icon">
                    <i class="fas fa-${data.is_anomaly ? 'exclamation-triangle' : 'check-circle'}"></i>
                </div>
                <div class="summary-content">
                    <h4>${data.is_anomaly ? 'Anomaly Detected' : 'Normal Log'}</h4>
                    <p>Confidence: ${(data.confidence * 100).toFixed(2)}%</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="summary-content">
                    <h4>Analysis Time</h4>
                    <p>${data.analysis_time.toFixed(3)}s</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon">
                    <i class="fas fa-layer-group"></i>
                </div>
                <div class="summary-content">
                    <h4>System Used</h4>
                    <p>${document.getElementById('systemSelect').selectedOptions[0].text}</p>
                </div>
            </div>
        </div>
    `;
    
    // Details
    let detailsHTML = '<div class="report-section">';
    detailsHTML += '<h4>Log Details</h4>';
    detailsHTML += '<div class="detail-grid">';
    detailsHTML += `<div class="detail-item"><strong>Template:</strong> ${data.parsed_log.template || 'N/A'}</div>`;
    detailsHTML += `<div class="detail-item"><strong>Severity:</strong> <span class="badge ${data.parsed_log.severity.toLowerCase()}">${data.parsed_log.severity}</span></div>`;
    detailsHTML += `<div class="detail-item"><strong>Component:</strong> ${data.parsed_log.component || 'N/A'}</div>`;
    detailsHTML += '</div></div>';
    
    if (data.alert && data.alert.description) {
        detailsHTML += '<div class="report-section">';
        detailsHTML += '<h4>Alert Information</h4>';
        detailsHTML += `<div class="alert-box ${data.alert.severity.toLowerCase()}">${data.alert.description}</div>`;
        detailsHTML += '</div>';
    }
    
    if (data.reasoning_steps && data.reasoning_steps.length > 0) {
        detailsHTML += '<div class="report-section">';
        detailsHTML += '<h4>Reasoning Chain</h4>';
        detailsHTML += '<ol class="reasoning-list">';
        data.reasoning_steps.forEach(step => {
            detailsHTML += `<li>${step}</li>`;
        });
        detailsHTML += '</ol></div>';
    }
    
    reportDetails.innerHTML = detailsHTML;
    
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Display batch results
function displayBatchResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const reportSummary = document.getElementById('reportSummary');
    const reportDetails = document.getElementById('reportDetails');
    const anomalyList = document.getElementById('anomalyList');
    
    analysisResults = data;
    
    // Summary
    const anomalyRate = (data.anomalies_detected / data.total_logs * 100).toFixed(2);
    reportSummary.innerHTML = `
        <div class="summary-cards">
            <div class="summary-card">
                <div class="summary-icon blue">
                    <i class="fas fa-file-alt"></i>
                </div>
                <div class="summary-content">
                    <h4>Total Logs</h4>
                    <p>${data.total_logs}</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon red">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="summary-content">
                    <h4>Anomalies Detected</h4>
                    <p>${data.anomalies_detected}</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon yellow">
                    <i class="fas fa-percentage"></i>
                </div>
                <div class="summary-content">
                    <h4>Anomaly Rate</h4>
                    <p>${anomalyRate}%</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon green">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="summary-content">
                    <h4>Total Time</h4>
                    <p>${data.total_time.toFixed(2)}s</p>
                </div>
            </div>
        </div>
    `;
    
    // Details
    reportDetails.innerHTML = `
        <div class="report-section">
            <h4>Analysis Summary</h4>
            <div class="detail-grid">
                <div class="detail-item"><strong>File:</strong> ${uploadedFile.name}</div>
                <div class="detail-item"><strong>System:</strong> ${document.getElementById('batchSystemSelect').selectedOptions[0].text}</div>
                <div class="detail-item"><strong>Avg Time/Log:</strong> ${(data.total_time / data.total_logs).toFixed(3)}s</div>
                <div class="detail-item"><strong>Throughput:</strong> ${(data.total_logs / data.total_time).toFixed(2)} logs/s</div>
            </div>
        </div>
    `;
    
    // Anomaly list
    if (data.anomalies && data.anomalies.length > 0) {
        let anomalyHTML = '<div class="report-section"><h4>Detected Anomalies</h4>';
        data.anomalies.forEach((anomaly, index) => {
            anomalyHTML += `
                <div class="anomaly-item">
                    <div class="anomaly-header">
                        <span class="anomaly-number">#${index + 1}</span>
                        <span class="badge ${anomaly.alert.severity.toLowerCase()}">${anomaly.alert.severity}</span>
                        <span class="anomaly-confidence">Confidence: ${(anomaly.confidence * 100).toFixed(2)}%</span>
                    </div>
                    <div class="anomaly-content">
                        <strong>Log:</strong> ${anomaly.log.content || anomaly.log.message}
                    </div>
                    <div class="anomaly-description">
                        ${anomaly.alert.description || anomaly.alert.explanation}
                    </div>
                </div>
            `;
        });
        anomalyHTML += '</div>';
        anomalyList.innerHTML = anomalyHTML;
    }
    
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Progress functions
function showProgress(message) {
    document.getElementById('progressSection').style.display = 'block';
    updateProgress(0, message);
}

function updateProgress(percent, message) {
    document.getElementById('progressFill').style.width = percent + '%';
    document.getElementById('progressText').textContent = message;
}

function hideProgress() {
    document.getElementById('progressSection').style.display = 'none';
}

// Download report
function downloadReport() {
    if (!analysisResults) return;
    
    const report = JSON.stringify(analysisResults, null, 2);
    const blob = new Blob([report], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analysis_report_${Date.now()}.json`;
    a.click();
}

// Export JSON
function exportJSON() {
    downloadReport();
}

// Clear analysis
function clearAnalysis() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('logInput').value = '';
    analysisResults = null;
}
