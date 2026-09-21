const TEME = [
  { id: "vse", label: "Vse" },
  { id: "ai", label: "AI" },
  { id: "medicina", label: "Medicina" },
  { id: "spacex", label: "SpaceX" },
  { id: "tesla", label: "Tesla" },
  { id: "robotika", label: "Robotika" },
  { id: "fizika", label: "Fizika" },
];

const STATUS_LABEL = {
  paper: "paper",
  uradno: "uradno",
  govorica: "govorica",
  napoved: "napoved",
  open: "odprto",
  hit: "zadetek",
  miss: "zgrešeno",
  partial: "delno",
  zapadlo: "zapadlo",
};

function formatDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d}. ${m}. ${y}`;
}

async function loadJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function stars(n) {
  const v = Number(n) || 0;
  return "●".repeat(v) + "○".repeat(Math.max(0, 5 - v));
}

function pillTeme(teme) {
  return (teme || []).map((t) => `<span class="pill">${esc(t)}</span>`).join("");
}

function viriHtml(viri) {
  if (!viri || !viri.length) return "";
  const links = viri
    .filter((v) => v.url)
    .map((v) => {
      const label = v.handle ? `@${v.handle}` : v.naslov || v.tip || "vir";
      return `<a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
    });
  return links.length ? `<div class="viri">${links.join(" · ")}</div>` : "";
}

function cardHtml(c) {
  const status = c.status || "";
  return `<article class="card" data-teme="${esc((c.teme || []).join(" "))}">
    <div class="row">
      ${pillTeme(c.teme)}
      <span class="pill status-${esc(status)}">${esc(STATUS_LABEL[status] || status)}</span>
      <span class="stars" title="zaupanje">${stars(c.zaupanje)}</span>
    </div>
    <h2>${esc(c.naslov)}</h2>
    <div class="body">${esc(c.povzetek_sl)}</div>
    ${c.zakaj_je_vazno ? `<div class="why">${esc(c.zakaj_je_vazno)}</div>` : ""}
    ${viriHtml(c.viri)}
  </article>`;
}

function filterCards(root, tema) {
  root.querySelectorAll(".card").forEach((el) => {
    const ok = tema === "vse" || (el.dataset.teme || "").split(/\s+/).includes(tema);
    el.hidden = !ok;
  });
}

function bindFilters(container, cardsRoot) {
  container.innerHTML = TEME.map(
    (t, i) => `<button type="button" data-tema="${t.id}" class="${i === 0 ? "on" : ""}">${t.label}</button>`
  ).join("");
  container.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    container.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === btn));
    filterCards(cardsRoot, btn.dataset.tema);
  });
}

async function latestDay() {
  const man = await loadJson("content/manifest.json");
  const dnevi = [...(man.dnevi || [])].sort().reverse();
  if (!dnevi.length) throw new Error("Ni dnevov v arhivu.");
  return dnevi[0];
}

async function initDanes() {
  const heroMeta = document.querySelector("[data-hero-meta]");
  const heroTitle = document.querySelector("[data-hero-title]");
  const cardsRoot = document.getElementById("cards");
  const filters = document.getElementById("filters");
  try {
    const day = await latestDay();
    const data = await loadJson(`content/dnevi/${day}.json`);
    heroMeta.textContent = formatDate(data.date || day);
    heroTitle.textContent = data.naslov_dneva || "Dnevni radar";
    const kartice = data.kartice || [];
    cardsRoot.innerHTML = kartice.length
      ? kartice.map(cardHtml).join("")
      : `<p class="empty">Danes ni kartic. Zaženi <code>python3 ingest.py</code> ali prilepi URL v inbox.</p>`;
    if (data.recap) {
      cardsRoot.insertAdjacentHTML(
        "afterbegin",
        `<article class="card"><div class="row"><span class="pill">tedenski recap</span></div>
         <h2>Kaj se je premaknilo</h2><div class="body">${esc(data.recap)}</div></article>`
      );
    }
    bindFilters(filters, cardsRoot);
  } catch (err) {
    cardsRoot.innerHTML = `<p class="napaka">${esc(err.message)}</p>`;
  }
}

