document.addEventListener('DOMContentLoaded', () => {
    const modelInfoBtn = document.getElementById('modelInfoBtn');
    const modelModal = document.getElementById('modelModal');
    const closeModal = document.querySelector('.close');
    const modelDetails = document.getElementById('modelDetails');

    // Show model info
    modelInfoBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/model-info');
            const data = await response.json();

            modelDetails.textContent = JSON.stringify(data, null, 2);
            modelModal.classList.add('show');
        } catch (error) {
            showToast('Failed to load model information', 'error');
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
