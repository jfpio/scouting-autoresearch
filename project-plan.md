# Scouting Autoresearch — plan projektu

## Cel

Projekt ma pomóc drużynowym oraz narzędziom opartym na modelach językowych znaleźć aktywność
pasującą do potrzeb grupy bez wielokrotnego przeszukiwania tych samych książek. Wspólna encja
`activity` obejmuje gry, próby i ćwiczenia; rekord może należeć do więcej niż jednego rodzaju.

Publiczna strona jest warstwą prezentacji. Obsidian Vault pozostaje źródłem prawdy, a JSON,
JSONL, `llms.txt`, `llms-full.txt` i strony Starlight są deterministycznymi produktami generatora.

## V0 — działający fundament

V0 importuje 117 gier z *Harcerza w polu* (Zygmunt Wyrobek, 1946) i 85 prób z *Prób wodzów*
(L. Ungeheuer, 1935). Nie kopiuje PDF-ów, całych książek ani historii Git. Każda aktywność ma:

- stabilny identyfikator `hwp-001`–`hwp-117` albo `pw-001`–`pw-085`,
- autora, oryginalny tytuł książki, rok i wydawcę,
- strony drukowane i PDF,
- URL Polony, wydania cyfrowego i facsimile na właściwej stronie,
- commit importu, hash treści, status transkrypcji, praw i bezpieczeństwa,
- polski tekst źródłowy oraz angielskie tłumaczenie maszynowe z modelem, wersją promptu,
  datą, hashem oryginału i statusem.

Tłumaczenia V0 wykonano przypiętym modelem `mistral-medium-2604`. Na poprzednim kluczu
`mistral-large-2512` zwracał błąd poziomu subskrypcji; nie zastosowano nieoznaczonego aliasu
ani cichej podmiany. Nowy klucz Education udostępnia dokładny wersjonowany model Large.

Dla nowych źródeł wybór modelu poprzedza ograniczony test jakości na reprezentatywnych
rekordach. Dla *Scouting for Boys* właściciel zatwierdził dostępny
`mistral-large-2512`; smoke test obejmuje pięć trudnych rekordów. Tłumaczenie nie włącza
reasoningu, ponieważ zadanie ma ścisły kontrakt wierności i formatu. Żądania używają limitu
wyjścia zależnego od rozmiaru rekordu i zapisują bezpieczne dane diagnostyczne o rzeczywistych
limitach dostawcy.

Strona oferuje osobne widoki „Wszystkie”, „Gry”, „Próby” i „Źródła” w języku polskim oraz
angielskim. Filtry obejmują tekst, rodzaj, cechę, autora, książkę, rok i dział.

### Kryteria V0

- dokładnie 202 unikalne aktywności: 117 gier i 85 prób,
- dokładnie 202 aktualne tłumaczenia angielskie,
- pełny tekst tylko dla `rightsStatus: public-domain`,
- zgodne identyfikatory i liczebność w obu językach,
- żadnych PDF-ów, sekretów ani zagnieżdżonych repozytoriów,
- testy, walidacja schematu, generowanie i statyczny build przechodzą lokalnie i w CI,
- GitHub Pages działa pod `/scouting-autoresearch/`.

## V1 — semantyczna taksonomia istniejącego korpusu

V1 porządkuje cechy 202 już zaimportowanych aktywności. Nie odkrywa ani nie importuje nowych
książek. Oryginalne cechy i określenia pozostają częścią rekordu jako dane źródłowe, a
szersze kategorie są osobną, współczesną warstwą ułatwiającą filtrowanie i wyszukiwanie.

Pipeline V1:

```text
normalize labels → embed source labels and activity context → propose clusters
                 → inspect outliers → version taxonomy → map activities → validate → publish
```

- Użyć dostępnego na koncie modelu `mistral-embed`; każda partia zapisuje faktyczny
  identyfikator modelu, wymiar wektora, wersję przepisu wejścia, datę oraz hash wejścia.
- Embedding obejmuje etykietę źródłową oraz krótki kontekst aktywności, aby odróżnić podobne
  słowa używane w różnych znaczeniach. Wyniki są cache'owane i ponawiane tylko po zmianie
  modelu, przepisu albo hasha wejścia.
- Sąsiedztwa wektorowe i klastrowanie służą do przygotowania propozycji, nie do dynamicznego
  zmieniania filtrów przy każdym buildzie. Produkcyjna mapa kategorii jest jawnym,
  wersjonowanym plikiem w `vault/taxonomy/`.
