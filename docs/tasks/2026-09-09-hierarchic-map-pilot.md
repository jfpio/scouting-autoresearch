# Prototyp V1 hierarchicznej mapy semantycznej gier

## Podsumowanie

- Zbudować publiczną betę inspirowaną mapą Jaya Alammara: 914 gier, dwa poziomy klastrów,
  drzewo tematów, powiększanie, wyszukiwanie, karty gier i przejścia do pełnych rekordów.
- Zachować nienadzorowaną geometrię. Pomysły „las”, „pomieszczenie”, „duża gra terenowa”
  i „zuchy” służą w V1 tylko jako pytania podczas recenzji klastrów; nie stają się jeszcze
  filtrami ani klasyfikacją per gra.
- Porównać klastrowanie UMAP 2D z klastrowaniem pełnych embeddingów. Wybrany wariant i cała
  hierarchia około 8 regionów oraz 32 podregionów wymagają zatwierdzenia właściciela.
- Opublikować mapę w dwóch formach: podgląd na obecnej stronie `/map/` oraz osobny
  pełnoekranowy eksplorator.
- Prowadzić całość na jednej gałęzi i utworzyć jeden końcowy PR, bez pośrednich PR-ów.

## Pipeline analityczny i nazwy

- Rozszerzyć istniejącą konfigurację mapy o przypięte parametry prototypu: 32 klastry
  szczegółowe, 8 nadrzędnych, `KMeans(n_init=50)`, stałe ziarna, wersje bibliotek i hash
  korpusu.
- Wygenerować dwa anonimowe warianty:
  - **A — visual-first:** K-Means na współrzędnych UMAP 2D; centroidy 2D grupowane ponownie
    do 8 regionów.
  - **B — semantic-first:** K-Means na znormalizowanych wektorach 1024D; centroidy grupowane
    do 8 regionów, a UMAP służy wyłącznie prezentacji.
- Porównać warianty przez semantic i visual silhouette, stabilność ARI między ziarnami,
  rozmiary klastrów oraz koncentrację źródeł. Pakiet ślepej recenzji pokaże reprezentantów
  centralnych, rekordy brzegowe i najbliższe gry spoza klastra.
- Pierwsza bramka człowieka wybiera wariant A albo B. Jeżeli oba warianty tworzą klastry
  mniejsze niż pięć rekordów albo są nieczytelne, zatrzymać publikację i przedstawić wyniki
  zamiast samodzielnie zmieniać parametry.
- Po wyborze użyć `mistral-large-2512`, bez `reasoning_effort`, do przygotowania propozycji
  nazw:
  - jeden request dla każdego z 32 podregionów;
  - drugi przebieg dla ośmiu regionów nadrzędnych, usuwający powtarzające się lub zbyt
    ogólne nazwy;
  - model otrzymuje tytuły, streszczenia, źródła i lata reprezentatywnych gier, ale nie
    poznaje wcześniej czterech eksperckich hipotez.
- Odpowiedź modelu ma wersjonowany schemat JSON: nazwa i jednozdaniowy opis PL/EN,
  reprezentatywne identyfikatory, możliwe nakładanie tematów i poziom pewności.
- Stosować `temperature: 0`, cache po hashu wejścia, checkpoint po każdym sukcesie,
  sprawdzenie `/v1/models`, ledger oraz istniejący limit referencyjny 10 USD.
- Brak modelu lub `tier_not_allowed` zatrzymuje etap bez automatycznej zamiany modelu. `429`
  korzysta z istniejącej polityki `Retry-After` albo godzinnego fallbacku.
- Druga bramka człowieka zatwierdza lub poprawia wszystkie około 40 nazw i opisów. Pakiet
  recenzencki pyta również, czy samoczynnie wyłoniły się regiony lasu, pomieszczeń, dużych
  gier terenowych lub zabaw zuchowych.
- Zatwierdzenie dotyczy nawigacyjnej prezentacji klastrów, a nie historycznej klasyfikacji
  każdej gry.

## Dane i interfejs publiczny

- Zachować istniejący raport UMAP i embeddingi. Dodać osobny raport klastrów V1 zawierający:
  - przypięty `corpusDigest`, wybrany algorytm i metryki;
  - dokładnie jeden `fineClusterId` i `topClusterId` dla każdego punktu;
  - dla każdego klastra: `id`, `parentId`, liczebność, centroid, granice, status oraz
    zatwierdzone etykiety i opisy PL/EN;
  - `projectionIsNavigationalOnly: true`.
