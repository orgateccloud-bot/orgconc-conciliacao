/* Orgatec · Deck Comercial 2026 — navegação */
(function () {
  const slides = document.querySelectorAll('.slide');
  const total = slides.length;
  const cur = document.getElementById('cur');
  let idx = 0;

  function show(i) {
    idx = (i + total) % total;
    slides.forEach((s, n) => s.classList.toggle('active', n === idx));
    if (cur) cur.textContent = String(idx + 1).padStart(2, '0');
  }
  function next()  { show(idx + 1); }
  function prev()  { show(idx - 1); }
  function reset() { show(0); }

  const $next  = document.getElementById('next');
  const $prev  = document.getElementById('prev');
  const $reset = document.getElementById('reset');
  if ($next)  $next.addEventListener('click', next);
  if ($prev)  $prev.addEventListener('click', prev);
  if ($reset) $reset.addEventListener('click', reset);

  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); next(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev(); }
    else if (e.key === 'Home') { e.preventDefault(); reset(); }
    else if (e.key === 'End')  { e.preventDefault(); show(total - 1); }
  });

  function scaleStage() {
    const stage = document.getElementById('stage');
    if (!stage) return;
    const vw = window.innerWidth  - 48;
    const vh = window.innerHeight - 200;
    const scale = Math.min(vw / 1920, vh / 1080, 1);
    stage.style.height = (1080 * scale) + 'px';
    stage.style.width  = (1920 * scale) + 'px';
    slides.forEach(s => {
      s.style.transform = `scale(${scale})`;
      s.style.transformOrigin = 'top left';
    });
  }
  window.addEventListener('resize', scaleStage);
  scaleStage();
})();
