let chartInstanceScatter = null;
let chartInstanceImportancia = null;
let municipios = [];

document.addEventListener("DOMContentLoaded", async () => {
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const mapImg = document.getElementById("map-img");

    // Carregar municípios
    try {
        const response = await fetch("/api/municipios");
        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // Autocomplete
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

    // Função principal: gerar gráficos e imagens
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

            // ======== PCA SCATTER ========
            const canvasScatter = document.getElementById("pca-scatter");
            const ctxScatter = canvasScatter.getContext("2d");
            const clustersUnicos = [...new Set(data.pca_data.map(d => d.cluster))];
            const datasetsScatter = clustersUnicos.map(c => ({
                label: `Cluster ${c}`,
                data: data.pca_data
                    .filter(d => d.cluster === c)
                    .map(p => ({ x: p.pca1, y: p.pca2 })),
                pointRadius: 4,
                backgroundColor: `hsl(${(c * 60) % 360}, 70%, 50%)`
            }));

            if (chartInstanceScatter) chartInstanceScatter.destroy();

            chartInstanceScatter = new Chart(ctxScatter, {
                type: "scatter",
                data: { datasets: datasetsScatter },
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

            // ======== GRÁFICO DE IMPORTÂNCIA ========
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
                        labels: labels,
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

            // ======== PERFIS MÉDIOS ========
            const perfilCom = document.getElementById("perfil_com_registro");
            const perfilSem = document.getElementById("perfil_sem_registro");

            if (data.perfil_medio_img_com_registro_ocorrencias && perfilCom) {
                perfilCom.src = `${data.perfil_medio_img_com_registro_ocorrencias}?v=${Date.now()}`;
                perfilCom.style.display = "block";
            }

            if (data.perfil_medio_img_sem_registro_ocorrencias && perfilSem) {
                perfilSem.src = `${data.perfil_medio_img_sem_registro_ocorrencias}?v=${Date.now()}`;
                perfilSem.style.display = "block";
            }

        } catch (err) {
            console.error("Erro ao carregar dados de agrupamento:", err);
            alert("Erro ao carregar dados. Veja o console para detalhes.");
        }
    }

    // ======== FILTROS ========
    async function aplicarFiltros() {
        const municipioValido = municipios.find(
            m => m.toLowerCase() === inputMunicipio.value.toLowerCase()
        );

        if (municipioValido || inputMunicipio.value === "") {
            await gerarGraficos();
        } else {
            alert("Município inválido. Selecione um da lista.");
        }
    }

    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ======== EXPORTAR PDF ========
    document.getElementById("btn-export-pdf").addEventListener("click", async () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("landscape", "px", "a4");
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth() - margin * 2;
        let yOffset = margin;

        const elementos = document.querySelectorAll("canvas, #map-img, #perfil-com-registro, #perfil-sem-registro");

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
