// Anonymous feedback form for filamentclip.com. Mounts into every [data-feedback-form] element:
//   data-source="download"  the prompt in studio.html, shown after the ZIP is downloaded
//   data-source="page"      the form on feedback.html
// Sends only: rating, source, chosen topic ids, and the typed comment, to POST /api/feedback. Nothing identifies the visitor.
// Everything is built with createElement/textContent and the visitor's text is never put into markup, so there is nothing
// to inject into. Fire-and-forget on failure: this can never affect generating or downloading.
(() => {
  const TAGS = [["easy","Easy to use"],["fit","Clips fit my spools"],["readable","Labels are readable"],["holders","Holders & templates"],["slicer","Opens in my slicer"],["slow","Too slow"],["confusing","Confusing"],["missing","Missing a spool or brand"],["bug","Something broke"]];
  const LABELS = ['Poor', 'Fair', 'Okay', 'Good', 'Great'];
  const SENT_KEY = 'clip-studio-feedback-sent';
  const REASK_MS = 30 * 24 * 60 * 60 * 1000; // after sending, the download prompt stays away for 30 days
  const MAX_COMMENT = 500;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const recentlySent = () => {
    try { return Date.now() - Number(localStorage.getItem(SENT_KEY)) < REASK_MS; } catch { return false; }
  };
  const markSent = () => { try { localStorage.setItem(SENT_KEY, String(Date.now())); } catch {} };

  function mount(host) {
    const source = host.dataset.source === 'download' ? 'download' : 'page';
    const state = { rating: 0, tags: new Set(), sending: false, done: false };
    const root = el('div', 'fb');

    root.append(el('p', 'fb-ask', 'How would you rate the studio?'));
    const stars = el('div', 'fb-stars');
    stars.setAttribute('role', 'radiogroup');
    stars.setAttribute('aria-label', 'Rating from 1 to 5');
    const hint = el('p', 'fb-hint');
    hint.setAttribute('aria-live', 'polite');
    const more = el('div', 'fb-more');
    more.hidden = true;

    const starButtons = LABELS.map((label, i) => {
      const b = el('button', 'fb-star', '★');
      b.type = 'button';
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', 'false');
      b.setAttribute('aria-label', `${i + 1} of 5, ${label}`);
      b.addEventListener('click', () => {
        state.rating = i + 1;
        starButtons.forEach((s, j) => { s.classList.toggle('on', j <= i); s.setAttribute('aria-checked', String(j === i)); });
        hint.textContent = LABELS[i];
        more.hidden = false;
        status.textContent = '';
      });
      stars.append(b);
      return b;
    });

    const chips = el('div', 'fb-chips');
    chips.setAttribute('role', 'group');
    chips.setAttribute('aria-label', 'Topics (optional)');
    for (const [id, label] of TAGS) {
      const c = el('button', 'fb-chip', label);
      c.type = 'button';
      c.setAttribute('aria-pressed', 'false');
      c.addEventListener('click', () => {
        const on = !state.tags.has(id);
        on ? state.tags.add(id) : state.tags.delete(id);
        c.setAttribute('aria-pressed', String(on));
      });
      chips.append(c);
    }

    const commentLabel = el('label', 'fb-comment', 'Anything else? (optional)');
    const comment = el('textarea');
    comment.maxLength = MAX_COMMENT;
    comment.rows = 3;
    comment.autocomplete = 'off';
    comment.setAttribute('spellcheck', 'true');
    commentLabel.append(comment);

    const hp = el('input', 'fb-hp'); // honeypot: people never see or fill this
    hp.type = 'text'; hp.name = 'website'; hp.tabIndex = -1; hp.autocomplete = 'off';
    hp.setAttribute('aria-hidden', 'true');

    const actions = el('div', 'fb-actions');
    const send = el('button', 'fb-send', 'Send feedback');
    send.type = 'button';
    const status = el('span', 'fb-status');
    status.setAttribute('role', 'status');
    actions.append(send);
    if (host.hasAttribute('data-dismissible')) {
      const skip = el('button', 'fb-skip', 'Not now');
      skip.type = 'button';
      skip.addEventListener('click', () => host.dispatchEvent(new CustomEvent('feedback-dismiss', { bubbles: true })));
      actions.append(skip);
    }
    actions.append(status);

    send.addEventListener('click', async () => {
      if (state.sending || state.done) return;
      if (!state.rating) { status.textContent = 'Pick a rating first.'; return; }
      state.sending = true;
      send.disabled = true;
      status.textContent = 'Sending…';
      try {
        const res = await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rating: state.rating, source, tags: [...state.tags], comment: comment.value, website: hp.value }),
        });
        if (!res.ok) throw new Error('status ' + res.status);
        state.done = true;
        markSent();
        const thanks = el('p', 'fb-thanks', 'Thanks! That really helps.');
        thanks.setAttribute('role', 'status');
        root.replaceChildren(thanks);
        host.dispatchEvent(new CustomEvent('feedback-sent', { bubbles: true }));
      } catch {
        status.textContent = 'Could not send just now. Please try again in a bit.';
        send.disabled = false;
      } finally {
        state.sending = false;
      }
    });

    more.append(chips, commentLabel, hp, actions, el('p', 'fb-note', 'Anonymous: no account, email or IP address is saved. Please do not include personal details. Feedback is never shown on this site.'));
    root.append(stars, hint, more);
    host.replaceChildren(root);
  }

  document.querySelectorAll('[data-feedback-form]').forEach(mount);

  // Studio: offer the form once the visitor has downloaded their ZIP (not before, and not again for 30 days after sending).
  const panel = document.getElementById('feedbackPrompt');
  const download = document.getElementById('download');
  if (panel && download) {
    let offered = false;
    download.addEventListener('click', () => {
      if (offered || recentlySent()) return;
      offered = true;
      panel.classList.remove('hidden');
    });
    panel.addEventListener('feedback-dismiss', () => panel.classList.add('hidden'));
  }
})();
