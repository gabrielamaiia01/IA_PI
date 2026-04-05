/* ============================================================
   associacao.js  –  Lógica da página de Regras de Associação
   ============================================================ */

"use strict";

// ── Instâncias de gráficos (para destruir/recriar) ───────────
let chartItemsets = null;
let chartScatter  = null;

// ── Dados brutos da última execução ─────────────────────────
let currentRules   = [];
let currentCooc    = {};
let currentColunas = [];

// ── Constante de rótulos amigáveis ───────────────────────────
const CRIME_LABELS = {
  hom_doloso:             "Homicídio Doloso",
  latrocinio:             "Latrocínio",
  hom_por_interv_policial:"Homicídio Policial",
  tentat_hom:             "Tentativa Homicídio",
  lesao_corp_dolosa:      "Lesão Corp. Dolosa",
  lesao_corp_culposa:     "Lesão Corp. Culposa",
  estupro:                "Estupro",
  roubo_veiculo:          "Roubo Veículo",
  roubo_rua:              "Roubo Rua",
  roubo_comercio:         "Roubo Comércio",
  roubo_residencia:       "Roubo Residência",
  estelionato:            "Estelionato",
  apreensao_drogas:       "Apreensão Drogas",
  trafico_drogas:         "Tráfico Drogas",
  apf:                    "Apreensão Arma",
  pessoas_desaparecidas:  "Pessoas Desap.",
  encontro_cadaver:       "Encontro Cadáver",
  registro_ocorrencias:   "Reg. Ocorrências",
  furto_veiculos:         "Furto Veículos",
};
const label = k => CRIME_LABELS[k] || k.replace(/_/g, " ");

// ── Paleta para heatmap ──────────────────────────────────────
function heatColor(val) {
  // val: 0..1  → branco → azul forte
  const r = Math.round(255 - val * 200);
  const g = Math.round(255 - val * 160);
  const b = Math.round(255);
  return `rgb(${r},${g},${b})`;
}

// ── Helpers ──────────────────────────────────────────────────
function liftBadge(lift) {
  if (lift >= 2.0) return `<span class="lift-badge lift-badge--hi">▲ ${lift}</span>`;
  if (lift >= 1.5) return `<span class="lift-badge lift-badge--mid">~ ${lift}</span>`;
  return               `<span class="lift-badge lift-badge--lo">▼ ${lift}</span>`;
}

function relBadge(lift, conf) {
  if (lift >= 2.0 && conf >= 0.7) return `<span class="rel-badge rel-badge--alta">Alta</span>`;
  if (lift >= 1.5 || conf >= 0.6) return `<span class="rel-badge rel-badge--media">Média</span>`;
  return                            `<span class="rel-badge rel-badge--baixa">Baixa</span>`;
}

function metricBar(val, color) {
  const pct = Math.min(100, Math.round(val * 100));
  return `
    <div class="metric-bar-wrap">
      <div class="metric-bar">
        <div class="metric-bar-fill" style="width:${pct}%;background:${color}"></div>
      </div>
      <span class="metric-val">${(val * 100).toFixed(0)}%</span>
    </div>`;
}

function chips(arr, cls = "") {
  return arr.map(c => `<span class="crime-chip ${cls}">${label(c)}</span>`).join(" ");
}

// ── Visibilidade de estados ──────────────────────────────────
function showState(state) {
  document.getElementById("empty-state").style.display    = state === "empty"   ? "" : "none";
  document.getElementById("loading-state").style.display  = state === "loading" ? "" : "none";
  document.getElementById("error-state").style.display    = state === "error"   ? "" : "none";
  document.getElementById("results-section").style.display= state === "results" ? "" : "none";
}