- Celować w około 10–15 szerokich, dwujęzycznych kategorii. Rekord zachowuje zarówno
  oryginalne `sourceTraits`, jak i stabilne identyfikatory współczesnych kategorii; żadna
  cecha źródłowa nie może zniknąć wskutek klastrowania.
- Raport V1 zawiera klastry, najbliższych sąsiadów, odstające etykiety, niejednoznaczne
  przypisania, wersję taksonomii, wykorzystane tokeny i koszt. Brakujące lub słabe
  dopasowanie pozostaje jawnie nieprzypisane zamiast być zgadywane.
- Korpus V1 jest jawny i skończony; nie stosujemy dziennego limitu dokumentów. Pojedynczy
  request obejmuje najwyżej 50 rekordów i nie przekracza granicy źródła, a po każdej odpowiedzi
  powstaje resumowalny checkpoint. Na koncie eksperymentalnym bez opłat koszt katalogowy jest
  raportem referencyjnym, nie bramką wykonania. Przejściowe ograniczenia API korzystają z zasad
  `Retry-After` dostawcy, a przy jego braku godzinnego fallbacku opisanego dla Goal Mode;
  wyczerpanie limitu miesięcznego lub brak dostępu zatrzymuje cel i wymaga interwencji.

### Kryteria V1

- wszystkie 202 aktywności mają zachowane niezmienione etykiety źródłowe,
- każdy wektor ma model, wersję wejścia i zgodny hash, a cache jest deterministyczny,
- produkcyjne kategorie i ich polskie/angielskie etykiety mają stabilne identyfikatory,
- filtry używają szerokich kategorii, a strona rekordu nadal pokazuje zapis źródłowy,
- raport wymienia wszystkie niejednoznaczne mapowania i nie ukrywa etykiet odstających,
- ponowny build bez zmian nie wykonuje nowych wywołań embedding API.

## Model danych i jakości

`vault/activities/<id>.md` przechowuje tekst w języku źródłowym. Tłumaczenie jest nakładką
w `vault/translations/<locale>/<id>.md`, nigdy zamiennikiem oryginału. Zmiana tytułu lub treści
zmienia `sourceHash` i unieważnia tłumaczenie.

`vault/exploration/` przechowuje hipotezy powstające podczas badań: pomysły na podział cech
(np. zakres „pomysłowości” w próbach) oraz kandydatury na rodzaje aktywności inne niż gra
i próba. Propozycje mają przykłady, kontrprzykłady, dwujęzyczne etykiety i status redakcyjny.
Nie wpływają na filtry ani eksport produkcyjny, dopóki człowiek ich nie zaakceptuje.

Bliskie warianty tej samej gry pozostają osobnymi rekordami, ponieważ każdy zachowuje własny
tekst, autora, wydanie, strony i historię przekazu. Zatwierdzona przez człowieka relacja jest
symetryczna: oba rekordy oraz ich strony wskazują drugi wariant. Sam wynik podobieństwa lub
sąsiedztwa wektorowego jest tylko kandydaturą i nie tworzy publicznego powiązania.

Pola wieku, czasu, sprzętu, liczby uczestników i ryzyka mogą pojawić się dopiero, gdy wynikają
wprost ze źródła albo przeszły osobną redakcję. Brakujące dane pozostają nieznane. Projekt
oddziela trzy rodzaje ocen:

1. **Pochodzenie** — czy znamy konkretną edycję, autora, rok i strony.
2. **Wierność** — czy ekstrakcja i OCR są kompletne, a tłumaczenie ma aktualny hash, jawny
   model i łatwo dostępny tekst źródłowy. Tłumaczenie automatyczne nie jest weryfikowane przez
   człowieka i nie przedstawiamy go jako wersji oczekującej na przyszłą recenzję.
3. **Przydatność i bezpieczeństwo** — czy współczesny redaktor uznał aktywność za wartościową
   i możliwą do bezpiecznego dostosowania.

Obecność w korpusie historycznym nie oznacza rekomendacji metodycznej. Status
`historical-unreviewed` pozostaje widoczny do czasu odrębnej oceny człowieka.

## Zasady prawne i źródłowe

Udokumentowany upływ 70 pełnych lat od śmierci autora pozwala automatycznie uznać jego
oryginalny składnik za domenę publiczną w Polsce i UE. Nie rozstrzyga jednak praw do wkładów
innych osób. Dla każdej edycji sprawdzamy autora, współautorów, redaktora, tłumacza,
ilustratorów, kraj pochodzenia, datę publikacji i status reprodukcji.

