import { escapeHtml as esc } from './model.js';
const svg = (body) => `<svg viewBox="0 0 540 290" role="img">${body}</svg>`;
export function scatter(rows) {
  const max = Math.max(1, ...rows.map((r) => r.count_7d)),
    magMax = Math.max(6, ...rows.map((r) => r.magnitude));
  let body =
    '<title>Magnitude versus subsequent seven-day nearby earthquake counts</title>';
  for (let i = 0; i <= 4; i++) {
    const y = 240 - i * 50;
    body += `<path d="M45 ${y}H515" stroke="#293b44"/><text x="5" y="${y + 3}">${Math.round((max * i) / 4)}</text>`;
  }
  for (let m = 5; m <= magMax; m += 0.5) {
    const x = 45 + ((m - 5) / (magMax - 5)) * 455;
    body += `<text x="${x}" y="262">${m.toFixed(1)}</text>`;
  }
  for (const r of rows) {
    const x = 45 + ((r.magnitude - 5) / (magMax - 5)) * 455,
      y = 240 - (r.count_7d / max) * 200;
    body += `<circle cx="${x}" cy="${y}" r="2.4" fill="${r.preceded_by_anchor ? '#f58c77' : '#b4efca'}" opacity=".35"><title>${esc(r.id)}: M${r.magnitude}, ${r.count_7d} events</title></circle>`;
  }
  return svg(body + '<text x="235" y="285">Anchor magnitude</text>');
}
export function distribution(groups) {
  const quantile = (a, q) => (a.length ? a[Math.floor((a.length - 1) * q)] : 0);
  const max = Math.max(1, ...groups.map((g) => quantile(g.values, 0.75)));
  let body =
    '<title>Median and interquartile range of subsequent earthquake counts by magnitude</title>';
  for (let i = 0; i <= 4; i++) {
    const x = 145 + i * 85;
    body += `<path d="M${x} 25V245" stroke="#293b44"/><text x="${x}" y="268">${((max * i) / 4).toFixed(1)}</text>`;
  }
  groups.forEach((g, i) => {
    const y = 50 + i * 53,
      q1 = quantile(g.values, 0.25),
      q3 = quantile(g.values, 0.75),
      med = quantile(g.values, 0.5);
    body += `<text x="8" y="${y}">M ${esc(g.label)}</text><text x="8" y="${y + 16}">n = ${g.n}</text><rect x="${145 + (q1 / max) * 340}" y="${y - 10}" width="${Math.max(2, ((q3 - q1) / max) * 340)}" height="20" fill="#31594e"/><circle cx="${145 + (med / max) * 340}" cy="${y}" r="4" fill="#b4efca"/>`;
  });
  return svg(body + '<text x="230" y="285">Subsequent events</text>');
}
