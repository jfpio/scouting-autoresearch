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
evidenceActivityIds:
  - gct-171
  - gct-172
  - gct-173
  - gct-174
  - gct-175
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

## Zatwierdzony kierunek redakcyjny

Właściciel projektu 7 września 2026 r. zatwierdził dalsze opracowanie dwóch odrębnych
rodzajów: `scout-course` oraz `scout-course-station`. Zatwierdził również model
wieloetykietowy na granicy z `trial`: punkt biegu będący jednocześnie próbą może zachować
obie etykiety, jeżeli każde z tych znaczeń ma osobną podstawę źródłową albo zostało ręcznie
potwierdzone. Nie należy rozstrzygać kolizji przez automatyczne wybranie tylko jednej z nich.

Właściciel 8 września 2026 r. zatwierdził produkcyjną migrację samego rodzaju
`scout-course` oraz piętnaście całych biegów Jasińskiego (`gct-171`–`gct-185`). Decyzję
zapisano w `vault/reviews/accepted/v3-scout-course-production-2026-09.md`. Nie zatwierdzono
jeszcze produkcyjnego rodzaju `scout-course-station`, dzielenia biegów na punkty ani relacji
całość–część.

## Materiał dowodowy do przeglądu

Raport `data/reports/jasinski-field-games-1938-candidates.json` zawiera kandydatury 171–185,
odpowiadające źródłowym nagłówkom „Bieg 1”–„Bieg 15”. V3-R1 zachował je poza korpusem,
natomiast późniejsza decyzja produkcyjna pozwoliła zaimportować je jako `scout-course`.
Osobne punkty nadal wymagają deterministycznego wydzielenia z wnętrza biegów i sprawdzenia
ich granic w skanie.

## Pytania do decyzji

1. Czy bieg ma być rekordem z relacją `has-part` do przyszłych rekordów punktów, czy relacja
   całość–część ma być reprezentowana inaczej?
2. Czy punkt może istnieć samodzielnie bez rodzica-biegu?
3. Czy w następnym etapie mapa semantyczna ma objąć także biegi i punkty, czy zachować
   osobne warstwy?

## Warunek akceptacji

Rodzaj `scout-course` spełnił warunek przykładów, etykiet i decyzji człowieka. Przed
wprowadzeniem `scout-course-station` trzeba nadal wskazać kontrprzykłady, ustalić model
relacji całość–część i uzyskać osobną decyzję człowieka.
