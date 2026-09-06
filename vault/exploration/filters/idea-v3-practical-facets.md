---
id: exploration-v3-practical-facets
proposalType: filter-facets
status: proposed
createdAt: "2026-09-04"
labels:
  pl: Praktyczne filtry gier V3
  en: V3 practical game filters
appliesTo:
  - game
relatedSourceIds:
  - hwp-1946
  - sfb-1908
  - bsh-1911-seton-games
evidenceActivityIds:
  - hwp-019
  - hwp-023
  - hwp-033
  - hwp-041
  - bsh-024
  - bsh-037
  - sfb-002
  - sfb-004
  - sfb-033
  - sfb-047
reviewRequired: true
sourceType: editorial-hypothesis
---

# Praktyczne filtry gier V3

## Pytanie badawcze

Które cechy pozwolą prowadzącemu szybko odsiać gry niemożliwe do przeprowadzenia w danych
warunkach, a jednocześnie dają się rzetelnie odczytać ze źródła lub zatwierdzić redakcyjnie?
Pozycja na mapie semantycznej nie może zastępować tych jawnych ograniczeń.

## Skala uczestników

Robocza lista rozróżnia pojedynczą osobę, parę, małą grupę, jeden zastęp, kilka zastępów,
jedną drużynę, kilka drużyn i dużą zbiorowość. Są to współczesne etykiety wyszukiwawcze,
nie słownictwo przypisywane autorom. Dopuszczalne są wielokrotne wartości, ponieważ ta sama
gra może mieć wariant indywidualny, w parach i zastępami.

Przykłady do kontroli:

- `sfb-033` — wyraźny przypadek pary,
- `hwp-019` — kilka zastępów oraz role wewnątrz zespołów,
- `hwp-033` i `sfb-047` — więcej niż jeden zastęp i organizacja większego wydarzenia,
- `bsh-037` — para uciekających oraz ścigający zastęp lub drużyna,
- `sfb-004` — źródło dopuszcza kilka różnych skal wykonania.

Przypadki graniczne:

- `hwp-023` dopuszcza punktację osoby albo zastępu i nie powinien zostać sprowadzony do
  jednej wartości,
- `bsh-024` ma pojedynczą rolę uciekającego, ale wymaga także grupy ścigających; sama fraza
  o jednym graczu nie określa całkowitej liczby uczestników.

Automatyczny audyt zapisuje wyłącznie obecność jawnych sygnałów językowych. Osobno wskazuje
rekordy zawierające liczbę osób albo względną proporcję, ale nie uznaje liczby opisanej roli
za całkowitą liczebność gry. Nie przypisuje wartości `participantScales`, nie wylicza
`minParticipants` ani `maxParticipants` i nie zmienia filtrów. Brak sygnału nie oznacza, że
gra jest indywidualna; pozostaje kandydatem do `unknown` albo ręcznego przeglądu.

## Pozostałe kandydatury

Do porównania pod względem pokrycia, jednoznaczności, kosztu redakcji i wartości użytkowej:

- układ stron oraz współpraca lub rywalizacja,
- eliminowanie uczestników i sposób rozstrzygnięcia,
- dominująca mechanika i ćwiczona sprawność,
- przestrzeń, wymagana powierzchnia i warunki terenowe,
- ruch oraz intensywność fizyczna,
- czas gry i przygotowania,
- sprzęt,
- pora dnia, widoczność, pogoda i sezon,
- kontakt fizyczny i ryzyko,
- hałas albo wymagana cisza,
- rola prowadzącego lub sędziego,
- dostępność, zalecany wiek i wymagane umiejętności.

`sfb-002`, `sfb-033`, `hwp-041` i para `bsh-037`–`hwp-041` są użytecznymi przykładami do
sprawdzenia, czy wymiary środowiska, kontaktu, pory dnia i mechaniki wnoszą informację inną
niż skala uczestników. Żadna z tych kandydatur nie jest jeszcze produkcyjną kategorią.

## Audyt korpusu

Wersjonowany audyt `v3-practical-facet-lexical-signals-v1` objął wszystkie 199 gier z trzech
źródeł. Nie klasyfikuje gier: mierzy wyłącznie, w ilu tekstach źródłowych występują jawne
sygnały leksykalne, ile rekordów ma sygnały kilku wartości i ile wymagałoby czytania bez
takiej podpowiedzi. Wynik znajduje się w
`data/reports/v3-practical-facet-audit.json`, a stan wznowienia w
`data/checkpoints/v3-practical-facet-audit.json`.

| Wymiar | Gry z sygnałem | Sygnały wielu wartości | Bez sygnału |
| --- | ---: | ---: | ---: |
| sposób interakcji | 127 (63,8%) | 25 | 72 |
| dominująca mechanika | 166 (83,4%) | 103 | 33 |
| przestrzeń i teren | 81 (40,7%) | 20 | 118 |
| wymagana powierzchnia | 52 (26,1%) | 0 | 147 |
| ruch i intensywność | 107 (53,8%) | 17 | 92 |
| czas i przygotowanie | 54 (27,1%) | 7 | 145 |
| sprzęt i materiały | 120 (60,3%) | 27 | 79 |
| światło, pogoda i sezon | 34 (17,1%) | 2 | 165 |
| kontakt fizyczny i ryzyko | 53 (26,6%) | 5 | 146 |
| hałas i cisza | 53 (26,6%) | 3 | 146 |
| rola prowadzącego | 30 (15,1%) | 3 | 169 |
| wiek, dostępność i wymagania | 62 (31,2%) | 2 | 137 |

Mechanika ma wysokie pokrycie, lecz 103 gry sygnalizują więcej niż jedną wartość, więc lepiej
traktować ją jako wielowartościowy tag niż pojedynczy filtr. Sprzęt, ruch, teren i sposób
interakcji mają dość sygnałów, by przeprowadzić próbę ręcznej precyzji. Niskie pokrycie pory,
pogody, roli prowadzącego i wymagań wstępnych oznacza, że ich brak nie może być interpretowany
jako brak ograniczenia. Dla wcześniejszej umiejętności nie znaleziono żadnego wystarczająco
jawnego sygnału; ten kandydat wymaga innej metody albo rezygnacji.

Rozkład sygnałów jest tylko proxy zdolności fasety do różnicowania korpusu. Nie mierzy realnej
wartości dla drużynowego. Raport pozostawia trzy oceny w skali 0–2 — wpływ na wykonalność,
częstość użycia przy decyzji i zrozumiałość etykiet — do uzupełnienia przez człowieka. Nie
podaje fikcyjnego czasu ani kosztu redakcji; zamiast tego raportuje liczbę rekordów do
weryfikacji, zimnego odczytu i rozstrzygnięcia sygnałów wielu wartości.

## Relacja do istniejącego modelu

Proponowane fasety opisują warunki przeprowadzenia gry. Taksonomia V1 opisuje przede wszystkim
temat i rozwijaną sprawność, a embedding oraz mapa V3 pokazują podobieństwo treści. Te warstwy
mogą się uzupełniać, ale nie powinny być automatycznie utożsamiane.

## Decyzja

Do uzupełnienia przez człowieka: zaakceptować, poprawić albo odrzucić definicje skali; ocenić
przygotowane próbki trafień i uzupełnić rubrykę wartości wyszukiwawczej; następnie wybrać
fasety, dla których warto projektować pola produkcyjne.
