// Small adapter for the pinned DataMapPlot 0.7.3 API. No corpus data lives here.
(() => {
  const send = message => parent.postMessage({channel:'scout-map', ...message}, location.origin);
  let map, home, current, ready = false, failed = false;
  const fail = () => { if (!failed) { failed = true; send({type:'error'}); } };
  addEventListener('error', fail);
  addEventListener('unhandledrejection', fail);
  // Observe failures in the generated workers, including async decompression failures.
  const NativeWorker = window.Worker;
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      this.addEventListener('error', fail);
      this.addEventListener('messageerror', fail);
      this.addEventListener('message', event => {
        if (event.data?.type === 'map-error') { event.stopImmediatePropagation(); fail(); }
      });
    }
  };
  window.scoutMapEngine = {
    attach(value) {
      map = value;
      home = {...map.deckgl.props.initialViewState};
      current = {...home};
      map.onViewStateChange('scout-shell', ({viewState}) => { current = {...viewState}; });
      map.deckgl.setProps({onError:fail});
    },
    select(id) { send({type:'select', id}); }
  };
  document.addEventListener('webglcontextlost', fail, true);
  document.addEventListener('datamapDataLoaded', () => {
    if (failed || ready) return;
    if (!map?.pointData || !map?.metaData || !map?.labelLayer) { fail(); return; }
    ready = true;
    // Keep hover informational; selection goes to the accessible parent panel.
    map.deckgl.setProps({getTooltip:null, onClick: ({index, layer}) => {
      if (index >= 0 && layer?.id === map.pointLayer.id) window.scoutMapEngine.select(map.metaData.activity_id[index]);
    }});
    send({type:'ready'});
  });
  const theme = mode => {
    const dark = mode === 'dark';
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.body.style.background = dark ? '#17130f' : '#fbf8f3';
    map.container.querySelectorAll('canvas').forEach(canvas => { canvas.style.background = document.body.style.background; });
    const colors = new Uint8Array(map.originalColors);
    if (dark) for (let i = 0; i < colors.length; i++) if (i % 4 !== 3) colors[i] = Math.round(colors[i] * .65 + 255 * .35);
    const points = map.pointLayer.clone({data:{...map.pointLayer.props.data, attributes:{...map.pointLayer.props.data.attributes,getFillColor:{value:colors,size:4}}}});
    map.layers = map.layers.map(layer => layer === map.pointLayer ? points : layer);
    map.pointLayer = points;
    const next = map.labelLayer.clone({
      getColor: dark ? [242,232,218] : [39,32,25],
      outlineColor: dark ? [23,19,15,255] : [251,248,243,255],
      getBackgroundColor: dark ? [23,19,15,200] : [251,248,243,200],
      updateTriggers:{getColor:mode,getBackgroundColor:mode}
    });
    map.layers = map.layers.map(layer => layer === map.labelLayer ? next : layer);
    map.labelLayer = next;
    map.deckgl.setProps({layers:map.layers});
  };
  window.addEventListener('message', event => {
    if (event.source !== parent || event.origin !== location.origin || event.data?.channel !== 'scout-map' || !ready || failed) return;
    const message = event.data;
    try {
      if (message.type === 'filter' && Array.isArray(message.indices)) {
        // DataMapPlot treats an empty selection as "all"; handle zero matches explicitly.
        map.selected.fill(-1);
        for (const i of message.indices) if (Number.isInteger(i) && i >= 0 && i < map.selected.length) map.selected[i] = 1;
        map.updateTriggerCounter++;
        const next = map.pointLayer.clone({
          data:{...map.pointLayer.props.data, attributes:{...map.pointLayer.props.data.attributes, getFilterValue:{value:map.selected,size:1}}},
          radiusMinPixels:message.indices.length < map.selected.length ? 3 : map.pointRadiusMinPixels,
          updateTriggers:{getFilterValue:map.updateTriggerCounter}
        });
        map.layers = map.layers.map(layer => layer === map.pointLayer ? next : layer);
        map.pointLayer = next;
        map.deckgl.setProps({layers:map.layers});
        document.documentElement.dataset.visiblePoints = String(message.indices.length);
        if (message.fit && message.indices.length) {
          let next = {...home};
          if (message.indices.length < map.selected.length) {
            const xs = message.indices.map(i => map.pointData.x[i]);
            const ys = message.indices.map(i => map.pointData.y[i]);
            const fit = calculateZoomLevel([Math.min(...xs)-.4,Math.max(...xs)+.4,Math.min(...ys)-.4,Math.max(...ys)+.4], map.container.clientWidth, map.container.clientHeight, .8);
            next = {longitude:fit.dataCenter[0],latitude:fit.dataCenter[1],zoom:Math.min(fit.zoomLevel,home.zoom+3)};
          }
          map.deckgl.setProps({initialViewState:next});
          map.notifyViewStateChange(next);
        }
      } else if (message.type === 'theme') theme(message.theme);
      else if (['zoom-in','zoom-out','reset','resize'].includes(message.type)) {
        const next = message.type === 'reset' ? {...home} : {...current};
        if (message.type === 'zoom-in') next.zoom += 0.6;
        if (message.type === 'zoom-out') next.zoom -= 0.6;
        next.zoom = Math.max(-2, Math.min(20, next.zoom));
        map.deckgl.setProps({initialViewState:next});
        map.notifyViewStateChange(next);
      }
    } catch { fail(); }
  });
})();
