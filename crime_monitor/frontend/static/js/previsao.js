document.addEventListener('DOMContentLoaded', () => { 
    const form = document.getElementById('prediction-form');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error-message');
    const successEl = document.getElementById('success-message');

    const previsaoLeituraEl = document.getElementById('previsao_leitura');
    const riscoEl = document.getElementById('risco');
    const intervalo95El = document.getElementById('intervalo_95');
    const tendenciaEl = document.getElementById('tendencia');
    const driversPrincipaisEl = document.getElementById('drivers_principais');
    const contribuicaoContainer = document.getElementById('contribuicaoContainer');

    let chartInstance = null;
    let featureChart = null;

    // ======= Preenche médias dos campos desativados =======
    async function preencherMediasDisabled() {
        try {
            const response = await fetch('/api/medias');
            const medias = await response.json();
            Object.keys(medias).forEach(key => {
                const input = document.querySelector(`input[name="${key}"][disabled]`);
                if (input) input.value = Math.round(medias[key]);
            });
        } catch (err) {
            console.error("Erro ao preencher médias:", err);
        }
    }
    preencherMediasDisabled();

    // ======= Criação do gráfico com intervalo de confiança =======
    function criarGraficoHistoricoPrevisao(historico_valores, historico_labels, prev_valores, intervalos_inferior, intervalos_superior) {
        const ctx = document.getElementById('historicoPrevisaoChart').getContext('2d');
        if (chartInstance) chartInstance.destroy();

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: historico_labels,
                datasets: [
                    {
                        label: 'Histórico Real',
                        data: historico_valores,
                        borderColor: 'blue',
                        backgroundColor: 'rgba(0, 0, 255, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Previsões',
                        data: prev_valores,
                        borderColor: 'orange',
                        backgroundColor: 'rgba(255, 165, 0, 0.2)',
                        borderDash: [5, 5],
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Intervalo de Confiança (95%)',
                        data: intervalos_superior,
                        borderColor: 'rgba(128,128,128,0.5)',
                        fill: '+1', // Preenche entre o limite inferior e superior
                        backgroundColor: 'rgba(128,128,128,0.2)',
                        pointRadius: 0,
                        tension: 0.3
                    },
                    {
                        label: 'Limite Inferior (95%)',
                        data: intervalos_inferior,
                        borderColor: 'rgba(128,128,128,0.5)',
                        pointRadius: 0,
                        fill: false,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Letalidade Violenta' } },
                    x: { title: { display: true, text: 'Período' } }
                },
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    // ======= Gráfico de Importância das Variáveis =======
    function mostrarFeatureImportance(featureImportance) {
        contribuicaoContainer.innerHTML = '';
        const canvas = document.createElement('canvas');
        canvas.id = 'featureChart';
        const featureCount = Object.keys(featureImportance).length;
        canvas.height = featureCount * 20;
        contribuicaoContainer.appendChild(canvas);
        const ctx = canvas.getContext('2d');

        const sorted = Object.entries(featureImportance).sort((a, b) => b[1] - a[1]);
        const labels = sorted.map(f => f[0]);
        const data = sorted.map(f => f[1]);

        if (featureChart) featureChart.destroy();

        featureChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Importância',
                    data,
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, title: { display: true, text: 'Importância' } },
                    y: {
                        ticks: {
                            autoSkip: false,
                            padding: 10,
                            callback: function(value) {
                                const label = this.getLabelForValue(value);
                                return label.length > 30 ? label.match(/.{1,30}/g) : label;
                            }
                        }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // ======= Evento do formulário =======
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        loadingEl.style.display = 'block';
        errorEl.style.display = 'none';
        successEl.style.display = 'none';

        const features = Array.from(document.querySelectorAll('input')).map(input => Number(input.value) || 0);

        try {
            const response = await fetch('/api/previsao', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ features })
            });

            const data = await response.json();
            console.log(data);

            if (!data.success) throw new Error(data.error || 'Erro desconhecido na previsão.');

            previsaoLeituraEl.textContent = Math.round(data.previsao_leitura);
            riscoEl.textContent = data.risco;
            intervalo95El.textContent = `${Math.round(data.intervalo_95[0])} - ${Math.round(data.intervalo_95[1])}`;
            tendenciaEl.textContent = data.tendencia;
            driversPrincipaisEl.textContent = "Drivers Principais: " + data.drivers;

            criarGraficoHistoricoPrevisao(
                data.historico_valores,
                data.historico_labels,
                data.prev_valores,
                data.interval_95_lower,
                data.interval_95_upper
            );

            mostrarFeatureImportance(data.feature_importance);

            loadingEl.style.display = 'none';
            successEl.style.display = 'block';
        } catch (error) {
            loadingEl.style.display = 'none';
            errorEl.textContent = error.message;
            errorEl.style.display = 'block';
        }
    });
});
