document.addEventListener('DOMContentLoaded', () => {
    const modelInfoBtn = document.getElementById('modelInfoBtn');
    const modelModal = document.getElementById('modelModal');
    const closeModal = document.querySelector('.close');
    const modelDetails = document.getElementById('modelDetails');

    // The model names are information, not decoration, so they are on the page
    // rather than behind the modal.
    const summary = document.getElementById('modelSummary');
    if (summary) {
        fetch('/api/model-info')
            .then(r => r.json())
            .then(info => {
                summary.textContent = '';
                [['Provider', info.provider], ['Text', info.text_model], ['Images', info.image_model]]
                    .filter(([, value]) => value)
                    .forEach(([label, value]) => {
                        const dt = document.createElement('dt');
                        dt.textContent = label;
                        const dd = document.createElement('dd');
                        dd.textContent = value;
                        summary.append(dt, dd);
                    });
            })
            .catch(() => { summary.textContent = 'Model information is unavailable.'; });
    }

    // Show model info
    modelInfoBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/model-info');
            const data = await response.json();

            modelDetails.textContent = JSON.stringify(data, null, 2);
            modelModal.classList.add('show');
        } catch (error) {
            showToast('Could not load the model details. Reload to try again.', 'error');
        }
    });

    // Close modal
    closeModal.addEventListener('click', () => {
        modelModal.classList.remove('show');
    });

    window.addEventListener('click', (e) => {
        if (e.target === modelModal) {
            modelModal.classList.remove('show');
        }
    });
});
