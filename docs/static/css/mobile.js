/* No scroll handler or animation loop: decorative motion uses CSS transforms. */
(() => {
  const root = document.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const saveData = navigator.connection?.saveData;
  let paused = reduce.matches || Boolean(saveData);
  const icon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M10 8v8m4-8v8"/></svg>';
  function update() {
    root.dataset.motion = paused ? 'paused' : 'running';
    document.querySelectorAll('[data-motion-toggle]').forEach(button => {
      button.setAttribute('aria-pressed', String(paused));
      button.innerHTML = icon + '<span>' + (paused ? 'Resume glow' : 'Pause glow') + '</span>';
    });
  }
  const visible = new IntersectionObserver(entries => entries.forEach(entry => {
    entry.target.classList.toggle('is-in-view', entry.isIntersecting);
  }), { threshold: 0 });
  const selectors = '.hero,.ajs-hero,.mast,.welcome-layout,.cover,.hero-grid,.vision';
  function scan(parent) {
    const candidates = [...parent.querySelectorAll(selectors)];
    if (parent.matches?.(selectors)) candidates.unshift(parent);
    for (const surface of candidates) {
      if (surface.classList.contains('live-surface') || surface.closest('.live-surface')) continue;
      surface.classList.add('live-surface');
      const clip = document.createElement('div');
      clip.className = 'ambient-clip'; clip.setAttribute('aria-hidden','true');
      clip.innerHTML = '<div class="ambient-sheen"></div>';
      surface.prepend(clip); visible.observe(surface);
    }
  }
  const changes = new MutationObserver(records => {
    for (const record of records) for (const node of record.addedNodes) {
      if (node.nodeType === 1 && !node.closest('.ambient-clip')) scan(node);
    }
    for (const record of records) for (const node of record.removedNodes) {
      if (node.nodeType !== 1 || node.isConnected) continue;
      if (node.classList.contains('live-surface')) visible.unobserve(node);
      node.querySelectorAll('.live-surface').forEach(surface => visible.unobserve(surface));
    }
  });
  function visibility() { root.toggleAttribute('data-page-hidden', document.hidden); }
  function start() {
    scan(document); update(); visibility();
    changes.observe(document.body, {childList:true,subtree:true});
    document.addEventListener('click', event => {
      const toggle = event.target.closest('[data-motion-toggle]');
      if (toggle) { paused = !paused; update(); }
      const action = event.target.closest('[data-quick-action]');
      if (action) {
        const target = document.querySelector(action.dataset.quickAction);
        target?.click();
        if (target?.getAttribute('role') === 'tab') target.closest('[role="tablist"]').scrollIntoView({block:'start'});
      }
    });
    document.addEventListener('visibilitychange', visibility);
    reduce.addEventListener('change', () => { paused = reduce.matches || Boolean(saveData); update(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
