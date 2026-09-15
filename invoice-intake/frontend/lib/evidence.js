// Find the source region(s) of a field value inside the OCR token map.
// Tokens are normalised [0..1] relative to page width/height.

function clean(text) {
  return String(text || "")
    .replace(/\s+/g, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}¥$]/gu, "");
}

function union(boxes) {
  if (boxes.length === 0) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const b of boxes) {
    x0 = Math.min(x0, b.x);
    y0 = Math.min(y0, b.y);
    x1 = Math.max(x1, b.x + b.w);
    y1 = Math.max(y1, b.y + b.h);
  }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

export function findEvidence(tokens, value, options = {}) {
  const target = clean(value);
  if (!tokens || !Array.isArray(tokens) || tokens.length === 0 || !target) return null;

  const enriched = tokens.map((t) => ({ ...t, key: clean(t.text) }));

  const pages = new Map();
  for (let i = 0; i < enriched.length; i += 1) {
    const t = enriched[i];
    if (!pages.has(t.page)) pages.set(t.page, []);
    pages.get(t.page).push(t);
  }

  // 1) single token equals target
  for (const t of enriched) {
    if (t.key === target) {
      return { boxes: [{ page: t.page, x: t.x, y: t.y, w: t.w, h: t.h }], matched: true, exact: true };
    }
  }

  // 2) token contains target (e.g. "¥184,800" token vs "184800")
  for (const t of enriched) {
    if (t.key.includes(target)) {
      return { boxes: [{ page: t.page, x: t.x, y: t.y, w: t.w, h: t.h }], matched: true, exact: false };
    }
  }

  // 3) sliding window across consecutive tokens per page
  let best = null;
  for (const [page, list] of pages.entries()) {
    for (let i = 0; i < list.length; i += 1) {
      let acc = "";
      const accItems = [];
      for (let j = i; j < list.length; j += 1) {
        acc += list[j].key;
        accItems.push(list[j]);
        if (acc.length >= target.length || acc.includes(target)) {
          if (acc.includes(target) || target.includes(acc)) {
            const cost = Math.abs(acc.length - target.length);
            if (!best || cost < best.cost) {
              best = {
                page,
                boxes: [union(accItems.map((t) => ({ x: t.x, y: t.y, w: t.w, h: t.h })))].filter(Boolean),
                cost,
              };
            }
          }
          if (acc.includes(target)) break;
        }
      }
    }
  }
  if (best && best.boxes.length) {
    return { boxes: best.boxes, page: best.page, matched: true, exact: false };
  }

  // 4) first token sharing a significant prefix (Japanese names, etc.)
  const firstChars = target.slice(0, Math.min(2, target.length));
  if (firstChars.length >= 2) {
    let found = null;
    for (const t of enriched) {
      if (t.key.startsWith(firstChars)) {
        found = t;
        break;
      }
    }
    if (found) {
      return {
        boxes: [{ page: found.page, x: found.x, y: found.y, w: found.w, h: found.h }],
        matched: true,
        exact: false,
        fuzzy: true,
      };
    }
  }

  return { boxes: [], matched: false };
}