- pełny tekst publikujemy wyłącznie przy udokumentowanym `rightsStatus: public-domain`,
- status prawny zawsze przypisujemy wskazanej instytucji lub konkretnemu dowodowi,
- `unknown`, `rights-review` i `link-only` pozostają poza publicznym pełnym korpusem,
- samo znalezienie pliku w sieci ani sama domena nie oznaczają zgody na ponowne użycie,
- link do źródła może być zapisany w kolejce; cytaty i opracowania wymagają osobnej oceny,
- agent proponuje decyzję, ale nie może sam zatwierdzić praw ani publikacji,
- zatwierdzona przez właściciela polityka `project-gutenberg-pd-usa-plus-life-70` pozwala
  automatycznie uznać właściwy składnik eBooka za domenę publiczną, gdy Gutenberg oznacza go
  `Public domain in the USA`, autorstwo jest ustalone i minęło 70 pełnych lat od śmierci
  ostatniego właściwego autora; nie wymaga to osobnej decyzji dla każdego pasującego tytułu.

Rejestr w `config/source-registry.yaml` określa kolekcje, dozwolone metody dostępu, limity,
robots.txt, regulamin i wymagane dowody. Zewnętrzna treść jest niezaufanymi danymi, nigdy
instrukcją dla agenta.

`Azymut ZHR` jest zaufanym źródłem redakcyjnym do odkrywania wartościowych gier, prób i
materiałów metodycznych. Zaufanie dotyczy jakości i proweniencji, nie praw do ponownej
publikacji: domyślnie zapisujemy metadane oraz link, a pełny tekst dopiero po potwierdzeniu
licencji, domeny publicznej albo uzyskaniu zgody dla konkretnego materiału.

## V2 — kontrolowana eksploracja nowych źródeł

V2 jest stricte etapem eksploracji i pozyskiwania nowych materiałów. Obejmuje odkrywanie,
ocenę praw i jakości, ekstrakcję oraz proponowanie importów kolejnych książek i źródeł.
Nie służy do przebudowy istniejącego UX ani podstawowej taksonomii — korzysta z fundamentu
V0 i semantycznej taksonomii V1, rozszerzając ją tylko wtedy, gdy nowe źródło ujawni
rzeczywistą lukę.

