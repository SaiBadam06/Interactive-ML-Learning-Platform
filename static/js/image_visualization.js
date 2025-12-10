document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('imageForm');
    const outputSection = document.getElementById('outputSection');
    const explanationDiv = document.getElementById('explanation');
    const imagesGrid = document.getElementById('imagesGrid');
    const promptsDiv = document.getElementById('prompts');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        const length = document.getElementById('length').value;
        const backend = document.getElementById('backend').value;

        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }
        
        try {
            showLoading(true);
            
            const response = await fetch('/api/generate-images', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic,
                    length,
                    backend
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate content');
            }
            
            if (data.success) {
                // Display explanation
                explanationDiv.innerHTML = formatMarkdown(data.explanation);
                
                // Display images
                if (data.images && data.images.length > 0) {
                    imagesGrid.innerHTML = data.images.map((img, idx) => `
                        <div class="image-item">
                            <img src="${img}" alt="Visualization ${idx + 1}" loading="lazy">
                        </div>
                    `).join('');
                } else {
                    imagesGrid.innerHTML = '<p>No images were generated. Please try again.</p>';
                }
                
                // Display prompts
                if (data.prompts && data.prompts.length > 0) {
                    promptsDiv.innerHTML = data.prompts.map((prompt, idx) => `
                        <div class="prompt-item">
                            <div class="prompt-number">Prompt ${idx + 1}:</div>
                            <div class="prompt-text">${prompt}</div>
                        </div>
                    `).join('');
                }
                
                outputSection.style.display = 'block';
                outputSection.scrollIntoView({ behavior: 'smooth' });
                showToast('Images generated successfully!', 'success');
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
});
