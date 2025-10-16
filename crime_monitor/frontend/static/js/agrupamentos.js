let chartInstanceScatter = null;
let chartInstanceImportancia = null;
let chartInstancePerfil = null; // novo
let municipios = [];

// Guarda os dados já carregados para não recalcular
let dadosClustersCache = null;

document.addEventListener("DOMContentLoaded", async () => {
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");

    // ===== Carregar municípios =====
    try {
        const response = await fetch("/api/municipios");
        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // ===== Autocomplete =====
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

    // ===== Função para gerar gráficos completos =====
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

            // ===== Dados de clusters =====
            const res = await fetch(`/api/agrupamentos_data?${params.toString()}`);
            if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
            const data = await res.json();
            if (data.error) {
                alert(data.error);
                return;
            }

            // Guarda em cache para atualizar mapa depois sem recalcular tudo
            dadosClustersCache = { data, inicio, fim };

            // ===== PCA SCATTER =====
            const canvasScatter = document.getElementById("pca-scatter");
            const ctxScatter = canvasScatter.getContext("2d");
            const clustersUnicos = [...new Set(data.pca_data.map(d => d.cluster))];
            const datasetsScatter = clustersUnicos.map(c => ({
                label: `Cluster ${c}`,
                data: data.pca_data.filter(d => d.cluster === c).map(p => ({ x: p.pca1, y: p.pca2 })),
                pointRadius: 4,
                backgroundColor: `hsl(${(c * 60) % 360}, 70%, 50%)`
            }));

            if (chartInstanceScatter) chartInstanceScatter.destroy();
            chartInstanceScatter = new Chart(ctxScatter, {
                type: "scatter",
                data: { datasets: datasetsScatter },
                options: {
                    responsive: true,
                    plugins: { legend: { position: "right" }, title: { display: true, text: "Distribuição dos Clusters (PCA 2D)" } },
                    scales: {
                        x: { title: { display: true, text: "Componente Principal 1" } },
                        y: { title: { display: true, text: "Componente Principal 2" } }
                    }
                }
            });

            // ===== Gráfico de importância =====
            if (data.importancias) {
                const div = document.getElementById("elbow-plot");
                div.innerHTML = '<canvas id="importancia-chart"></canvas>';
                const ctxImp = document.getElementById("importancia-chart").getContext("2d");
                const labels = Object.keys(data.importancias);
                const valores = Object.values(data.importancias);

                if (chartInstanceImportancia) chartInstanceImportancia.destroy();
                chartInstanceImportancia = new Chart(ctxImp, {
                    type: "bar",
                    data: { 
                        labels, 
                        datasets: [{
                            label: 'Importância na formação dos clusters', 
                            data: valores, 
                            backgroundColor: valores.map(v => v >= 0 ? 'rgba(75, 192, 192, 0.7)' : 'rgba(255, 99, 132, 0.7)'), 
                            borderColor: valores.map(v => v >= 0 ? 'rgba(75, 192, 192, 1)' : 'rgba(255, 99, 132, 1)'), 
                            borderWidth: 1 
                        }]
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false, 
                        scales: { 
                            y: { beginAtZero: true, title: { display: true, text: "Importância" } }, 
                            x: { title: { display: true, text: "Variável" } } 
                        }, 
                        plugins: { legend: { display: false } } 
                    }
                });
            }

            // ===== Perfil médio interativo =====
            if (data.perfil_medio_data) {
                const container = document.getElementById("perfil-container");
                container.innerHTML = `<canvas id="perfilChart"></canvas>`;
                const canvas = document.getElementById("perfilChart");
                canvas.style.minHeight = "400px"; // altura mínima
                canvas.style.width = "100%";

                const ctxPerfil = canvas.getContext("2d");
                const mediaClusters = data.perfil_medio_data;
                const clusters = Object.keys(mediaClusters);
                const variaveis = Object.keys(mediaClusters[clusters[0]]);

                // Paleta de cores fixa
                const coresFixas = [
                    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                    "#bcbd22", "#17becf", "#a55194", "#393b79",
                    "#637939", "#8c6d31", "#843c39", "#7b4173",
                    "#3182bd", "#e6550d", "#31a354", "#756bb1"
                ];

                const datasets = variaveis.map((variavel, i) => ({
                    label: variavel,
                    data: clusters.map(c => mediaClusters[c][variavel]),
                    backgroundColor: coresFixas[i % coresFixas.length],
                    borderColor: "#333",
                    borderWidth: 1
                }));

                if (chartInstancePerfil) chartInstancePerfil.destroy();
                chartInstancePerfil = new Chart(ctxPerfil, {
                    type: "bar",
                    data: {
                        labels: clusters.map(c => `Cluster ${c}`),
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        layout: { padding: { bottom: 20 } }, // espaço para legenda
                        plugins: {
                            legend: {
                                position: "top",
                                labels: { usePointStyle: true },
                                onClick: (e, legendItem, legend) => {
                                    const ci = legend.chart;
                                    const index = legendItem.datasetIndex;
                                    const meta = ci.getDatasetMeta(index);
                                    meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
                                    ci.update();
                                }
                            }
                        },
                        interaction: { mode: 'index', intersect: false },
                        scales: {
                            x: { title: { display: true, text: "Clusters" }, stacked: false },
                            y: { beginAtZero: true, title: { display: true, text: "Intensidade relativa" } }
                        }
                    }
                });
            }

            // ===== Atualiza mapa =====
            await atualizarMapa();

        } catch (err) {
            console.error("Erro ao carregar dados de agrupamento:", err);
            alert("Erro ao carregar dados. Veja o console para detalhes.");
        }
    }

    // ===== Função separada para atualizar o mapa =====
    async function atualizarMapa() {
        if (!dadosClustersCache) return;
        const group_by = document.getElementById("group-by").value || "cisp";
        const mapClusters = document.getElementById("mapa_clusters_img");
        const { inicio, fim } = dadosClustersCache;

        try {
            const resMapa = await fetch(`/api/mapa_clusters?group_by=${group_by}&inicio=${inicio}&fim=${fim}&k=${document.getElementById("num-clusters").value}&mcirc=${inputMunicipio.value}`);
            if (!resMapa.ok) throw new Error(`Erro HTTP ${resMapa.status}`);
            const dataMapa = await resMapa.json();

            if (dataMapa.mapa_clusters) {
                mapClusters.src = `${dataMapa.mapa_clusters}?v=${Date.now()}`;
                mapClusters.style.display = "block";
            } else {
                console.error("Resposta inesperada da API de clusters:", dataMapa);
            }
        } catch (err) {
            console.error("Erro ao atualizar mapa dos clusters:", err);
        }
    }

    // ===== Filtros =====
    async function aplicarFiltros() {
        const municipioValido = municipios.find(m => m.toLowerCase() === inputMunicipio.value.toLowerCase());
        if (municipioValido || inputMunicipio.value === "") {
            await gerarGraficos();
        } else {
            alert("Município inválido. Selecione um da lista.");
        }
    }

    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ===== Atualiza mapa apenas quando mudar o select =====
    document.getElementById("group-by").addEventListener("change", async () => {
        await atualizarMapa();
    });
});

