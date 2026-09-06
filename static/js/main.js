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

// Show/hide loading overlay. These requests take 15-90 s, which feels broken
// without a message saying what is happening and a counter proving it still is.
let loadingTimer = null;

function showLoading(show = true, message = '') {
    const overlay = document.getElementById('loadingOverlay');
    const elapsed = document.getElementById('loadingElapsed');
    clearInterval(loadingTimer);
    loadingTimer = null;

    if (!show) {
        overlay.classList.remove('show');
        return;
    }
    if (message) document.getElementById('loadingMessage').textContent = message;
    const started = Date.now();
    elapsed.textContent = '0 s';
    loadingTimer = setInterval(() => {
        elapsed.textContent = Math.round((Date.now() - started) / 1000) + ' s';
    }, 1000);
    overlay.classList.add('show');
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

// ===== Recent topics, ?topic= prefill, cross-feature links =====
// Every localStorage access is wrapped: private mode and a full quota both
// throw, and losing the recents list must never break the page.
const RECENT_KEY = 'recentTopics';
const RECENT_MAX = 8;
const FEATURE_PAGES = [
    { key: 'text', path: '/text-explanation', label: 'Explain', icon: 'fa-book' },
    { key: 'code', path: '/code-generation', label: 'Code', icon: 'fa-code' },
    { key: 'audio', path: '/audio-learning', label: 'Audio', icon: 'fa-headphones' },
    { key: 'images', path: '/image-visualization', label: 'Images', icon: 'fa-image' },
];

function recentTopics() {
    try {
        const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
        return Array.isArray(parsed)
            ? parsed.filter(t => typeof t === 'string' && t.trim()).slice(0, RECENT_MAX)
            : [];
    } catch (err) {
        return [];
    }
}

function topicChip(href, text, icon) {
    const chip = document.createElement('a');
    chip.className = 'topic-chip';
    chip.href = href;
    if (icon) {
        const i = document.createElement('i');
        i.className = 'fas ' + icon;
        chip.appendChild(i);
    }
    chip.append(text);
    return chip;
}

function renderRecentTopics() {
    const box = document.getElementById('recentTopics');
    if (!box) return;
    const topics = recentTopics();
    box.textContent = '';
    box.hidden = !topics.length;
    if (!topics.length) return;
    const label = document.createElement('span');
    label.className = 'chips-label';
    label.textContent = 'Recently studied:';
    box.appendChild(label);
    // On Home the chips go to the text page; above a feature form they reload
    // that same page with the topic filled in.
    const target = box.dataset.target || window.location.pathname;
    topics.forEach(t => box.appendChild(topicChip(target + '?topic=' + encodeURIComponent(t), t)));
}

function renderContinueRow() {
    const row = document.getElementById('continueRow');
    if (!row) return;
    const topicEl = document.getElementById('topic');
    const topic = topicEl ? topicEl.value.trim() : '';
    row.textContent = '';
    row.hidden = !topic;
    if (!topic) return;
    const label = document.createElement('span');
    label.className = 'chips-label';
    label.textContent = 'Continue with this topic:';
    row.appendChild(label);
    FEATURE_PAGES
        .filter(page => page.key !== row.dataset.current)
        .forEach(page => row.appendChild(
            topicChip(page.path + '?topic=' + encodeURIComponent(topic), page.label, page.icon)));
}

// Called by each page after a successful generation.
function rememberTopic(topic) {
    const clean = String(topic || '').trim();
    if (clean) {
        try {
            const kept = recentTopics().filter(t => t.toLowerCase() !== clean.toLowerCase());
            localStorage.setItem(RECENT_KEY, JSON.stringify([clean, ...kept].slice(0, RECENT_MAX)));
        } catch (err) {
            // Recents are a convenience; a storage failure is not worth reporting.
        }
    }
    renderRecentTopics();
    renderContinueRow();
}

document.addEventListener('DOMContentLoaded', () => {
    // ?topic= prefills but never auto-submits: the learner may want to change
    // the depth or the level first.
    const topicInput = document.getElementById('topic');
    const topicParam = (new URLSearchParams(window.location.search).get('topic') || '').trim();
    if (topicInput && topicParam) {
        topicInput.value = topicParam.slice(0, 300);
        topicInput.dataset.prefilled = 'true';
        topicInput.focus();
    }
    renderRecentTopics();
    renderContinueRow();

    // Home hero: one topic box, four destinations.
    const quickTopic = document.getElementById('quickTopic');
    if (quickTopic) {
        document.querySelectorAll('#quickStart button[data-path]').forEach(button => {
            button.addEventListener('click', () => {
                const topic = quickTopic.value.trim();
                window.location.href = button.dataset.path +
                    (topic ? '?topic=' + encodeURIComponent(topic) : '');
            });
        });
    }
});


// ===== Download the whole lesson as Markdown =====
// Built from what is actually on the page rather than from saved state, so the
// file always matches what the learner just read - including their own edits to
// the code and the follow-up thread.
function buildLesson() {
    const value = id => { const el = document.getElementById(id); return el ? el.value : ''; };
    const topic = value('topic').trim() || 'Lesson';
    const level = value('level');
    const out = ['# ' + topic + (level ? ' (' + level + ')' : ''), ''];

    const editor = document.getElementById('codeEditor');
    const codeEl = document.getElementById('codeContent');
    const code = editor && editor.style.display === 'block'
        ? editor.value
        : (codeEl ? codeEl.textContent : '');

    const explanation = document.getElementById('explanation');
    if (explanation && explanation.innerText.trim()) {
        out.push(code ? '## Walkthrough' : '## Explanation', '', explanation.innerText.trim(), '');
    }
    if (code) {
        out.push('## Code', '', '```python', code, '```', '');
    }

    const sections = document.querySelectorAll('.code-section');
    if (sections.length) {
        out.push('## Code, Section by Section', '');
        sections.forEach(sec => {
            const title = sec.querySelector('.code-section-title');
            out.push('### ' + (title ? title.innerText.replace(/\s+/g, ' ').trim() : ''), '');
            const snippet = sec.querySelector('.code-section-code');
            if (snippet) out.push('```python', snippet.innerText, '```', '');
            const why = sec.querySelector('.code-section-explanation');
            if (why) out.push(why.textContent, '');
        });
    }

    const quiz = getLastQuiz();
    if (quiz && quiz.key_terms && quiz.key_terms.length) {
        out.push('## Key Terms', '');
        quiz.key_terms.forEach(t => out.push('- **' + t.term + '** - ' + t.definition));
        out.push('');
    }
    if (quiz && quiz.questions && quiz.questions.length) {
        out.push('## Check Your Understanding', '');
        quiz.questions.forEach((q, i) => {
            out.push((i + 1) + '. ' + q.question);
            q.options.forEach((o, oi) => out.push('   ' + 'ABCD'[oi] + ') ' + o));
            out.push('');
        });
    }

    const thread = document.querySelectorAll('.follow-up-msg');
    if (thread.length) {
        out.push('## Follow-up Questions', '');
        thread.forEach(msg => {
            out.push((msg.classList.contains('user') ? '**You:** ' : '**Tutor:** ') + msg.innerText.trim(), '');
        });
    }

    // Answers last so the questions can be attempted first.
    if (quiz && quiz.questions && quiz.questions.length) {
        out.push('## Answers', '');
        quiz.questions.forEach((q, i) => {
            out.push((i + 1) + '. ' + 'ABCD'[q.answer] + ') ' + q.options[q.answer] +
                     ' - ' + q.explanation);
        });
        out.push('');
    }

    return out.join('\n');
}

document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('downloadLessonBtn');
    if (!button) return;
    button.addEventListener('click', () => {
        const topicEl = document.getElementById('topic');
        const topic = (topicEl ? topicEl.value.trim() : '') || 'lesson';
        downloadTextFile(buildLesson(), topic.replace(/\s+/g, '_') + '_lesson.md');
    });
});