async function initSpremljam() {
  const root = document.getElementById("cards");
  const filters = document.getElementById("filters");
  try {
    const data = await loadJson("content/watchlist.json");
    document.querySelector("[data-hero-meta]").textContent =
      "posodobljeno " + formatDate(data.posodobljeno);
    root.innerHTML = (data.teme || [])
      .map((t) => {
        const zg = (t.zgodovina || [])
          .slice()
          .reverse()
          .map((z) => `<li><time>${esc(formatDate(z.date))}</time>${esc(z.text)}</li>`)
          .join("");
        return `<article class="card" data-teme="${esc((t.teme || []).join(" "))}">
          <div class="row">${pillTeme(t.teme)}</div>
          <h2>${esc(t.naslov)}</h2>
          <p class="watch-status">${esc(t.status_sl)}</p>
          ${t.naslednje_pricakovano ? `<p class="watch-next">Naprej · ${esc(t.naslednje_pricakovano)}</p>` : ""}
          ${zg ? `<ul class="zgodovina">${zg}</ul>` : ""}
        </article>`;
      })
      .join("");
    bindFilters(filters, root);
  } catch (err) {
    root.innerHTML = `<p class="napaka">${esc(err.message)}</p>`;
  }
}

async function initNapovedi() {
  const root = document.getElementById("cards");
  try {
    const data = await loadJson("content/napovedi.json");
    document.querySelector("[data-hero-meta]").textContent =
      "posodobljeno " + formatDate(data.posodobljeno);
    const list = data.napovedi || [];
    if (!list.length) {
      root.innerHTML = `<p class="empty">Še ni napovedi. Nedeljski ingest jih predlaga ločeno od novic.</p>`;
      return;
    }
    root.innerHTML = list
      .map((n) => {
        const st = n.status || "open";
        return `<article class="card">
          <div class="row">
            <span class="pill status-${esc(st)}">${esc(STATUS_LABEL[st] || st)}</span>
            <span class="stars">${esc(formatDate(n.narejena))} → ${esc(formatDate(n.horizont))}</span>
          </div>
          <p class="claim">${esc(n.claim)}</p>
          ${n.razsodba ? `<p class="razsodba">${esc(n.razsodba)}</p>` : ""}
        </article>`;
      })
      .join("");
  } catch (err) {
    root.innerHTML = `<p class="napaka">${esc(err.message)}</p>`;
  }
}

async function initArhiv() {
  const kal = document.getElementById("kalendar");
  const cardsRoot = document.getElementById("cards");
  const search = document.getElementById("search");
  let cache = {};
  let active = null;

  async function show(day) {
    active = day;
    kal.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.day === day));
    if (!cache[day]) cache[day] = await loadJson(`content/dnevi/${day}.json`);
    const data = cache[day];
    const q = (search.value || "").trim().toLowerCase();
    const kartice = (data.kartice || []).filter((c) => {
      if (!q) return true;
      const blob = `${c.naslov} ${c.povzetek_sl} ${(c.teme || []).join(" ")}`.toLowerCase();
      return blob.includes(q);
    });
    cardsRoot.innerHTML = kartice.length
      ? kartice.map(cardHtml).join("")
      : `<p class="empty">Ni zadetkov za ${esc(formatDate(day))}.</p>`;
  }

  try {
    const man = await loadJson("content/manifest.json");
    const dnevi = [...(man.dnevi || [])].sort().reverse();
    if (!dnevi.length) {
      cardsRoot.innerHTML = `<p class="empty">Arhiv je prazen.</p>`;
      return;
    }
    kal.innerHTML = dnevi
      .map((d, i) => `<button type="button" data-day="${esc(d)}" class="${i === 0 ? "on" : ""}">${esc(formatDate(d))}</button>`)
      .join("");
    kal.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (btn) show(btn.dataset.day);
    });
    search.addEventListener("input", () => {
      if (active) show(active);
    });
    await show(dnevi[0]);
  } catch (err) {
    cardsRoot.innerHTML = `<p class="napaka">${esc(err.message)}</p>`;
  }
}

window.Vremenko = { initDanes, initSpremljam, initNapovedi, initArhiv };
