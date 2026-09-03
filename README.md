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

## Taksonomia V1

Przed wywołaniem API skrypt pokazuje plan partii, koszt referencyjny i granicę źródła:

```bash
.venv/bin/python scripts/embed_taxonomy.py
.venv/bin/python scripts/embed_taxonomy.py --execute --limit 50
.venv/bin/python scripts/audit_taxonomy_inputs.py
.venv/bin/python scripts/analyze_taxonomy.py
.venv/bin/python scripts/propose_taxonomy.py
```

Cache jest ważny tylko dla zgodnego modelu, przepisu i hasha wejścia. Embeddingi nie mają
dziennego limitu dokumentów: jawny, skończony korpus ogranicza zakres, a konfiguracja dopuszcza
maksymalnie 50 rekordów w pojedynczym requeście. Selektor nie przechodzi do kolejnej książki
w środku requestu. Po każdej odpowiedzi zapisuje atomowy ledger i checkpoint, dzięki czemu
Goal Mode może kontynuować do ukończenia źródła. Przejściowy błąd API zapisuje `nextRetryAt`
zamiast utrzymywać uśpiony proces.

Obecny `billingMode: experimental-no-charge` zapisuje naliczony koszt jako 0 USD. Cena modelu
służy jedynie do raportowania kosztu referencyjnego i nie blokuje wykonania. Konfiguracja
zachowuje wyłączony bezpiecznik kosztu referencyjnego, który trzeba ponownie włączyć przed
użyciem rozliczanego konta.

Analizator nie wywołuje API. Wylicza deterministyczne sąsiedztwa i techniczne klastry,
oznacza niejednoznaczne przypisania oraz kandydatów odstających. Dopóki nie ma wszystkich
202 aktualnych cache’y, raport ma status `partial`; zawsze pozostaje propozycją do ręcznego
przeglądu i nie zmienia produkcyjnych kategorii ani filtrów.

Generator propozycji taksonomii materializuje 13 szerokich, dwujęzycznych kategorii oraz
jawne mapowania oparte wyłącznie na zastanych działach i polach redakcyjnych. Wynik trafia do
raportu z oznaczeniami `proposalOnly` i `reviewRequired`; nie zmienia `vault/taxonomy/`,
filtrów ani eksportów przed decyzją człowieka.

Kod obsługuje też przepis `activity-context-v2`, który przed skróceniem kontekstu usuwa
techniczną stopkę źródłową oraz adresy URL z Markdown, zachowując tekst widoczny odnośników.
Zmiana `recipeVersion` jest jawna i celowo unieważnia wcześniejsze cache’e. Wszystkie 202
aktywności źródeł `hwp-1946` i `pw-1935` mają aktualny cache v2; raport kosztu zachowuje
osobno zastąpiony pilotażowy przebieg v1. Jeżeli raport jakości ma status
`recipe-upgrade-pending`, tryb `--execute` jest blokowany dla starej receptury. Dry-run
pokazuje przyczynę blokady; wykonanie staje się możliwe dopiero po przełączeniu konfiguracji
na wskazaną recepturę kandydującą. Dopóki wszystkie ID z
`reembedBeforeNewActivities` nie mają aktualnego cache’a, selektor nie dobiera do partii
żadnych nowych aktywności — również po częściowym odzyskaniu przerwanej partii.

## Struktura

- `vault/` — źródło prawdy zgodne z Obsidianem,
- `vault/exploration/` — niezatwierdzone pomysły na taksonomię i nowe rodzaje aktywności,
- `data/generated/` — wersjonowane eksporty JSON i JSONL,
- `public/data/` — te same eksporty publikowane na stronie,
- `src/content/docs/` — generowane strony Starlight,
- `scripts/` — import, tłumaczenia, generowanie, analiza i walidacja,
- `config/` — kolejka badawcza i rejestr dozwolonych kolekcji.

Pełny kierunek rozwoju opisuje [project-plan.md](project-plan.md).

## Etapy rozwoju

- **V0:** działający, dwujęzyczny import 202 aktywności z dwóch polskich książek.
- **V1:** semantyczne uporządkowanie cech istniejącego korpusu za pomocą `mistral-embed` oraz
  wersjonowanej, dwujęzycznej taksonomii. Oryginalne określenia źródłowe pozostają bez zmian.
- **V2:** wyłącznie eksploracja, ocena i pozyskiwanie nowych książek oraz źródeł polskich
  i zagranicznych; korzysta z modelu danych i taksonomii wypracowanych w V0–V1.

Autoresearch prowadzi Codex w Goal Mode. Wiążące zasady pracy agenta znajdują się w
[`AGENTS.md`](AGENTS.md); `project-plan.md` opisuje kierunek produktu. Stan operacji zapisują
checkpointy właściwe dla konkretnego źródła lub pipeline'u, a ukończona jednostka otrzymuje
osobny commit natychmiast wypchnięty na gałąź pull requestu. Przejściowy limit API powoduje
checkpoint i wznowienie, a problemy wymagające decyzji człowieka zatrzymują cel.

## Zaufane źródła badawcze

[Azymut ZHR](https://azymut.zhr.pl/) jest zatwierdzonym źródłem redakcyjnym do odkrywania
współczesnych gier, prób i materiałów metodycznych. Zaufanie dotyczy jakości źródła, nie
zbiorczej zgody na przedruk: każdy materiał zachowuje autora, datę i link, a możliwość
publikacji pełnego tekstu jest ustalana osobno.

## Licencje i bezpieczeństwo

Kod: MIT. Projektowe metadane i tłumaczenia: CC BY 4.0 w zakresie posiadanych praw.
Importowane teksty zachowują status przypisany konkretnemu rekordowi; szczegóły zawiera
[DATA-LICENSE.md](DATA-LICENSE.md).

Dla Project Gutenberg obowiązuje zatwierdzona przez właściciela reguła: oznaczenie konkretnego
eBooka `Public domain in the USA` wraz z udokumentowanym upływem 70 pełnych lat od śmierci
ostatniego właściwego autora pozwala automatycznie przypisać jego składnikowi
`rightsStatus: public-domain` dla publikacji projektu w Polsce i UE. Osobno wyłącza się wkłady
innych autorów, późniejszą redakcję oraz licencję, znak i cyfrowe opakowanie Gutenberga.

Materiały historyczne nie są automatycznie współczesnymi rekomendacjami. Każda aktywność
wymaga oceny ryzyka, wieku uczestników, warunków i obowiązujących zasad.
