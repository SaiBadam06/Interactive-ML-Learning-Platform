document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('codeForm');
    const outputSection = document.getElementById('outputSection');
    const explanationDiv = document.getElementById('explanation');
    const codeContent = document.getElementById('codeContent');
    const dependenciesSection = document.getElementById('dependenciesSection');
    const dependenciesDiv = document.getElementById('dependencies');
    const copyCodeBtn = document.getElementById('copyCodeBtn');
    const downloadCodeBtn = document.getElementById('downloadCodeBtn');
    
    let currentCode = '';
    let currentExplanation = '';
    let currentTopic = '';
    
    // Tab functionality
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(`${tabName}Tab`).classList.add('active');
        });
    });
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        const length = document.getElementById('length').value;

        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }

        currentTopic = topic;
        
        try {
            showLoading(true);
            
            const response = await fetch('/api/generate-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic,
                    length
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
                
                // Display code
                currentCode = data.code;
                codeContent.textContent = data.code;
                if (window.Prism) Prism.highlightElement(codeContent);

                // Section-by-section breakdown. Best effort on the server, so
                // hide the card entirely rather than showing an empty one.
                const sectionsCard = document.getElementById('codeSectionsCard');
                const sectionsDiv = document.getElementById('codeSections');
                sectionsDiv.textContent = '';
                if (Array.isArray(data.sections) && data.sections.length) {
                    data.sections.forEach((sec, i) => {
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

                        wrap.append(head, pre, why);
                        sectionsDiv.appendChild(wrap);
                        if (window.Prism) Prism.highlightElement(codeEl);
                    });
                    sectionsCard.style.display = 'block';
                } else {
                    sectionsCard.style.display = 'none';
                }
                
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
                    copyBtn.className = 'btn btn-secondary install-copy';
                    copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
                    copyBtn.addEventListener('click', () => copyToClipboard(installCmd));

                    row.append(code, copyBtn);
                    dependenciesDiv.append(badges, row);

                    dependenciesSection.style.display = 'block';
                } else {
                    dependenciesSection.style.display = 'none';
                }
                
                outputSection.style.display = 'block';
                outputSection.scrollIntoView({ behavior: 'smooth' });
                showToast('Code generated successfully!', 'success');
            } else {
                throw new Error('Failed to generate content');
            }
            
        } catch (error) {
            console.error('Error:', error);
            showToast(error.message || 'An error occurred', 'error');
        } finally {
            showLoading(false);
        }
    });
    
    // Copy code button
    copyCodeBtn.addEventListener('click', () => {
        copyToClipboard(currentCode);
    });
    
    // Download code button
    downloadCodeBtn.addEventListener('click', () => {
        const filename = `${currentTopic.replace(/\s+/g, '_')}.py`;
        downloadTextFile(currentCode, filename);
    });
});