// ── Renderizar tabela ────────────────────────────────────────
function renderTable(rules) {
  const tbody = document.getElementById("rules-tbody");
  if (!rules.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:#64748b">
      Nenhuma regra corresponde ao filtro.</td></tr>`;
    return;
  }
  tbody.innerHTML = rules.map(r => `
    <tr>
      <td>${chips(r.antecedentes)}</td>
      <td>${chips(r.consequentes, "crime-chip--consequente")}</td>
      <td>${metricBar(r.support, "#0ea5e9")}</td>
      <td>${metricBar(r.confidence, "#8b5cf6")}</td>
      <td>${liftBadge(r.lift)}</td>
      <td>${relBadge(r.lift, r.confidence)}</td>
    </tr>`).join("");
}

// ── Filtro + ordenação da tabela ─────────────────────────────
function applyTableFilters() {
  const q     = document.getElementById("search-rules").value.toLowerCase();
  const sort  = document.getElementById("sort-rules").value;
  let rules   = [...currentRules];

  if (q) {
    rules = rules.filter(r =>
      [...r.antecedentes, ...r.consequentes].some(c => label(c).toLowerCase().includes(q) || c.includes(q))
    );
  }
  rules.sort((a, b) => b[sort] - a[sort]);
  renderTable(rules);
}

// ── Gráfico de barras: itemsets frequentes ───────────────────
function renderItemsets(itemsets) {
  const ctx = document.getElementById("chart-itemsets").getContext("2d");
  if (chartItemsets) chartItemsets.destroy();

  const topN = itemsets.slice(0, 15);
  chartItemsets = new Chart(ctx, {
    type: "bar",
    data: {
      labels: topN.map(i => {
        // troca chaves brutas por labels amigáveis
        const partes = i.itemset_label.split(" + ").map(label);
        return partes.join(" + ");
      }),
      datasets: [{
        label: "Suporte",
        data: topN.map(i => +(i.support * 100).toFixed(2)),
        backgroundColor: topN.map((_, idx) =>
          `hsl(${210 + idx * 8}, 70%, ${55 - idx * 1.5}%)`
        ),
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` Suporte: ${ctx.raw}%`
          }
        }
      },
      scales: {
        x: { title: { display: true, text: "Suporte (%)" }, beginAtZero: true },
        y: { ticks: { font: { size: 11 } } }
      }
    }
  });
}

// ── Gráfico scatter: suporte × confiança × lift ──────────────
function renderScatter(rules) {
  const ctx = document.getElementById("chart-scatter").getContext("2d");
  if (chartScatter) chartScatter.destroy();

  const dataset = rules.map(r => ({
    x: +(r.support * 100).toFixed(2),
    y: +(r.confidence * 100).toFixed(2),
    r: Math.max(4, Math.min(22, r.lift * 4)),
    label: `${r.antecedentes.map(label).join(", ")} → ${r.consequentes.map(label).join(", ")}`,
    lift: r.lift,
  }));

  chartScatter = new Chart(ctx, {
    type: "bubble",
    data: {
      datasets: [{
        label: "Regra",
        data: dataset,
        backgroundColor: dataset.map(d =>
          d.lift >= 2 ? "rgba(22,163,74,.65)" :
          d.lift >= 1.5 ? "rgba(202,138,4,.65)" :
          "rgba(220,38,38,.55)"
        ),
        borderColor: "#fff",
        borderWidth: 1.5,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const d = ctx.raw;
              return [
                d.label,
                `Suporte: ${d.x}% · Confiança: ${d.y}% · Lift: ${d.lift}`
              ];
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: "Suporte (%)" }, beginAtZero: true },
        y: { title: { display: true, text: "Confiança (%)" }, min: 0, max: 105 }
      }
    }
  });
}

// ── Heatmap de co-ocorrência ─────────────────────────────────
function renderHeatmap(cooc, colunas) {
  const container = document.getElementById("heatmap-container");
  if (!colunas.length) { container.innerHTML = "<p>Sem dados.</p>"; return; }

  // limitar a 14 colunas para evitar overflow extremo
  const cols = colunas.slice(0, 14);

  let html = `<table class="heatmap-table"><thead><tr><th></th>`;
  cols.forEach(c => {
    html += `<th title="${label(c)}">${label(c).slice(0,10)}…</th>`;
  });
  html += `</tr></thead><tbody>`;

  cols.forEach(row => {
    html += `<tr><th class="row-label" title="${label(row)}">${label(row).slice(0,12)}…</th>`;
    cols.forEach(col => {
      const val = (cooc[row] && cooc[row][col] != null) ? cooc[row][col] : 0;
      const pct = (val * 100).toFixed(0);
      const bg  = heatColor(val);
      // texto escuro se fundo claro
      const textColor = val > 0.5 ? "#fff" : "#1e293b";
      html += `<td style="background:${bg};color:${textColor}" title="${label(row)} ∩ ${label(col)}: ${pct}%">${pct}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  container.innerHTML = html;
}

// ── Rede de associações (canvas manual) ──────────────────────
function renderNetwork(rules) {
  const canvas = document.getElementById("network-canvas");
  const W = canvas.offsetWidth || 700;
  const H = parseInt(canvas.getAttribute("height")) || 480;
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  if (!rules.length) return;

  // Coletar nós únicos e calcular frequência
  const nodeFreq = {};
  rules.forEach(r => {
    [...r.antecedentes, ...r.consequentes].forEach(c => {
      nodeFreq[c] = (nodeFreq[c] || 0) + 1;
    });
  });
  const nodes = Object.keys(nodeFreq);
  const N     = nodes.length;
  if (!N) return;

  // Posicionar em círculo com pequeno jitter
  const cx = W / 2, cy = H / 2;
  const radius = Math.min(W, H) * 0.35;
  const pos = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / N - Math.PI / 2;
    pos[n] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });

  // Desenhar arestas
  rules.slice(0, 40).forEach(r => {
    r.antecedentes.forEach(ant => {
      r.consequentes.forEach(cons => {
        if (!pos[ant] || !pos[cons]) return;
        const width  = Math.max(1, Math.min(6, (r.lift - 1) * 2));
        const alpha  = Math.min(0.85, 0.25 + r.confidence * 0.6);
        ctx.beginPath();
        ctx.moveTo(pos[ant].x, pos[ant].y);

        // curva quadrática para não sobrepor
        const mx = (pos[ant].x + pos[cons].x) / 2 + (Math.random() - 0.5) * 30;
        const my = (pos[ant].y + pos[cons].y) / 2 + (Math.random() - 0.5) * 30;
        ctx.quadraticCurveTo(mx, my, pos[cons].x, pos[cons].y);

        ctx.strokeStyle = r.lift >= 2
          ? `rgba(22,163,74,${alpha})`
          : r.lift >= 1.5
            ? `rgba(202,138,4,${alpha})`
            : `rgba(148,163,184,${alpha})`;
        ctx.lineWidth = width;
        ctx.stroke();

        // seta simples
        const angle2 = Math.atan2(pos[cons].y - my, pos[cons].x - mx);
        ctx.beginPath();
        ctx.moveTo(pos[cons].x, pos[cons].y);
        ctx.lineTo(
          pos[cons].x - 10 * Math.cos(angle2 - 0.4),
          pos[cons].y - 10 * Math.sin(angle2 - 0.4)
        );
        ctx.lineTo(
          pos[cons].x - 10 * Math.cos(angle2 + 0.4),
          pos[cons].y - 10 * Math.sin(angle2 + 0.4)
        );
        ctx.closePath();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.fill();
      });
    });
  });

  // Desenhar nós
  const maxFreq = Math.max(...Object.values(nodeFreq));
  nodes.forEach(n => {
    const {x, y} = pos[n];
    const r      = 8 + (nodeFreq[n] / maxFreq) * 18;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fillStyle   = "#1e40af";
    ctx.strokeStyle = "#fff";
    ctx.lineWidth   = 2;
    ctx.fill();
    ctx.stroke();

    // label
    ctx.fillStyle  = "#1e293b";
    ctx.font       = `${Math.max(9, 10 + (nodeFreq[n] / maxFreq) * 3)}px sans-serif`;
    ctx.textAlign  = "center";
    ctx.textBaseline = "middle";
    const lbl = label(n);
    const shortLbl = lbl.length > 14 ? lbl.slice(0, 13) + "…" : lbl;

    // fundo branco atrás do texto
    const tw = ctx.measureText(shortLbl).width;
    ctx.fillStyle   = "rgba(255,255,255,0.8)";
    ctx.fillRect(x - tw / 2 - 2, y + r + 2, tw + 4, 14);
    ctx.fillStyle = "#1e293b";
    ctx.fillText(shortLbl, x, y + r + 9);
  });
}

