---
id: v3-component-authorship-2026-09
recordType: component-authorship-batch
status: awaiting-human-decision
createdAt: "2026-09-07"
reviewRequired: true
runId: v3-source-expansion-2026-09
candidateCount: 760
importedActivityCount: 0
---

# V3-R1 — autorstwo składników znalezionych gier

OCR i ekstrakcja dały 760 lokalizatorów kandydatów w ośmiu książkach. Raporty kandydatów
zawierają wyłącznie tytuły, numery stron lub widoków oraz hashe; pełna treść OCR pozostaje w
scratch. Kandydat nie jest jeszcze decyzją o publikacji ani nawet potwierdzoną samodzielną grą.

Zatwierdzona wcześniej domena publiczna własnej prozy nazwanych autorów nie wystarcza do
przypisania im każdego opisu w kompilacji. Inspekcja przedmów wykazała zarówno stosunkowo
proste przypadki, jak i książki z nieprzypisanymi wkładami wielu osób.

## Wynik per źródło

| Źródło | Kandydaci | Ustalenie | Rekomendacja |
| --- | ---: | --- | --- |
| Jan Jasiński, *Gry i ćwiczenia terenowe* (1938) | 181 | Autor pisze, że książka opiera się na jego wieloletnim doświadczeniu; w sprawdzonym wstępie nie znaleziono zbiorczego kredytu dla cudzych opisów. | Dopuścić kontrolę i import własnej prozy Jasińskiego; wykluczać każdy osobno podpisany lub cytowany blok. |
| Herman Mojmir, *Ćwiczenia i zabawy skautowe* (1912) | 85 | Książka wskazuje Baden-Powella, Setona, Cenara i inne wcześniejsze zbiory. Nie ma jeszcze mapy źródła dla wszystkich opisów. | Na razie mapować autorstwo per kandydat; nie zatwierdzać całych 85 opisów jednym przypisaniem. |
| Juliusz Dąbrowski, *Gry i zabawy w izbie harcerskiej* (1934) | 183 | Autor wprost podaje, że gry pochodzą od wielu harcerzy i drużyn warszawskich, dziękuje W. Dehnelowi za uzupełnienia oraz wymienia m.in. zbiór redagowany przez Ewę Grodecką. Grodecka zmarła w 1973 r., więc jej proza nie jest jeszcze domeną publiczną w Polsce i UE. | Zachować metadata-only, dopóki porównanie per gra nie odseparuje prozy Dąbrowskiego i innych potwierdzonych autorów od chronionych lub anonimowych wkładów. |
| Eugeniusz Piasecki, *Zabawy i gry ruchowe dzieci i młodzieży* (1922) | 133 | Pozycja 103 jest przypisana Kazimierzowi Lutosławskiemu (1880–1924); pierwsze 30 pozycji miesza reguły z pieśniami lub wierszami; przedmowa mówi też o dosłownym powtarzaniu części opisów. | Dopuścić prozę Piaseckiego i opis nr 103 jako prozę Lutosławskiego, lecz dopiero po wycięciu muzyki, tekstów pieśni, wierszy i nieustalonych cytatów per rekord. |
| Alojzy Pawełek, *Młoda drużyna* (1919) | 24 | Przedmowa mówi, że współpracownicy mogą rozpoznać własne myśli, i wymienia trzy wcześniejsze książki użyte przy pisaniu. | Najpierw mapować komponenty per kandydat; nie przypisywać zbiorczo wszystkich opisów Pawełkowi. Przedmowa Lutosławskiego pozostaje wyłączona. |
| Hanna Kopciówna w *W gromadzie zuchów* (1945) | 74 | Podpis `Hanna Kopciówna` stoi bezpośrednio przed Działem I gier. Źródła biograficzne i cmentarne pozwalają utożsamić ją z Hanną Brzozowską-Kopciówną (1907–1944), więc jej własna proza jest domeną publiczną. Nie jest jednak rozstrzygnięte, czy podpis obejmuje wszystkie 74 opisy w pracy zbiorowej. | Wymaga decyzji człowieka co do zakresu podpisu; bez niej pozostać przy metadata-only. |
| M. Schreiber i E. Piasecki, *Harce młodzieży polskiej* (1917) | 40 | Przedmowa pierwszego wydania mówi, że nazwani współpracownicy dostarczyli przykłady i opisy, bez pełnego przypisania per gra. | Mapować komponenty per kandydat; do tego czasu metadata-only. |
| Stanisław Sedlaczek, *Szkoła harcerza* (1921) | 40 | Przedmowa przypisuje większość gier Hermanowi Mojmirowi, kilka Edmundowi Cenarowi, a część ćwiczeń Tadeuszowi Jaroszyńskiemu. Zmarli odpowiednio w 1919, 1913 i 1933 r.; ich własna proza jest domeną publiczną. | Dopuścić import po zachowaniu atrybucji źródłowej i sprawdzeniu granic bloków; uszkodzonych stron 211–212 nie rekonstruować. |

