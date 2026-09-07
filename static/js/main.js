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

// These requests take 15-90 s, which feels broken without a message saying what
// is happening and a counter proving it still is. A skeleton in the shape of the
// coming result says it in place, and leaves the rest of the page usable - the
// full-screen overlay it replaces did neither.
let loadingTimer = null;

function showLoading(show = true, message = '') {
    const skeleton = document.getElementById('skeleton');
    clearInterval(loadingTimer);
    loadingTimer = null;
    if (!skeleton) return;

    if (!show) {
        skeleton.hidden = true;
        return;
    }
    const label = document.getElementById('loadingMessage');
    const elapsed = document.getElementById('loadingElapsed');
    if (message && label) label.textContent = message;
    const started = Date.now();
    if (elapsed) {
        elapsed.textContent = '0 s';
        loadingTimer = setInterval(() => {
            elapsed.textContent = Math.round((Date.now() - started) / 1000) + ' s';
        }, 1000);
    }
    skeleton.hidden = false;
    skeleton.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

// Model output is the only thing that ever reaches this function, and its result
// goes straight to innerHTML on five pages. Escaping here rather than at each
// call site means a page added later cannot forget to do it.
function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
}

function formatMarkdown(text) {
    text = escapeHtml(text);
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

    // Segmented controls are radio groups (so arrow keys work for free) that
    // mirror into the hidden #level / #length inputs every page's JS reads.
    document.querySelectorAll('.segmented input[data-mirror]').forEach(radio => {
        radio.addEventListener('change', () => {
            const mirror = document.getElementById(radio.dataset.mirror);
            if (mirror) mirror.value = radio.value;
        });
    });

    initWording();

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
// innerText is empty for anything inside a hidden tab panel, and every result
// section now lives in one - so the lesson download silently dropped whichever
// tab the learner had not opened. textContent always has the characters but
// loses every line break, which turns a walkthrough into one run-on paragraph.
// Walk the nodes instead and break at block boundaries, so the file is the same
// whichever tab happens to be on screen.
const BLOCK_TAGS = /^(P|DIV|LI|H[1-6]|PRE|UL|OL|TR|SECTION|ARTICLE|BLOCKQUOTE)$/;

function readBlockText(el) {
    if (!el) return '';
    let out = '';
    (function walk(node) {
        node.childNodes.forEach(child => {
            if (child.nodeType === Node.TEXT_NODE) {
                out += child.nodeValue;
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                if (child.tagName === 'BR') { out += '\n'; return; }
                walk(child);
                if (BLOCK_TAGS.test(child.tagName)) out += '\n';
            }
        });
    })(el);
    return out.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

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

    // The audio page's script is a result in its own right and was never exported.
    const script = readBlockText(document.getElementById('script'));
    if (script) out.push('## Script', '', script, '');

    const explanation = readBlockText(document.getElementById('explanation'));
    if (explanation) {
        out.push(code ? '## Walkthrough' : '## Explanation', '', explanation, '');
    }
    if (code) {
        out.push('## Code', '', '```python', code, '```', '');
    }

    const sections = document.querySelectorAll('.code-section');
    if (sections.length) {
        out.push('## Code, Section by Section', '');
        sections.forEach(sec => {
            const title = sec.querySelector('.code-section-title');
            out.push('### ' + (title ? readBlockText(title).replace(/\s+/g, ' ') : ''), '');
            const snippet = sec.querySelector('.code-section-code');
            if (snippet) out.push('```python', readBlockText(snippet), '```', '');
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
            // Quiz content lives in a panel, so this is the one action that does
            // switch tabs - otherwise the questions would land out of sight.
            if (card.dataset.tab) selectTab(card.dataset.tab);
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


// ===== Nav drawer =====
// Below 768 px the menu is a drawer over the page, so it has to behave like one:
// trap the focus inside it, close on Escape, and give the focus back.
document.addEventListener('DOMContentLoaded', () => {
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    if (!navToggle || !navMenu) return;

    let backdrop = null;

    const focusables = () => Array.from(
        navMenu.querySelectorAll('a[href], button:not([disabled]), input, select, textarea'));

    const setOpen = (open) => {
        navMenu.classList.toggle('active', open);
        navToggle.setAttribute('aria-expanded', String(open));
        navToggle.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
        if (open) {
            backdrop = document.createElement('div');
            backdrop.className = 'nav-backdrop';
            backdrop.addEventListener('click', () => setOpen(false));
            document.body.appendChild(backdrop);
            const first = focusables()[0];
            if (first) first.focus();
        } else {
            if (backdrop) { backdrop.remove(); backdrop = null; }
            navToggle.focus();
        }
    };

    navToggle.addEventListener('click', () => setOpen(!navMenu.classList.contains('active')));

    document.addEventListener('keydown', (e) => {
        if (!navMenu.classList.contains('active')) return;
        if (e.key === 'Escape') { setOpen(false); return; }
        if (e.key !== 'Tab') return;
        const items = focusables();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
});


// ===== Theme: light | dark | system =====
// Applied to <html> before first paint by an inline script in base.html; this
// only handles the toggle and remembers the choice.
document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('themeToggle');
    if (!button) return;
    const ORDER = ['system', 'light', 'dark'];

    const read = () => {
        try {
            const stored = localStorage.getItem('theme');
            return ORDER.includes(stored) ? stored : 'system';
        } catch (err) {
            return 'system';
        }
    };

    const apply = (theme) => {
        if (theme === 'system') document.documentElement.removeAttribute('data-theme');
        else document.documentElement.setAttribute('data-theme', theme);
        button.title = 'Theme: ' + theme;
        button.setAttribute('aria-label', 'Switch theme (currently ' + theme + ')');
    };

    apply(read());
    button.addEventListener('click', () => {
        const next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
        try { localStorage.setItem('theme', next); } catch (err) { /* private mode */ }
        apply(next);
        showToast('Theme: ' + next, 'info');
    });
});


// ===== Tabs =====
// Real tabs, not styled divs. Inactive panels keep their DOM - only the `hidden`
// attribute goes on - so a run started in one panel keeps streaming while
// another is open, and assistive tech and Ctrl+F both skip what is not shown.
function initTabs(root) {
    const list = root.querySelector('[role="tablist"]');
    if (!list) return;
    const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
    if (tabs.length < 2) { list.hidden = true; return; }

    const select = (tab, { focus = true, hash = true } = {}) => {
        tabs.forEach(t => {
            const on = t === tab;
            t.setAttribute('aria-selected', String(on));
            t.tabIndex = on ? 0 : -1;
            const panel = document.getElementById(t.getAttribute('aria-controls'));
            if (panel) panel.hidden = !on;
        });
        clearTabDot(tab.id);
        if (focus) tab.focus();
        if (hash) {
            const name = tab.dataset.tab;
            try { history.replaceState(null, '', '#' + name); } catch (err) { /* file:// */ }
        }
    };
    root._selectTab = select;

    tabs.forEach(tab => tab.addEventListener('click', () => select(tab)));

    list.addEventListener('keydown', (e) => {
        const i = tabs.indexOf(document.activeElement);
        if (i < 0) return;
        const keys = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: tabs.length - 1 };
        if (!(e.key in keys)) return;
        e.preventDefault();
        select(tabs[(keys[e.key] + tabs.length) % tabs.length]);
    });

    // Deep link and restore. An unknown hash falls back to the first tab.
    const wanted = decodeURIComponent(window.location.hash.slice(1));
    const target = tabs.find(t => t.dataset.tab === wanted) || tabs[0];
    select(target, { focus: false, hash: false });
}

// "Something arrived on a tab you are not looking at." Without this the learner
// never finds out the sections or the quiz appeared.
function markTabNew(tabId) {
    const tab = document.getElementById(tabId);
    if (!tab || tab.getAttribute('aria-selected') === 'true' || tab.querySelector('.tab-dot')) return;
    const dot = document.createElement('span');
    dot.className = 'tab-dot';
    const word = document.createElement('span');
    word.className = 'sr-only tab-dot-word';
    word.textContent = ' (new)';
    tab.append(dot, word);
}

function clearTabDot(tabId) {
    const tab = document.getElementById(tabId);
    if (!tab) return;
    tab.querySelectorAll('.tab-dot, .tab-dot-word').forEach(el => el.remove());
}

function selectTab(tabId) {
    const tab = document.getElementById(tabId);
    const root = tab && tab.closest('.tabs');
    if (root && root._selectTab) root._selectTab(tab, { focus: false });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tabs').forEach(initTabs);
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

    const addMessage = (role, text) => {
        const div = document.createElement('div');
        div.className = 'follow-up-msg ' + role;
        div.innerHTML = formatMarkdown(text);
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
            pending.innerHTML = formatMarkdown(data.answer);
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


// ===== Reading level =====
// How hard the sentences are, which is a different question from how much theory
// the reader wants - a learner can want Advanced material in plain English, or be
// reading in a second language. Stored per browser so it is set once rather than
// on every page, and sent with every generation request.
//
// The server re-validates the value against its own allow-list, so a tampered
// localStorage entry cannot smuggle text into a prompt.
const WORDINGS = ['Simple', 'Standard'];

function wordingPref() {
    try {
        const stored = localStorage.getItem('wording');
        return WORDINGS.includes(stored) ? stored : 'Standard';
    } catch (e) {
        return 'Standard';           // private mode, or storage blocked
    }
}

function setWordingPref(value) {
    if (!WORDINGS.includes(value)) return;
    try { localStorage.setItem('wording', value); } catch (e) { /* preference is not critical */ }
    // Keep every control on the page in step, including one in another section.
    document.querySelectorAll('input[data-wording]').forEach(radio => {
        radio.checked = radio.value === value;
    });
}

// Attached once, centrally, for the same reason the server gates auth in a
// before_request hook: a page added later cannot forget to opt in.
const _nativeFetch = window.fetch.bind(window);
window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = ((init && init.method) || 'GET').toUpperCase();
    if (method === 'POST' && url.indexOf('/api/') === 0 && init && typeof init.body === 'string') {
        try {
            const body = JSON.parse(init.body);
            if (body && typeof body === 'object' && !Array.isArray(body) && !('wording' in body)) {
                body.wording = wordingPref();
                init = Object.assign({}, init, { body: JSON.stringify(body) });
            }
        } catch (e) { /* not a JSON body - send it untouched */ }
    }
    return _nativeFetch(input, init);
};

function initWording() {
    const current = wordingPref();
    document.querySelectorAll('input[data-wording]').forEach(radio => {
        radio.checked = radio.value === current;
        radio.addEventListener('change', () => {
            if (radio.checked) setWordingPref(radio.value);
        });
    });
}

// Make functions globally available
window.showToast = showToast;
window.showLoading = showLoading;
window.copyToClipboard = copyToClipboard;
window.downloadTextFile = downloadTextFile;
window.formatMarkdown = formatMarkdown;
window.renderQuiz = renderQuiz;
window.rememberTopic = rememberTopic;
window.selectTab = selectTab;
window.markTabNew = markTabNew;
// The lesson download (below) needs whatever quiz is currently on screen.
window.getLastQuiz = () => lastQuiz;
window.wordingPref = wordingPref;
window.setWordingPref = setWordingPref;
