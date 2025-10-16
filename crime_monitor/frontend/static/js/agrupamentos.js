let chartInstanceScatter = null;
let chartInstanceImportancia = null;
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
                    data: { labels, datasets: [{ label: 'Importância na formação dos clusters', data: valores, backgroundColor: valores.map(v => v >= 0 ? 'rgba(75, 192, 192, 0.7)' : 'rgba(255, 99, 132, 0.7)'), borderColor: valores.map(v => v >= 0 ? 'rgba(75, 192, 192, 1)' : 'rgba(255, 99, 132, 1)'), borderWidth: 1 }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, title: { display: true, text: "Importância" } }, x: { title: { display: true, text: "Variável" } } }, plugins: { legend: { display: false } } }
                });
            }

            // ===== Perfis médios =====
            const perfilCom = document.getElementById("perfil_com_registro");
            const perfilSem = document.getElementById("perfil_sem_registro");
            if (data.perfil_medio_img_com_registro_ocorrencias) {
                perfilCom.src = `${data.perfil_medio_img_com_registro_ocorrencias}?v=${Date.now()}`;
                perfilCom.style.display = "block";
            }
            if (data.perfil_medio_img_sem_registro_ocorrencias) {
                perfilSem.src = `${data.perfil_medio_img_sem_registro_ocorrencias}?v=${Date.now()}`;
                perfilSem.style.display = "block";
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
