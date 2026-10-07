/* AQMon dashboard: calls the Cognito-protected HTTP API and draws charts with Chart.js. */
(function () {
  const cfg = window.AQMON_CONFIG;
  const $ = (id) => document.getElementById(id);
  const MAX_BYTES = 5 * 1024 * 1024;
  const SERIES_VARS = ["--s1", "--s2", "--s3", "--s4"];
  const CATEGORY_ORDER = ["Good", "Fair", "Poor", "Very poor", "Extremely poor"];
  const UNITS = { pm25: "µg/m³", pm10: "µg/m³", no2: "ppm", o3: "ppm", co: "ppm", so2: "ppm" };
  const LABELS = { pm25: "PM2.5", pm10: "PM10", no2: "NO₂", o3: "O₃", co: "CO", so2: "SO₂" };

  let stations = [];
  let stationColor = {};
  const charts = {};

  // ------------------------------------------------------------------ helpers
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const fmt = (v, param) => (v == null ? "–" : Number(v).toFixed(UNITS[param] === "ppm" ? 4 : 1));

  function showError(message) {
    const b = $("banner");
    b.textContent = message;
    b.hidden = false;
  }

  async function api(path, options = {}) {
    const token = await AQAuth.getIdToken();
    if (!token) {
      showLanding();
      throw new Error("not signed in");
    }
    const res = await fetch(cfg.apiUrl + path, {
      ...options,
      headers: { Authorization: token, "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const body = await res.json().catch(() => ({}));
    if (res.status === 401) {
      sessionStorage.clear();
      showLanding();
      throw new Error("session expired, please sign in again");
    }
    if (!res.ok) throw new Error(body.error || `request failed (${res.status})`);
    return body;
  }

  function cell(row, text, opts = {}) {
    const td = document.createElement("td");
    if (opts.swatch) {
      const s = document.createElement("span");
      s.className = "swatch";
      s.style.background = opts.swatch;
      td.appendChild(s);
    }
    if (opts.status) {
      const s = document.createElement("span");
      s.className = `status ${opts.status}`;
      s.textContent = text;
      td.appendChild(s);
    } else {
      td.appendChild(document.createTextNode(text));
    }
    if (opts.title) td.title = opts.title;
    row.appendChild(td);
    return td;
  }

  function fillTable(tableId, rows, cols, emptyText) {
    const tbody = $(tableId).querySelector("tbody");
    tbody.replaceChildren();
    if (!rows.length) {
      const tr = tbody.insertRow();
      const td = cell(tr, emptyText);
      td.colSpan = cols;
      td.className = "empty";
      return;
    }
    rows.forEach((r) => {
      const tr = tbody.insertRow();
      r(tr);
    });
  }

  // ------------------------------------------------------------------ views
  function showLanding() {
    $("landing").hidden = false;
    $("app").hidden = true;
    $("user-box").hidden = true;
  }

  function showApp() {
    const c = AQAuth.claims();
    const groups = c["cognito:groups"] || [];
    const uploader = groups.includes("uploaders");
    $("landing").hidden = true;
    $("app").hidden = false;
    $("user-box").hidden = false;
    $("user-email").textContent = c.email || c.sub;
    $("user-role").textContent = uploader ? "uploader" : "viewer";
    $("upload-allowed").hidden = !uploader;
    $("upload-denied").hidden = uploader;
  }

  // ------------------------------------------------------------------ charts
  function baseOptions(yTitle) {
    const ink2 = css("--ink-2");
    const grid = css("--grid");
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { color: ink2, boxWidth: 12, boxHeight: 12, usePointStyle: false } },
        tooltip: { padding: 10, boxPadding: 4 },
      },
      scales: {
        x: { ticks: { color: ink2, maxRotation: 0, autoSkipPadding: 16 }, grid: { display: false }, border: { color: css("--axis") } },
        y: {
          beginAtZero: true,
          title: { display: !!yTitle, text: yTitle, color: ink2 },
          ticks: { color: ink2 },
          grid: { color: grid },
          border: { display: false },
        },
      },
    };
  }

  function draw(id, config) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id), config);
  }

  function assignStationColors() {
    // Colour follows the station (sorted by id), never its rank in a filtered view.
    stationColor = {};
    stations.forEach((s, i) => {
      stationColor[s.station_id] = i < SERIES_VARS.length ? css(SERIES_VARS[i]) : css("--muted");
    });
  }

  function drawDaily(records, param, limit) {
    const dates = [...new Set(records.map((r) => r.date))].sort();
    const byStation = {};
    records.forEach((r) => ((byStation[r.station_id] ||= {})[r.date] = r.mean));
    const datasets = stations
      .filter((s) => byStation[s.station_id])
      .map((s) => ({
        label: s.station_name,
        data: dates.map((d) => byStation[s.station_id][d] ?? null),
        borderColor: stationColor[s.station_id],
        backgroundColor: stationColor[s.station_id],
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        spanGaps: false,
      }));
    if (limit != null) {
      datasets.push({
        label: `24-h limit (${limit} ${UNITS[param]})`,
        data: dates.map(() => limit),
        borderColor: css("--limit"),
        backgroundColor: css("--limit"),
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
      });
    }
    const opts = baseOptions(`${LABELS[param]} daily mean (${UNITS[param]})`);
    opts.plugins.tooltip.callbacks = { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y, param)}` };
    draw("chart-daily", { type: "line", data: { labels: dates, datasets }, options: opts });
    $("daily-title").textContent = `${LABELS[param]} daily mean by station`;
  }

  function drawMonthly(summary, param) {
    const months = [...new Set(summary.flatMap((s) => Object.keys(s.monthly)))].sort();
    const datasets = summary.map((s) => ({
      label: s.station_name,
      data: months.map((m) => s.monthly[m] ?? null),
      backgroundColor: stationColor[s.station_id],
      borderRadius: 4,
      borderSkipped: "start",
      barPercentage: 0.85,
      categoryPercentage: 0.8,
    }));
    const opts = baseOptions(`${LABELS[param]} (${UNITS[param]})`);
    opts.plugins.tooltip.callbacks = { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y, param)}` };
    draw("chart-monthly", { type: "bar", data: { labels: months, datasets }, options: opts });
  }

  function drawExceedances(summary, param, limit) {
    const note = $("exceed-note");
    if (limit == null) {
      $("exceed-title").textContent = "Days above the 24-hour limit";
      note.textContent = `No 24-hour alert limit is configured for ${LABELS[param]}; alerts cover PM2.5 and PM10.`;
      draw("chart-exceed", { type: "bar", data: { labels: [], datasets: [] }, options: baseOptions("") });
      return;
    }
    $("exceed-title").textContent = `Days above the ${LABELS[param]} 24-hour limit (${limit} ${UNITS[param]})`;
    note.textContent = "Only days with at least 18 hourly readings are counted.";
    const opts = baseOptions("days");
    opts.plugins.legend.display = false;
    opts.scales.y.ticks.precision = 0;
    draw("chart-exceed", {
      type: "bar",
      data: {
        labels: summary.map((s) => s.station_name),
        datasets: [
          {
            label: "Days over limit",
            data: summary.map((s) => s.exceedance_days),
            backgroundColor: summary.map((s) => stationColor[s.station_id]),
            borderRadius: 4,
            borderSkipped: "start",
            barPercentage: 0.6,
          },
        ],
      },
      options: opts,
    });
  }

  function drawCategories(pm25Summary) {
    const ramp = ["--ord1", "--ord2", "--ord3", "--ord4", "--ord5"].map(css);
    const datasets = CATEGORY_ORDER.map((cat, i) => ({
      label: cat,
      data: pm25Summary.map((s) => (s.categories || {})[cat] || 0),
      backgroundColor: ramp[i],
      borderColor: css("--surface"),
      borderWidth: { left: 0, right: 2, top: 0, bottom: 0 },
      barPercentage: 0.6,
    })).filter((d) => d.data.some((v) => v > 0));
    const opts = baseOptions("");
    opts.indexAxis = "y";
    opts.scales.x.stacked = true;
    opts.scales.y.stacked = true;
    opts.scales.x.title = { display: true, text: "station-days", color: css("--ink-2") };
    opts.scales.x.grid = { color: css("--grid") };
    opts.scales.y.grid = { display: false };
    opts.interaction = { mode: "nearest", intersect: true };
    draw("chart-category", { type: "bar", data: { labels: pm25Summary.map((s) => s.station_name), datasets }, options: opts });
  }

  function drawTiles(pm25Summary) {
    const days = pm25Summary.reduce((a, s) => a + s.days, 0);
    const over = pm25Summary.reduce((a, s) => a + (s.exceedance_days || 0), 0);
    const peak = pm25Summary.reduce((best, s) => (!best || s.peak_value > best.peak_value ? s : best), null);
    const tiles = [
      ["Stations", stations.length, "with uploaded data"],
      ["Station-days analysed", days.toLocaleString(), "PM2.5 daily records"],
      ["Days over PM2.5 limit", over, "24-h mean above 25 µg/m³"],
      ["Highest PM2.5 day", peak ? `${fmt(peak.peak_value, "pm25")}` : "–", peak ? `${peak.station_name}, ${peak.peak_day}` : "no data yet"],
    ];
    const box = $("tiles");
    box.replaceChildren(
      ...tiles.map(([label, value, hint]) => {
        const div = document.createElement("div");
        div.className = "tile";
        div.innerHTML = '<div class="label"></div><div class="value"></div><div class="hint"></div>';
        div.querySelector(".label").textContent = label;
        div.querySelector(".value").textContent = value;
        div.querySelector(".hint").textContent = hint;
        return div;
      })
    );
  }

  function fillSummaryTable(summary, param) {
    fillTable(
      "summary-table",
      summary.map((s) => (tr) => {
        cell(tr, s.station_name, { swatch: stationColor[s.station_id] });
        cell(tr, s.days);
        cell(tr, fmt(s.average, param));
        cell(tr, s.peak_day);
        cell(tr, fmt(s.peak_value, param));
        cell(tr, s.exceedance_days ?? "–");
      }),
      6,
      "No data yet - upload a CSV file."
    );
  }

  // ------------------------------------------------------------------ data loading
  async function loadAnalytics() {
    const param = $("f-param").value;
    const from = $("f-from").value;
    const to = $("f-to").value;
    const q = new URLSearchParams({ parameter: param, from, to });
    const pm25q = new URLSearchParams({ parameter: "pm25", from, to });
    const [st, daily, summary, pm25] = await Promise.all([
      api("/stations"),
      api(`/daily?${q}`),
      api(`/summary?${q}`),
      param === "pm25" ? null : api(`/summary?${pm25q}`),
    ]);
    stations = st.stations.sort((a, b) => a.station_id.localeCompare(b.station_id));
    assignStationColors();
    const pm25Summary = (pm25 || summary).stations;
    drawTiles(pm25Summary);
    drawDaily(daily.records, param, summary.limit);
    drawMonthly(summary.stations, param);
    drawExceedances(summary.stations, param, summary.limit);
    drawCategories(pm25Summary);
    fillSummaryTable(summary.stations, param);
  }

  async function loadAlerts() {
    const { alerts } = await api("/alerts");
    $("alerts-note").textContent = `${alerts.length} alert day(s)`;
    fillTable(
      "alerts-table",
      alerts.map((a) => (tr) => {
        cell(tr, a.date);
        cell(tr, a.station_name);
        cell(tr, LABELS[a.parameter] || a.parameter);
        cell(tr, `${fmt(a.mean, a.parameter)} ${a.units}`);
        cell(tr, `${a.limit} ${a.units}`);
      }),
      5,
      "No exceedances detected yet."
    );
  }

  async function loadUploads() {
    const { uploads } = await api("/uploads");
    fillTable(
      "uploads-table",
      uploads.map((u) => (tr) => {
        cell(tr, u.filename);
        cell(tr, u.status.replace("_", " ").toLowerCase(), { status: u.status, title: u.error || "" });
        cell(tr, u.rows_total ?? "–");
        cell(tr, u.daily_records ?? "–");
        cell(tr, u.exceedances ?? "–");
        cell(tr, new Date(u.created_at).toLocaleString());
      }),
      6,
      "No uploads yet."
    );
    const failed = uploads.filter((u) => u.status === "FAILED");
    $("jobs-note").textContent = failed.length ? `${failed.length} failed - hover the status for the reason` : "";
    return uploads;
  }

  async function refreshAll() {
    $("banner").hidden = true;
    try {
      await Promise.all([loadAnalytics(), loadAlerts(), loadUploads()]);
    } catch (e) {
      showError(e.message);
    }
  }

  // ------------------------------------------------------------------ upload
  async function uploadFiles(files) {
    const list = $("upload-progress");
    list.replaceChildren();
    const ids = [];
    for (const file of files) {
      const li = document.createElement("li");
      list.appendChild(li);
      if (!/\.csv$/i.test(file.name) || file.size === 0 || file.size > MAX_BYTES) {
        li.textContent = `✗ ${file.name}: must be a non-empty .csv file of at most 5 MB`;
        continue;
      }
      try {
        li.textContent = `… ${file.name}: requesting upload URL`;
        const target = await api("/uploads", { method: "POST", body: JSON.stringify({ filename: file.name, size: file.size }) });
        const form = new FormData();
        Object.entries(target.fields).forEach(([k, v]) => form.append(k, v));
        form.append("file", file);
        li.textContent = `… ${file.name}: uploading to S3`;
        const res = await fetch(target.url, { method: "POST", body: form });
        if (!res.ok) throw new Error(`S3 rejected the upload (${res.status})`);
        li.textContent = `✓ ${file.name}: stored in S3, queued for processing`;
        ids.push(target.upload_id);
      } catch (e) {
        li.textContent = `✗ ${file.name}: ${e.message}`;
      }
    }
    if (ids.length) await waitForProcessing(ids);
  }

  async function waitForProcessing(ids) {
    const deadline = Date.now() + 3 * 60 * 1000;
    while (Date.now() < deadline) {
      const uploads = await loadUploads();
      const pending = uploads.filter((u) => ids.includes(u.upload_id) && !["PROCESSED", "FAILED"].includes(u.status));
      if (!pending.length) break;
      await new Promise((r) => setTimeout(r, 3000));
    }
    await refreshAll();
  }

  // ------------------------------------------------------------------ start
  async function start() {
    $("login-btn").addEventListener("click", () => AQAuth.login());
    $("logout-btn").addEventListener("click", () => AQAuth.logout());
    $("refresh-btn").addEventListener("click", refreshAll);
    $("f-param").addEventListener("change", refreshAll);
    $("file-input").addEventListener("change", (e) => ($("upload-btn").disabled = !e.target.files.length));
    $("upload-btn").addEventListener("click", async () => {
      const input = $("file-input");
      $("upload-btn").disabled = true;
      await uploadFiles([...input.files]);
      input.value = "";
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (!$("app").hidden) refreshAll();
    });

    if (!cfg || !cfg.apiUrl) {
      showError("config.js is missing - run deploy/deploy.sh to generate it.");
      return;
    }
    try {
      await AQAuth.handleRedirect();
    } catch (e) {
      showError(e.message);
    }
    if (!(await AQAuth.getIdToken())) {
      showLanding();
      return;
    }
    showApp();
    refreshAll();
  }

  start();
})();
