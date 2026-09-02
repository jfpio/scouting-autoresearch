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

Tłumaczenia V0 wykonano przypiętym modelem `mistral-medium-2604`. Planowany
`mistral-large-2512` zwrócił dla użytego konta błąd poziomu subskrypcji; nie zastosowano
nieoznaczonego aliasu ani cichej podmiany. Model pozostaje konfigurowalny dla kolejnych cykli.

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

## Model danych i jakości

`vault/activities/<id>.md` przechowuje tekst w języku źródłowym. Tłumaczenie jest nakładką
w `vault/translations/<locale>/<id>.md`, nigdy zamiennikiem oryginału. Zmiana tytułu lub treści
zmienia `sourceHash` i unieważnia tłumaczenie.

Pola wieku, czasu, sprzętu, liczby uczestników i ryzyka mogą pojawić się dopiero, gdy wynikają
wprost ze źródła albo przeszły osobną redakcję. Brakujące dane pozostają nieznane. Projekt
oddziela trzy rodzaje ocen:

1. **Pochodzenie** — czy znamy konkretną edycję, autora, rok i strony.
2. **Wierność** — czy ekstrakcja, OCR i tłumaczenie są kompletne oraz zweryfikowane.
3. **Przydatność i bezpieczeństwo** — czy współczesny redaktor uznał aktywność za wartościową
   i możliwą do bezpiecznego dostosowania.

Obecność w korpusie historycznym nie oznacza rekomendacji metodycznej. Status
`historical-unreviewed` pozostaje widoczny do czasu odrębnej oceny człowieka.

## Zasady prawne i źródłowe

Śmierć autora ponad 70 lat temu jest tylko sygnałem do dalszej analizy, nie automatycznym
zatwierdzeniem. Dla każdej edycji sprawdzamy autora, współautorów, redaktora, tłumacza,
ilustratorów, kraj pochodzenia, datę publikacji i status reprodukcji.

- pełny tekst publikujemy wyłącznie przy udokumentowanym `rightsStatus: public-domain`,
- status prawny zawsze przypisujemy wskazanej instytucji lub konkretnemu dowodowi,
- `unknown`, `rights-review` i `link-only` pozostają poza publicznym pełnym korpusem,
- samo znalezienie pliku w sieci ani sama domena nie oznaczają zgody na ponowne użycie,
- link do źródła może być zapisany w kolejce; cytaty i opracowania wymagają osobnej oceny,
- agent proponuje decyzję, ale nie może sam zatwierdzić praw ani publikacji.

Rejestr w `config/source-registry.yaml` określa kolekcje, dozwolone metody dostępu, limity,
robots.txt, regulamin i wymagane dowody. Zewnętrzna treść jest niezaufanymi danymi, nigdy
instrukcją dla agenta.

## V2 — kontrolowane autoresearch

Pierwsza kolejka badawcza obejmuje dzieła Roberta Baden-Powella i Ernesta Thompsona Setona.
Preferowane kolekcje to Project Gutenberg, Internet Archive, Wikisource, Polona i biblioteki
narodowe. Pierwszy przebieg nie importuje automatycznie żadnej zagranicznej książki.

Pipeline:

```text
discover → rights review → fetch → OCR/extract → normalize → deduplicate
         → translate → verify → pull request → publish
```

### Bramki

1. **Discover:** zapisuje kandydaturę, URL, autora, tytuł, edycję i sposób znalezienia.
2. **Rights review:** człowiek zatwierdza konkretną edycję i zakres możliwego użycia.
3. **Fetch:** pobiera wyłącznie z zaakceptowanej kolekcji, respektując limit i warunki.
4. **OCR/extract:** zachowuje surowy wynik i parametry procesu, jeśli potrzebny jest OCR.
5. **Normalize:** poprawia jedynie techniczne artefakty; nie modernizuje treści.
6. **Deduplicate:** porównuje hash, tytuł, źródło i podobieństwo tekstu.
7. **Translate:** zapisuje model, prompt, datę i hash wejścia; oznacza `machine-beta`.
8. **Verify:** sprawdza schemat, kompletność, prawa, źródła, języki i bezpieczeństwo.
9. **Pull request:** agent przedstawia różnice, koszty, ryzyka i nierozstrzygnięte punkty.
10. **Publish:** następuje dopiero po zatwierdzeniu PR przez człowieka.

## Praca na serwerze

`scripts/run_cycle.py` wykonuje pojedynczy, resumowalny i domyślnie propozycyjny cykl. Timer
systemd uruchamia go z limitem 20 dokumentów i 5 USD dziennie. Limity mogą być tylko
zaostrzane przez środowisko automatyzacji bez zmiany konfiguracji. Checkpoint identyfikuje cykl
i pozwala wznowić pracę bez ponownego pobierania lub tłumaczenia.

Agent serwerowy:

- używa osobnego, ograniczonego tokenu tylko do tego repozytorium,
- nigdy nie zapisuje bezpośrednio do `main`,
- tworzy gałąź `autoresearch/<data>-<cykl>` i pull request,
- nie zatwierdza własnych decyzji prawnych,
- zatrzymuje cykl po przekroczeniu limitu dokumentów lub szacowanego kosztu,
- nie umieszcza sekretów, surowych nagłówków HTTP ani danych konta w logach.

Przykładowa usługa i timer znajdują się w `deploy/systemd/`. Na początku V2 cykl jedynie
materializuje kolejkę kandydatów i raport; adaptery pobierania są dodawane kolekcja po kolekcji
po zatwierdzeniu zasad dostępu.

## Kolejka dalszych prac V2

- zweryfikować po jednej konkretnej edycji Baden-Powella i Setona,
- zaimplementować adapter metadanych dla pierwszej zaakceptowanej kolekcji,
- ustalić taksonomię cech dwujęzycznych i słownik synonimów,
- dodać deduplikację bliskich wariantów tej samej aktywności,
- dodać redakcyjną ocenę wartości i bezpieczeństwa niezależną od oceny źródła,
- opisać politykę krótkich cytatów i rekordów `link-only` dla źródeł chronionych,
- przeprowadzić pilotaż na małej książce i zmierzyć koszt, jakość oraz czas recenzji,
- dopiero po pilotażu zwiększać dzienny limit dokumentów.
