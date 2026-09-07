---
id: v3-polish-sources-acquisition
recordType: source-acquisition-batch
status: accepted
createdAt: "2026-09-06"
reviewRequired: false
publicationBlocked: false
humanApproved: true
runId: v3-source-expansion-2026-09
manifest: config/v3-source-expansion.yaml
sourceUnitCount: 10
proposedUse:
  - documented-download-to-temporary-scratch
  - inspect-title-pages-credits-and-table-of-contents
  - ocr-or-text-extraction-of-potential-game-pages
  - publish-game-prose-from-library-objects-explicitly-marked-public-domain
outsideProductScope:
  - illustrations-photographs-covers-music-and-lyrics
  - digital-library-site-database-and-packaging
supersededRightsScopeBy: vault/reviews/accepted/v3-component-authorship-2026-09.md
humanDecision:
  status: approved
  approvedBy: repository-owner
  reviewedAt: "2026-09-06"
  notes: >-
    Zatwierdzono tymczasowe pobranie do scratch obiektów Polony i dozwolonych
    bezpośrednich PDF-ów, własną prozę wskazanych autorów w domenie publicznej oraz
    wyłączenie nieustalonych i osobno chronionych składników. Dla dwóch rekordów PBC
    Rzeszów zatwierdzono wyłącznie dalsze szukanie dozwolonych alternatyw; automatyczne
    ZIP-y blokowane przez robots.txt pozostają zabronione.
---

# V3-R1 — polskie źródła: nabycie i bramka prawna

> Aktualizacja 7 września 2026 r.: poniższa pierwotna, ostrożniejsza kwalifikacja została
> zastąpiona decyzją w `vault/reviews/accepted/v3-component-authorship-2026-09.md`. Jawne
> oznaczenie konkretnego obiektu przez bibliotekę jako domeny publicznej jest dla projektu
> rozstrzygające. Informacje o współpracownikach i zapożyczeniach zachowujemy jako
> proweniencję, nie jako bramkę prawną.

Pierwotna analiza w tym pakiecie nie uznawała etykiety jednej biblioteki za samodzielny dowód
i łączyła opis wydania z autorstwem oraz datą śmierci. Ten sposób kwalifikacji pozostaje niżej
jako historia decyzji, ale nie obowiązuje już dla obiektów z jednoznacznym statusem
instytucjonalnym.

Zatwierdzenie poniższej propozycji pozwoli pobrać dziesięć wskazanych obiektów wyłącznie do
tymczasowego katalogu w `$SCRATCH`, ustalić mapę składników i przetwarzać tekst. Nie obejmie
automatycznie ilustracji, fotografii, okładek, nut, tekstów pieśni ani cudzych lub anonimowych
wkładów. Szczegółowa kontrola `robots.txt` i warunków pięciu bibliotek regionalnych znajduje
się w `vault/reviews/accepted/v3-regional-library-access.md`; trzy ZIP-y PBC Rzeszów są wyłączone
z automatycznego pobierania. Pełny tekst trafi do korpusu dopiero z dowodem na poziomie
rekordu i strony.

## Ocena pozycji

1. **Jan Jasiński, *Gry i ćwiczenia terenowe*, wyd. 2, 1938.** Rekord Polony wskazany w
   manifeście dotyczy tego wydania. Bibliografia BN identyfikuje autora jako `1901–1939`, więc
   jego własna proza spełnia w 2026 r. regułę życia plus 70 lat. Opis egzemplarza tego samego
   wydania przypisuje projekt okładki W. Świerczyńskiemu — okładka i ilustracje pozostają poza
   zakresem do czasu inspekcji. Status: **proza Jasińskiego kwalifikuje się warunkowo; wymagane
   sprawdzenie kart tytułowych i podpisów ilustracji**.

2. **Herman Mojmir, *Ćwiczenia i zabawy skautowe*, 1912.** Rekord Polony wskazuje pierwsze
   wytypowane wydanie. *Harcerski słownik biograficzny* Muzeum Harcerstwa identyfikuje autora
   jako Hermana Aleksandra Mojmira, wcześniej Hermanna Biesika (`1874–1919`), i wprost wymienia
   książkę z 1912 r. Status: **proza Mojmira kwalifikuje się warunkowo; osobne wkłady wymagają
   inspekcji**.

3. **Juliusz Dąbrowski, *Gry i zabawy w izbie harcerskiej*, wyd. 2, 1934.** Oficjalny rekord
   Podkarpackiej Biblioteki Cyfrowej podaje autora `1909–1940`, rok, drugie wydanie, format DjVu
   oraz oznaczenie `Domena publiczna (public domain)`. Ponieważ `robots.txt` blokuje zbiorczy
   ZIP PBC, manifest został przełączony na dokładne wydanie drugie z 1934 r. w Polonie pod
   UUID `f8a00528-6a07-4916-9a76-c1e094e317da`; oficjalne metadane Polony potwierdzają tytuł,
   wydanie i imprint oraz oznaczają obiekt jako niechroniony. Status: **proza Dąbrowskiego
   kwalifikuje się warunkowo; grafika i cudze cytaty pozostają wyłączone**.

