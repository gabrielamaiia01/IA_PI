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
    let ultimaPrevisao = null;
 
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
    function criarGraficoHistoricoPrevisao(historico_valores, historico_labels, prev_valores, prev_labels, media_historica_valores, media_previsoes_valores) {
        const ctx = document.getElementById('historicoPrevisaoChart').getContext('2d');
        if (chartInstance) chartInstance.destroy();
 
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: historico_labels,
                datasets: [
                    {
                        label: 'Soma de histórico',
                        data: historico_valores,
                        borderColor: 'rgba(0, 123, 255, 1)',
                        backgroundColor: 'rgba(0, 123, 255, 0.2)',
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: 'rgba(0, 123, 255, 1)',
                        pointRadius: 3
                    },
                    {
                        label: 'Soma das previsões',
                        data: historico_labels.map((lbl, i) =>
                        prev_labels.includes(lbl) ? prev_valores[i] : null
                        ),
                        borderColor: 'rgba(255, 165, 0, 1)',
                        backgroundColor: 'rgba(255, 165, 0, 0.2)',
                        borderDash: [5, 5],
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: 'rgba(255, 165, 0, 1)',
                        pointRadius: 3
                    },
                    {
                        label: 'Média Histórica',
                        data: media_historica_valores,
                        borderColor: 'rgba(40, 167, 69, 1)',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        fill: '+1',
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'Média de Previsões',
                        data: historico_labels.map((lbl, i) =>
                        prev_labels.includes(lbl) ? media_previsoes_valores[i] : null
                        ),
                        borderColor: 'rgba(220, 53, 69, 1)',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        borderDash: [3, 3]
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
                            label: function (context) {
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
                            callback: function (value) {
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
 
    // ======= Evento do formulário de previsão =======
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
            if (!data.success) throw new Error(data.error || 'Erro desconhecido na previsão.');
 
            // Exibe resultados
            previsaoLeituraEl.textContent = Math.round(data.previsao_leitura);
            riscoEl.textContent = data.risco;
            intervalo95El.textContent = `${Math.round(data.intervalo_95[0])} - ${Math.round(data.intervalo_95[1])}`;
            tendenciaEl.textContent = data.tendencia;
            driversPrincipaisEl.textContent = "Drivers Principais: " + data.drivers;
 
            // Atualiza gráficos
            criarGraficoHistoricoPrevisao(
                data.historico_valores,
                data.historico_labels,
                data.prev_valores,
                data.prev_labels,
                data.media_historica_valores,
                data.media_previsoes_valores
            );
 
            mostrarFeatureImportance(data.feature_importance);
 
            // Armazena a última previsão completa
            ultimaPrevisao = {
                ...data,
                features_dict: {
                    cisp: features[0],
                    mes: features[1],
                    ano: features[2],
                    mcirc: features[3],
                    tentat_hom: features[4],
                    estupro: features[5],
                    lesao_corp_culposa: features[6],
                    roubo_veiculo: features[7],
                    estelionato: features[8],
                    apreensao_drogas: features[9],
                    trafico_drogas: features[10],
                    apf: features[11],
                    pessoas_desaparecidas: features[12],
                    encontro_cadaver: features[13],
                    registro_ocorrencias: features[14]
                }
            };
 
            // Habilita o botão de exportar
            const btnExportar = document.getElementById('btn-export-previsao');
            if (btnExportar) btnExportar.disabled = false;
 
            loadingEl.style.display = 'none';
            successEl.style.display = 'block';
        } catch (error) {
            loadingEl.style.display = 'none';
            errorEl.textContent = error.message;
            errorEl.style.display = 'block';
        }
    });
 
    // ======= Preenche selects (CISP e MCIRC) =======
    async function preencherSelects() {
        try {
            const response = await fetch('/api/valores_select');
            const data = await response.json();
 
            const cispList = document.getElementById('lista-cisps');
            const mcircList = document.getElementById('lista-mcircs');
 
            data.cisps.forEach(c => {
                const option = document.createElement('option');
                option.value = c;
                cispList.appendChild(option);
            });
 
            data.mcircs.forEach(m => {
                const option = document.createElement('option');
                option.value = m;
                mcircList.appendChild(option);
            });
        } catch (err) {
            console.error("Erro ao preencher datalists:", err);
        }
    }
    preencherSelects();
 
    // ======= Exportar PDF =======
    async function exportarPrevisaoPDF() {
        if (!ultimaPrevisao) {
            alert('Por favor, faça uma previsão antes de exportar o relatório.');
            return;
        }
 
        const btnExportar = document.getElementById('btn-export-previsao');
 
        try {
            const response = await fetch('/api/export_previsao_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ultimaPrevisao)
            });
 
            if (!response.ok) throw new Error('Erro ao gerar PDF');
 
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
 
            const features = ultimaPrevisao.features_dict || {};
            const filename = `relatorio_previsao.pdf`;
            a.download = filename;
 
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
 
            alert('Relatório PDF gerado com sucesso!');
        } catch (error) {
            console.error('Erro ao exportar PDF:', error);
            alert('Erro ao gerar relatório PDF: ' + error.message);
        }
    }
 
    // ======= Evento do botão de exportar =======
    const btnExportar = document.getElementById('btn-export-previsao');
    if (btnExportar) {
        btnExportar.addEventListener('click', exportarPrevisaoPDF);
        btnExportar.disabled = true;
    }
});