// ===== Check your understanding: quiz + key terms =====
// Everything here is built with DOM APIs and textContent: the questions are
// model output and must never reach innerHTML.
let lastQuiz = null;

function renderQuiz(container, data, onRegenerate) {
    container.textContent = '';
    lastQuiz = data;

    if (data.key_terms && data.key_terms.length) {
        const terms = document.createElement('div');
        terms.className = 'quiz-terms';
        data.key_terms.forEach(item => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'quiz-term';
            chip.textContent = item.term;
            const def = document.createElement('span');
            def.className = 'quiz-term-def';
            def.textContent = item.definition;
            def.hidden = true;
            chip.appendChild(def);
            chip.addEventListener('click', () => {
                def.hidden = !def.hidden;
                chip.classList.toggle('open', !def.hidden);
            });
            terms.appendChild(chip);
        });
        container.appendChild(terms);
    }

    const score = document.createElement('p');
    score.className = 'quiz-score';
    let answered = 0;
    let correct = 0;

    data.questions.forEach((q, qi) => {
        const wrap = document.createElement('div');
        wrap.className = 'quiz-q';

        const text = document.createElement('p');
        text.className = 'quiz-q-text';
        text.textContent = (qi + 1) + '. ' + q.question;
        wrap.appendChild(text);

        const why = document.createElement('p');
        why.className = 'quiz-explanation';
        why.textContent = q.explanation;
        why.hidden = true;

        const buttons = q.options.map((option, oi) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'quiz-option';
            button.textContent = option;
            button.addEventListener('click', () => {
                // One shot per question: answering locks it, which is what makes
                // the score mean anything.
                if (buttons.some(b => b.disabled)) return;
                answered += 1;
                if (oi === q.answer) correct += 1;
                buttons.forEach((b, bi) => {
                    b.disabled = true;
                    if (bi === q.answer) b.classList.add('correct');
                });
                if (oi !== q.answer) button.classList.add('incorrect');
                why.hidden = false;
                score.textContent = correct + ' / ' + answered +
                    (answered === data.questions.length ? ' - all answered' : '');
            });
            return button;
        });

        const options = document.createElement('div');
        options.className = 'quiz-options';
        buttons.forEach(b => options.appendChild(b));
        wrap.append(options, why);
        container.appendChild(wrap);
    });

    container.appendChild(score);

    if (onRegenerate) {
        const again = document.createElement('button');
        again.type = 'button';
        again.className = 'btn btn-secondary';
        again.textContent = 'Try another set';
        again.addEventListener('click', onRegenerate);
        container.appendChild(again);
    }
}

