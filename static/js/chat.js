// ===== Chat =====
// One thread replaces the four generator forms. Everything a lesson produces -
// a program, a recording, a diagram - arrives inside a turn rather than on its
// own page, so the learner never loses the conversation to get at it.
//
// Two rules run through the whole file:
//   1. Model output is untrusted. Prose goes through window.formatMarkdown,
//      which escapes its own input; everything else is createElement plus
//      textContent. Nothing here ever writes untrusted text to innerHTML.
//   2. Every localStorage access is wrapped. Private mode throws on read.

(function () {
    'use strict';

    const thread = document.getElementById('chatThread');
    if (!thread) return;                       // not the chat page

    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');
    const stopBtn = document.getElementById('chatStop');
    const emptyState = document.getElementById('chatEmpty');
    const modeSel = document.getElementById('chatMode');
    const levelSel = document.getElementById('chatLevel');
    const wordingSel = document.getElementById('chatWording');
    const rail = document.getElementById('chatRail');
    const railToggle = document.getElementById('railToggle');
    const railTopics = document.getElementById('railTopics');
    const newBtn = document.getElementById('newLessonBtn');

    const THREAD_KEY = 'chatThread';
    const RECENT_KEY = 'recentTopics';         // shared with main.js
    const MODES = ['explain', 'code', 'audio', 'images'];
    const LEVELS = ['Beginner', 'Intermediate', 'Advanced'];
    const WORDINGS = ['Simple', 'Standard'];
    const MAX_TURNS = 40;                      // what is kept across a reload
    const SEND_TURNS = 12;                     // what the server actually reads
    const SIMPLER = 'Say that again in simpler words.';

    let messages = [];                         // [{role, content}]
    let controller = null;                     // in-flight request, or null
    let live = null;                           // streaming buffers, or null
    let frame = 0;                             // pending rAF id
    let lastTopic = '';

    // ---------- storage -------------------------------------------------

    function pref(key, allowed, fallback) {
        try {
            const value = localStorage.getItem(key);
            return allowed.indexOf(value) >= 0 ? value : fallback;
        } catch (err) {
            return fallback;
        }
    }

    function savePref(key, value) {
        try { localStorage.setItem(key, value); } catch (err) { /* preference only */ }
    }

    function loadThread() {
        try {
            const parsed = JSON.parse(localStorage.getItem(THREAD_KEY) || '[]');
            if (!Array.isArray(parsed)) return [];
            return parsed
                .filter(m => m && (m.role === 'user' || m.role === 'assistant') &&
                             typeof m.content === 'string' && m.content.trim())
                .slice(-MAX_TURNS);
        } catch (err) {
            return [];
        }
    }

    function saveThread() {
        try {
            localStorage.setItem(THREAD_KEY, JSON.stringify(messages.slice(-MAX_TURNS)));
        } catch (err) {
            // A full quota must not cost the learner the conversation on screen.
        }
    }

    // Same shape main.js reads; it keeps its parser private, so this mirrors it.
    function recentTopics() {
        try {
            const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
            return Array.isArray(parsed)
                ? parsed.filter(t => typeof t === 'string' && t.trim()).slice(0, 8)
                : [];
        } catch (err) {
            return [];
        }
    }

    // ---------- small builders ------------------------------------------

    function makeBtn(label, className, onClick) {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = className;
        el.textContent = label;
        el.addEventListener('click', onClick);
        return el;
    }

    // Image and audio locations come back with the model's answer, so they are
    // treated as untrusted: anything that is not an ordinary media URL is dropped
    // rather than handed to an element that would follow it.
    function safeUrl(value) {
        const url = String(value == null ? '' : value).trim();
        return /^(https?:\/\/|data:image\/|\/[^/])/i.test(url) ? url : '';
    }

    function fileStem() {
        const stem = (lastTopic || 'lesson').replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '');
        return (stem || 'lesson').slice(0, 40);
    }

    // ---------- rail ------------------------------------------------------

    function renderRail() {
        const topics = recentTopics();
        railTopics.textContent = '';
        if (!topics.length) {
            const note = document.createElement('p');
            note.className = 'chat-rail-empty';
            note.textContent = 'Nothing yet. Ask about anything below.';
            railTopics.appendChild(note);
            return;
        }
        topics.forEach(topic => {
            railTopics.appendChild(makeBtn(topic, 'chat-rail-item', () => {
                fillComposer(topic);
                setRail(false);
            }));
        });
    }

    function setRail(open) {
        rail.classList.toggle('is-open', open);
        railToggle.setAttribute('aria-expanded', String(open));
    }

    // ---------- composer ---------------------------------------------------

    function growInput() {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    }

    function fillComposer(text) {
        input.value = String(text || '');
        growInput();
        input.focus();
    }

    function setBusy(busy) {
        sendBtn.hidden = busy;
        sendBtn.disabled = busy;
        stopBtn.hidden = !busy;
        thread.setAttribute('aria-busy', String(busy));
    }

    // ---------- turns -------------------------------------------------------

    function nearBottom() {
        return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 140;
    }

    function scrollToEnd() {
        thread.scrollTop = thread.scrollHeight;
    }

    function addUserTurn(text) {
        const turn = document.createElement('div');
        turn.className = 'chat-turn chat-turn-user';
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = text;
        turn.appendChild(bubble);
        thread.appendChild(turn);
        return turn;
    }

    // The assistant turn is full width and has no bubble: it is the page, not a
    // remark in it. The scratchpad sits above the answer, folded away, so it can
    // never be read as the answer itself.
    function addAssistantTurn() {
        const turn = document.createElement('div');
        turn.className = 'chat-turn chat-turn-assistant';

        const think = document.createElement('div');
        think.className = 'chat-thinking';
        think.hidden = true;

        const details = document.createElement('details');
        details.className = 'disclosure chat-thinking-box';
        const summary = document.createElement('summary');
        summary.textContent = 'Thinking';
        const body = document.createElement('div');
        body.className = 'disclosure-body chat-thinking-body';
        details.appendChild(summary);
        details.appendChild(body);

        const dismiss = makeBtn('Hide', 'btn btn-quiet chat-thinking-dismiss', () => think.remove());
        dismiss.setAttribute('aria-label', 'Hide the thinking notes');
        think.appendChild(details);
        think.appendChild(dismiss);

        const prose = document.createElement('div');
        prose.className = 'chat-prose';

        const status = document.createElement('p');
        status.className = 'run-status run-status-busy chat-status';
        status.hidden = true;

        const extras = document.createElement('div');
        extras.className = 'chat-extras';

        const actions = document.createElement('div');
        actions.className = 'chat-actions';

        turn.appendChild(think);
        turn.appendChild(prose);
        turn.appendChild(status);
        turn.appendChild(extras);
        turn.appendChild(actions);
        thread.appendChild(turn);

        return { turn, think, details, body, prose, status, extras, actions };
    }

    // Copy is useful; Simplify is the reason this page exists. It leads, and it
    // is the only primary button in a finished turn.
    function addActions(view, text) {
        view.actions.textContent = '';
        const simplify = makeBtn('Simplify', 'btn btn-primary chat-simplify', () => send(SIMPLER));
        simplify.title = 'Ask for the same answer in easier words';
        view.actions.appendChild(simplify);
        view.actions.appendChild(makeBtn('Copy', 'btn btn-quiet', () => window.copyToClipboard(text)));
    }

    function showError(view, message) {
        const line = document.createElement('p');
        line.className = 'run-status run-status-error chat-error';
        line.textContent = String(message || 'Something went wrong. Ask again in a moment.');
        view.extras.appendChild(line);
    }

    // ---------- rich parts on done ------------------------------------------

    // Same structure as the Code page, down to the gutter being a sibling of the
    // <pre>: the numbers stay out of anything Copy or Download picks up, and the
    // 21.6px line box keeps them level with the code.
    function codeBlock(source) {
        const code = String(source);
        const wrap = document.createElement('div');
        wrap.className = 'chat-code';

        const scroller = document.createElement('div');
        scroller.className = 'code-with-gutter';
        const gutter = document.createElement('div');
        gutter.className = 'code-gutter';
        const pre = document.createElement('pre');
        const codeEl = document.createElement('code');
        codeEl.className = 'language-python';
        codeEl.textContent = code;
        pre.appendChild(codeEl);
        scroller.appendChild(gutter);
        scroller.appendChild(pre);

        const lines = code.split('\n');
        if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop();
        lines.forEach((line, i) => {
            const num = makeBtn(String(i + 1), '', () =>
                fillComposer('Explain line ' + (i + 1) + ': ' + line.trim()));
            num.title = 'Ask about this line';
            gutter.appendChild(num);
        });

        if (window.Prism) window.Prism.highlightElement(codeEl);

        const row = document.createElement('div');
        row.className = 'card-actions chat-extra-actions';
        row.appendChild(makeBtn('Copy', 'btn btn-outline', () => window.copyToClipboard(code)));
        row.appendChild(makeBtn('Download .py', 'btn btn-outline', () =>
            window.downloadTextFile(code, fileStem() + '.py')));

        // Running it belongs to the Code page, which already has the runner.
        const open = document.createElement('a');
        open.className = 'btn btn-outline';
        open.href = '/code-generation?topic=' + encodeURIComponent(lastTopic || 'machine learning');
        open.textContent = 'Open in the Code page';
        row.appendChild(open);

        wrap.appendChild(scroller);
        wrap.appendChild(row);
        return wrap;
    }

    function audioBlock(url, name) {
        const src = safeUrl(url);
        if (!src) {
            const note = document.createElement('p');
            note.className = 'section-hint chat-note';
            note.textContent = 'The recording could not be loaded, but the script is above.';
            return note;
        }
        const wrap = document.createElement('div');
        wrap.className = 'audio-player chat-audio';

        const audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'none';
        audio.src = src;

        const row = document.createElement('div');
        row.className = 'card-actions chat-extra-actions';
        const download = document.createElement('a');
        download.className = 'btn btn-outline';
        download.href = src;
        download.setAttribute('download', String(name || fileStem() + '.mp3'));
        download.textContent = 'Download the recording';
        row.appendChild(download);

        wrap.appendChild(audio);
        wrap.appendChild(row);
        return wrap;
    }

    function imagesBlock(images, prompts) {
        const grid = document.createElement('div');
        grid.className = 'images-grid chat-images';
        images.forEach((raw, i) => {
            const src = safeUrl(raw);
            if (!src) return;
            const item = document.createElement('div');
            item.className = 'image-item';
            const img = document.createElement('img');
            img.src = src;
            img.loading = 'lazy';
            const caption = Array.isArray(prompts) && typeof prompts[i] === 'string'
                ? prompts[i].trim() : '';
            img.alt = caption || ('Diagram ' + (i + 1));
            item.appendChild(img);
            if (caption) {
                const text = document.createElement('p');
                text.className = 'prompt-text chat-caption';
                text.textContent = caption;
                item.appendChild(text);
            }
            grid.appendChild(item);
        });
        return grid;
    }

    function renderExtras(view, done) {
        if (done.code) view.extras.appendChild(codeBlock(done.code));
        if (done.audio) view.extras.appendChild(audioBlock(done.audio, done.audio_name));
        if (Array.isArray(done.images) && done.images.length) {
            view.extras.appendChild(imagesBlock(done.images, done.prompts));
        }
        if (done.note) {
            const note = document.createElement('p');
            note.className = 'section-hint chat-note';
            note.textContent = String(done.note);
            view.extras.appendChild(note);
        }
    }

    // ---------- streaming ---------------------------------------------------

    // Tokens arrive faster than anyone can read. Reformatting the accumulated
    // answer once a frame keeps the markdown live without re-running it - or
    // touching the rest of the thread - on every event.
    function flush(stick) {
        frame = 0;
        if (!live) return;
        if (live.thinkDirty) {
            live.view.body.textContent = live.thinking;
            live.thinkDirty = false;
        }
        if (live.proseDirty) {
            live.view.prose.innerHTML = window.formatMarkdown(live.text);
            live.proseDirty = false;
        }
        if (stick) scrollToEnd();
    }

    function paint() {
        if (frame) return;
        const stick = nearBottom();
        frame = requestAnimationFrame(() => flush(stick));
    }

    function handleEvent(event, view) {
        if (event.type === 'thinking') {
            live.thinking += String(event.text || '');
            live.thinkDirty = true;
            if (view.think.isConnected) {
                view.think.hidden = false;
                if (!view.details.dataset.settled) view.details.open = true;
            }
            paint();
        } else if (event.type === 'content') {
            // The scratchpad is not the answer: fold it the moment one starts.
            if (!view.details.dataset.settled) {
                view.details.dataset.settled = 'true';
                view.details.open = false;
            }
            live.text += String(event.text || '');
            live.proseDirty = true;
            paint();
        } else if (event.type === 'working') {
            view.status.hidden = false;
            view.status.textContent = String(event.label || 'Working') + '…';
        } else if (event.type === 'error') {
            showError(view, event.error);
        }
    }

    async function readStream(body, view) {
        const reader = body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let done = null;

        for (;;) {
            const chunk = await reader.read();
            if (chunk.done) break;
            buffer += decoder.decode(chunk.value, { stream: true });
            // A chunk can split mid-line, so only whole lines are parsed and the
            // remainder waits for the next read.
            let cut = buffer.indexOf('\n');
            while (cut >= 0) {
                const line = buffer.slice(0, cut).trim();
                buffer = buffer.slice(cut + 1);
                cut = buffer.indexOf('\n');
                if (line.slice(0, 5) !== 'data:') continue;
                let event;
                try {
                    event = JSON.parse(line.slice(5));
                } catch (err) {
                    continue;                  // half an event, or a keep-alive
                }
                if (!event || typeof event !== 'object') continue;
                if (event.type === 'done') { done = event; continue; }
                handleEvent(event, view);
            }
        }
        return done;
    }

    function finishTurn(view, done) {
        const stick = nearBottom();
        if (frame) { cancelAnimationFrame(frame); frame = 0; }

        let text = live ? live.text.trim() : '';
        // The fence is rendered below as a real listing, so it is not left in the
        // prose as well - formatMarkdown has no fence handling and would print it
        // as running paragraphs.
        if (done && done.code) text = text.replace(/```[\w+.-]*\r?\n?[\s\S]*?```/g, '').trim();

        view.prose.innerHTML = text ? window.formatMarkdown(text) : '';
        view.turn.classList.remove('is-streaming');
        view.status.hidden = true;
        if (view.think.isConnected) view.details.open = false;

        if (text) {
            messages.push({ role: 'assistant', content: text });
            if (messages.length > MAX_TURNS) messages = messages.slice(-MAX_TURNS);
            saveThread();
        }
        if (done) renderExtras(view, done);
        if (text) addActions(view, text);
        if (!text && !view.extras.childNodes.length) {
            showError(view, 'Nothing came back. Ask again in a moment.');
        }

        live = null;
        controller = null;
        setBusy(false);
        if (stick) scrollToEnd();
    }

    async function send(text) {
        if (controller) return;                // one request at a time
        const clean = String(text || '').trim();
        if (!clean) return;

        emptyState.hidden = true;
        messages.push({ role: 'user', content: clean });
        addUserTurn(clean);
        if (!lastTopic) {
            // The opening question is the lesson's topic; a follow-up is not.
            lastTopic = clean.slice(0, 120);
            window.rememberTopic(lastTopic);
            renderRail();
        }
        saveThread();

        input.value = '';
        growInput();
        setBusy(true);
        scrollToEnd();

        const view = addAssistantTurn();
        view.turn.classList.add('is-streaming');
        live = { view: view, text: '', thinking: '', proseDirty: false, thinkDirty: false };
        scrollToEnd();

        controller = new AbortController();
        let done = null;
        try {
            // main.js wraps fetch and adds the CSRF header and the reading level.
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: messages.slice(-SEND_TURNS),
                    mode: modeSel.value,
                    level: levelSel.value
                }),
                signal: controller.signal
            });
            // 400, 429 and 503 answer with plain JSON, not a stream.
            if (!res.ok || !res.body) {
                const payload = await res.json().catch(() => null);
                throw new Error((payload && payload.error) ||
                    'The lesson could not be fetched. Try again in a moment.');
            }
            done = await readStream(res.body, view);
        } catch (err) {
            if (!err || err.name !== 'AbortError') {
                showError(view, err && err.message);
            }
        }
        finishTurn(view, done);
    }

    // ---------- wiring ------------------------------------------------------

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        send(input.value);
    });

    input.addEventListener('input', growInput);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            send(input.value);
        }
    });

    stopBtn.addEventListener('click', () => {
        if (controller) controller.abort();
    });

    modeSel.value = pref('chatMode', MODES, 'explain');
    modeSel.addEventListener('change', () => savePref('chatMode', modeSel.value));

    levelSel.value = pref('chatLevel', LEVELS, 'Beginner');
    levelSel.addEventListener('change', () => savePref('chatLevel', levelSel.value));

    // The reading level is one preference for the whole site, so it goes through
    // main.js rather than getting a second key of its own.
    wordingSel.value = window.wordingPref ? window.wordingPref() : 'Standard';
    if (WORDINGS.indexOf(wordingSel.value) < 0) wordingSel.value = 'Standard';
    wordingSel.addEventListener('change', () => {
        if (window.setWordingPref) window.setWordingPref(wordingSel.value);
    });

    document.querySelectorAll('#chatSuggestions .chat-chip').forEach(chip => {
        chip.addEventListener('click', () => fillComposer(chip.textContent.trim()));
    });

    newBtn.addEventListener('click', () => {
        if (controller) controller.abort();
        messages = [];
        lastTopic = '';
        try { localStorage.removeItem(THREAD_KEY); } catch (err) { /* nothing kept */ }
        thread.textContent = '';
        thread.appendChild(emptyState);
        emptyState.hidden = false;
        setRail(false);
        input.focus();
    });

    // Below 900px the rail is an overlay. No backdrop and no focus trap: it must
    // never stand between the learner and the thread.
    railToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        setRail(!rail.classList.contains('is-open'));
    });
    document.addEventListener('click', (e) => {
        if (rail.classList.contains('is-open') &&
            !rail.contains(e.target) && !railToggle.contains(e.target)) setRail(false);
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && rail.classList.contains('is-open')) {
            setRail(false);
            railToggle.focus();
        }
    });

    // ---------- start -------------------------------------------------------

    renderRail();

    messages = loadThread();
    if (messages.length) {
        emptyState.hidden = true;
        const firstUser = messages.find(m => m.role === 'user');
        lastTopic = firstUser ? firstUser.content.slice(0, 120) : '';
        messages.forEach(m => {
            if (m.role === 'user') {
                addUserTurn(m.content);
            } else {
                const view = addAssistantTurn();
                view.think.remove();           // a scratchpad is not worth keeping
                view.prose.innerHTML = window.formatMarkdown(m.content);
                addActions(view, m.content);
            }
        });
        scrollToEnd();
    }

    const wanted = (new URLSearchParams(window.location.search).get('topic') || '').trim();
    if (wanted) fillComposer(wanted.slice(0, 300));
})();
