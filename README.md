# Scouting Autoresearch

Dwujęzyczna, otwarta baza historycznych gier, prób i ćwiczeń harcerskich. Bieżący korpus
zawiera 284 aktywności z czterech książek w domenie publicznej:

- 117 gier z *Harcerza w polu* Zygmunta Wyrobka (1946),
- 85 prób z *Prób wodzów* L. Ungeheuera (1935),
- 49 gier z oryginalnego angielskiego tekstu *Scouting for Boys* Roberta Baden-Powella
  (1908), wybranych z przypiętego wydania Project Gutenberg bez ilustracji i późniejszych
  dodatków,
- 33 gry z rozdziału „The Games” Ernesta Thompsona Setona w pierwszym wydaniu
  *Boy Scouts Handbook* (1911), po wyłączeniu wkładów innych autorów i wariantów obecnych
  już w korpusie.

Pierwsze dwie książki składają się na zamknięty fundament V0. Tekst źródłowy jest polski albo
angielski zależnie od książki, a wersja w drugim języku jest tłumaczeniem automatycznym bez
weryfikacji człowieka. Każdy rekord prowadzi bezpośrednio do tekstu źródłowego i wydania
cyfrowego oraz zachowuje autora, oryginalny tytuł książki, rok, strony, przypiętą rewizję
źródła i status prawny.

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
rekordy z aktualnym hashem. Tłumaczenia V0 pozostają przypisane do
`mistral-medium-2604`. Dla nowych źródeł model jest przypinany w polityce źródła; bieżącym
modelem produkcyjnym dla `sfb-1908` jest zatwierdzony `mistral-large-2512`, bez włączania
`reasoning_effort`.

Import Project Gutenberg korzysta z jawnego manifestu, przypiętego SHA-256 i cache'u poza
repozytorium. Na Heliosie:

```bash
module purge
module load GCCcore/13.3.0 Python/3.12.3
source "$SCRATCH/scouting-autoresearch/venvs/x86_64-py312/bin/activate"
python scripts/import_gutenberg.py
python scripts/evaluate_translation_models.py
python scripts/evaluate_translation_models.py --execute
python scripts/translate.py --source-id sfb-1908
```

Importer zapisuje w repozytorium tylko wybrane rekordy i raport proweniencji; pobrany HTML
pozostaje w `$SCRATCH`. Tłumacz działa sekwencyjnie, po każdym sukcesie zapisuje atomowo
rekord i checkpoint, a przy `429` kończy proces z `nextRetryAt` zamiast utrzymywać go w uśpieniu.
Termin pochodzi bezpośrednio z poprawnego `Retry-After`; gdy nagłówka nie ma albo jest błędny,
pipeline stosuje godzinny fallback.
Limit wyjścia jest wyliczany z wielkości rekordu i zapisywany w ledgerze zamiast stałej
rezerwy 16 384 tokenów. Checkpoint błędu zawiera wyłącznie kod HTTP i dozwolone pola
diagnostyczne, bez pełnych nagłówków lub treści odpowiedzi.

Pierwsze polecenie ewaluacji jest dry-runem. Wariant `--execute` wykonuje sekwencyjny smoke
test `mistral-large-2512` na pięciu trudnych rekordach, bez reasoningu. Pełne wyniki trafiają
do `$SCRATCH/scouting-autoresearch/model-evaluations/`, a repozytorium zachowuje tylko
resumowalny checkpoint. Test nie zastępuje przeglądu jakości przez człowieka i respektuje
aktywny cooldown produkcyjnego tłumaczenia. Przed pierwszym tłumaczeniem pipeline sprawdza
również dokładny identyfikator modelu w `/v1/models`; model niedostępny dla planu zapisuje
trwały checkpoint zamiast zużywać kolejne requesty.

## Ocena redakcyjna

Wartość edukacyjna, praktyczna wykonalność i bezpieczeństwo są oceniane niezależnie od
statusu prawnego oraz jakości źródła. `scripts/prepare_editorial_review.py` tworzy dla
konkretnej aktywności pusty formularz przypięty do jej `sourceHash`; agent nie wypełnia ocen
i nie zatwierdza publikacji. Zmiana tekstu źródłowego powoduje błąd walidacji istniejącej
oceny. Ręcznie zaakceptowane rekordy zachowują osobę, datę i uzasadnienie, a ich rekomendacje
nie modyfikują automatycznie tekstu historycznego, tłumaczeń, praw ani eksportów.

## Bliskie warianty

`scripts/analyze_duplicates.py` porównuje aktywności z różnych książek w jednym języku,
korzystając z tekstu źródłowego albo aktualnego tłumaczenia angielskiego. Deterministyczny
TF-IDF na słowach i parach słów tworzy wyłącznie krótką listę kandydatów do ręcznej oceny.
Stopki proweniencji i URL-e nie wpływają na wynik, raport jest przypięty do hashy tekstów,
a algorytm nigdy nie scala ani nie usuwa rekordów automatycznie.

