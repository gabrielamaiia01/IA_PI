document.addEventListener("DOMContentLoaded", async () => {
    try {
        const response = await fetch("http://127.0.0.1:5000/api/dashboard_data");
        const data = await response.json();

        if (data.error) {
            console.error(data.error);
            return;
        }

        // ===========================
        // Atualiza KPIs
        // ===========================
        document.getElementById("total_letalidade").textContent = data.letalidade_violenta_total;
        document.getElementById("homicidios_dolosos").textContent = data.homicidios_dolosos;
        document.getElementById("latrocinios").textContent = data.latrocinios;
        document.getElementById("mortes_policial").textContent = data.mortes_intervencao_policial;

        // ===========================
        // Evolução temporal (linha)
        // ===========================
        const ctxLinha = document.createElement("canvas");
        const linhaContainer = document.querySelector(".chart-row .chart-card:first-child .chart-placeholder");
        linhaContainer.innerHTML = ""; // Limpa se houver canvas anterior
        linhaContainer.appendChild(ctxLinha);

        new Chart(ctxLinha, {
            type: "line",
            data: {
                labels: data.evolucao_temporal.map(item => item.x),
                datasets: [{
                    label: "Letalidade Violenta",
                    data: data.evolucao_temporal.map(item => item.y),
                    borderColor: "rgba(75, 192, 192, 1)",
                    backgroundColor: "rgba(75, 192, 192, 0.2)",
                    fill: true,
                    tension: 0.3
                }]
            },
            options: { responsive: true, plugins: { legend: { display: true } }, scales: { y: { beginAtZero: true } } }
        });

        // ===========================
        // Gráfico de barras (correlação)
        // ===========================
        const correlacao = data.correlacao_crimes;
        const vars = Object.keys(correlacao);
        const values = Object.values(correlacao);

        const ctxBar = document.createElement("canvas");
        const barContainer = document.getElementById("chart-heatmap");
        barContainer.innerHTML = "";
        barContainer.appendChild(ctxBar);

        new Chart(ctxBar, {
            type: "bar",
            data: {
                labels: vars,
                datasets: [{
                    label: 'Correlação com Letalidade Violenta',
                    data: values,
                    backgroundColor: values.map(v => v >= 0 ? 'rgba(75, 192, 192, 0.7)' : 'rgba(255, 99, 132, 0.7)'),
                    borderColor: values.map(v => v >= 0 ? 'rgba(75, 192, 192, 1)' : 'rgba(255, 99, 132, 1)'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, min: -1, max: 1, title: { display: true, text: 'Correlação' } },
                    x: { title: { display: true, text: 'Variáveis' } }
                },
                plugins: {
                    tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}` } },
                    legend: { display: false }
                }
            }
        });

        // ===========================
        // Scatterplot (roubo x letalidade)
        // ===========================
        const scatterData = data.scatter_data;
        const ctxScatter = document.createElement("canvas");
        const scatterContainer = document.getElementById("chart-scatter");
        scatterContainer.innerHTML = "";
        scatterContainer.appendChild(ctxScatter);

        new Chart(ctxScatter, {
            type: "scatter",
            data: {
                datasets: [{
                    label: "Roubo via Pública x Letalidade Violenta",
                    data: scatterData,
                    backgroundColor: "rgba(75, 192, 192, 0.7)"
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { title: { display: true, text: "Roubo via Pública" } },
                    y: { title: { display: true, text: "Letalidade Violenta" } }
                },
                plugins: {
                    tooltip: { callbacks: { label: (ctx) => `Roubo: ${ctx.parsed.x}, Letalidade: ${ctx.parsed.y}` } }
                }
            }
        });
        ctxScatter.width = 1500;

        // ===========================
        // Mapas como imagens
        // ===========================
        const mapImg = document.getElementById("map-img");
        async function loadMapImage(groupBy = "mcirc") {
            mapImg.src = ""; // Placeholder enquanto carrega
            const response = await fetch(`http://127.0.0.1:5000/api/map_image/${groupBy}`);
            const data = await response.json();
            if (data.image_url) mapImg.src = data.image_url;
        }

        document.getElementById("map-group").addEventListener("change", (e) => {
            loadMapImage(e.target.value);
        });

        loadMapImage("mcirc");

    } catch (err) {
        console.error("Erro ao carregar dashboard:", err);
    }
});
