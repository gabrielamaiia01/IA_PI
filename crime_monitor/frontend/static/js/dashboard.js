document.addEventListener("DOMContentLoaded", async () => {
    let municipios = [];
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const mapImg = document.getElementById("map-img");

    // ===========================
    // Carregar municípios
    // ===========================
    try {
        const response = await fetch("/api/municipios");
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // Autocomplete do input município
    inputMunicipio.addEventListener("input", () => {
        const valor = inputMunicipio.value.toLowerCase();
        datalist.innerHTML = "";
        municipios
            .filter(m => m.toLowerCase().startsWith(valor))
            .forEach(m => {
                const option = document.createElement("option");
                option.value = m;
                datalist.appendChild(option);
            });
    });

    // ===========================
    // Função para carregar mapa
    // ===========================
    async function loadMapImage(groupBy = "mcirc") {
        if (!mapImg) return;

        const dataInicio = document.getElementById("data-inicio").value;
        const dataFim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;

        const params = new URLSearchParams();
        if (dataInicio) params.append("inicio", dataInicio);
        if (dataFim) params.append("fim", dataFim);
        if (municipio) params.append("municipio", municipio);

        try {
            const response = await fetch(`/api/map_image/${groupBy}?${params.toString()}`);
            const data = await response.json();
            if (data.image_url) mapImg.src = data.image_url;
        } catch (err) {
            console.error("Erro ao carregar mapa:", err);
        }
    }
    document.getElementById("map-group").addEventListener("change", (e) => loadMapImage(e.target.value));

    // ===========================
    // Função para carregar dashboard
    // ===========================
    async function carregarDashboard(params = "") {
        try {
            const response = await fetch(`/api/dashboard_data${params ? "?" + params : ""}`);
            const data = await response.json();

            if (data.error) {
                console.error(data.error);
                return;
            }

            // Atualiza KPIs
            document.getElementById("total_letalidade").textContent = data.letalidade_violenta_total;
            document.getElementById("homicidios_dolosos").textContent = data.homicidios_dolosos;
            document.getElementById("latrocinios").textContent = data.latrocinios;
            document.getElementById("mortes_policial").textContent = data.mortes_intervencao_policial;

            // Atualiza descrições
            let homicidiosPct = data.homicidios_dolosos_pct;
            let homicidiosText = homicidiosPct != null
                ? (homicidiosPct >= 0 ? "+" : "") + parseInt(homicidiosPct) + "%"
                : "N/A";
            document.querySelector("#homicidios_dolosos + .description").textContent =
                "comparado ao mês anterior: " + homicidiosText;

            let latroPct = data.variacao_latrocinio_anual_pct;
            let latroText = latroPct != null
                ? (latroPct >= 0 ? "+" : "") + parseInt(latroPct) + "%"
                : "N/A";
            document.querySelector("#latrocinios + .description").textContent =
                "variação anual: " + latroText;

            document.querySelector("#mortes_policial + .description").textContent =
                "tendência: " + data.tendencia_mortes_intervencao_policial;

            // Evolução temporal (linha)
            const ctxLinha = document.createElement("canvas");
            const linhaContainer = document.querySelector(".chart-row .chart-card:first-child .chart-placeholder");
            linhaContainer.innerHTML = "";
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

            // Gráfico de barras (correlação)
            const correlacao = data.correlacao_crimes || {};
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
                    scales: { y: { beginAtZero: true, min: -1, max: 1 }, x: {} },
                    plugins: { legend: { display: false } }
                }
            });

            // Scatterplot
            const scatterData = data.scatter_data || [];
            const ctxScatter = document.createElement("canvas");
            const scatterContainer = document.getElementById("chart-scatter");
            scatterContainer.innerHTML = "";
            scatterContainer.appendChild(ctxScatter);

            new Chart(ctxScatter, {
                type: "scatter",
                data: { datasets: [{ label: "Roubo x Letalidade", data: scatterData, backgroundColor: "rgba(75, 192, 192, 0.7)" }] },
                options: { responsive: true }
            });

        } catch (err) {
            console.error("Erro ao carregar dashboard:", err);
        }
    }

    // ===========================
    // Função aplicar filtros
    // ===========================
    async function aplicarFiltros() {
        const dataInicio = document.getElementById("data-inicio").value;
        const dataFim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;

        const params = new URLSearchParams();
        if (dataInicio) params.append("inicio", dataInicio);
        if (dataFim) params.append("fim", dataFim);
        if (municipio) params.append("municipio", municipio);

        await carregarDashboard(params.toString());
        await loadMapImage(document.getElementById("map-group").value);
    }

    // ===========================
    // Só aplica filtros ao clicar no botão
    // ===========================
    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ===========================
    // Exportar PDFs
    // ===========================
    document.getElementById("btn-export-pdf").addEventListener("click", async () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("p", "mm", "a4");
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth() - margin * 2;
        let yOffset = margin;

        const elements = [...document.querySelectorAll(".chart-placeholder")];

        for (let element of elements) {
            try {
                const canvas = await html2canvas(element, { scale: 2 });
                const imgData = canvas.toDataURL("image/png");
                const imgProps = pdf.getImageProperties(imgData);
                const pdfHeight = (imgProps.height * pageWidth) / imgProps.width;

                if (yOffset + pdfHeight > pdf.internal.pageSize.getHeight()) {
                    pdf.addPage();
                    yOffset = margin;
                }

                pdf.addImage(imgData, "PNG", margin, yOffset, pageWidth, pdfHeight);
                yOffset += pdfHeight + 10;
            } catch (err) {
                console.error("Erro ao capturar elemento para PDF:", err);
            }
        }

        pdf.save("dashboard.pdf");
    });
});
