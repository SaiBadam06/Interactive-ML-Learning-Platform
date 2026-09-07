document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('codeForm');
    const outputSection = document.getElementById('outputSection');
    const explanationDiv = document.getElementById('explanation');
    const codeContent = document.getElementById('codeContent');
    const dependenciesSection = document.getElementById('dependenciesSection');
    const dependenciesDiv = document.getElementById('dependencies');
    const copyCodeBtn = document.getElementById('copyCodeBtn');
    const downloadCodeBtn = document.getElementById('downloadCodeBtn');
    const runBtn = document.getElementById('runCodeBtn');
    const stopBtn = document.getElementById('stopCodeBtn');
    const editBtn = document.getElementById('editCodeBtn');
    const codeScroller = document.getElementById('codeScroller');
    const codeEditor = document.getElementById('codeEditor');
    const runOutput = document.getElementById('runOutput');
    const runStatus = document.getElementById('runStatus');
    const runText = document.getElementById('runText');
    const runFigures = document.getElementById('runFigures');

    let currentCode = '';
    let currentExplanation = '';
    let currentTopic = '';

    // ===== Run the program in the browser (Pyodide in a worker) =====
    const RUN_LIMIT_MS = 60000;
    let worker = null;
    let runTimer = null;
    let editing = false;

    // Run/Copy/Download all act on what the learner can see right now, which in
    // edit mode is the textarea, not the last generated program.
    const codeText = () => (editing ? codeEditor.value : currentCode);

    // The gutter is a sibling of the <pre>, not part of it: keeping the numbers
    // out of the code element means Copy, Download and Run never pick them up.
    const codeGutter = document.getElementById('codeGutter');

    function renderGutter(text) {
        codeGutter.textContent = '';
        const lines = text.split('\n');
        // A trailing newline is not a line anyone can click on.
        if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop();
        lines.forEach((line, i) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = String(i + 1);
            button.title = 'Ask about this line';
            button.addEventListener('click', () => {
                if (window.askFollowUp) {
                    window.askFollowUp('Explain line ' + (i + 1) + ': ' + line.trim());
                }
            });
            codeGutter.appendChild(button);
        });
    }

    function setCode(text) {
        currentCode = text;
        codeContent.textContent = text;
        if (window.Prism) Prism.highlightElement(codeContent);
        renderGutter(text);
        const meta = document.getElementById('resultsMeta');
        if (meta) {
            const level = document.getElementById('level');
            const lines = text.replace(/\n$/, '').split('\n').length;
            meta.textContent = (level ? level.value + ' · ' : '') + lines + ' lines';
        }
    }

    // A run started in Program keeps streaming while another tab is open, so the
    // tab itself has to say it is still going.
    function setRunIndicator(on) {
        const tab = document.getElementById('tab-program');
        if (!tab) return;
        const existing = tab.querySelector('.spinner');
        if (on && !existing) tab.appendChild(Object.assign(document.createElement('span'), { className: 'spinner' }));
        if (!on && existing) existing.remove();
    }

    function setStatus(text, kind) {
        runStatus.textContent = text;
        runStatus.className = 'run-status' + (kind ? ' run-status-' + kind : '');
    }

    function appendOutput(text, isError) {
        const span = document.createElement('span');
        if (isError) span.className = 'run-err';
        span.textContent = text;
        runText.appendChild(span);
        runText.scrollTop = runText.scrollHeight;
    }

    function runFinished() {
        clearTimeout(runTimer);
        runTimer = null;
        runBtn.disabled = false;
        stopBtn.style.display = 'none';
        setRunIndicator(false);
    }

    // Killing the worker is the only way to stop Python: it cannot be
    // interrupted from JavaScript. The next Run boots a fresh one.
    function killWorker(message) {
        if (worker) { worker.terminate(); worker = null; }
        runFinished();
        if (message) setStatus(message, 'error');
    }

    function onWorkerMessage(e) {
        const msg = e.data || {};
        if (msg.type === 'status') {
            setStatus(msg.text, 'busy');
        } else if (msg.type === 'stdout' || msg.type === 'stderr') {
            appendOutput(msg.text, msg.type === 'stderr');
        } else if (msg.type === 'images') {
            msg.images.forEach((b64, i) => {
                const img = document.createElement('img');
                img.src = 'data:image/png;base64,' + b64;
                img.alt = 'Figure ' + (i + 1);
                runFigures.appendChild(img);
            });
        } else if (msg.type === 'done') {
            runFinished();
            setStatus('Finished in ' + (msg.ms / 1000).toFixed(1) + ' s', 'ok');
        } else if (msg.type === 'error') {
            runFinished();
            appendOutput(msg.text + '\n', true);
            setStatus('Error', 'error');
        }
    }

    if (runBtn) {
        runBtn.addEventListener('click', () => {
            const code = codeText();
            if (!code.trim()) return;
            runOutput.style.display = 'block';
            runText.textContent = '';
            runFigures.textContent = '';
            setStatus('Starting...', 'busy');
            runBtn.disabled = true;
            stopBtn.style.display = '';
            setRunIndicator(true);
            if (!worker) {
                worker = new Worker(runBtn.dataset.worker, { type: 'module' });
                worker.onmessage = onWorkerMessage;
                // Pyodide comes from a CDN; with no network the page still works,
                // only Run fails, and it must say so rather than hang.
                worker.onerror = () => killWorker('Error - the Python runtime could not be loaded (needs internet access).');
            }
            runTimer = setTimeout(
                () => killWorker('Stopped after 60 s - the program may have an infinite loop.'),
                RUN_LIMIT_MS);
            worker.postMessage({ code });
        });

        stopBtn.addEventListener('click', () => killWorker('Stopped.'));

        editBtn.addEventListener('click', () => {
            if (!editing) {
                codeEditor.value = currentCode;
                codeEditor.style.height = Math.max(codeScroller.offsetHeight, 160) + 'px';
                codeScroller.style.display = 'none';
                codeEditor.style.display = 'block';
                editBtn.textContent = 'Done';
                editing = true;
                codeEditor.focus();
            } else {
                editing = false;
                setCode(codeEditor.value);
                codeEditor.style.display = 'none';
                codeScroller.style.display = '';
                editBtn.textContent = 'Edit';
            }
        });

        // Tab in a code editor means indent, not "move to the next button".
        codeEditor.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            e.preventDefault();
            codeEditor.setRangeText('    ', codeEditor.selectionStart, codeEditor.selectionEnd, 'end');
        });
    }

    // ===== Code, section by section =====
    // A second model call, so it is fetched after the code is already on screen
    // rather than being waited for inside /api/generate-code.
    const sectionsCard = document.getElementById('codeSectionsCard');
    const sectionsDiv = document.getElementById('codeSections');

    function renderSections(sections) {
        sectionsDiv.textContent = '';
        sections.forEach((sec, i) => {
            const wrap = document.createElement('div');
            wrap.className = 'code-section';

            const head = document.createElement('h3');
            head.className = 'code-section-title';
            const num = document.createElement('span');
            num.className = 'code-section-num';
            num.textContent = i + 1;
            head.appendChild(num);
            head.appendChild(document.createTextNode(sec.title || `Part ${i + 1}`));
            if (sec.start_line) {
                const lines = document.createElement('span');
                lines.className = 'code-section-lines';
                lines.textContent = `lines ${sec.start_line}–${sec.end_line}`;
                head.appendChild(lines);
            }

            const pre = document.createElement('pre');
            pre.className = 'code-section-code';
            const codeEl = document.createElement('code');
            codeEl.className = 'language-python';
            codeEl.textContent = sec.code || '';
            pre.appendChild(codeEl);

            const why = document.createElement('p');
            why.className = 'code-section-explanation';
            why.textContent = sec.explanation || '';

            const ask = document.createElement('button');
            ask.type = 'button';
            ask.className = 'btn btn-outline code-section-ask';
            ask.textContent = 'Ask about this section';
            ask.addEventListener('click', () => {
                const title = sec.title || `Part ${i + 1}`;
                const range = sec.start_line ? ` (lines ${sec.start_line}-${sec.end_line})` : '';
                if (window.askFollowUp) {
                    window.askFollowUp(`Explain the section "${title}"${range} in more detail`);
                }
            });

            wrap.append(head, pre, why, ask);
            // The one orchestrated moment: sections reveal top to bottom, once.
            wrap.classList.add('reveal');
            wrap.style.animationDelay = (i * 40) + 'ms';
            sectionsDiv.appendChild(wrap);
            if (window.Prism) Prism.highlightElement(codeEl);
        });
        sectionsCard.style.display = 'block';
        // They arrive after the code, so say so on the tab that now holds them.
        if (window.markTabNew) markTabNew('tab-walkthrough');
    }

    async function loadSections(code, topic) {
        sectionsDiv.textContent = '';
        const pending = document.createElement('p');
        pending.className = 'section-hint';
        pending.textContent = 'Working out the section-by-section breakdown...';
        sectionsDiv.appendChild(pending);
        sectionsCard.style.display = 'block';
        try {
            const response = await fetch('/api/code-sections', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, topic })
            });
            const data = await response.json();
            if (!response.ok || !Array.isArray(data.sections) || !data.sections.length) {
                throw new Error(data.error || 'No sections');
            }
            renderSections(data.sections);
        } catch (err) {
            // The prose walkthrough already covers the whole program, so a
            // missing breakdown disappears quietly instead of raising an error.
            sectionsDiv.textContent = '';
            sectionsCard.style.display = 'none';
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        const length = document.getElementById('length').value;
        const level = document.getElementById('level').value;

        if (!topic) {
            showToast('Name a topic first.', 'error');
            return;
        }

        currentTopic = topic;
        
        try {
            showLoading(true, 'Generating the code and its section breakdown - usually 40-90 s');
            
            const response = await fetch('/api/generate-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic,
                    length,
                    level
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate content');
            }
            
            if (data.success) {
                // Display explanation
                currentExplanation = data.explanation;
                explanationDiv.innerHTML = formatMarkdown(data.explanation);
                
                // Display code. A previous run's output belongs to the old
                // program, so clear it and leave edit mode.
                if (editing) editBtn.click();
                setCode(data.code);
                if (runOutput) {
                    runOutput.style.display = 'none';
                    runText.textContent = '';
                    runFigures.textContent = '';
                }

                // The breakdown is a second, slower request; kick it off but do
                // not wait for it - the code and walkthrough are already here.
                loadSections(data.code, topic);

                // Display dependencies
                if (data.dependencies && data.dependencies.length > 0) {
                    // Built as real elements: the previous "<br><br>" inside a flex
                    // container made the install command a sibling flex item, so it
                    // sat beside the badges instead of below them.
                    dependenciesDiv.textContent = '';

                    const badges = document.createElement('div');
                    badges.className = 'dependency-badges';
                    data.dependencies.forEach(dep => {
                        const badge = document.createElement('span');
                        badge.className = 'dependency-badge';
                        badge.textContent = dep;
                        badges.appendChild(badge);
                    });

                    const installCmd = `pip install ${data.dependencies.join(' ')}`;
                    const row = document.createElement('div');
                    row.className = 'install-command';

                    const code = document.createElement('code');
                    code.textContent = installCmd;

                    const copyBtn = document.createElement('button');
                    copyBtn.type = 'button';
                    copyBtn.className = 'btn btn-outline install-copy';
                    copyBtn.textContent = 'Copy';
                    copyBtn.addEventListener('click', () => copyToClipboard(installCmd));

                    row.append(code, copyBtn);
                    dependenciesDiv.append(badges, row);

                    dependenciesSection.style.display = 'block';
                } else {
                    dependenciesSection.style.display = 'none';
                }
                
                const title = document.getElementById('resultsTitle');
                if (title) title.textContent = topic;
                outputSection.hidden = false;
                outputSection.scrollIntoView({ behavior: 'smooth' });
                rememberTopic(topic);
                showToast('Your program is ready.', 'success');
            } else {
                throw new Error('Failed to generate content');
            }
            
        } catch (error) {
            console.error('Error:', error);
            showToast(error.message || 'That did not work. Try again in a moment.', 'error');
        } finally {
            showLoading(false);
        }
    });
    
    // Copy code button
    copyCodeBtn.addEventListener('click', () => {
        copyToClipboard(codeText());
    });

    // Download code button
    downloadCodeBtn.addEventListener('click', () => {
        const filename = `${currentTopic.replace(/\s+/g, '_')}.py`;
        downloadTextFile(codeText(), filename);
    });
});
