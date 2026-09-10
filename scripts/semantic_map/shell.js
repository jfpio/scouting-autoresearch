(() => {
  const {records, locale} = JSON.parse(document.getElementById('map-records').textContent);
  const t = (pl, en) => locale === 'pl' ? pl : en;
  const $ = id => document.getElementById(id);
  const mobile = matchMedia('(max-width: 767px)');
  const frame = $('map-engine');
  const panel = $('panel');
  const query = $('map-search');
  const region = $('region');
  const normalize = value => String(value).toLocaleLowerCase(locale).normalize('NFKD').replace(/\p{Diacritic}/gu, '').replace(/ł/g, 'l');
  const searchable = records.map(r => normalize([r.title,r.author,r.sourceTitle,r.topName,r.fineName,r.id].join(' ')));
  const rows = [...document.querySelectorAll('[data-map-list-item]')];
  let indices = records.map((_, i) => i);
  let timer;
  let panelOpener;
  const send = message => frame.contentWindow?.postMessage({channel:'scout-map', ...message}, location.origin);
  const sync = (fit = false) => {
    send({type:'filter', indices, fit});
    send({type:'theme', theme:document.documentElement.dataset.theme});
  };
  const apply = () => {
    const needle = normalize(query.value.trim());
    indices = records.flatMap((r, i) => (!needle || searchable[i].includes(needle)) && (!region.value || [r.topClusterId,r.fineClusterId].includes(region.value)) ? [i] : []);
    const visible = new Set(indices.map(i => records[i].id));
    rows.forEach(row => { row.hidden = !visible.has(row.dataset.id); });
    $('result-count').textContent = `${indices.length} / ${records.length} ${t('gier', 'games')}`;
    $('empty').hidden = indices.length !== 0;
    $('clear').hidden = !query.value && !region.value;
    const download = region.selectedOptions[0].dataset.download;
    $('download').hidden = !download;
    if (download) $('download').href = download;
    else $('download').removeAttribute('href');
    if (frame.dataset.state === 'ready') sync(true);
  };
  const fail = () => {
    clearTimeout(timer);
    frame.dataset.state = 'error';
    $('map-status').hidden = false;
    $('status-text').textContent = t('Nie udało się uruchomić mapy. Lista gier jest nadal dostępna.', 'The map could not start. The game list is still available.');
    $('recovery').hidden = false;
    document.querySelectorAll('[data-map-action]').forEach(b => { b.disabled = true; });
  };
  const start = () => {
    clearTimeout(timer);
    frame.dataset.state = 'loading';
    $('map-status').hidden = false;
    $('status-text').textContent = t('Ładowanie mapy…', 'Loading map…');
    $('recovery').hidden = true;
    // A fresh document also discards failed workers and graphics resources.
    frame.src = `engine.html?attempt=${Date.now()}`;
    timer = setTimeout(fail, 30000);
  };
  const setView = view => {
    document.body.dataset.view = view;
    $('list-view').hidden = view !== 'list';
    $('map-view').hidden = view !== 'map';
    document.querySelectorAll('[data-view-button]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.viewButton === view)));
    if (view === 'map' && frame.dataset.state === 'idle') start();
    if (view === 'map' && frame.dataset.state === 'ready') send({type:'resize'});
  };
  const openPanel = () => {
    if (!mobile.matches) return;
    panelOpener = document.activeElement;
    if (!panel.open) panel.showModal();
  };
  const detail = id => {
    const record = records.find(r => r.id === id);
    if (!record) return;
    $('game-detail').hidden = false;
    $('detail-title').textContent = record.title;
    $('detail-source').textContent = `${record.author} · ${record.sourceTitle} · ${record.year}`;
    $('detail-summary').textContent = record.summary;
    $('detail-link').href = record.activityUrl;
    $('detail-translation').hidden = record.translationStatus !== 'machine-translation';
    $('detail-original').href = ['pl','en'].includes(record.originalLanguage)
      ? `/scouting-autoresearch/${record.originalLanguage === 'en' ? 'en/' : ''}activities/${record.id}/`
      : record.sourceUrl;
    $('detail-edition').href = record.digitalEditionUrl;
    openPanel();
    $('game-detail').scrollIntoView({block:'nearest'});
    $('detail-link').focus({preventScroll:true});
  };
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.channel !== 'scout-map') return;
    if (event.data.type === 'ready' && frame.dataset.state === 'loading') {
      clearTimeout(timer);
      frame.dataset.state = 'ready';
      $('map-status').hidden = true;
      document.querySelectorAll('[data-map-action]').forEach(b => { b.disabled = false; });
      sync(true);
    } else if (event.data.type === 'error') fail();
    else if (event.data.type === 'select') detail(event.data.id);
  });
  const layoutPanel = () => {
    if (panel.open) panel.close();
    if (!mobile.matches) panel.setAttribute('open', '');
  };
  panel.addEventListener('cancel', event => { if (!mobile.matches) event.preventDefault(); });
  panel.addEventListener('close', () => {
    if (mobile.matches) (panelOpener instanceof HTMLIFrameElement ? $('open-panel') : panelOpener)?.focus();
  });
  $('open-panel').addEventListener('click', openPanel);
  $('close-panel').addEventListener('click', () => panel.close());
  query.addEventListener('input', apply);
  region.addEventListener('change', apply);
  $('clear').addEventListener('click', () => { query.value = ''; region.value = ''; apply(); query.focus(); });
  document.querySelectorAll('[data-view-button]').forEach(b => b.addEventListener('click', () => setView(b.dataset.viewButton)));
  document.querySelectorAll('[data-map-action]').forEach(b => b.addEventListener('click', () => send({type:b.dataset.mapAction})));
  $('retry').addEventListener('click', start);
  $('fallback-list').addEventListener('click', () => { setView('list'); document.querySelector('[data-view-button="list"]').focus(); });
  document.addEventListener('mapThemeChanged', () => send({type:'theme', theme:document.documentElement.dataset.theme}));
  mobile.addEventListener('change', layoutPanel);
  layoutPanel();
  apply();
  setView(mobile.matches ? 'list' : 'map');
})();
