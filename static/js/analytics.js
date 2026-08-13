/**
 * Sales forecast chart (admin analytics page).
 *
 * The series is handed over in a <script type="application/json"> block rather
 * than an inline script, because our Content-Security-Policy has no
 * 'unsafe-inline' -- a JSON data block is never executed, so it is allowed.
 */
document.addEventListener('DOMContentLoaded', function () {
    const canvas = document.getElementById('forecastChart');
    const dataTag = document.getElementById('forecastData');
    if (!canvas || !dataTag || typeof Chart === 'undefined') {
        return;
    }

    let series;
    try {
        series = JSON.parse(dataTag.textContent);
    } catch (e) {
        return;
    }

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: Object.keys(series),
            datasets: [{
                label: 'Forecasted Daily Sales (Rs)',
                data: Object.values(series),
                borderColor: '#febd69',
                backgroundColor: 'rgba(254,189,105,0.2)',
                tension: 0.3,
                fill: true,
            }],
        },
        options: { responsive: true, plugins: { legend: { display: true } } },
    });

    const refreshBtn = document.getElementById('refreshForecastBtn');
    if (refreshBtn && refreshBtn.closest('form')) {
        refreshBtn.closest('form').addEventListener('submit', function () {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML =
                '<span class="spinner-border spinner-border-sm"></span> Refreshing...';
        });
    }
});