// One implementation for all three pages. The card says which elements make up
// the context via data-context-ids; Practice simply lists none.
document.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('quizCard');
    if (!card) return;
    const button = document.getElementById('quizGenerateBtn');
    const target = document.getElementById('quizContent');
    const contextIds = (card.dataset.contextIds || '').split(/\s+/).filter(Boolean);

    const generate = async () => {
        const topicEl = document.getElementById('topic');
        const topic = topicEl ? topicEl.value.trim() : '';
        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }
        const levelEl = document.getElementById('level');
        const context = contextIds
            .map(id => document.getElementById(id))
            .filter(Boolean)
            .map(el => el.innerText || el.textContent || '')
            .join('\n\n');

        const label = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Writing questions...';
        try {
            const response = await fetch('/api/quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, context, level: levelEl ? levelEl.value : 'Beginner' })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to generate the quiz');
            renderQuiz(target, data, generate);
            target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } catch (err) {
            showToast(err.message || 'An error occurred', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = label;
        }
    };

    // On Practice the button is the form's submit button, so Enter in the topic
    // field works; elsewhere the card's button stands on its own.
    if (button.form) {
        button.form.addEventListener('submit', (e) => { e.preventDefault(); generate(); });
    } else {
        button.addEventListener('click', generate);
    }
});


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

    // Anything that wants to ask a question - the line-number gutter, the
    // "Ask about this section" buttons - fills the input and submits the form,
    // so there is one code path and the learner sees their question in the box.
    window.askFollowUp = (question) => {
        input.value = question;
        document.getElementById('followUp').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        form.requestSubmit();
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;
        const topicEl = document.getElementById('topic');
        const levelEl = document.getElementById('level');
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
                body: JSON.stringify({
                    topic: topicEl ? topicEl.value : '', context, history, question,
                    level: levelEl ? levelEl.value : 'Beginner'
                })
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
window.renderQuiz = renderQuiz;
window.rememberTopic = rememberTopic;
// The lesson download (below) needs whatever quiz is currently on screen.
window.getLastQuiz = () => lastQuiz;
