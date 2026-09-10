"""Accessible interface independent of the optional DataMapPlot frame."""
import html
import json


def shell_html(records, locale, options):
    pl = locale == 'pl'
    t = lambda a, b: a if pl else b
    esc = lambda value: html.escape(str(value), quote=True)
    title = t('Mapa semantyczna', 'Semantic map')
    base = '/scouting-autoresearch/' + ('' if pl else 'en/')
    fields = ('id', 'title', 'author', 'year', 'sourceTitle', 'summary', 'topName', 'fineName', 'topClusterId', 'fineClusterId', 'activityUrl', 'translationStatus', 'originalLanguage', 'digitalEditionUrl', 'sourceUrl')
    payload = json.dumps({'records': [{k: r.get(k) for k in fields} for r in records], 'locale': locale}, ensure_ascii=False).replace('<', '\\u003c')
    items = ''.join(
        f'<li data-map-list-item data-id="{esc(r["id"])}"><a target="_top" href="{esc(r["activityUrl"])}">{esc(r["title"])}</a>'
        f'<p>{esc(r["author"])} · {esc(r["sourceTitle"])} · {esc(r["year"])}</p>'
        f'<span>{esc(r["topName"])} / {esc(r["fineName"])}</span></li>'
        for r in sorted(records, key=lambda r: (r['title'].casefold(), r['id']))
    )
    choices = ''
    for level in ('top', 'fine'):
        choices += f'<optgroup label="{t("Regiony", "Regions") if level == "top" else t("Podregiony", "Subregions")}">'
        choices += ''.join(f'<option value="{o["id"]}" data-download="{esc(o["url"])}">{esc(o["name"])} ({o["size"]})</option>' for o in options if o['level'] == level)
        choices += '</optgroup>'
    return f'''<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} · Scouting Autoresearch</title><link rel="stylesheet" href="shell.css"><script src="theme.js"></script><script src="shell.js" defer></script></head>
<body data-view="list"><header class="map-header"><div><a class="back" target="_top" href="{base}map/">← {t('Powrót', 'Back')}</a><h1>{title}</h1><p>{len(records)} {t('gier · 8 regionów · 32 podregiony', 'games · 8 regions · 32 subregions')}</p></div><a class="locale-link" target="_top" href="../{'en' if pl else 'pl'}/">{'EN' if pl else 'PL'}</a></header>
<div class="toolbar"><label class="search-container" for="map-search"><span>{t('Znajdź grę', 'Find a game')}</span><input type="search" id="map-search" placeholder="{t('Tytuł, autor, książka…', 'Title, author, book…')}" autocomplete="off"></label>
<div class="view-switch" role="group" aria-label="{t('Widok', 'View')}"><button data-view-button="list" aria-pressed="true">{t('Lista', 'List')}</button><button data-view-button="map" aria-pressed="false">{t('Mapa', 'Map')}</button></div><button id="open-panel">{t('Regiony i opcje', 'Regions & options')}</button></div>
<div class="workspace"><main id="main"><div class="results-bar"><span id="result-count" role="status">{len(records)} {t('gier', 'games')}</span><button id="clear" hidden>{t('Wyczyść', 'Clear')}</button></div>
<section id="list-view" aria-label="{t('Lista gier', 'Game list')}" data-accessible-map-list><p id="empty" hidden>{t('Brak pasujących gier. Zmień zapytanie lub region.', 'No matching games. Change your search or region.')}</p><ol class="game-list">{items}</ol></section>
<section id="map-view" hidden aria-label="{t('Interaktywna mapa', 'Interactive map')}"><iframe id="map-engine" title="{t('Punkty i regiony mapy', 'Map points and regions')}" data-state="idle"></iframe>
<div id="map-status" role="status"><span id="status-text">{t('Ładowanie mapy…', 'Loading map…')}</span><div id="recovery" hidden><button id="retry">{t('Spróbuj ponownie', 'Try again')}</button><button id="fallback-list">{t('Przejdź do listy', 'Go to list')}</button></div></div>
<div class="map-controls" aria-label="{t('Sterowanie mapą', 'Map controls')}"><button data-map-action="zoom-in" aria-label="{t('Przybliż', 'Zoom in')}" disabled>+</button><button data-map-action="zoom-out" aria-label="{t('Oddal', 'Zoom out')}" disabled>−</button><button data-map-action="reset" disabled>{t('Cała mapa', 'Whole map')}</button></div></section></main>
<dialog id="panel" class="panel" aria-labelledby="panel-title"><div class="panel-heading"><h2 id="panel-title">{t('Odkrywaj gry', 'Explore games')}</h2><button id="close-panel" aria-label="{t('Zamknij panel', 'Close panel')}">×</button></div>
<div class="topic-tree"><label for="region">{t('Region lub podregion', 'Region or subregion')}</label><select id="region"><option value="">{t('Wszystkie regiony', 'All regions')}</option>{choices}</select><p class="muted">{t('Zawęź listę i mapę do wybranego obszaru.', 'Narrow the list and map to the selected area.')}</p></div>
<div data-cluster-downloads><a id="download" data-cluster-download-link download hidden>{t('Pobierz region jako TXT', 'Download region as TXT')} ↓</a><p id="download-hint" class="muted">{t('Wybierz region, aby pobrać pełne teksty gier i ich źródła do dalszej pracy, także z LLM.', 'Choose a region to download full game texts and sources for further work, including with an LLM.')}</p></div>
<section id="game-detail" hidden aria-labelledby="detail-title"><p class="eyebrow">{t('Wybrana gra', 'Selected game')}</p><h2 id="detail-title"></h2><p id="detail-source" class="muted"></p><p id="detail-summary"></p><p id="detail-translation" class="muted" hidden>{t("Tłumaczenie automatyczne — bez weryfikacji człowieka.", "Machine translation — not human-verified.")}</p><div class="detail-sources"><a id="detail-original" target="_top">{t("Tekst źródłowy", "Source text")}</a> · <a id="detail-edition" target="_top">{t("Wydanie źródłowe", "Source edition")}</a></div><a id="detail-link" target="_top" class="primary">{t('Otwórz grę', 'Open game')} →</a></section>
<details class="map-help"><summary>{t('Jak czytać mapę?', 'How to read the map?')}</summary><p>{t('Bliskie punkty oznaczają podobieństwo tekstów. Położenie i regiony służą nawigacji; nie są klasyfikacją historyczną ani dowodem wspólnego pochodzenia.', 'Nearby points indicate text similarity. Positions and regions are navigational, not a historical classification or evidence of common origins.')}</p><p>{t('Wybierz punkt, aby zobaczyć grę. Przeciągaj mapę i używaj przycisków + / − lub gestu powiększania.', 'Select a point to see a game. Drag the map and use + / − or pinch to zoom.')}</p></details></dialog></div>
<noscript><p>{t('Lista gier i odnośniki działają bez JavaScript. Włącz JavaScript, aby filtrować i otworzyć mapę.', 'Game links and the list work without JavaScript. Enable JavaScript to filter and open the map.')}</p></noscript>
<script type="application/json" id="map-records">{payload}</script></body></html>'''