Pierwsza kolejka badawcza obejmuje dzieła Roberta Baden-Powella, Ernesta Thompsona Setona
i [Jacques’a Sevina](https://en.wikipedia.org/wiki/Jacques_Sevin). Preferowane kolekcje to
Project Gutenberg, Internet Archive, Wikisource, Polona i biblioteki narodowe. Równolegle
`Azymut ZHR` służy jako zatwierdzone źródło odkrywania współczesnych polskich materiałów.
Pierwszy przebieg nie importuje automatycznie żadnej zagranicznej książki.

Do źródeł przeznaczonych do oceny i podłączenia w V2 należą również:

- [historyczna.slaska.zhp.pl](https://historyczna.slaska.zhp.pl/?page_id=210),
- [Archiwum Harcerskie](https://archiwumharcerskie.pl/).

Oba serwisy są kandydatami do rejestru źródeł. Przed uruchomieniem adaptera sprawdzamy ich
regulamin, `robots.txt`, dozwoloną metodę dostępu oraz dowód statusu prawnego każdej konkretnej
publikacji; umieszczenie serwisu na liście V2 nie zatwierdza automatycznie pełnego tekstu.

Pipeline:

```text
discover → rights review → fetch → OCR/extract → normalize → deduplicate
         → translate → verify → pull request → publish
```

### Bramki

1. **Discover:** zapisuje kandydaturę, URL, autora, tytuł, edycję i sposób znalezienia.
   Może również dopisać propozycję taksonomii lub nowego rodzaju aktywności do eksploracji.
2. **Rights review:** człowiek zatwierdza regułę lub wyjątek; jednoznaczne dopasowanie
   istniejącej polityki kolekcji nie wymaga ponownej decyzji.
3. **Fetch:** pobiera wyłącznie z zaakceptowanej kolekcji, respektując limit i warunki.
4. **OCR/extract:** zachowuje surowy wynik i parametry procesu, jeśli potrzebny jest OCR.
5. **Normalize:** poprawia jedynie techniczne artefakty; nie modernizuje treści.
6. **Deduplicate:** porównuje hash, tytuł, źródło i podobieństwo tekstu. Dokładny duplikat
   może zostać wyłączony przed importem; bliski wariant pozostaje osobnym rekordem i po
   decyzji człowieka otrzymuje dwukierunkowy link do podobnej gry.
7. **Translate:** zapisuje model, prompt, datę i hash wejścia; oznacza
   `machine-translation` i zawsze linkuje tekst źródłowy oraz skan.
8. **Verify:** sprawdza schemat, kompletność, prawa, źródła, języki i bezpieczeństwo.
9. **Pull request:** agent przedstawia różnice, koszty, ryzyka i nierozstrzygnięte punkty.
10. **Publish:** następuje dopiero po zatwierdzeniu PR przez człowieka.

## Praca z Codex Goal Mode

Autoresearch orkiestruje Codex w Goal Mode. Wiążące zasady bezpieczeństwa, limitów,
checkpointów, publikacji i wznowień znajdują się wyłącznie w `AGENTS.md`; ten dokument
opisuje cele i kolejność rozwoju produktu.

Kolejka wskazuje następny temat, rekordy w `vault/reviews/` dokumentują decyzje, a checkpointy
konkretnych pipeline'ów przechowują wyłącznie stan potrzebny do bezpiecznego wznowienia.
Orkiestrację, gałęzie, commity i pull requesty prowadzi Codex zgodnie z `AGENTS.md`. Adaptery
pobierania są dodawane kolekcja po kolekcji po zatwierdzeniu zasad dostępu.

## Kolejka dalszych prac V2

- zweryfikować po jednej konkretnej edycji Baden-Powella, Setona i Sevina,
- ocenić zasady dostępu oraz kolekcje `historyczna.slaska.zhp.pl` i Archiwum Harcerskiego,
- zaimplementować adapter metadanych dla pierwszej zaakceptowanej kolekcji,
- dodać deduplikację bliskich wariantów tej samej aktywności,
- dodać redakcyjną ocenę wartości i bezpieczeństwa niezależną od oceny źródła,
- opisać politykę krótkich cytatów i rekordów `link-only` dla źródeł chronionych,
- przeprowadzić pilotaż na małej książce i zmierzyć koszt, jakość oraz czas recenzji,
- po pilotażu skalować liczbę źródeł według zmierzonej przepustowości i zewnętrznych limitów.

## V3 — embeddingi gier i mapa semantyczna

V3 tworzy semantyczną warstwę eksploracji całego korpusu gier. Pierwsza iteracja obejmuje
każdą aktywność zawierającą rodzaj `game`; próby pozostają poza zakresem, dopóki osobna
decyzja nie rozszerzy mapy. V3 nie zastępuje taksonomii V1, tekstu źródłowego ani ręcznie
zatwierdzonych relacji między wariantami.

Pipeline V3:

```text
review participant scale → version input recipe → embed every game
                         → verify cache and coverage → compute nearest neighbours
                         → project to 2D → overlay approved relations
                         → validate → publish filters and semantic map
```

- V3 dodaje ustrukturyzowaną skalę uczestników niezależną od embeddingu. Rekord może mieć
  zakres `minParticipants`–`maxParticipants`, jeżeli liczby są podane w źródle lub
  zatwierdzone redakcyjnie, oraz jedną lub więcej wartości `participantScales`:
  `individual`, `pair`, `small-group`, `single-patrol`, `multiple-patrols`, `single-troop`,
  `multiple-troops`, `mass-event` albo `unknown`. Dla układu typu „dwa zastępy” można
  dodatkowo zapisać liczbę i rodzaj jednostek. Każda wartość zachowuje podstawę
  `source-stated`, `human-reviewed` albo
  `unknown`; agent nie wylicza jej wyłącznie z podobieństwa semantycznego ani nie zgaduje z
  nieprecyzyjnego opisu.
- Publiczny interfejs pozwala filtrować co najmniej: pojedynczą osobę, parę, małą grupę,
  zastęp, drużynę, kilka drużyn i grę masową. Osobno można użyć minimalnej lub maksymalnej
  liczby uczestników tam, gdzie liczby są znane. `unknown` pozostaje widoczną opcją, a gra
  bez danych nie jest cicho przypisywana do najbliższego przedziału.
- Przed zamrożeniem filtrów V3 trzeba przeprowadzić audyt innych praktycznych wymiarów.
  Kandydatami są: układ uczestników (indywidualnie, pary, zespoły, wszyscy przeciw wszystkim),
  współpraca lub rywalizacja, eliminowanie uczestników, dominująca mechanika (np. pościg,
  skradanie, obserwacja, sygnalizacja, pamięć, sztafeta), ćwiczona sprawność, przestrzeń
  (wewnątrz, na zewnątrz, teren otwarty, las, woda), wymagana powierzchnia, ruch i intensywność
  fizyczna, czas gry i przygotowania, sprzęt, pora dnia lub widoczność, pogoda i sezon, kontakt
  fizyczny i ryzyko, hałas lub wymagana cisza, rola prowadzącego, dostępność, zalecany wiek
  oraz wymagane umiejętności. Audyt ma dla każdego wymiaru zmierzyć pokrycie, jednoznaczność
  źródeł, koszt redakcji i wartość dla wyszukiwania.
  Dopiero człowiek wybiera z tej listy filtry produkcyjne; pozostałe mogą zostać metadanymi,
  fasetami eksperymentalnymi albo elementami mapy semantycznej. Każde pole zachowuje podstawę
  `source-stated`, `human-reviewed` albo `unknown` i nie jest uzupełniane samym modelem.
  Pierwszy audyt leksykalny porównuje 12 wymiarów na wszystkich 199 grach, raportuje osobno
  pokrycie, sygnały wielu wartości, obciążenie zimnym odczytem i zdolność rozkładu sygnałów do
  różnicowania korpusu. Nie utożsamia tych proxy z trafnością ani wartością dla użytkownika;
  próbki precyzji i rubryka wartości pozostają bramką decyzji człowieka.
- Każda gra otrzymuje jeden wektor z wersjonowanego, ograniczonego do kontekstu modelu
  wejścia. Przepis zachowuje tytuł i treść w języku źródłowym oraz dodaje tytuł i krótki
  kontekst w drugim języku, aby mapa nie dzieliła się wyłącznie według języka. Hash wejścia
  obejmuje obie warstwy i unieważnia cache po zmianie tekstu lub tłumaczenia.
- V3 ma osobną konfigurację, checkpointy, ledger kosztu i katalog cache od embeddingów V1.
  Każdy wektor zapisuje dokładny model, wymiar, wersję przepisu, hash i użycie tokenów.
  Ponowny build bez zmian nie wykonuje requestów API.
- Najbliżsi sąsiedzi są propozycjami eksploracyjnymi. Tylko relacje zatwierdzone przez
  człowieka mogą pojawić się jako trwałe linki „bardzo podobna gra”; na mapie zatwierdzone
  relacje i sugestie algorytmu muszą wyglądać inaczej.
  Dopóki polityka zabrania publicznej ekspozycji kandydatur, pełna kolejka sąsiadów pozostaje
  w dwujęzycznym pakiecie recenzenckim niewłączanym do publicznej strony. Publiczny widok nie
  może wyprzedzić decyzji człowieka tylko po to, aby spełnić wymaganie prezentacyjne.
- Projekcja dwuwymiarowa używa przypiętej wersji algorytmu i zależności, jawnego ziarna oraz
  hasha pełnego korpusu. Współrzędne są pomocą nawigacyjną, nie kategorią ani twierdzeniem o
  historycznym pochodzeniu; dodanie źródeł może zmienić układ całej mapy.
- Widok mapy pozwala przejść do strony gry, filtrować co najmniej po źródle i zatwierdzonej
  kategorii oraz zobaczyć najbliższe gry. Musi mieć dostępną alternatywę listową i nie może
  wymagać interakcji wskaźnikiem.
- Raport V3 podaje pokrycie korpusu, model, recepturę, tokeny, koszt, parametry sąsiedztwa i
  projekcji, kandydatury podobnych gier, stabilność layoutu, audyt kandydatów na filtry oraz
  wynik ręcznego smoke testu.

### Kryteria V3

- zbiór identyfikatorów embeddingów jest dokładnie równy zbiorowi aktywności rodzaju `game`,
- nie ma współdzielonego ani cicho ponownie użytego cache między V1 i V3,
- każdy wektor i projekcja są odtwarzalne z przypiętej konfiguracji oraz hashy wejścia,
- mapa pokazuje źródło i prowadzi do właściwej strony każdego punktu,
- każda gra ma jawne `participantScales`, choćby `[unknown]`, a filtr skali odróżnia co
  najmniej parę, jeden i kilka zastępów oraz jedną i wiele drużyn; filtry liczbowe korzystają
  tylko z potwierdzonych wartości `minParticipants` i `maxParticipants`,
- raport audytu porównuje pokrycie i użyteczność pozostałych kandydatów na filtry, a żaden z
  nich nie staje się filtrem produkcyjnym bez decyzji człowieka,
- ręcznie zatwierdzone podobne gry są połączone dwukierunkowo, a sugestie pozostają oznaczone
  jako niezatwierdzone,
- zmiana samego stylu lub ponowny build nie uruchamia embedding API,
- mapa ma działającą alternatywę listową oraz podstawową obsługę klawiatury.
