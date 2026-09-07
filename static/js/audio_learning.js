document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('audioForm');
    const outputSection = document.getElementById('outputSection');
    const audioPlayer = document.getElementById('audioPlayer');
    const scriptDiv = document.getElementById('script');
    const explanationDiv = document.getElementById('explanation');
    const downloadAudioBtn = document.getElementById('downloadAudioBtn');
    const copyScriptBtn = document.getElementById('copyScriptBtn');
    
    let currentScript = '';
    let currentAudioFile = null;
    let currentAudioData = null;
    
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
            showLoading(true, 'Writing and recording your audio lesson - usually 30-60 s');
            
            const response = await fetch('/api/generate-audio', {
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
                
                // Display script
                currentScript = data.script;
                scriptDiv.innerHTML = formatMarkdown(data.script);
                
                // Display audio player
                if (data.audio_file) {
                    currentAudioFile = data.audio_file;
                    currentAudioData = data.audio_data || null;
                    // DOM APIs rather than innerHTML: the filename comes back from
                    // the response and must not be parsed as markup.
                    audioPlayer.textContent = '';
                    const audio = document.createElement('audio');
                    audio.controls = true;
                    audio.src = data.audio_data || ('/api/download-audio/' + encodeURIComponent(data.audio_file));
                    audio.append('Your browser does not support the audio element.');
                    audioPlayer.appendChild(audio);
                } else {
                    audioPlayer.textContent = '';
                    const failed = document.createElement('p');
                    failed.textContent = 'Audio generation failed. Please try again.';
                    audioPlayer.appendChild(failed);
                }
                
                outputSection.hidden = false;
                outputSection.scrollIntoView({ behavior: 'smooth' });
                rememberTopic(topic);
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
            if (currentAudioData) {
                const a = document.createElement('a');
                a.href = currentAudioData;
                a.download = currentAudioFile || 'explanation.mp3';
                document.body.appendChild(a); a.click(); a.remove();
            } else {
                window.location.href = `/api/download-audio/${currentAudioFile}`;
            }
            showToast('Downloading audio file...', 'info');
        }
    });
    
    // Copy script button
    copyScriptBtn.addEventListener('click', () => {
        copyToClipboard(currentScript);
    });
});
