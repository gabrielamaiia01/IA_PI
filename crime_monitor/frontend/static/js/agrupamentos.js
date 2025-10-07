let chartInstance = null;
let municipios = [];

document.addEventListener("DOMContentLoaded", async () => {
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const mapImg = document.getElementById("map-img");

    // ===========================
    // Carregar municípios
    // ===========================
    try {
        const response = await fetch("/api/municipios");
        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // ===========================
    // Autocomplete
    // ===========================
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
    // Gerar gráficos
    // ===========================
    async function gerarGraficos() {
        const k = document.getElementById("num-clusters").value;
        const inicio = document.getElementById("data-inicio").value;
        const fim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;

        try {
            const params = new URLSearchParams({ k });
            if (inicio) params.append("inicio", inicio);
            if (fim) params.append("fim", fim);
            if (municipio) params.append("municipio", municipio);

            const res = await fetch(`/api/agrupamentos_data?${params.toString()}`);
            if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);

            const data = await res.json();
            if (data.error) {
                alert(data.error);
                return;
            }

            // ===========================
            // PCA Scatter
            // ===========================
            const canvas = document.getElementById("pca-scatter");
            const ctx = canvas.getContext("2d");

            const clustersUnicos = [...new Set(data.pca_data.map(d => d.cluster))];
            const datasets = clustersUnicos.map(c => ({
                label: `Cluster ${c}`,
                data: data.pca_data
                    .filter(d => d.cluster === c)
                    .map(p => ({ x: p.pca1, y: p.pca2 })),
                pointRadius: 4,
                backgroundColor: `hsl(${(c * 60) % 360}, 70%, 50%)`
            }));

            if (chartInstance) chartInstance.destroy();

            chartInstance = new Chart(ctx, {
                type: "scatter",
                data: { datasets },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: "right" },
                        title: { display: true, text: "Distribuição dos Clusters (PCA 2D)" }
                    },
                    scales: {
                        x: { title: { display: true, text: "Componente Principal 1" } },
                        y: { title: { display: true, text: "Componente Principal 2" } }
                    }
                }
            });

            // ===========================
            // Gráfico de importância (Chart.js)
            // ===========================
            if (data.importancias) {
                const div = document.getElementById("elbow-plot");
                div.innerHTML = '<canvas id="importancia-chart"></canvas>';
                const ctx2 = document.getElementById("importancia-chart").getContext("2d");
                const labels = Object.keys(data.importancias);
                const valores = Object.values(data.importancias);

                chartInstance = new Chart(ctx2, {
                    type: "scatter",
                    data: { datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false, // permite que ocupe mais espaço
                        plugins: {
                            legend: { position: "right" },
                            title: { display: false } // remove o título
                        },
                        scales: {
                            x: { title: { display: true, text: "Componente Principal 1" } },
                            y: { title: { display: true, text: "Componente Principal 2" } }
                        }
                    }
                });

            }

        } catch (err) {
            console.error("Erro ao carregar dados de agrupamento:", err);
            alert("Erro ao carregar dados. Veja o console para detalhes.");
        }
    }

    // ===========================
    // Atualizar mapa
    // ===========================
    async function loadMapImage() {
        if (!mapImg) return;

        const inicio = document.getElementById("data-inicio")?.value;
        const fim = document.getElementById("data-fim")?.value;
        const municipio = inputMunicipio.value;

        const params = new URLSearchParams();
        if (inicio) params.append("inicio", inicio);
        if (fim) params.append("fim", fim);
        if (municipio) params.append("municipio", municipio);

        try {
            const response = await fetch(`/api/map_image/mcirc?${params.toString()}`);
            const data = await response.json();
            if (data.image_url) mapImg.src = data.image_url;
        } catch (err) {
            console.error("Erro ao carregar mapa:", err);
        }
    }

    // ===========================
    // Aplicar filtros
    // ===========================
    async function aplicarFiltros() {
        const municipioValido = municipios.find(
            m => m.toLowerCase() === inputMunicipio.value.toLowerCase()
        );

        if (municipioValido || inputMunicipio.value === "") {
            await gerarGraficos();
            await loadMapImage();
        } else {
            alert("Município inválido. Selecione um da lista.");
        }
    }

    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ===========================
    // Exportar dashboard como PDF
    // ===========================
    document.getElementById("btn-export-pdf").addEventListener("click", async () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("landscape", "px", "a4");
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth() - margin * 2;
        let yOffset = margin;

        const elementos = document.querySelectorAll("canvas, #map-img");

        for (let el of elementos) {
            try {
                const canvasImg = await html2canvas(el, { scale: 2 });
                const imgData = canvasImg.toDataURL("image/png");
                const imgProps = pdf.getImageProperties(imgData);
                const pdfWidth = pageWidth;
                const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

                if (yOffset + pdfHeight > pdf.internal.pageSize.getHeight()) {
                    pdf.addPage();
                    yOffset = margin;
                }

                pdf.addImage(imgData, "PNG", margin, yOffset, pdfWidth, pdfHeight);
                yOffset += pdfHeight + 10;
            } catch (err) {
                console.error("Erro ao capturar elemento para PDF:", err);
            }
        }

        pdf.save("dashboard.pdf");
    });
});
