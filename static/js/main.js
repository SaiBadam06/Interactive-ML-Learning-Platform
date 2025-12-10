// ===== Common Utility Functions =====

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Show/hide loading overlay
function showLoading(show = true) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('show');
    } else {
        overlay.classList.remove('show');
    }
}

// Get API key from .env file (server-side)
// Returns empty string so backend will use .env configuration
function getApiKey(inputId = 'apiKey') {
    // API keys are now configured in .env file
    // Return empty string so backend reads from environment
    return '';
}

// Get HF API key from .env file (server-side)
// Returns empty string so backend will use .env configuration
function getHFKey(inputId = 'hfKey') {
    // API keys are now configured in .env file
    // Return empty string so backend reads from environment
    return '';
}

// Copy text to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard!', 'success');
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showToast('Copied to clipboard!', 'success');
    }
}

// Download text as file
function downloadTextFile(content, filename) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('File downloaded!', 'success');
}

// Format text to HTML (no markdown processing)
function formatMarkdown(text) {
    // Simple text formatting - preserve line breaks and paragraphs
    // Do NOT process markdown symbols
    text = text.replace(/\n\n/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');

    return '<p>' + text + '</p>';
}

// Load saved API keys on page load
document.addEventListener('DOMContentLoaded', () => {
    // Mobile navigation toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
        });
    }
    
    // API keys are now configured in .env file on the server
    // No need to load from localStorage
    
    // Show/hide HF key based on backend selection
    const backendSelect = document.getElementById('backend');
    const hfKeyGroup = document.getElementById('hfKeyGroup');
    
    if (backendSelect && hfKeyGroup) {
        backendSelect.addEventListener('change', (e) => {
            if (e.target.value === 'HuggingFace Stable Diffusion') {
                hfKeyGroup.style.display = 'block';
            } else {
                hfKeyGroup.style.display = 'none';
            }
        });
    }
});

// Make functions globally available
window.showToast = showToast;
window.showLoading = showLoading;
window.getApiKey = getApiKey;
window.getHFKey = getHFKey;
window.copyToClipboard = copyToClipboard;
window.downloadTextFile = downloadTextFile;
window.formatMarkdown = formatMarkdown;
