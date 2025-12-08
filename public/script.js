async function makePrediction() {
    const cryptoSelect = document.getElementById('crypto-select');
    const crypto = cryptoSelect.value;
    
    const btn = document.getElementById('predict-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('loader');
    const resultCard = document.getElementById('result-card');
    const errorMsg = document.getElementById('error-message');

    // Reset UI
    btn.disabled = true;
    btnText.classList.add('hidden');
    loader.classList.remove('hidden');
    resultCard.classList.add('hidden');
    errorMsg.classList.add('hidden');

    try {
        const response = await fetch('/api/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ crypto: crypto }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch prediction');
        }

        // Update UI with data
        document.getElementById('result-crypto').textContent = data.crypto;
        document.getElementById('current-price').textContent = formatCurrency(data.current_price);
        document.getElementById('predicted-price').textContent = formatCurrency(data.predicted_price);
        
        const changePercent = data.change_percent;
        const badge = document.getElementById('prediction-badge');
        const changeText = document.getElementById('change-percent');
        const trendText = document.getElementById('trend-text');

        changeText.textContent = (changePercent > 0 ? '+' : '') + changePercent + '%';
        
        badge.className = 'prediction-badge'; // reset classes
        if (changePercent >= 0) {
            badge.classList.add('positive');
            trendText.textContent = 'BULLISH 🚀';
        } else {
            badge.classList.add('negative');
            trendText.textContent = 'BEARISH 📉';
        }

        document.getElementById('result-timestamp').textContent = new Date(data.timestamp).toLocaleTimeString();
        resultCard.classList.remove('hidden');

    } catch (error) {
        console.error('Error:', error);
        errorMsg.textContent = error.message || 'An error occurred while predicting.';
        errorMsg.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btnText.classList.remove('hidden');
        loader.classList.add('hidden');
    }
}

function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}
