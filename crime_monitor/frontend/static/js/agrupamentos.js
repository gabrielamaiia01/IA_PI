let chartInstanceScatter = null;
let chartInstanceImportancia = null;
let chartInstancePerfil = null; // novo
let municipios = [];
let dadosClustersCache = null;

document.addEventListener("DOMContentLoaded", async () => {
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const btnAplicar = document.getElementById("btn-aplicar");
    const groupBySelect = document.getElementById("group-by");
    const btnExportPdf = document.getElementById("btn-export-pdf");

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

            const res = await fetch(`/api/agrupamentos_data?${params.toString()}`);
            if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
            const data = await res.json();
            if (data.error) return alert(data.error);

            dadosClustersCache = { data, inicio, fim };

            // ===== PCA SCATTER =====
            const canvasScatter = document.getElementById("pca-scatter");
            const ctxScatter = canvasScatter.getContext("2d");
            const clustersUnicos = [...new Set(data.pca_data.map(d => d.cluster))];

            const gerarCoresDistintas = (n) => {
                const cores = [];
                const saturacao = 70;
                const luminosidade = 50;
                for (let i = 0; i < n; i++) {
                    const h = Math.round((360 / n) * i);
                    cores.push(`hsl(${h}, ${saturacao}%, ${luminosidade}%)`);
                }
                return cores;
            };

            const coresDistintas = gerarCoresDistintas(clustersUnicos.length);
            const datasetsScatter = clustersUnicos.map((c, i) => ({
                label: `Cluster ${c}`,
                data: data.pca_data.filter(d => d.cluster === c).map(p => ({ x: p.pca1, y: p.pca2 })),
                pointRadius: 4,
                backgroundColor: coresDistintas[i]
            }));

            if (chartInstanceScatter) chartInstanceScatter.destroy();
            chartInstanceScatter = new Chart(ctxScatter, {
                type: "scatter",
                data: { datasets: datasetsScatter },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: "top" },
                        title: { display: true, text: "Distribuição dos Clusters (PCA 2D)" }
                    },
                    scales: {
                        x: { title: { display: true, text: "Componente Principal 1" } },
                        y: { title: { display: true, text: "Componente Principal 2" } }
                    }
                }
            });

            // ===== Importância das variáveis =====
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

            // ===== Perfil médio dos clusters =====
            if (data.perfil_medio_data) {
                const container = document.getElementById("perfil-container");
                container.innerHTML = `<canvas id="perfilChart"></canvas>`;
                const canvas = document.getElementById("perfilChart");
                canvas.style.minHeight = "400px";
                canvas.style.width = "100%";
                const ctxPerfil = canvas.getContext("2d");

                const mediaClusters = data.perfil_medio_data;
                const clusters = Object.keys(mediaClusters);
                const variaveis = Object.keys(mediaClusters[clusters[0]]);
                const coresFixas = [
                    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                    "#bcbd22", "#17becf", "#a55194", "#393b79"
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
                    data: { labels: clusters.map(c => `Cluster ${c}`), datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        layout: { padding: { bottom: 20 } },
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
                            x: { title: { display: true, text: "Clusters" } },
                            y: { beginAtZero: true, title: { display: true, text: "Intensidade relativa" } }
                        }
                    }
                });
            }

            await atualizarMapa();
        } catch (err) {
            console.error("Erro ao carregar dados de agrupamento:", err);
            alert("Erro ao carregar dados. Veja o console para detalhes.");
        }
    }

    // ===== Atualizar mapa =====
    async function atualizarMapa() {
        if (!dadosClustersCache) return;
        const group_by = groupBySelect.value || "cisp";
        const mapClusters = document.getElementById("mapa_clusters_img");
        const { inicio, fim } = dadosClustersCache;

        try {
            const resMapa = await fetch(`/api/mapa_clusters?group_by=${group_by}&inicio=${inicio}&fim=${fim}&k=${document.getElementById("num-clusters").value}&mcirc=${inputMunicipio.value}`);
            if (!resMapa.ok) throw new Error(`Erro HTTP ${resMapa.status}`);
            const dataMapa = await resMapa.json();

            if (dataMapa.mapa_clusters) {
                mapClusters.src = `${dataMapa.mapa_clusters}?v=${Date.now()}`;
                mapClusters.style.display = "block";
            } else console.error("Resposta inesperada da API de clusters:", dataMapa);
        } catch (err) {
            console.error("Erro ao atualizar mapa dos clusters:", err);
        }
    }

    // ===== Aplicar filtros =====
    btnAplicar.addEventListener("click", async () => {
        const municipioValido = municipios.find(m => m.toLowerCase() === inputMunicipio.value.toLowerCase());
        if (municipioValido || inputMunicipio.value === "") {
            await gerarGraficos();
        } else {
            alert("Município inválido. Selecione um da lista.");
        }
    });

    groupBySelect.addEventListener("change", async () => await atualizarMapa());

    // ===== Exportar PDF =====
    btnExportPdf.addEventListener("click", async () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("p", "mm", "a4");
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth() - 2 * margin;
        const pageHeight = pdf.internal.pageSize.getHeight() - 2 * margin;
        let yOffset = margin;

        const elementos = [
            document.getElementById("pca-scatter"),
            document.getElementById("importancia-chart"),
            document.getElementById("perfilChart"),
            document.getElementById("mapa_clusters_img")
        ].filter(el => el);

        for (let el of elementos) {
            let imgData;
            if (el.tagName.toLowerCase() === "canvas") {
                imgData = await html2canvas(el, { scale: 2 }).then(c => c.toDataURL("image/png"));
            } else imgData = el.src;

            const imgProps = pdf.getImageProperties(imgData);
            const pdfWidth = pageWidth;
            const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

            if (yOffset + pdfHeight > pageHeight + margin) {
                pdf.addPage();
                yOffset = margin;
            }

            pdf.addImage(imgData, "PNG", margin, yOffset, pdfWidth, pdfHeight);
            yOffset += pdfHeight + 10;
        }

        pdf.save("graficos_agrupamento.pdf");
    });

    // ===== Previsão de cluster =====
    const formCluster = document.getElementById('cluster-prediction-form');
    const resultadoCluster = document.getElementById('resultado-cluster');

    if (formCluster) {
        formCluster.addEventListener('submit', async (e) => {
            e.preventDefault();
            resultadoCluster.style.color = "#333";
            resultadoCluster.textContent = "⏳ Calculando cluster...";

            // Declarar a variável features como objeto vazio
            const features = {};

            // Selecionar todos os inputs do formulário
            const inputs = formCluster.querySelectorAll('input');

            // Preencher o objeto features com os valores do formulário
            inputs.forEach(input => {
                const val = input.value || input.getAttribute('value'); // pega value mesmo se disabled
                features[input.name] = parseFloat(val);
            });

            const k = parseInt(document.getElementById("num-clusters").value);

            console.log("Dados enviados para previsão de cluster:", features, "com k =", k);

            try {
                const res = await fetch('/api/predizer_cluster', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ features, k })
                });
                const data = await res.json();

                if (data.error) {
                    resultadoCluster.style.color = "red";
                    resultadoCluster.textContent = `Erro: ${data.error}`;
                } else {
                    resultadoCluster.style.color = "green";
                    resultadoCluster.innerHTML = `O registro informado pertence ao <strong>Cluster ${data.cluster}</strong><br>(k = ${data.k})`;
                }
            } catch (err) {
                console.error("Erro ao prever cluster:", err);
                resultadoCluster.style.color = "red";
                resultadoCluster.textContent = "Erro ao prever cluster.";
            }
        });
    }
});
