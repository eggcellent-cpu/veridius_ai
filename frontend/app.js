// frontend/app.js
const summaryEl = document.getElementById("summary");
const cardsEl = document.getElementById("cards");
const emptyEl = document.getElementById("empty");
const metaEl = document.getElementById("meta");
const btnReload = document.getElementById("btnReload");

function copyWhatsApp(eventId) {
  const el = document.getElementById(`wa-text-${eventId}`);
  if (!el) return;

  navigator.clipboard.writeText(el.innerText)
    .then(() => alert("WhatsApp text copied!"))
    .catch(err => alert("Failed to copy: " + err));
}

function copyWhatsApp(eventId) {
  const el = document.getElementById(`wa-text-${eventId}`);
  if (!el) return;

  navigator.clipboard.writeText(el.innerText)
    .then(() => alert("WhatsApp text copied!"))
    .catch(err => alert("Failed to copy: " + err));
}

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return await res.json();
}

function esc(s) {
  return (s ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function cardHTML(item) {
  const ev = item.event?.event || {};
  const dt = ev.datetime || {};
  const reg = item.event?.registration || {};
  const media = item.event?.media || {};
  const images = media.images?.items || [];
  const heroImg = images.length ? images[0].url : "";

  const draft = item.draft || {};

  const title = ev.title || "(Untitled Event)";
  const subject = draft.subject || "(no subject)";
  const blurb = draft.email_blurb || "(no email blurb)";
  const whatsapp = draft.whatsapp_text || "(no whatsapp text)";
  const date = dt.date_range || "-";
  const time = dt.time_range || "-";
  const venue = ev.location || "-";
  const link = reg.signup_link || "#";

  const previewPath = item.email_preview_path || "";

  return `
  <div class="card">
    <div class="cardTop">
      <h3>${esc(title)}</h3>
      <span class="badge">${esc(item.change_type || "")}</span>
    </div>

    ${
    heroImg
      ? `<img class="hero" src="${(heroImg)}" alt="" loading="lazy" />`
      : ""
    }

    <div class="kv">
      <div><b>Subject:</b> ${esc(subject)}</div>
      <div><b>Date:</b> ${esc(date)}</div>
      <div><b>Time:</b> ${esc(time)}</div>
      <div><b>Venue:</b> ${esc(venue)}</div>
      <div><b>Link:</b> <a href="${esc(
        link
      )}" target="_blank" rel="noreferrer">Open registration</a></div>
      ${
        previewPath
          ? `<div><b>Email Preview:</b> <a href="../${esc(
              previewPath
            )}" target="_blank">Open HTML</a></div>`
          : ""
      }
    </div>

    <div class="box">
      <div class="boxTitle">Email blurb</div>
      <div class="boxBody">${esc(blurb)}</div>
    </div>

    <div class="box">
      <div class="boxTitle">WhatsApp text</div>
      <div class="boxBody">${esc(whatsapp)}</div>
      <div style="text-align: right;">
        <button onclick="window.open(\`https://wa.me/?text=${encodeURIComponent(whatsapp)}\`, '_blank')" 
                style="background:#25D366;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;">
          Share on WhatsApp
        </button>
      </div>
    </div>
  </div>`;
}

async function reload() {
  // If you run frontend from /frontend, these relative paths matter:
  // - delta is in /data
  // - drafts is in /out
  const delta = await loadJSON("../data/events_delta.json");
  const drafts = await loadJSON("../out/drafts.json");

  metaEl.textContent = `run_at: ${delta.summary?.run_at || "-"} | items: ${
    drafts.items?.length || 0
  }`;
  summaryEl.textContent = JSON.stringify(delta.summary || {}, null, 2);

  const items = (drafts.items || []).filter((x) => x.draft); // only successful drafts

  if (!items.length) {
    emptyEl.classList.remove("hidden");
    cardsEl.innerHTML = "";
    return;
  }

  emptyEl.classList.add("hidden");
  cardsEl.innerHTML = items.map(cardHTML).join("\n");
}

btnReload.addEventListener("click", reload);
reload().catch((err) => {
  summaryEl.textContent = "Frontend error:\n" + err.message;
});
