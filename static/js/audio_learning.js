document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('audioForm');
    const outputSection = document.getElementById('outputSection');
    const audioPlayer = document.getElementById('audioPlayer');
    const scriptDiv = document.getElementById('script');
    const explanationDiv = document.getElementById('explanation');
    const downloadAudioBtn = document.getElementById('downloadAudioBtn');
    const copyScriptBtn = document.getElementById('copyScriptBtn');
    
    let currentScript = '';
    let currentAudioFile = '';
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const topic = document.getElementById('topic').value.trim();
        const length = document.getElementById('length').value;

        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }
        
        try {
            showLoading(true);
            
            const response = await fetch('/api/generate-audio', {
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
                explanationDiv.innerHTML = formatMarkdown(data.explanation);
                
                // Display script
                currentScript = data.script;
                scriptDiv.innerHTML = formatMarkdown(data.script);
                
                // Display audio player
                if (data.audio_file) {
                    currentAudioFile = data.audio_file;
                    audioPlayer.innerHTML = `
                        <audio controls>
                            <source src="/api/download-audio/${data.audio_file}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    `;
                } else {
                    audioPlayer.innerHTML = '<p>Audio generation failed. Please try again.</p>';
                }
                
                outputSection.style.display = 'block';
                outputSection.scrollIntoView({ behavior: 'smooth' });
                showToast('Audio lesson generated successfully!', 'success');
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
    
    // Download audio button
    downloadAudioBtn.addEventListener('click', () => {
        if (currentAudioFile) {
            window.location.href = `/api/download-audio/${currentAudioFile}`;
            showToast('Downloading audio file...', 'info');
        }
    });
    
    // Copy script button
    copyScriptBtn.addEventListener('click', () => {
        copyToClipboard(currentScript);
    });
});