```bash
python scripts/analyze_duplicates.py
python scripts/analyze_duplicates.py --check
```

## Pilotaż Setona

Rozdział gier Setona pełni rolę pierwszej małej jednostki pilotażowej. Raport
`data/reports/bsh-1911-seton-games-pilot.json` wylicza zakres, koszt katalogowy, wyniki
automatycznych kontroli i znane czasy wyłącznie z przypiętych artefaktów. Nie uzupełnia
brakujących pomiarów szacunkiem: pełny czas pipeline'u i czas ręcznej recenzji pozostają
`not-recorded`. Pięć formularzy w `vault/reviews/editorial/inbox/` odpowiada wcześniejszej
próbie porównawczej modeli. Dopóki człowiek nie oceni tych rekordów i nie poda czasu,
raport ma status oczekujący i nie pozwala uznać pilota za podstawę skalowania.

```bash
python scripts/build_pilot_report.py
python scripts/build_pilot_report.py --check
```

## Materiały chronione

Materiały chronione i te o nierozstrzygniętych prawach są domyślnie zapisywane jako
`link-only`: fakty bibliograficzne, identyfikator, kanoniczny URL i własna notatka, bez tekstu,
OCR-u, skanu, obrazu lub tłumaczenia. Repozytorium nie przyjmuje liczbowego limitu cytatu jako
automatycznej bezpiecznej reguły. Każdy cytat wymaga osobnej decyzji człowieka, wskazanego celu,
uzasadnienia zakresu, pełnej atrybucji i precyzyjnej lokalizacji. Szczegóły oraz źródła prawne
są w `vault/policies/protected-sources.md`.

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
zamiast utrzymywać uśpiony proces, stosując `Retry-After` dostawcy albo godzinny fallback.

Nowe wywołania używają kredytów API subskrypcji Education. `billingMode:
education-credit` zapisuje koszt katalogowy i egzekwuje twardy limit 10 USD; faktyczna kwota
rozliczenia pozostaje nieznana, ponieważ API jej nie zwraca. Historyczne operacje wykonane
poprzednim kluczem zachowują `experimental-no-charge`. Sam abonament Education nie jest
traktowany jako dowód wyższego rate limitu — dostęp jest sprawdzany empirycznie dla dokładnego
identyfikatora modelu.

Analizator nie wywołuje API. Wylicza deterministyczne sąsiedztwa i techniczne klastry,
oznacza niejednoznaczne przypisania oraz kandydatów odstających. Dopóki nie ma wszystkich
202 aktualnych cache’y, raport ma status `partial`; zawsze pozostaje propozycją do ręcznego
przeglądu i nie zmienia produkcyjnych kategorii ani filtrów.

Generator propozycji taksonomii materializuje 13 szerokich, dwujęzycznych kategorii oraz
jawne mapowania oparte wyłącznie na zastanych działach i polach redakcyjnych. Wynik trafia do
raportu z oznaczeniami `proposalOnly` i `reviewRequired`; nie zmienia `vault/taxonomy/`,
filtrów ani eksportów przed decyzją człowieka.

## Audyt skali uczestników V3

Pierwszy krok V3 mierzy, w ilu tekstach gier występują jawne sygnały skali uczestników oraz
wzmianki o liczbie osób. Raport leksykalny nie jest klasyfikacją: nie zapisuje
`participantScales`, nie wyprowadza `minParticipants` ani `maxParticipants` i nie zmienia
produkcyjnych filtrów. Wielokrotne trafienie jest oczekiwane, bo źródło może opisywać kilka
wariantów albo różne role w tej samej grze. Wynik oraz checkpoint są deterministyczne i
wymagają decyzji człowieka przed zmianą schematu.

```bash
python scripts/audit_v3_participants.py
python scripts/audit_v3_participants.py --check
```

Embeddingi mapy semantycznej mają osobny przepis, cache, ledger, raport i checkpoint od V1.
Wejście łączy tytuł oraz ograniczony kontekst źródłowy z tytułem i krótszym kontekstem w
drugim języku. Przed każdym requestem pipeline sprawdza dokładny model w `/v1/models`, nie
łączy książek w jednej partii i egzekwuje łączny limit kosztu referencyjnego 10 USD.

```bash
python scripts/embed_semantic_map.py --source-id bsh-1911-seton-games --limit 1
python scripts/embed_semantic_map.py --source-id bsh-1911-seton-games --limit 1 --execute
python scripts/embed_semantic_map.py --source-id bsh-1911-seton-games --limit 50 --execute
```