// ===== Função para exportar PDF =====
document.getElementById("btn-export-pdf").addEventListener("click", async () => {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF("p", "mm", "a4");
    const margin = 10;
    const pageWidth = pdf.internal.pageSize.getWidth() - 2 * margin;
    const pageHeight = pdf.internal.pageSize.getHeight() - 2 * margin;
    let yOffset = margin;

    // Seleciona todos os elementos que queremos colocar no PDF
    const elementos = [
        document.getElementById("pca-scatter"),
        document.getElementById("importancia-chart"),
        document.getElementById("perfilChart"),
        document.getElementById("mapa_clusters_img") // mapa
    ].filter(el => el); // remove nulls caso algum ainda não exista

    for (let el of elementos) {
        let imgData;

        if (el.tagName.toLowerCase() === "canvas") {
            // Se for canvas, usamos html2canvas
            imgData = await html2canvas(el, { scale: 2 }).then(c => c.toDataURL("image/png"));
        } else if (el.tagName.toLowerCase() === "img") {
            // Se for img (mapa), usamos direto src
            imgData = el.src;
        }

        const imgProps = pdf.getImageProperties(imgData);
        const pdfWidth = pageWidth;
        const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

        if (yOffset + pdfHeight > pageHeight + margin) {
            pdf.addPage();
            yOffset = margin;
        }

        pdf.addImage(imgData, "PNG", margin, yOffset, pdfWidth, pdfHeight);
        yOffset += pdfHeight + 10; // espaço entre imagens
    }

    pdf.save("graficos_agrupamento.pdf");
});


