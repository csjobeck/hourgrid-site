// Live two-city hour grid for the time-difference pages. Uses the browser's own time-zone
// rules (Intl), so it stays right across daylight saving changes without updates.
(function () {
  const root = document.getElementById("live");
  if (!root) return;
  const cities = JSON.parse(root.dataset.cities); // [{name, tz, workdays:[0-6], opens, closes}]
  const h12 = new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hourCycle === "h12";

  // Local wall-clock parts of an instant in a time zone.
  const partsCache = {};
  function parts(tz, ms) {
    const f = partsCache[tz] || (partsCache[tz] = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", weekday: "short", hourCycle: "h23",
    }));
    const p = {};
    for (const x of f.formatToParts(new Date(ms))) p[x.type] = x.value;
    const weekday = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(p.weekday);
    return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour % 24, mi: +p.minute, weekday };
  }
  function offsetMs(tz, ms) {
    const p = parts(tz, ms);
    return Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi) - Math.floor(ms / 60000) * 60000;
  }
  // The instant of local midnight on a calendar date in a time zone.
  function midnight(tz, y, mo, d) {
    let guess = Date.UTC(y, mo - 1, d);
    for (let i = 0; i < 3; i++) guess = Date.UTC(y, mo - 1, d) - offsetMs(tz, guess);
    return guess;
  }

  function label(p) {
    if (!h12) return { main: String(p.h).padStart(2, "0"), sub: p.mi ? ":" + String(p.mi).padStart(2, "0") : "" };
    const hour = p.h % 12 || 12;
    return { main: String(hour), sub: p.mi ? ":" + String(p.mi).padStart(2, "0") : (p.h < 12 ? "am" : "pm") };
  }
  function time(p) {
    const l = label(p);
    if (!h12) return `${l.main}:${String(p.mi).padStart(2, "0")}`;
    return `${l.main}:${String(p.mi).padStart(2, "0")} ${p.h < 12 ? "am" : "pm"}`;
  }
  // Night, morning/evening, day, or office hours (on a workday).
  function kind(c, p) {
    const t = p.h + p.mi / 60;
    if (c.workdays.includes(p.weekday) && t >= c.opens && t < c.closes) return "o";
    if (t >= 8 && t < 18) return "d";
    if (t >= 6 && t < 22) return "e";
    return "n";
  }

  const now = Date.now();
  const today = parts(cities[0].tz, now);
  let day = Date.UTC(today.y, today.mo - 1, today.d);

  const title = root.querySelector("[data-day]");
  const table = root.querySelector("table");
  const best = root.querySelector("[data-best]");
  const nowLine = root.querySelector("[data-now]");

  function render() {
    const d = new Date(day);
    const start = midnight(cities[0].tz, d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
    const hours = Array.from({ length: 24 }, (_, i) => start + i * 3600000);
    title.textContent = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(d) + " in " + cities[0].name;

    const both = hours.map((ms) => cities.every((c) => kind(c, parts(c.tz, ms)) === "o"));
    table.innerHTML = "";
    const marks = document.createElement("tr");
    marks.innerHTML = "<th>Both at work</th>" + both.map((b) => `<td class="mark">${b ? "✓" : ""}</td>`).join("");
    table.appendChild(marks);
    for (const c of cities) {
      const tr = document.createElement("tr");
      const offset = (offsetMs(c.tz, start + 12 * 3600000) - offsetMs(cities[0].tz, start + 12 * 3600000)) / 3600000;
      const off = c === cities[0] ? "" : (offset === 0 ? "same time" : (offset > 0 ? "+" : "−") + formatHours(Math.abs(offset)));
      tr.innerHTML = `<th>${c.name}<small>${off}</small></th>` + hours.map((ms) => {
        const p = parts(c.tz, ms);
        const l = label(p);
        const isNow = now >= ms && now < ms + 3600000;
        const newDay = p.h === 0 ? ` title="${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][p.weekday]} ${p.d}"` : "";
        return `<td class="${kind(c, p)}${isNow ? " now" : ""}"${newDay}>${p.h === 0 ? "<b>" + ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][p.weekday] + "</b>" : l.main}<small>${p.h === 0 ? p.d : l.sub}</small></td>`;
      }).join("");
      table.appendChild(tr);
    }

    // Longest stretch when everyone is at work, in 15-minute steps so half-hour zones are exact.
    const step = 15 * 60000;
    const atWork = (ms) => cities.every((c) => {
      const p = parts(c.tz, ms), t = p.h + p.mi / 60;
      return c.workdays.includes(p.weekday) && t >= c.opens && t < c.closes;
    });
    let run = null, cur = null;
    for (let i = 0; i < 96; i++) {
      if (atWork(start + i * step)) {
        cur = cur ? { from: cur.from, to: i } : { from: i, to: i };
        if (!run || cur.to - cur.from > run.to - run.from) run = cur;
      } else cur = null;
    }
    if (run) {
      const from = start + run.from * step, to = start + (run.to + 1) * step;
      best.textContent = "Best time to meet: " + cities.map((c) => `${time(parts(c.tz, from))}–${time(parts(c.tz, to))} in ${c.name}`).join(" = ") + ".";
    } else {
      best.textContent = "No time on this day is inside both working days (9 to 5 on workdays). The cells marked morning or evening are the least bad times.";
    }
    // On narrow screens, open at the first shared work hour (or 7 am) rather than midnight.
    const scroller = root.querySelector(".scroll");
    const firstBoth = both.indexOf(true);
    const cells = table.rows[1].cells;
    const target = cells[1 + (firstBoth >= 0 ? Math.max(0, firstBoth - 1) : 7)];
    if (target) scroller.scrollLeft = target.offsetLeft - cells[0].offsetWidth - 8;
    nowLine.textContent = "Right now: " + cities.map((c) => `${time(parts(c.tz, now))} in ${c.name}`).join(", ") + ".";
  }
  function formatHours(h) {
    const whole = Math.floor(h), mins = Math.round((h - whole) * 60);
    return mins ? `${whole}:${String(mins).padStart(2, "0")}h` : `${whole}h`;
  }

  root.querySelector("[data-prev]").addEventListener("click", () => { day -= 86400000; render(); });
  root.querySelector("[data-next]").addEventListener("click", () => { day += 86400000; render(); });
  root.querySelector("[data-today]").addEventListener("click", () => { day = Date.UTC(today.y, today.mo - 1, today.d); render(); });
  const picker = root.querySelector("[data-date]");
  picker.addEventListener("change", () => { if (picker.value) { const [y, m, d] = picker.value.split("-").map(Number); day = Date.UTC(y, m - 1, d); render(); } });
  render();
})();
