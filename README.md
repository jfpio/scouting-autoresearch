# Scouting Autoresearch

Dwujęzyczna, otwarta baza historycznych gier, prób i ćwiczeń harcerskich. Wersja V0 zawiera
202 aktywności z dwóch książek oznaczonych przez Polonę jako domena publiczna:

- 117 gier z *Harcerza w polu* Zygmunta Wyrobka (1946),
- 85 prób z *Prób wodzów* L. Ungeheuera (1935).

Polskie transkrypcje są tekstem źródłowym. Angielskie wersje są tłumaczeniami automatycznymi
i nie są weryfikowane przez człowieka. Każdy rekord prowadzi bezpośrednio do polskiej
transkrypcji i skanu oraz zachowuje autora, oryginalny tytuł książki, rok, strony, commit
źródłowego wydania cyfrowego i status prawny.

Strona: <https://jfpio.github.io/scouting-autoresearch/>

## Uruchomienie na czystym serwerze

Wymagane są Node.js 24 i Python 3.12+:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci
.venv/bin/python scripts/validate.py
npm run build
```

Gotowa strona znajduje się w `dist/`. Można też użyć kontenera:

```bash
docker build -t scouting-autoresearch .
docker run --rm -p 8080:80 scouting-autoresearch
```

## Odtworzenie importu

Repozytoria źródłowe pozostają niezależne. Po ich sklonowaniu do sąsiednich katalogów:

```bash
.venv/bin/python scripts/import_sources.py \
  --harcerz ../harcerz-w-polu \
  --proby ../proby-wodzow
.venv/bin/python scripts/translate.py
.venv/bin/python scripts/build_content.py
.venv/bin/python scripts/validate.py
```

Importer zapisuje commity i sumy kontrolne w `imports.lock.json`. Tłumacz wczytuje
`MISTRAL_API_KEY` z `~/.secrets/mistral.env` albo środowiska, nie zapisuje klucza i pomija
rekordy z aktualnym hashem. Model V0 to `mistral-medium-2604`; żądany pierwotnie
`mistral-large-2512` nie był dostępny dla użytego planu API.

## Struktura

- `vault/` — źródło prawdy zgodne z Obsidianem,
- `vault/exploration/` — niezatwierdzone pomysły na taksonomię i nowe rodzaje aktywności,
- `data/generated/` — wersjonowane eksporty JSON i JSONL,
- `public/data/` — te same eksporty publikowane na stronie,
- `src/content/docs/` — generowane strony Starlight,
- `scripts/` — import, tłumaczenia, generowanie, walidacja i cykl V2,
- `config/` — kolejka badawcza i rejestr dozwolonych kolekcji,
- `deploy/systemd/` — przykładowy ograniczony timer serwerowy.

Pełny kierunek rozwoju opisuje [project-plan.md](project-plan.md).

## Licencje i bezpieczeństwo

Kod: MIT. Projektowe metadane i tłumaczenia: CC BY 4.0 w zakresie posiadanych praw.
Importowane teksty zachowują status przypisany konkretnemu rekordowi; szczegóły zawiera
[DATA-LICENSE.md](DATA-LICENSE.md).

Materiały historyczne nie są automatycznie współczesnymi rekomendacjami. Każda aktywność
wymaga oceny ryzyka, wieku uczestników, warunków i obowiązujących zasad.
