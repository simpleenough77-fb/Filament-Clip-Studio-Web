// Shows what visitors have said on feedback.html: the average, a 1-5 breakdown, and the latest responses.
// Data comes from GET /api/feedback. Every value is treated as untrusted: numbers are clamped, topics are looked up in a
// fixed table, and all text is set with textContent, so nothing a visitor typed can ever become markup or script.
(() => {
  const host = document.getElementById('feedbackList');
  if (!host) return;
  const labels = window.clipFeedbackTags || {};

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const num = (v, min, max) => Math.max(min, Math.min(max, Math.round(Number(v)) || 0));
  const stars = (rating) => {
    const s = el('span', 'fb-stars-static', '★'.repeat(rating) + '☆'.repeat(5 - rating));
    s.setAttribute('role', 'img');
    s.setAttribute('aria-label', `${rating} out of 5`);
    return s;
  };

  function render(data) {
    const count = num(data.count, 0, 1e9);
    if (!count) {
      host.replaceChildren(el('p', 'small', 'No feedback yet. Be the first to leave some above.'));
      return;
    }
    const average = Math.max(0, Math.min(5, Number(data.average) || 0));
    const counts = Array.isArray(data.counts) ? data.counts.slice(0, 5).map((c) => num(c, 0, 1e9)) : [0, 0, 0, 0, 0];

    const summary = el('div', 'fb-summary');
    const big = el('div', 'fb-average');
    big.append(el('strong', '', average.toFixed(1)), stars(num(average, 1, 5)), el('span', 'small', `${count} rating${count === 1 ? '' : 's'}`));
    const bars = el('div', 'fb-bars');
    for (let r = 5; r >= 1; r--) {
      const n = counts[r - 1] || 0;
      const row = el('div', 'fb-bar-row');
      const track = el('div', 'fb-bar');
      const fill = el('div', 'fb-bar-fill');
      fill.style.width = (count ? Math.round((n / count) * 100) : 0) + '%';
      track.append(fill);
      row.append(el('span', 'small', `${r}★`), track, el('span', 'small', String(n)));
      bars.append(row);
    }
    summary.append(big, bars);

    const list = el('div', 'fb-items');
    for (const item of Array.isArray(data.items) ? data.items : []) {
      if (!item || typeof item !== 'object') continue;
      const card = el('article', 'fb-item');
      const head = el('div', 'fb-item-head');
      head.append(stars(num(item.rating, 1, 5)));
      if (typeof item.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(item.date)) head.append(el('time', 'small', item.date));
      card.append(head);
      const tags = Array.isArray(item.tags) ? item.tags.filter((t) => typeof t === 'string' && Object.prototype.hasOwnProperty.call(labels, t)) : [];
      if (tags.length) {
        const chips = el('div', 'fb-chip-list');
        for (const t of tags) chips.append(el('span', 'fb-chip-static', labels[t]));
        card.append(chips);
      }
      if (typeof item.comment === 'string' && item.comment) card.append(el('p', 'fb-comment-text', item.comment));
      list.append(card);
    }
    host.replaceChildren(summary, list);
  }

  fetch('/api/feedback', { headers: { Accept: 'application/json' } })
    .then((r) => { if (!r.ok) throw new Error('status ' + r.status); return r.json(); })
    .then((d) => { if (!d || typeof d !== 'object') throw new Error('bad data'); render(d); })
    .catch(() => host.replaceChildren(el('p', 'small', 'Feedback could not be loaded right now.')));
})();