Pierwsze polecenie jest dry-runem, drugie najmniejszym requestem smoke, a trzecie kończy
bieżące źródło. Po `429` proces zapisuje `nextRetryAt` i kończy się bez oczekiwania na węźle
logowania. Źródło można commitować dopiero, gdy wszystkie jego gry mają aktualny cache.
Wszystkie 199 gier z trzech źródeł ma aktualne embeddingi V3. Sześć requestów zużyło łącznie
149 629 tokenów wejściowych, co odpowiada kosztowi referencyjnemu 0,0149629 USD. API nie
zwróciło kwoty faktycznie rozliczonej z kredytów Education.

Przypięty `umap-learn` wylicza na węźle CPU pozycje 2D, dziesięciu najbliższych sąsiadów
każdej gry i wzajemne pary między różnymi źródłami do ręcznej oceny. Raport jest wyłącznie
propozycją: kandydatury algorytmiczne nie trafiają do produkcyjnych relacji, a zatwierdzone
relacje są nakładane jako osobna warstwa. Trzy dodatkowe ziarna mierzą stabilność układu;
współrzędne służą do nawigacji, nie są kategorią ani dowodem pochodzenia historycznego.

```bash
python scripts/analyze_semantic_map.py
python scripts/analyze_semantic_map.py --check
python scripts/analyze_semantic_map.py --check --portable
python scripts/audit_v3_facets.py
python scripts/audit_v3_facets.py --check
python scripts/build_semantic_review_packet.py
python scripts/build_semantic_review_packet.py --check
```

Pełny `--check` jest kontrolą odtwarzalności w przypiętym środowisku Heliosa. Wariant
`--portable`, używany w CI, nadal porównuje dokładnie hashe korpusu, sąsiadów cosinusowych,
kandydatury i zatwierdzone relacje, ale pomija współrzędne i metryki projekcji UMAP, które
mogą różnić się między implementacjami CPU mimo tych samych wersji bibliotek i ziaren.

Audyt praktycznych faset V3 działa bez API i nie zapisuje kategorii do aktywności. Dla 12
wymiarów podaje pokrycie jawnych sygnałów w tekstach źródłowych, rekordy z sygnałami wielu
wartości, obciążenie ręcznego odczytu oraz proxy różnicowania korpusu. Wartość wyszukiwawcza
i precyzja próbek pozostają jawnie nieocenioną decyzją człowieka.

Pakiet recenzencki mapy materializuje wszystkie wzajemne, międzyźródłowe kandydatury z
raportu analizy wraz z dwujęzycznymi tytułami, krótkimi fragmentami, wynikiem cosinusowym i
rangami w obu kierunkach. Nie jest częścią publicznej strony i nie zapisuje relacji. Każda z
30 par pozostaje `pending` do osobnej decyzji człowieka.

Dla bieżącego korpusu raport zawiera 199 punktów i 30 niezatwierdzonych par do przeglądu.
Zatwierdzona relacja `bsh-037`–`hwp-041` jest w obu kierunkach najbliższym sąsiadem również
w embeddingach V3. Trustworthiness projekcji przy `k=10` wynosi 0,72618405, a najniższa
korelacja rangowa odległości między dodatkowymi ziarnami wynosi 0,81821257.

Dwujęzyczna strona `/map/` pokazuje wyłącznie punkty, filtr źródła i zatwierdzone relacje.
Ma równoważną listę linków oraz obsługę klawiatury. Nie publikuje kandydatur algorytmicznych;
filtry kategorii i skali uczestników pozostają wyłączone do decyzji człowieka.

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
- **V3:** embeddingi wszystkich gier, mapa semantyczna oraz jawne, ręcznie zatwierdzane
  fasety praktyczne; pierwszy audyt mierzy sygnały skali uczestników bez klasyfikowania gier.

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

Metadane Project Gutenberg pobiera `scripts/gutenberg_metadata.py` z oficjalnych rekordów
RDF pojedynczych eBooków. Adapter nie crawluje stron katalogowych przeznaczonych dla ludzi,
waliduje identyfikator rekordu, ogranicza odpowiedź do 2 MiB, przypina SHA-256 wejścia i
atomowo przechowuje cache pod `$SCRATCH/scouting-autoresearch/sources/`. Przykład lekkiego
wywołania na węźle logowania:

```bash
python scripts/gutenberg_metadata.py --ebook-id 65993 --output "$SCRATCH/scouting-autoresearch/metadata/pg-65993.json"
```

Wynik jest wyłącznie rekordem odkrywania. Oznaczenie praw z RDF nadal wymaga zastosowania
zatwierdzonej reguły kolekcji, ustalenia autorstwa właściwego składnika oraz zachowania
osobnej bramki dla konkretnej edycji i jej wkładów.