4. **Eugeniusz Piasecki, *Zabawy i gry ruchowe dzieci i młodzieży*, wyd. 3, 1922.** Pierwotny
   manifest błędnie przypisywał tę pozycję również Mieczysławowi Schreiberowi i datował na
   1920 r. Oficjalny rekord KPBC dla wydania `183639/193867` podaje wyłącznie Piaseckiego
   (`1872–1947`), rok 1922, wydanie trzecie poprawione i rozszerzone, 226 stron oraz oznaczenie
   domeny publicznej. Akademia Wychowania Fizycznego w Poznaniu niezależnie informuje, że
   twórczość Piaseckiego przeszła do domeny publicznej. Rekord wymienia nuty i rysunki, więc te
   składniki są wyłączone. Status: **proza Piaseckiego kwalifikuje się warunkowo**.

5. **Juliusz Dąbrowski, *Harce zimowe w polu*, 1935.** Oficjalny rekord PBC podaje autora
   `1909–1940`, oznaczenie domeny publicznej i format DjVu. Informuje też, że w egzemplarzu
   brakuje stron 82–83; brak musi znaleźć się w proweniencji i raporcie uzysku. Status:
   **proza Dąbrowskiego kwalifikuje się warunkowo; nie wolno rekonstruować brakujących stron**.

6. **Alojzy Pawełek, *Młoda drużyna*, wyd. 2, 1919.** Aktualny rekord Podlaskiej Biblioteki
   Cyfrowej to publikacja `29783`, wydanie `28922` — dawny adres z samym numerem publikacji
   prowadzi dziś do innego obiektu i został poprawiony w manifeście. Rekord podaje autora
   `1893–1930`, drugie wydanie, PDF i domenę publiczną. *Harcerski słownik biograficzny*
   potwierdza śmierć autora w 1930 r. Status: **proza Pawełka kwalifikuje się warunkowo;
   przedmowy, podziękowania i cudze wkłady trzeba rozdzielić**.

7. **Praca zbiorowa pod redakcją Jadwigi Zwolakowskiej, *W gromadzie zuchów*, wyd. 3,
   1945.** BN identyfikuje wydanie nowojorskie Girl Scouts of America jako pracę zbiorową pod
   redakcją Zwolakowskiej. Sama redaktorka (`1895–1944`) spełnia regułę życia plus 70 lat, ale
   jej data śmierci nie rozstrzyga praw autorów poszczególnych rozdziałów, gier, opowiadań,
   pieśni i ilustracji. Status: **zgoda może objąć pobranie do sporządzenia mapy autorstwa, lecz
   żaden anonimowy ani nieustalony wkład nie może zostać opublikowany**.

8. **Stanisław Sedlaczek, *Metodyka harców w przykładach*, 1935.** Oficjalny rekord PBC
   `11539/10606` podaje autora `1892–1941`, domenę publiczną, format DjVu i obecność ilustracji
   oraz spisu ćwiczeń i gier. Internetowy Polski Słownik Biograficzny podaje dokładne daty
   `1892-01-31 — 1941-08-03` i wymienia tę publikację. Status: **proza Sedlaczka kwalifikuje
   się warunkowo; ilustracje pozostają wyłączone**.

9. **Mieczysław Schreiber i Eugeniusz Piasecki, *Harce młodzieży polskiej*, wyd. 2, 1917.**
   Manifest został przełączony z zabezpieczonego egzemplarza PBC na otwarty egzemplarz WBC
   `515207/440525`. Oficjalny rekord WBC podaje obu twórców, wydanie drugie, 287 stron,
   `domena publiczna` i dostęp bez ograniczeń. Piasecki zmarł w 1947 r.; źródła biograficzne
   identyfikują Schreibera jako `1879–1920`. Książka opiera się na *Scouting for Boys*, którego
   autor Robert Baden-Powell zmarł w 1941 r. Status: **proza obu opracowujących kwalifikuje się
   warunkowo; cytaty, rysunki i inne wkłady wymagają rozdzielenia**.

10. **Stanisław Sedlaczek, *Szkoła harcerza*, wyd. 3, 1921.** Oficjalny rekord Śląskiej
    Biblioteki Cyfrowej podaje Sedlaczka (`1892–1941`), trzecie wydanie, oznaczenie domeny
    publicznej i uszkodzone strony 211–212. Tytuł wskazuje opracowanie na podstawie
    Baden-Powella i polskiej literatury harcerskiej, dlatego nie wolno automatycznie przypisać
    Sedlaczkowi każdego cytatu lub zapożyczenia. Status: **własna proza Sedlaczka kwalifikuje
    się warunkowo; cudze bloki i uszkodzenia wymagają jawnego oznaczenia**.

## Dowody