- Oddzielić rejestr zatwierdzonych nazw od propozycji LLM. Publiczny generator odmawia pracy,
  dopóki wybrany wariant, wszystkie nazwy i oba języki nie mają statusu `human-approved`.
- Nie zmieniać rekordów aktywności, taksonomii ani praktycznych filtrów. Nie publikować
  kandydatur podobieństw; zachować wyłącznie istniejące relacje zatwierdzone przez człowieka.
- Przypiąć `datamapplot==0.7.3` i generować dwujęzyczny, ciemny widok zawierający:
  - dwa poziomy etykiet i drzewo tematów;
  - granice klastrów, zoom, przesuwanie i wyszukiwanie;
  - tooltip: tytuł, autor, rok, książka, streszczenie, region i podregion;
  - kliknięcie prowadzące do strony gry;
  - osobną warstwę wyłącznie dla zatwierdzonych powiązań wariantów.
- Użyć `inline_data=False` i deterministycznych ścieżek dla skompresowanych danych. Zależności
  JavaScript i fonty osadzić przez offline mode DataMapPlot, aby mapa nie zależała od CDN.
- Istniejąca strona `/map/` i jej angielski odpowiednik otrzymują responsywny podgląd iframe
  oraz przycisk „Otwórz pełną mapę”.
- Pełnoekranowe trasy zawierają mapę, powrót do serwisu i stały, kontrastowy dark mode.
- Nie umieszczać pełnych tekstów gier w payloadzie. Dostępna lista tekstowa wszystkich
  punktów pozostaje poza canvasem jako równoważna nawigacja klawiaturowa.

## Uruchomienie, walidacja i publikacja

- Zacząć na nowej gałęzi od aktualnego `main` po zakończeniu równoległych zmian nawigacji.
  Nie mieszać zmian z innego chatu do zakresu mapy.
- Przed Slurmem zweryfikować na żywo konto, partycję i moduły. Nie używać GPU ani nowego
  środowiska; rozszerzyć istniejący job CPU `v3-semantic-validate`: 1 CPU, 8 GB RAM,
  30 minut, Python 3.12.
- Najpierw uruchomić w scratchu smoke render na 64 punktach, sprawdzić logi i komplet plików,
  a następnie pełne klastrowanie oraz rendering 914 punktów.
- Wywołania Mistrala wykonywać z login node w Goal Mode. Nie pozostawiać procesu oczekującego
  podczas cooldownu.
- Dodać testy sprawdzające:
  - kompletność 914 unikalnych ID i zgodność hashy z bazowym raportem;
  - deterministyczne K-Means, 32 niepuste klastry, 8 niepustych rodziców i dokładnie jednego
    rodzica na klaster;
  - poprawność metryk i anonimowego pakietu porównawczego;
  - blokadę publikacji niezatwierdzonych lub niepełnych nazw;
  - kompletność PL/EN, wewnętrznych URL-i i brak kandydatur podobieństw w publicznym payloadzie;
  - obecność drzewa tematów, wyszukiwania, tooltipów, zatwierdzonych relacji i dostępnej listy;
  - brak nowych requestów embeddingowych podczas ponownego buildu.
- CI instaluje przypięte zależności, sprawdza portable semantic report, buduje oba artefakty
  DataMapPlot, uruchamia testy, Astro build i kontrolę linków.
- Dokładne odtworzenie klastrów i pełny render przechodzą wcześniej na przypiętym środowisku
  Heliosa.
- Ręczny smoke przed PR obejmuje oba języki, podgląd i pełny ekran, wyszukiwanie, drzewo
  tematów, zoom, hover, kliknięcie rekordu, relacje, urządzenie mobilne i czytelność ciemnego
  motywu.

## Założenia

- „V1” oznacza pierwszą wersję hierarchicznego interfejsu mapy nad istniejącym pipeline’em
  V3, a nie zmianę taksonomii projektu V1.
- Korpus pozostaje przypięty do obecnych 914 gier. Zmiana `corpusDigest` przed implementacją
  wymaga najpierw odtworzenia embeddingów i bazowego raportu.
- W V1 nie ma eksperckich filtrów „las”, „pomieszczenie”, „duża gra” ani „zuchy”. Ich
  ewentualne przypisania per gra będą osobnym etapem.
- Nie wykonujemy nowych promptów per gra; LLM służy wyłącznie do propozycji nazw i opisów
  klastrów.
