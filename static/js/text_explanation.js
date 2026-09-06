document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('textForm');
    const outputSection = document.getElementById('outputSection');
    const explanationDiv = document.getElementById('explanation');
    const copyBtn = document.getElementById('copyBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    
    let currentExplanation = '';
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        const length = document.getElementById('length').value;
        const level = document.getElementById('level').value;

        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }
        try {
            showLoading(true, 'Writing your explanation - usually 15-40 s');
            const response = await fetch('/api/generate-text', {
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
                currentExplanation = data.content;
                explanationDiv.innerHTML = formatMarkdown(data.content);
                outputSection.style.display = 'block';
                outputSection.scrollIntoView({ behavior: 'smooth' });
                rememberTopic(topic);
                showToast('Explanation generated successfully!', 'success');
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
    // Copy button
    copyBtn.addEventListener('click', () => {
        copyToClipboard(currentExplanation);
    });
    // Download button
    downloadBtn.addEventListener('click', () => {
        const topic = document.getElementById('topic').value.trim();
        const filename = `${topic.replace(/\s+/g, '_')}_explanation.txt`;
        downloadTextFile(currentExplanation, filename);
    });
});
