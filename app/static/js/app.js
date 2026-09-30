// Register the service worker so the app is installable / works offline.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(console.error);
}

// Live search: fetch a server-rendered list fragment and swap it in.
// Works as a progressive enhancement — plain navigation still works without JS.
const search = document.getElementById("search");
if (search) {
  let timer;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const params = new URLSearchParams({ q: search.value, partial: "1" });
      try {
        const res = await fetch("/?" + params.toString());
        document.getElementById("recipe-list").innerHTML = await res.text();
      } catch (e) {
        console.error(e);
      }
    }, 200);
  });
}

// ---------------------------------------------------------------------------
// Portion scaling (recipe detail page).
// Parses the leading quantity of each ingredient line — "2", "1.5", "1/2",
// "1 1/2" or unicode fractions like "½" — multiplies it by the chosen factor,
// and rewrites the line. The original text is kept in data-original so any
// factor is always computed from the source, never compounded.
// ---------------------------------------------------------------------------
const scaler = document.getElementById("scaler");
if (scaler) {
  const UNICODE_FRACTIONS = {
    "¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3,
    "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
    "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
  };

  // Matches an optional whole number + fraction/decimal at the start of a line.
  // Groups: 1 = whole part, 2 = "a/b" fraction, 3 = unicode fraction char.
  const QTY_RE = new RegExp(
    "^\\s*(\\d+(?:[.,]\\d+)?)?\\s*(?:(\\d+\\s*/\\s*\\d+)|([" +
      Object.keys(UNICODE_FRACTIONS).join("") + "]))?"
  );

  function parseQty(text) {
    const m = text.match(QTY_RE);
    if (!m || (!m[1] && !m[2] && !m[3])) return null;
    let value = m[1] ? parseFloat(m[1].replace(",", ".")) : 0;
    if (m[2]) {
      const [num, den] = m[2].split("/").map((s) => parseFloat(s));
      if (den) value += num / den;
    } else if (m[3]) {
      value += UNICODE_FRACTIONS[m[3]];
    }
    return { value, rest: text.slice(m[0].length) };
  }

  // Render a number as a tidy quantity: whole numbers as-is, common values as
  // fractions (1½, ¾ …), everything else as a short decimal.
  function formatQty(value) {
    const whole = Math.floor(value);
    const frac = value - whole;
    if (frac < 0.01) return String(whole);
    const NICE = [
      [0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"],
    ];
    for (const [v, sym] of NICE) {
      if (Math.abs(frac - v) < 0.02) return (whole ? whole + " " : "") + sym;
    }
    return String(Math.round(value * 100) / 100);
  }

  function applyFactor(factor) {
    document.querySelectorAll("#ingredient-list li").forEach((li) => {
      const original = li.dataset.original;
      const parsed = parseQty(original);
      if (!parsed) {
        li.textContent = original; // no quantity to scale (e.g. "salt to taste")
        return;
      }
      li.textContent = formatQty(parsed.value * factor) + parsed.rest;
    });
    const servings = document.getElementById("servings");
    if (servings) {
      const parsed = parseQty(servings.dataset.original);
      servings.textContent = parsed
        ? formatQty(parsed.value * factor) + parsed.rest
        : servings.dataset.original;
    }
  }

  scaler.querySelectorAll(".scale-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      scaler.querySelectorAll(".scale-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("scale-custom").value = "";
      applyFactor(parseFloat(btn.dataset.factor));
    });
  });

  document.getElementById("scale-custom").addEventListener("input", (e) => {
    const factor = parseFloat(e.target.value);
    if (!factor || factor <= 0) return;
    scaler.querySelectorAll(".scale-btn").forEach((b) => b.classList.remove("active"));
    applyFactor(factor);
  });
}