## Dowody uzupełniające

- Hanna Kopciówna jako hufcowa warszawska w urzędowych materiałach ZHP z 1933 i 1938 r.:
  https://archiwumharcerskie.pl/images/d/dd/1933-11_W-wa_Wiadomo%C5%9Bci_Urz%C4%99dowe_nr_9.pdf,
  https://archiwumharcerskie.pl/images/8/8f/1938-06_Wiadomosci_urzedowe_nr_6.pdf
- Hanna Kopć ps. Brzozowska w ewidencji medyków Powstania Warszawskiego:
  https://lekarzepowstania.pl/osoba/hanna-kopc-ps-brzozowska/
- Grób Hanny Brzozowskiej-Kopciówny, daty `1907-01-01 — 1944-08-04`:
  https://www.ecmentarze.pl/cmentarz/wojskowy-warszawa/grave/detail/4580621
- Edmund Cenar i jego *Gry i zabawy ruchowe różnych narodów*:
  https://jbc.bj.uj.edu.pl/Content/701688/NDIGCZAS041513_1910_003.pdf,
  https://kuriergalicyjski.com/edmund-cenar/
- Tadeusz Jaroszyński (`1880–1933`) i bibliografia jego prac:
  https://jbc.bj.uj.edu.pl/Content/857915/NDIGCZAS050627_1935_006.pdf?handler=pdf,
  https://bn.org.pl/download/document/1301389326.pdf
- Kazimierz Lutosławski (`1880–1924`):
  https://www.muzeum-drozdowo.pl/historia/20-lutosawscy-w-drozdowie

Identyfikacja Kopciówny jest wnioskiem z połączonych źródeł: tej samej formy nazwiska,
warszawskiej działalności harcerskiej, służby wojennej oraz pełnego nazwiska na grobie.
Nie rozstrzyga ona sama zakresu podpisu w konkretnej pracy zbiorowej.

## Rekomendowana decyzja

Najbezpieczniejszy przebieg V3 to teraz dopuścić trzy dobrze określone zakresy, a pozostałe
pięć książek poddać mapowaniu komponentów zamiast publikować je zbiorczo. Taki wybór nie
usuwa żadnego kandydata: kandydaci oczekujący pozostaną w repo jako metadata-only i mogą
wejść do późniejszego uzupełnienia V3.

> Zatwierdzam dla V3-R1 przegląd i publikację pełnej prozy gier Jana Jasińskiego z *Gier i
> ćwiczeń terenowych*, własnej prozy Eugeniusza Piaseckiego oraz przypisanego Kazimierzowi
> Lutosławskiemu opisu nr 103 z *Zabaw i gier ruchowych dzieci i młodzieży*, a także gier ze
> *Szkoły harcerza* przypisanych Hermanowi Mojmirowi, Edmundowi Cenarowi lub Tadeuszowi
> Jaroszyńskiemu. Wymagam zachowania atrybucji per rekord oraz wyłączenia ilustracji, muzyki,
> pieśni, wierszy, cytatów, osobno podpisanych i nieustalonych wkładów. Dla opisów z książek
> Mojmira, Dąbrowskiego, Pawełka, *Harców młodzieży polskiej* oraz *W gromadzie zuchów*
> zatwierdzam dalsze mapowanie autorstwa, ale do czasu jego zakończenia pozostawiam pełny
> tekst poza publikowanym korpusem. Nie zatwierdzam rekonstrukcji uszkodzonych ani brakujących
> stron.

Ta decyzja nie zatwierdza automatycznie wszystkich 354 kandydatów z trzech dopuszczonych
książek. Pozwala agentowi przejrzeć ich granice i składniki, importując tylko te rekordy,
które faktycznie mieszczą się w opisanym zakresie.
