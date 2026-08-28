(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    config: null,
    reader: null,
    playing: false,
    crumbs: [{ kind: "FL", parent: null, title: "Favorites" }],
    qk: [],
    volTimer: 0,
    sqlTimer: 0,
    lastStatusAt: 0,
    displayed: null,
    pollBusy: false,
    listsLoaded: false,
  };

  async function api(path, opts) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.statusText);
    return data;
  }

  function setLink(on) {
    $("link").classList.toggle("on", on);
    $("link").classList.toggle("off", !on);
  }

  function radioErrorText(info) {
    const where = info && info.scanner ? ` at ${info.scanner}` : "";
    const why = (info && info.error) || "no response";
    return `Cannot reach scanner${where} — ${why}`;
  }

  function setRadioError(message) {
    const el = $("radio-error");
    if (!message) {
      el.textContent = "";
      el.classList.add("hidden");
      return;
    }
    el.textContent = message;
    el.classList.remove("hidden");
    setLink(false);
    $("channel-name").textContent = "Scanner unreachable";
  }

  async function pollHealth() {
    try {
      const health = await api("/api/health");
      if (health.ok) {
        setRadioError("");
        setLink(true);
        if (health.model) $("model").textContent = `${health.model} ${health.version}`.trim();
        return health;
      }
      setRadioError(radioErrorText(health));
      if (!health.model) $("model").textContent = health.scanner || "scanner unreachable";
      return health;
    } catch (err) {
      setRadioError(err.message || "ScanHead unreachable");
      return { ok: false, error: String(err.message || err) };
    }
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value || "—";
  }

  function clean(value) {
    const text = (value || "").toString().trim();
    if (!text || text === "None" || text === "TGID None" || text === "UID None") return "";
    return text;
  }

  function nodeName(node) {
    return clean(node && node.Name);
  }

  function stripPrefix(value, prefix) {
    const text = clean(value);
    const head = `${prefix}:`;
    if (text.toLowerCase().startsWith(head.toLowerCase())) return text.slice(head.length).trim();
    return text;
  }

  function composeListen(s) {
    const channel = s.channel || {};
    const site = s.site || {};
    const raw = s.raw || {};
    const siteFreq = s.siteFrequency || raw.SiteFrequency || {};
    const unitNode = s.unitId || raw.UnitID || {};
    const overwrite = clean(s.view && s.view.overwrite);
    const tgid = stripPrefix(channel.TGID, "TGID");
    const title = nodeName(channel) || nodeName(s.department) || nodeName(s.system) || overwrite;
    const listen = {
      title,
      frequency: clean(channel.Freq) || clean(siteFreq.Freq),
      tgid,
      modulation: clean(channel.Mod) || clean(site.Mod),
      service: clean(channel.SvcType),
      unit: stripPrefix(unitNode.Name || unitNode.U_Id, "UID"),
      system: nodeName(s.system),
      department: nodeName(s.department),
      site: nodeName(site),
      overwrite,
      landed: Boolean(nodeName(channel) || tgid) && !overwrite,
      scanning: Boolean(overwrite),
    };
    return listen;
  }

  function holdBadge(name, node) {
    if (!name) return "—";
    const bits = [name];
    if (node && node.Hold === "On") bits.push("HOLD");
    if (node && node.Avoid && node.Avoid !== "Off") bits.push(node.Avoid);
    return bits.join(" · ");
  }

  function renderStatus(s) {
    state.displayed = s;
    const prop = s.property || {};
    const listen = composeListen(s);
    const display = $("display");
    display.classList.toggle("scanning", Boolean(listen.scanning));
    display.classList.toggle("landed", Boolean(listen.landed));
    setText("mode", s.mode);
    setText("p25", prop.P25Status);
    setText("mute", prop.Mute);
    setText("overwrite", listen.overwrite || "");
    setText("channel-name", listen.title);
    setText("freq", listen.frequency);
    setText("mod", listen.modulation);
    setText("tgid", listen.tgid);
    setText("sys", holdBadge(listen.system, s.system));
    setText("dept", holdBadge(listen.department, s.department));
    setText("site", holdBadge(listen.site, s.site));
    setText("svc", listen.service);
    setText("uid", listen.unit);
    const sig = Number(prop.Sig || 0);
    const bars = $("sig");
    bars.dataset.n = String(Math.min(5, Math.max(0, sig)));
    bars.innerHTML = "<span></span><span></span><span></span><span></span><span></span>";
    $("rssi").value = Number(prop.Rssi || 0);
    $("info-lines").textContent = [s.view && s.view.info1, s.view && s.view.info2].filter(Boolean).join("  ");
    if (prop.VOL != null && document.activeElement !== $("vol")) {
      $("vol").value = prop.VOL;
      $("vol-out").textContent = prop.VOL;
    }
    if (prop.SQL != null && document.activeElement !== $("sql")) {
      $("sql").value = prop.SQL;
      $("sql-out").textContent = prop.SQL;
    }
    const popup = s.view && s.view.popup;
    const hasPopup = popup && typeof popup === "object" && Object.keys(popup).length;
    $("popup").classList.toggle("hidden", !hasPopup);
    if (hasPopup) $("popup-text").textContent = popup.Text || popup.Name || "Confirm";
  }

  function displayedChannelBody(extra) {
    const t = state.displayed && state.displayed.target;
    if (!t || !t.tkw) throw new Error("no displayed channel");
    return { tkw: t.tkw, xxx1: t.xxx1 || "", xxx2: t.xxx2 || "", ...extra };
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/api/ws`);
    state.lastStatusAt = Date.now();
    ws.onopen = () => {};
    ws.onclose = () => {
      setTimeout(connectWs, 1500);
    };
    ws.onmessage = (ev) => {
      const payload = JSON.parse(ev.data);
      if (payload.error) {
        setRadioError(radioErrorText(payload));
        return;
      }
      setRadioError("");
      setLink(true);
      state.lastStatusAt = Date.now();
      renderStatus(payload);
    };
  }

  async function refreshStatus(force) {
    const path = force ? "/api/status?fresh=1" : "/api/status";
    renderStatus(await api(path));
    state.lastStatusAt = Date.now();
  }

  function playAudio() {
    if (state.playing) {
      if (state.reader) state.reader.close();
      state.reader = null;
      $("audio").srcObject = null;
      state.playing = false;
      $("play").textContent = "Play audio";
      $("play").classList.remove("on");
      $("audio-state").textContent = "stopped";
      return;
    }
    if (!window.MediaMTXWebRTCReader) {
      $("audio-state").textContent = "reader missing";
      return;
    }
    $("audio-state").textContent = "connecting";
    state.reader = new window.MediaMTXWebRTCReader({
      url: state.config.whepUrl,
      onError: (err) => {
        $("audio-state").textContent = String(err);
      },
      onTrack: (evt) => {
        $("audio").srcObject = evt.streams[0];
        $("audio").play().catch(() => {});
        $("audio-state").textContent = "live";
      },
    });
    state.playing = true;
    $("play").textContent = "Stop audio";
    $("play").classList.add("on");
  }

  async function sendKey(code, mode) {
    await api("/api/key", { method: "POST", body: JSON.stringify({ code, mode: mode || "P" }) });
  }

  function childKind(kind, item, crumb) {
    if (kind === "FL") return { kind: "SYS", parent: item.Index, title: item.Name };
    if (kind === "SYS") return { kind: "DEPT", parent: item.Index, title: item.Name, sysType: item.Type };
    if (kind === "DEPT") {
      const t = `${crumb.sysType || ""} ${item.Type || ""}`.toLowerCase();
      const trunk = /trunk|edacs|motorola|ltr|dmr|nxdn|p25/.test(t);
      return { kind: trunk ? "TGID" : "CFREQ", parent: item.Index, title: item.Name };
    }
    if (kind === "SITE") return { kind: "SFREQ", parent: item.Index, title: item.Name };
    return null;
  }

  function renderCrumbs() {
    $("crumbs").innerHTML = "";
    state.crumbs.forEach((c, i) => {
      const b = document.createElement("button");
      b.className = "crumb";
      b.textContent = c.title;
      b.onclick = () => {
        state.crumbs = state.crumbs.slice(0, i + 1);
        loadList();
      };
      $("crumbs").appendChild(b);
    });
  }

  async function loadList() {
    renderCrumbs();
    const cur = state.crumbs[state.crumbs.length - 1];
    const qs = cur.parent != null ? `?parent=${encodeURIComponent(cur.parent)}` : "";
    $("list").textContent = "Loading…";
    try {
      const data = await api(`/api/lists/${cur.kind}${qs}`);
      $("list").innerHTML = "";
      (data.items || []).forEach((item) => {
        const b = document.createElement("button");
        const extra = [item.Type, item.Avoid, item.Q_Key && item.Q_Key !== "None" ? `QK ${item.Q_Key}` : ""]
          .filter(Boolean)
          .join(" · ");
        b.textContent = extra ? `${item.Name || item.Freq || item.TGID}  ${extra}` : item.Name || item.Freq || item.Index;
        b.onclick = () => {
          const next = childKind(data.kind || cur.kind, item, cur);
          if (!next) return;
          state.crumbs.push(next);
          loadList();
        };
        $("list").appendChild(b);
      });
      if (!(data.items || []).length) $("list").textContent = "No entries";
    } catch (err) {
      $("list").textContent = err.message;
    }
  }

  function renderQk(fields) {
    state.qk = fields.slice(1).map((v) => Number(v));
    $("qk").innerHTML = "";
    state.qk.forEach((st, i) => {
      const b = document.createElement("button");
      b.textContent = String(i);
      b.dataset.st = String(st);
      b.onclick = async () => {
        if (st === 0) return;
        state.qk[i] = st === 2 ? 1 : 2;
        await api("/api/qk/fqk", { method: "POST", body: JSON.stringify({ values: state.qk }) });
        renderQk(["FQK", ...state.qk]);
      };
      $("qk").appendChild(b);
    });
  }

  async function renderMenu(data) {
    $("menu-title").textContent = data.name || "Menu";
    $("menu-error").textContent = (data.error && data.error.Text) || "";
    $("menu-items").innerHTML = "";
    (data.items || []).forEach((item) => {
      const b = document.createElement("button");
      b.textContent = item.Value ? `${item.Name}  ${item.Value}` : item.Name;
      b.onclick = async () => {
        const next = await api("/api/menu/value", {
          method: "POST",
          body: JSON.stringify({ value: String(item.Index ?? item.Name) }),
        });
        renderMenu(next);
      };
      $("menu-items").appendChild(b);
    });
    const input = data.input && data.input.MaxLength;
    $("menu-form").classList.toggle("hidden", !input);
    if (input) $("menu-input").maxLength = Number(data.input.MaxLength);
  }

  function debounceLevel(which, value) {
    $(`${which}-out`).textContent = value;
    clearTimeout(state[`${which}Timer`]);
    state[`${which}Timer`] = setTimeout(() => {
      api(`/api/${which}`, { method: "POST", body: JSON.stringify({ level: Number(value) }) }).catch(() => {});
    }, 180);
  }

  function switchTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === `panel-${name}`));
  }

  function setAdvanced(on) {
    document.body.classList.toggle("advanced-on", on);
  }

  async function loadOptional() {
    if (state.listsLoaded) return;
    state.listsLoaded = true;
    loadList();
    try {
      const loc = await api("/api/location");
      const [_, lat, lon, rng] = loc.fields;
      const form = $("loc-form");
      form.latitude.value = lat || "";
      form.longitude.value = lon || "";
      form.range.value = rng || "";
    } catch {
      /* optional */
    }
    try {
      const clock = await api("/api/clock");
      $("clock").textContent = clock.fields.join(" ");
    } catch {
      /* optional */
    }
  }

  async function init() {
    $("sig").innerHTML = "<span></span><span></span><span></span><span></span><span></span>";
    try {
      state.config = await api("/api/config");
      $("model").textContent = `${state.config.model} ${state.config.version}`.trim();
      $("vol").max = state.config.volMax;
      $("sql").max = state.config.sqlMax;
      const listen = state.config.hlsUrl || "";
      $("client-rtsp").textContent = listen ? `vlc ${listen}` : "";
      $("client-mplayer").textContent = listen
        ? `ffmpeg -hide_banner -i ${listen} -f alsa default`
        : "";
      $("app-version").textContent = state.config.appVersion ? `ScanHead ${state.config.appVersion}` : "";
    } catch (err) {
      $("model").textContent = err.message;
    }
    const health = await pollHealth();
    if (health.ok) {
      try {
        await refreshStatus(true);
      } catch (err) {
        setRadioError(err.message);
      }
      loadOptional();
    } else {
      $("list").textContent = $("radio-error").textContent;
    }
    connectWs();
    setInterval(async () => {
      if (state.pollBusy) return;
      state.pollBusy = true;
      try {
        const next = await pollHealth();
        if (!next.ok) return;
        if (!state.listsLoaded) loadOptional();
        if (Date.now() - state.lastStatusAt > 2000) {
          await refreshStatus(false).catch((err) => setRadioError(err.message));
        }
      } finally {
        state.pollBusy = false;
      }
    }, 2000);

    $("play").onclick = playAudio;
    $("advanced-controls").onchange = (e) => setAdvanced(e.target.checked);
    setAdvanced($("advanced-controls").checked);
    $("vol").oninput = (e) => debounceLevel("vol", e.target.value);
    $("sql").oninput = (e) => debounceLevel("sql", e.target.value);
    document.querySelector(".actions").addEventListener("click", async (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const act = btn.dataset.act;
      const extra = act === "avoid" ? { status: Number(btn.dataset.status) } : {};
      await api(`/api/${act}`, { method: "POST", body: JSON.stringify(displayedChannelBody(extra)) });
    });
    document.body.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-key]");
      if (!btn) return;
      sendKey(btn.dataset.key).catch((err) => console.error(err));
    });
    document.querySelector(".tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (btn) switchTab(btn.dataset.tab);
    });
    $("qk-load").onclick = async () => {
      const data = await api("/api/qk/fqk");
      renderQk(data.fields);
    };
    $("menu-top").onclick = async () => renderMenu(await api("/api/menu", { method: "POST", body: JSON.stringify({ menu_id: "TOP" }) }));
    $("menu-back").onclick = async () => renderMenu(await api("/api/menu/back", { method: "POST", body: JSON.stringify({ level: "" }) }));
    $("menu-exit").onclick = async () => {
      await api("/api/menu/back", { method: "POST", body: JSON.stringify({ level: "RETURN_PREVOUS_MODE" }) });
      $("menu-title").textContent = "Menu";
      $("menu-items").innerHTML = "";
    };
    $("menu-form").onsubmit = async (e) => {
      e.preventDefault();
      renderMenu(await api("/api/menu/value", { method: "POST", body: JSON.stringify({ value: $("menu-input").value }) }));
    };
    document.querySelector(".modes").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-jpm]");
      if (!btn) return;
      await api("/api/jpm", { method: "POST", body: JSON.stringify({ mode: btn.dataset.jpm, index: btn.dataset.index || "" }) });
    });
    $("rec-start").onclick = () => api("/api/replay", { method: "POST", body: JSON.stringify({ start: true }) });
    $("rec-stop").onclick = () => api("/api/replay", { method: "POST", body: JSON.stringify({ start: false }) });
    $("rec-files").onclick = async () => {
      const data = await api("/api/lists/IREC_FILE");
      $("more-list").innerHTML = (data.items || [])
        .map((item) => `<button type="button">${item.Name || item.Index} ${item.Time || ""}</button>`)
        .join("");
    };
    $("loc-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await api("/api/location", {
        method: "POST",
        body: JSON.stringify({
          latitude: fd.get("latitude"),
          longitude: fd.get("longitude"),
          range: fd.get("range"),
        }),
      });
    };
  }

  window.addEventListener("load", init);
})();