- Jan Jasiński i bibliografia BN: https://bn.org.pl/download/document/1301389326.pdf
- Opis dokładnego wydania Jasińskiego z 1938 r. i kredyt okładki:
  https://www.lamus.pl/pliki/VII%20internetowa%20aukcja%20ksiazek%20i%20grafiki/katalog-2016-2.pdf
- Herman Mojmir, *Harcerski słownik biograficzny*, t. 4, s. 140–142:
  https://muzeumharcerstwa.pl/wp-content/uploads/2025/04/HSB_tom4.pdf
- Rekordy Dąbrowskiego i Sedlaczka w PBC:
  https://www.pbc.rzeszow.pl/dlibra/publication/11501/edition/10568,
  https://www.pbc.rzeszow.pl/dlibra/publication/11554/edition/10620,
  https://www.pbc.rzeszow.pl/dlibra/publication/11539/edition/10606
- Aktualne rekordy metadanych Polony używane w V3-R1:
  https://polona.pl/api/library-object-query/digital-objects/b1600bcb-668f-4daf-a37b-81fade26971f,
  https://polona.pl/api/library-object-query/digital-objects/71788615-5b35-4973-88c0-f6e1550be578,
  https://polona.pl/api/library-object-query/digital-objects/f8a00528-6a07-4916-9a76-c1e094e317da,
  https://polona.pl/api/library-object-query/digital-objects/3f71abd7-af13-4f31-9b48-cab79f380362
- Piasecki 1922 w KPBC: https://kpbc.umk.pl/dlibra/publication/183639/edition/193867
- Informacja AWF o domenie publicznej twórczości Piaseckiego:
  https://old.awf.poznan.pl/pl/biblioteka/4330-profesor-eugeniusz-piasecki-1872-1947-wybrane-publikacje-w-zbiorach-biblioteki-glownej-awf-w-poznaniu
- Pawełek w PBC: https://pbc.biaman.pl/dlibra/publication/29783/edition/28922
- Pawełek, *Harcerski słownik biograficzny*, t. 1:
  https://muzeumharcerstwa.pl/wp-content/uploads/2025/04/HSB1.pdf
- Zwolakowska, *Harcerski słownik biograficzny*, t. 1, s. 259–260:
  https://muzeumharcerstwa.pl/wp-content/uploads/2025/04/HSB1.pdf
- Rekord BN wydania *W gromadzie zuchów*:
  https://www.bn.org.pl/download/document/1540383143.pdf
- Sedlaczek w IPSB:
  https://www.ipsb.nina.gov.pl/a/biografia/stanislaw-marian-sedlaczek-1892-1941-dzialacz-harcerski-pedagog-psycholog
- *Harce młodzieży polskiej* w WBC:
  https://www.wbc.poznan.pl/publication/515207/edition/440525/
- Mieczysław Schreiber (`1879–1920`) w katalogu BN:
  https://www.bn.org.pl/download/document/1540383143.pdf
- Dokładne daty życia Mieczysława Schreibera (`1879-08-16 — 1920-09-06`) w materiale IPN:
  https://przystanekhistoria.pl/pa2/tematy/wojna-polsko-bolszewick/87655%2CFirlejowka-wrzesniowy-boj-1920-roku.html
- *Szkoła harcerza* w ŚBC:
  https://www.sbc.org.pl/dlibra/publication/68754/edition/64835
- Wszystkie trzy rekordy Polony pozostają przypięte bezpośrednio w manifeście.

## Gotowa formuła decyzji

> Zatwierdzam udokumentowane pobranie do tymczasowego `$SCRATCH` dziesięciu polskich
> obiektów z manifestu V3-R1 w celu ustalenia autorstwa składników, OCR-u lub ekstrakcji i
> wyszukania gier. Zatwierdzam domenę publiczną własnej prozy Jana Jasińskiego, Hermana
> Mojmira, Juliusza Dąbrowskiego, Eugeniusza Piaseckiego, Alojzego Pawełka, Mieczysława
> Schreibera, Stanisława Sedlaczka i Roberta Baden-Powella na podstawie zapisanych dowodów i
> upływu 70 pełnych lat od śmierci. Nie zatwierdzam automatycznie ilustracji, fotografii,
> okładek, muzyki, tekstów pieśni, anonimowych wkładów ani wkładów innych osób. Dla *W
> gromadzie zuchów* zatwierdzam wyłącznie pobranie i sporządzenie mapy autorstwa; publikacja
> poszczególnych składników wymaga ustalenia ich autora i osobnej podstawy prawnej.
> Zatwierdzam zakres dostępu opisany w `v3-regional-library-access.md`: pobrania per-item z
> Polony i dozwolonych bezpośrednich PDF-ów, z zachowaniem kanonicznych rekordów i
> atrybucji, oraz dalsze poszukiwanie alternatyw dla PBC Rzeszów. Nie zatwierdzam
> automatycznego pobierania trzech ZIP-ów blokowanych przez `robots.txt`.
