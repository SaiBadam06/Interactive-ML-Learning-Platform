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
                
                // Display dependencies
                if (data.dependencies && data.dependencies.length > 0) {
                    dependenciesDiv.innerHTML = data.dependencies
                        .map(dep => `<span class="dependency-badge">${dep}</span>`)
                        .join('');
                    
                    // Also show install command
                    const installCmd = `pip install ${data.dependencies.join(' ')}`;
                    dependenciesDiv.innerHTML += `<br><br><code>${installCmd}</code>`;
                    
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