// ── Insights narrativos automáticos ─────────────────────────
function renderInsights(rules, stats) {
  const list = document.getElementById("insights-list");
  const insights = [];

  if (!rules.length) {
    list.innerHTML = `<li class="insight-item"><span class="insight-text">Nenhuma regra encontrada com os parâmetros atuais.</span></li>`;
    return;
  }

  // Top regra por lift
  const top = rules[0];
  insights.push({
    icon: "🔗",
    text: `A associação mais forte do período liga <strong>${top.antecedentes.map(label).join(" + ")}</strong> a <strong>${top.consequentes.map(label).join(" + ")}</strong> com lift de <strong>${top.lift}</strong> — ${(top.lift * 100 - 100).toFixed(0)}% mais provável que o acaso.`
  });

  // Regra com maior confiança
  const hConf = [...rules].sort((a,b) => b.confidence - a.confidence)[0];
  insights.push({
    icon: "🎯",
    text: `Quando ocorre <strong>${hConf.antecedentes.map(label).join(" + ")}</strong>, há <strong>${(hConf.confidence * 100).toFixed(0)}%</strong> de chance de também ocorrer <strong>${hConf.consequentes.map(label).join(" + ")}</strong> na mesma área-período.`
  });

  // Crime mais frequente como antecedente
  const freq = {};
  rules.forEach(r => r.antecedentes.forEach(a => { freq[a] = (freq[a]||0)+1; }));
  const topAnt = Object.entries(freq).sort((a,b) => b[1]-a[1])[0];
  if (topAnt) {
    insights.push({
      icon: "📌",
      text: `<strong>${label(topAnt[0])}</strong> aparece como antecedente em <strong>${topAnt[1]}</strong> regra(s), sendo o crime com maior poder preditivo sobre outros delitos.`
    });
  }

  // Cobertura média
  insights.push({
    icon: "📊",
    text: `As <strong>${stats.total_regras}</strong> regras encontradas cobrem em média <strong>${(stats.suporte_medio * 100).toFixed(1)}%</strong> das transações, com confiança média de <strong>${(stats.confianca_media * 100).toFixed(1)}%</strong>.`
  });

  // Regras de alta relevância
  const alta = rules.filter(r => r.lift >= 2.0 && r.confidence >= 0.7).length;
  if (alta > 0) {
    insights.push({
      icon: "🚨",
      text: `<strong>${alta}</strong> regra(s) apresentam alta relevância (lift ≥ 2 e confiança ≥ 70%), indicando padrões criminais com forte correlação que merecem atenção prioritária das forças de segurança.`
    });
  }

  // Período
  insights.push({
    icon: "📅",
    text: `Análise baseada em <strong>${stats.total_transacoes.toLocaleString("pt-BR")}</strong> registros entre <strong>${stats.periodo_inicio}</strong> e <strong>${stats.periodo_fim}</strong>, gerando <strong>${stats.total_itemsets}</strong> conjuntos frequentes.`
  });

  list.innerHTML = insights.map((ins, i) =>
    `<li class="insight-item" style="animation-delay:${i * 60}ms">
      <span class="insight-icon">${ins.icon}</span>
      <span class="insight-text">${ins.text}</span>
    </li>`
  ).join("");
}

