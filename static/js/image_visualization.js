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
        const level = document.getElementById('level').value;

        if (!topic) {
            showToast('Name a topic first.', 'error');
            return;
        }
        
        try {
            showLoading(true, 'Generating 3 images - usually 30-90 s');
            
            const response = await fetch('/api/generate-images', {
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
                explanationDiv.innerHTML = formatMarkdown(data.explanation);
                
                // Built with DOM APIs, not innerHTML: the prompts are model output
                // and the image sources come back from the same response, so
                // neither is trusted enough to be parsed as markup.
                imagesGrid.textContent = '';
                if (data.images && data.images.length > 0) {
                    data.images.forEach((img, idx) => {
                        const item = document.createElement('div');
                        item.className = 'image-item';
                        const el = document.createElement('img');
                        el.src = img;
                        el.alt = 'Visualization ' + (idx + 1);
                        el.loading = 'lazy';
                        item.appendChild(el);
                        imagesGrid.appendChild(item);
                    });
                } else {
                    const empty = document.createElement('p');
                    empty.textContent = 'No images were generated. Please try again.';
                    imagesGrid.appendChild(empty);
                }

                // Display prompts
                promptsDiv.textContent = '';
                if (data.prompts && data.prompts.length > 0) {
                    data.prompts.forEach((prompt, idx) => {
                        const item = document.createElement('div');
                        item.className = 'prompt-item';
                        const number = document.createElement('div');
                        number.className = 'prompt-number';
                        number.textContent = 'Prompt ' + (idx + 1) + ':';
                        const text = document.createElement('div');
                        text.className = 'prompt-text';
                        text.textContent = prompt;
                        item.append(number, text);
                        promptsDiv.appendChild(item);
                    });
                }
                
                outputSection.hidden = false;
                outputSection.scrollIntoView({ behavior: 'smooth' });
                rememberTopic(topic);
                showToast('Your diagrams are ready.', 'success');
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
});
