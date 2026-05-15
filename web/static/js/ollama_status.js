// Ollama Status Management - Common script for all pages

// Use global ollamaAvailable from log_analyzer.js if available, otherwise initialize
if (typeof ollamaAvailable === 'undefined') {
    window.ollamaAvailable = false;
}

// Check Ollama status and update UI
async function updateOllamaStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        window.ollamaAvailable = data.ollama_available || false;
        window.llmProvider = data.provider || 'unknown';

        // Hide Ollama section for cloud providers
        const cloudProviders = ['groq', 'openai', 'anthropic', 'gemini'];
        const isCloudProvider = cloudProviders.includes(window.llmProvider.toLowerCase());

        const ollamaStatusElements = ['ollamaStatus', 'ollamaStatusSidebar'];
        ollamaStatusElements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (isCloudProvider) {
                    // Hide Ollama status for cloud providers
                    element.style.display = 'none';
                    return;
                } else {
                    element.style.display = 'flex';
                }
            }
        });

        if (isCloudProvider) {
            console.log(`Using cloud provider: ${window.llmProvider} - Ollama status hidden`);
            return;
        }

        // Update all Ollama status elements (already declared above)
        ollamaStatusElements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (window.ollamaAvailable) {
                    element.innerHTML = '<i class="fas fa-circle" style="color: #10b981; font-size: 0.75rem;"></i> Ollama Active (Click for details)';
                    element.style.color = '#10b981';
                } else {
                    element.innerHTML = '<i class="fas fa-circle" style="color: #ef4444; font-size: 0.75rem;"></i> Ollama Inactive (Click for details)';
                    element.style.color = '#ef4444';
                }
            }
        });
    } catch (error) {
        console.error('Ollama status check failed:', error);
        window.ollamaAvailable = false;

        // Only update if not using cloud provider
        const cloudProviders = ['groq', 'openai', 'anthropic', 'gemini'];
        if (window.llmProvider && cloudProviders.includes(window.llmProvider.toLowerCase())) {
            return;
        }

        // Update Ollama status elements
        ['ollamaStatus', 'ollamaStatusSidebar'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.style.display = 'flex';
                element.innerHTML = '<i class="fas fa-circle" style="color: #ef4444; font-size: 0.75rem;"></i> Ollama Inactive (Click for details)';
                element.style.color = '#ef4444';
            }
        });
    }
}

// Show Ollama details dialog
async function showOllamaDetails() {
    // Fetch Ollama model info
    let modelInfo = null;
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        if (data.ollama_available) {
            modelInfo = data.ollama_model || 'Unknown';
        }
    } catch (error) {
        console.error('Failed to fetch Ollama model info:', error);
    }

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3><i class="fas fa-brain"></i> Ollama Status</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom: 1rem;">
                    <strong>Status:</strong>
                    <span style="margin-left: 0.5rem; color: ${window.ollamaAvailable ? '#10b981' : '#f59e0b'};">
                        ${window.ollamaAvailable ? 'Running' : 'Not Running'}
                    </span>
                </div>
                <div style="margin-bottom: 1rem;">
                    <strong>Base URL:</strong>
                    <span style="margin-left: 0.5rem; color: var(--text-secondary);">http://localhost:11434</span>
                </div>
                ${window.ollamaAvailable && modelInfo ? `
                <div style="margin-bottom: 1rem;">
                    <strong>LLM Model:</strong>
                    <span style="margin-left: 0.5rem; color: var(--text-secondary);">${modelInfo}</span>
                </div>
                ` : ''}
                <div style="margin-bottom: 1rem;">
                    <strong>Purpose:</strong>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">
                        Ollama is required for Agentic RAG analysis to use the ReAct technique with local LLM models.
                    </p>
                </div>
                ${!window.ollamaAvailable ? `
                <div style="margin-bottom: 1rem; padding: 1rem; background: rgba(245, 158, 11, 0.1); border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.3);">
                    <strong style="color: #f59e0b;">How to start Ollama:</strong>
                    <ul style="color: var(--text-secondary); margin-top: 0.5rem; margin-left: 1.5rem;">
                        <li>Install Ollama from <a href="https://ollama.ai" target="_blank" style="color: var(--color-teal);">ollama.ai</a></li>
                        <li>Run: <code style="background: var(--glass-light); padding: 0.25rem 0.5rem; border-radius: 4px;">ollama serve</code></li>
                        <li>Ensure it's running on port 11434</li>
                    </ul>
                </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="this.closest('.modal').remove()">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Close on click outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateOllamaStatus();
    setInterval(updateOllamaStatus, 10000);
});