Adapter `scripts/gallica.py` pobiera tylko obiekt mający dokładne `itemApproval` w rejestrze.
Adresy paginacji, widoku IIIF i PDF-u wyprowadza z zatwierdzonego identyfikatora, nie pozwala
zapisać wyniku poza `$SCRATCH/scouting-autoresearch/`, ogranicza rozmiar odpowiedzi,
sprawdza typ i sygnaturę pliku oraz zapisuje go atomowo. Stan dostawcy w scratch wymusza
minimalny odstęp wynikający z `rateLimitPerMinute` bez usypiania procesu. Bez `--execute` wykonuje tylko
dry-run. Dla pełnego dokumentu respektuje `nextRetryAt` checkpointu, po `429` lub `5xx`
zapisuje wyłącznie bezpieczną diagnostykę i termin podany przez dostawcę albo godzinny
fallback. Przykład:

```bash
python scripts/gallica.py --source-id chamarande-1934 --artifact pdf
python scripts/gallica.py --source-id chamarande-1934 --artifact pdf --execute
```

Jeżeli udokumentowany endpoint pełnego PDF pozostaje ograniczony przez dostawcę, fallback
`scripts/gallica_views.py` wybiera jeden brakujący widok IIIF na uruchomienie. Nie omija
cooldownu ani limitu kolekcji, nie zmienia dostawcy i po każdym sukcesie zapisuje hash oraz
postęp w checkpointcie. Dzięki temu Goal Mode może wznawiać pobieranie bez procesu śpiącego
na login node:

```bash
python scripts/gallica_views.py --source-id chamarande-1934
python scripts/gallica_views.py --source-id chamarande-1934 --execute
```

Po zapisaniu i zweryfikowaniu wszystkich 188 widoków ich inspekcja graficzna odbywa się na
węźle CPU, nie na login node. Zadanie sprawdza komplet plików i przypięty hash paginacji, po
czym tworzy w scratch dwa arkusze: w kolejności widoków Gallici oraz według numerów stron
drukowanych. Drugi wariant jest konieczny, ponieważ składki książki nie są zeskanowane w
ciągłej kolejności stron:

```bash
mkdir -p "$SCRATCH/scouting-autoresearch/logs"
sbatch jobs/helios/chamarande-contact-sheets.slurm
```

Wyniki trafiają pod
`$SCRATCH/scouting-autoresearch/runs/chamarande-1934/iiif-contact-full/<job-id>/` i służą
wyłącznie do zaproponowania zakresów stron. Nie zatwierdzają automatycznie autorstwa ani
uruchomienia OCR-u.

Zatwierdzone lokalne obrazy stron można przekazać do Mistral OCR przez drugi adapter,
również domyślnie działający jako dry-run:

```bash
python scripts/mistral_ocr.py \
  --config config/ocr/chamarande-1934.yaml \
  --image "$SCRATCH/scouting-autoresearch/sources/chamarande-1934/f19-1200.jpg"
```

`--execute` najpierw sprawdza dokładny model przez `/v1/models`, a potem przetwarza obrazy
sekwencyjnie. Surowe odpowiedzi zostają w scratch; śledzony checkpoint zapisuje hashe,
liczbę stron, bezpieczne dane retry, rozliczenie `education-credit` i egzekwowany limit
kosztu referencyjnego. Produkcyjne wykonanie pozostaje zablokowane przez `executionReady`
do czasu ustalenia i wpisania zakresów widoków zawierających wyłącznie zatwierdzoną prozę.

## Licencje i bezpieczeństwo

Kod: MIT. Projektowe metadane i tłumaczenia: domyślnie CC BY 4.0 w zakresie posiadanych
praw. Importowane teksty zachowują status i warunki przypisane konkretnemu rekordowi.
Materiał odtworzony z reprodukcji Gallici oraz oparte na nim tłumaczenia stanowią jawny
wyjątek niekomercyjny; szczegóły zawiera [DATA-LICENSE.md](DATA-LICENSE.md).

Dla Project Gutenberg obowiązuje zatwierdzona przez właściciela reguła: oznaczenie konkretnego
eBooka `Public domain in the USA` wraz z udokumentowanym upływem 70 pełnych lat od śmierci
ostatniego właściwego autora pozwala automatycznie przypisać jego składnikowi
`rightsStatus: public-domain` dla publikacji projektu w Polsce i UE. Osobno wyłącza się wkłady
innych autorów, późniejszą redakcję oraz licencję, znak i cyfrowe opakowanie Gutenberga.

Materiały historyczne nie są automatycznie współczesnymi rekomendacjami. Każda aktywność
wymaga oceny ryzyka, wieku uczestników, warunków i obowiązujących zasad.