// ── KPIs ─────────────────────────────────────────────────────
function renderKPIs(stats) {
  const kpis = [
    { label: "Transações",       value: stats.total_transacoes.toLocaleString("pt-BR"), sub: "registros analisados" },
    { label: "Itemsets Freq.",   value: stats.total_itemsets,    sub: `suporte ≥ ${(stats.suporte_medio*100).toFixed(1)}% médio` },
    { label: "Regras Geradas",   value: stats.total_regras,      sub: "após filtros aplicados" },
    { label: "Lift Médio",       value: stats.lift_medio,        sub: "força média das regras" },
    { label: "Confiança Média",  value: (stats.confianca_media*100).toFixed(1)+"%", sub: "precisão média" },
    { label: "Período",          value: stats.periodo_inicio.slice(0,7), sub: `até ${stats.periodo_fim.slice(0,7)}` },
  ];
  document.getElementById("assoc-kpis").innerHTML = kpis.map(k =>
    `<div class="assoc-kpi">
      <div class="assoc-kpi-label">${k.label}</div>
      <div class="assoc-kpi-value">${k.value}</div>
      <div class="assoc-kpi-sub">${k.sub}</div>
    </div>`
  ).join("");
}

// ── Highlight principal ──────────────────────────────────────
function renderHighlight(rules) {
  if (!rules.length) return;
  const top = rules[0];
  const ant = top.antecedentes.map(label).join(" + ");
  const con = top.consequentes.map(label).join(" + ");
  document.getElementById("assoc-highlight").innerHTML =
    `🔍 <strong>Insight em destaque:</strong> Nos dados filtrados, quando ocorre 
     <strong>${ant}</strong> em uma área, a probabilidade de também ocorrer 
     <strong>${con}</strong> é de <strong>${(top.confidence*100).toFixed(0)}%</strong> 
     — <strong>${(top.lift * 100 - 100).toFixed(0)}%</strong> acima do esperado ao acaso 
     (lift = <strong>${top.lift}</strong>).`;
}

