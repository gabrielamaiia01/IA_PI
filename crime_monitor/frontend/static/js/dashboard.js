document.addEventListener("DOMContentLoaded", async () => {
    let municipios = [];
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const mapImg = document.getElementById("map-img");

    // ===========================
    // 1. Carregar municípios
    // ===========================
    try {
        const response = await fetch("/api/municipios");
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // Autocomplete do input de município
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

    function getColor(valor, min, max) {
        valor = Number(valor) || 0;

        if (max === min) return '#ffffe5'; // evita divisão por zero

        // Normaliza entre 0 e 1
        const t = (valor - min) / (max - min);

        // Gradiente: amarelo -> vermelho -> preto
        let r, g, b;

        if (t < 0.5) {
            // #ffffe5 → #bd0026
            const t2 = t * 2;

            r = Math.round(255 * (1 - t2) + 189 * t2);
            g = Math.round(255 * (1 - t2) + 0 * t2);
            b = Math.round(229 * (1 - t2) + 38 * t2); // 🔥 229 ao invés de 178
        } else {
            // vermelho (#bd0026) → preto (#000000)
            const t2 = (t - 0.5) * 2;
            r = Math.round(189 * (1 - t2));
            g = Math.round(0);
            b = Math.round(38 * (1 - t2));
        }

        return `rgb(${r}, ${g}, ${b})`;
    }
    // ===========================
    // 2. Carregar mapa temático
    // ===========================
    let mapa = null;
    let camadaGeo = null;

    const nomesBonitos = {
        letalidade_violenta: "Letalidade Violenta",
        hom_doloso: "Homicídio Doloso",
        latrocinio: "Latrocínio",
        hom_por_interv_policial: "Intervenção Policial",
        tentat_hom: "Tentativa de Homicídio",
        lesao_corp_dolosa: "Lesão Corporal Dolosa",
        estupro: "Estupro",
        lesao_corp_culposa: "Lesão Corporal Culposa",
        roubo_veiculo: "Roubo de Veículo",
        roubo_rua: "Roubo de Rua",
        roubo_comercio: "Roubo a Comércio",
        roubo_residencia: "Roubo a Residência",
        estelionato: "Estelionato",
        apreensao_drogas: "Apreensão de Drogas",
        trafico_drogas: "Tráfico de Drogas",
        apf: "APF",
        pessoas_desaparecidas: "Pessoas Desaparecidas",
        encontro_cadaver: "Encontro de Cadáver",
        registro_ocorrencias: "Registro de Ocorrências",
        furto_veiculos: "Furto de Veículos"
    };

      async function loadMapImage(groupBy = "mcirc", coluna = "letalidade_violenta") {

        const dataInicio = document.getElementById("data-inicio").value;
        const dataFim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;

        const params = new URLSearchParams();
        if (dataInicio) params.append("inicio", dataInicio);
        if (dataFim) params.append("fim", dataFim);
        if (municipio) params.append("municipio", municipio);

        try {
            // 🔥 AGORA COM COLUNA NA URL
            const response = await fetch(`/api/map_image/${groupBy}/${coluna}?${params.toString()}`);
            const data = await response.json();

            if (data.error) {
                console.error(data.error);
                return;
            }

            const geojson = typeof data.geojson === "string"
                ? JSON.parse(data.geojson)
                : data.geojson;

            const colunaAtual = data.coluna;
            const label = nomesBonitos[colunaAtual] || colunaAtual;

            if (!mapa) {
                mapa = L.map('map').setView([-22.9, -43.2], 7);

                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap'
                }).addTo(mapa);

                setTimeout(() => mapa.invalidateSize(), 100);
            }

            if (camadaGeo) {
                mapa.removeLayer(camadaGeo);
            }

            const valores = geojson.features.map(f => Number(f.properties[colunaAtual]) || 0);

            const min = Math.min(...valores);
            const max = Math.max(...valores);

            camadaGeo = L.geoJSON(geojson, {

                style: function (feature) {
                    const valor = feature.properties[colunaAtual];

                    return {
                        fillColor: getColor(valor, min, max),
                        weight: 1,
                        color: '#ccc',
                        fillOpacity: 1
                    };
                },

                onEachFeature: function (feature, layer) {

                    const nome = feature.properties.nome || "Região";
                    const valor = feature.properties[colunaAtual];

                    layer.bindTooltip(
                        `<b>${nome}</b><br>${label}: ${valor}`,
                        { sticky: true }
                    );

                    layer.on({
                        mouseover: function (e) {
                            e.target.setStyle({
                                weight: 2,
                                color: '#000',
                                fillOpacity: 0.9
                            });
                        },
                        mouseout: function (e) {
                            camadaGeo.resetStyle(e.target);
                        }
                    });
                }

            }).addTo(mapa);

            mapa.fitBounds(camadaGeo.getBounds());

        } catch (err) {
            console.error("Erro ao carregar mapa:", err);
        }
    }

    document.getElementById("map-group").addEventListener("change", (e) => loadMapImage(e.target.value, document.getElementById("map-column").value));
    document.getElementById("map-column").addEventListener("change", (e) => loadMapImage(document.getElementById("map-group").value, e.target.value));
    // ===========================
    // 3. Carregar Dashboard
    // ===========================
    async function carregarDashboard(params = "") {
        try {
            const response = await fetch(`/api/dashboard_data${params ? "?" + params : ""}`);
            const data = await response.json();

            if (data.error) {
                console.error(data.error);
                return;
            }

            // KPIs principais
            document.getElementById("total_letalidade").textContent = data.letalidade_violenta_total ?? "N/A";
            document.getElementById("homicidios_dolosos").textContent = data.homicidios_dolosos ?? "N/A";
            document.getElementById("latrocinios").textContent = data.latrocinios ?? "N/A";
            document.getElementById("mortes_policial").textContent = data.mortes_intervencao_policial ?? "N/A";

            // Textos auxiliares (variações e tendências)
            const pctH = data.homicidios_dolosos_pct;
            document.querySelector("#homicidios_dolosos + .description").textContent =
                "comparado ao mês anterior: " + (pctH != null ? (pctH >= 0 ? "+" : "") + parseInt(pctH) + "%" : "N/A");

            const pctL = data.variacao_latrocinio_anual_pct;
            document.querySelector("#latrocinios + .description").textContent =
                "variação anual: " + (pctL != null ? (pctL >= 0 ? "+" : "") + parseInt(pctL) + "%" : "N/A");

            document.querySelector("#mortes_policial + .description").textContent =
                "tendência: " + (data.tendencia_mortes_intervencao_policial ?? "N/A");

            // Gráfico de linha
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
                        borderColor: "rgba(26, 50, 181, 1)",
                        backgroundColor: "rgba(0, 81, 255, 0.54)",
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { responsive: true, scales: { y: { beginAtZero: true } } }
            });

            // Gráfico de correlação (barras)
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
                        backgroundColor: values.map(v => v >= 0 ? 'rgba(0, 17, 255, 0.7)' : 'rgba(0, 204, 255, 0.8)')
                    }]
                },
                options: {
                    responsive: true,
                    scales: { y: { beginAtZero: true, min: -1, max: 1 } },
                    plugins: { legend: { display: false } }
                }
            });

            // Scatter plot
            const scatterData = data.scatter_data || [];
            const ctxScatter = document.createElement("canvas");
            const scatterContainer = document.getElementById("chart-scatter");
            scatterContainer.innerHTML = "";
            scatterContainer.appendChild(ctxScatter);

            new Chart(ctxScatter, {
                type: "scatter",
                data: { datasets: [{ label: "Roubo x Letalidade", data: scatterData, backgroundColor: "#007bff" }] },
                options: { responsive: true }
            });

        } catch (err) {
            console.error("Erro ao carregar dashboard:", err);
        }
    }

    // ===========================
    // 4. Aplicar filtros
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

    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ===========================
    // 5. Exportar PDF (via API Flask)
    // ===========================
    document.getElementById("btn-export-pdf").addEventListener("click", async () => {
        const dataInicio = document.getElementById("data-inicio").value;
        const dataFim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;
        const groupBy = document.getElementById("map-group").value;

        const params = new URLSearchParams();
        if (dataInicio) params.append("inicio", dataInicio);
        if (dataFim) params.append("fim", dataFim);
        if (municipio) params.append("municipio", municipio);
        if (groupBy) params.append("group_by", groupBy);
        try {
            const response = await fetch(`/api/export_dashboard_pdf?${params.toString()}`);
            if (!response.ok) throw new Error("Erro ao gerar PDF");

            // Cria o download automático do PDF
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "relatorio_dashboard.pdf";
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Erro ao exportar PDF:", err);
            alert("Erro ao gerar PDF. Verifique o servidor.");
        }
    });

    // ===========================
    // 6. Inicializar
    // ===========================
    await carregarDashboard();
    await loadMapImage();
});
