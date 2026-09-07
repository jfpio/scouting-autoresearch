---
id: exploration-scout-courses-and-stations
proposalType: activity-kind
status: proposed
createdAt: 2026-09-07
labels:
  pl: Biegi harcerskie i punkty biegu
  en: Scout courses and course stations
appliesTo:
  - corpus
relatedSourceIds:
  - jasinski-field-games-1938
evidenceActivityIds: []
reviewRequired: true
sourceType: editorial-hypothesis
---

# Biegi harcerskie i punkty biegu

Jasiński podaje serię jawnie nazwanych propozycji „Bieg 1”–„Bieg 15”. Przykładowy bieg
zestawia w jednej sekwencji przyszycie guzika, wejście na drzewo, zapis alfabetem Morse’a,
obserwację mrowiska oraz rozpalenie i zatarcie śladów ogniska. Taki zapis nie jest jedną grą:
opisuje kompozycję wielu zadań, które można rozstawić jako kolejne punkty biegu.

## Proponowane rodzaje

- `scout-course` — **bieg harcerski / scout course**: źródło przedstawia rekord jako
  zaplanowany ciąg co najmniej dwóch zadań, prób lub stanowisk, wykonywanych w trasie albo
  w ustalonej kolejności. Wynik może być mierzony, ale rywalizacja nie jest konieczna.
- `scout-course-station` — **punkt biegu / scout-course station**: źródło przedstawia
  samodzielnie opisane zadanie jako konkretny punkt, stację lub element biegu.

Nie należy nadawać `scout-course-station` tylko dlatego, że redaktor uznał, iż zadanie
nadawałoby się na punkt biegu. Potrzebny jest zapis źródłowy albo późniejsza jawna decyzja
redakcyjna o takim sposobie użycia.

## Granica względem gry i próby

- `game` opisuje reguły pojedynczej gry; bieg może zawierać gry, ale nie staje się przez to
  jedną grą.
- `trial` opisuje podejmowane wyzwanie, kryterium lub próbę sprawności. `scout-course-station`
  opisuje natomiast rolę zadania w strukturze biegu.
- Rodzaje nie muszą być rozłączne. To samo zadanie może otrzymać `trial` i
  `scout-course-station`, jeżeli oba znaczenia są udokumentowane. Sam fakt sprawdzania
  umiejętności na punkcie nie wystarcza jednak do automatycznego uznania go za próbę.
- Lista wielu zadań bez trasy, kolejności ani określenia jej jako biegu jest kontrprzykładem
  dla `scout-course`.
- Samodzielna gra terenowa z metą lub biegiem uczestników jest kontrprzykładem, jeżeli nie
  organizuje wielu odrębnych punktów lub zadań.

## Materiał dowodowy do przeglądu

Raport `data/reports/jasinski-field-games-1938-candidates.json` zawiera kandydatury 171–185,
odpowiadające źródłowym nagłówkom „Bieg 1”–„Bieg 15”. W V3-R1 pozostają one poza importem
produkcyjnym, ponieważ bieżący manifest dopuszcza wyłącznie `game`. Mogą dostarczyć co
najmniej pięciu przykładów `scout-course`; osobne punkty wymagają jeszcze deterministycznego
wydzielenia z wnętrza biegów i sprawdzenia ich granic w skanie.

## Pytania do decyzji

1. Czy `scout-course` i `scout-course-station` mają zostać dwoma rodzajami, czy bieg ma być
   rekordem z relacją `has-part` do zwykłych aktywności?
2. Czy punkt może istnieć samodzielnie bez rodzica-biegu?
3. Czy relacja z próbą ma być wieloetykietowa, czy `trial` powinno opisywać wyłącznie
   osobiste wyzwania niezależne od formatu biegu?
4. Czy po akceptacji nowego rodzaju mapa semantyczna ma objąć także biegi i punkty, czy
   zachować osobne warstwy?

## Warunek akceptacji

Przed zmianą schematu trzeba wskazać lub utworzyć identyfikatory co najmniej pięciu przykładów
i dwóch kontrprzykładów, sprawdzić dwujęzyczne etykiety, ustalić model relacji całość–część
oraz uzyskać decyzję człowieka. Do tego czasu oba rodzaje pozostają hipotezą redakcyjną.
