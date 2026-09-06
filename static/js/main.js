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

// Format plain text to HTML. The model is told to emit Title Case headings on
// their own line rather than markdown, so promote those to real headings and
// turn "- " lines into list items. No markdown symbols are processed.
const WALKTHROUGH_HEADINGS = [
    'What This Program Does', 'Packages And Imports', 'Step By Step Walkthrough',
    'Key Functions Explained', 'Things To Try'
];

function formatMarkdown(text) {
    const isHeading = line => {
        const t = line.trim();
        if (!t || t.length > 70) return false;
        if (WALKTHROUGH_HEADINGS.includes(t)) return true;
        // A short line with no terminal punctuation reads as a heading.
        return t.length < 60 && !/[.:,;?!]$/.test(t) && /^[A-Z]/.test(t) && t.split(/\s+/).length <= 8;
    };

    const out = [];
    let paragraph = [];
    let list = [];
    const flushParagraph = () => {
        if (paragraph.length) { out.push('<p>' + paragraph.join('<br>') + '</p>'); paragraph = []; }
    };
    const flushList = () => {
        if (list.length) { out.push('<ul>' + list.map(i => '<li>' + i + '</li>').join('') + '</ul>'); list = []; }
    };

    text.split('\n').forEach(line => {
        const t = line.trim();
        if (!t) { flushParagraph(); flushList(); return; }
        if (/^[-*]\s+/.test(t)) { flushParagraph(); list.push(t.replace(/^[-*]\s+/, '')); return; }
        flushList();
        if (isHeading(t) && !paragraph.length) { flushParagraph(); out.push('<h4>' + t + '</h4>'); return; }
        paragraph.push(t);
    });
    flushParagraph();
    flushList();
    return out.join('');
}

// Load saved API keys on page load
document.addEventListener('DOMContentLoaded', () => {
    // Mobile navigation toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle) {
        navToggle.addEventListener('click', () => {
            const open = navMenu.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', String(open));
        });
    }
    
    // API keys are now configured in .env file on the server
    // No need to load from localStorage
    
});


// Follow-up questions. The server is stateless: this page keeps the thread and
// resends it with whatever content is currently rendered on screen.
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('followUpForm');
    if (!form) return;
    const input = document.getElementById('followUpInput');
    const thread = document.getElementById('followUpThread');
    const button = form.querySelector('button');
    const history = [];
    const contextIds = ['explanation', 'codeContent', 'script', 'prompts'];
    const escapeHtml = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

    const addMessage = (role, text) => {
        const div = document.createElement('div');
        div.className = 'follow-up-msg ' + role;
        div.innerHTML = formatMarkdown(escapeHtml(text));
        thread.appendChild(div);
        div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return div;
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;
        const topicEl = document.getElementById('topic');
        const context = contextIds
            .map(id => document.getElementById(id))
            .filter(Boolean)
            .map(el => el.innerText || el.textContent || '')
            .join('\n\n');
        addMessage('user', question);
        input.value = '';
        button.disabled = true;
        const pending = addMessage('assistant', 'Thinking...');
        try {
            const response = await fetch('/api/follow-up', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: topicEl ? topicEl.value : '', context, history, question })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to answer');
            pending.innerHTML = formatMarkdown(escapeHtml(data.answer));
            history.push({ role: 'user', content: question });
            history.push({ role: 'assistant', content: data.answer });
        } catch (err) {
            pending.remove();
            showToast(err.message || 'An error occurred', 'error');
        } finally {
            button.disabled = false;
            input.focus();
        }
    });
});

// Make functions globally available
window.showToast = showToast;
window.showLoading = showLoading;
window.copyToClipboard = copyToClipboard;
window.downloadTextFile = downloadTextFile;
window.formatMarkdown = formatMarkdown;