// ── Executar análise ─────────────────────────────────────────
async function executarAnalise() {
  showState("loading");

  const params = new URLSearchParams({
    min_support: document.getElementById("min-support").value,
    min_conf:    document.getElementById("min-conf").value,
    min_lift:    document.getElementById("min-lift").value,
    group_by:    document.getElementById("group-by").value,
    top_n:       50,
  });

  const inicio    = document.getElementById("data-inicio").value;
  const fim       = document.getElementById("data-fim").value;
  const municipio = document.getElementById("municipio").value;
  if (inicio)    params.append("inicio",    inicio);
  if (fim)       params.append("fim",       fim);
  if (municipio) params.append("municipio", municipio);

  try {
    const res  = await fetch(`/api/associacao_data?${params.toString()}`);
    const data = await res.json();

    if (data.error) {
      document.getElementById("error-msg").textContent = data.error;
      showState("error");
      return;
    }

    currentRules   = data.rules;
    currentCooc    = data.coocorrencia;
    currentColunas = data.colunas;

    showState("results");

    renderKPIs(data.stats);
    renderHighlight(data.rules);
    renderTable(data.rules);
    renderItemsets(data.itemsets_freq);
    renderScatter(data.rules);
    renderHeatmap(data.coocorrencia, data.colunas);
    renderInsights(data.rules, data.stats);

    // Rede com pequeno delay para o canvas ter dimensões corretas
    setTimeout(() => renderNetwork(data.rules), 100);

  } catch (err) {
    console.error(err);
    document.getElementById("error-msg").textContent = "Erro de conexão com o servidor.";
    showState("error");
  }
}

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {

  // Carregar municípios
  try {
    const municipios = await (await fetch("/api/municipios")).json();
    const dl = document.getElementById("lista-municipios");
    const inp = document.getElementById("municipio");
    inp.addEventListener("input", () => {
      const v = inp.value.toLowerCase();
      dl.innerHTML = "";
      municipios.filter(m => m.toLowerCase().startsWith(v)).forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        dl.appendChild(opt);
      });
    });
  } catch (e) { console.warn("Municípios não carregados:", e); }

  // Sliders → atualizar valor exibido
  ["min-support", "min-conf", "min-lift"].forEach(id => {
    const input = document.getElementById(id);
    const span  = document.getElementById(id + "-val");
    input.addEventListener("input", () => {
      span.textContent = parseFloat(input.value).toFixed(2);
    });
  });

  // Botão executar
  document.getElementById("btn-aplicar").addEventListener("click", executarAnalise);

  // Filtro de tabela em tempo real
  document.getElementById("search-rules").addEventListener("input",  applyTableFilters);
  document.getElementById("sort-rules").addEventListener("change",   applyTableFilters);

  // Re-renderizar rede ao redimensionar janela
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (currentRules.length) renderNetwork(currentRules);
    }, 300);
  });
});

// ===== Exportar PDF - Associação =====
document.getElementById("btn-export-associacao").addEventListener("click", async () => {
  const dataInicio = document.getElementById("data-inicio").value;
  const dataFim = document.getElementById("data-fim").value;
  const municipio = document.getElementById("municipio").value;
  const groupBy = document.getElementById("group-by").value;

  const params = new URLSearchParams();
  if (dataInicio) params.append("inicio", dataInicio);
  if (dataFim) params.append("fim", dataFim);
  if (municipio) params.append("municipio", municipio);
  if (groupBy) params.append("group_by", groupBy);

  try {
    const response = await fetch(`/api/export_associacao_pdf?${params.toString()}`);
    if (!response.ok) throw new Error("Erro ao gerar PDF");

    // Download automático
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "relatorio_associacao.pdf";
    document.body.appendChild(a);
    a.click();

    a.remove();
    window.URL.revokeObjectURL(url);

  } catch (err) {
    console.error("Erro ao exportar PDF:", err);
    alert("Erro ao gerar PDF. Verifique o servidor.");
  }
});