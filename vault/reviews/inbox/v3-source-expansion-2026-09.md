---
id: v3-source-expansion-2026-09
recordType: research-run-review
status: ready-for-final-review
createdAt: "2026-09-06"
reviewRequired: false
manifest: config/v3-source-expansion.yaml
milestone: V3-R1
sourceUnitCount: 11
pullRequestPolicy: one-at-end-of-run
reportPath: data/reports/v3-source-expansion-2026-09.json
approvedHumanDecisions:
  - id: historyczna-directory-access
    reviewRecord: vault/reviews/accepted/collection-historyczna-slaska.md
  - id: chamarande-ocr-page-scope
    reviewRecord: vault/reviews/accepted/chamarande-1934-prose-scope.md
  - id: polish-source-acquisition-and-rights
    reviewRecord: vault/reviews/accepted/v3-polish-sources-acquisition.md
approvedAt: "2026-09-06"
approvedBy: repository-owner
candidateCount: 867
importedActivityCount: 715
ocrReferenceCostUsd: 2.616
---

# V3-R1 — rozszerzenie korpusu przed mapą semantyczną

Run obejmuje dziesięć wytypowanych polskich książek oraz *Chamarande*. Lista, kolejność,
adresy konkretnych wydań, bramki i kontrakt raportu znajdują się w manifeście. Każda książka
jest osobną jednostką wznawiania, ale praca kończy się jednym raportem zbiorczym i jednym
pull requestem. Pośrednie PR-y per książka są wyłączone.

## Co jest już ustalone

- Produkcyjny import obejmuje w tym runie tylko samodzielne gry. Inne typy materiału są
  raportowane jako kandydatury eksploracyjne.
- Dokładne duplikaty nie są importowane. Bliskie warianty pozostają osobnymi rekordami i
  trafiają do przeglądu relacji podobieństwa.
- Dla polskich źródeł kierunek tłumaczenia to polski → angielski. *Chamarande* zachowuje
  francuski oryginał i wymaga polskiej oraz angielskiej warstwy maszynowej.
- Po imporcie trzeba przebudować audyty V3, embeddingi, mapę i pakiet recenzencki na pełnym,
  powiększonym zbiorze gier.
- Raport musi wykazać również źródła bez uzysku, pominięte rekordy oraz przyczyny blokad.

## Zatwierdzone bramki wykonania

1. Zatwierdzono użycie katalogu Komisji Historycznej Chorągwi Śląskiej wyłącznie do metadanych
   strony i odkrywania linków. Nie jest to zgoda na kopiowanie treści ani zbiorcza decyzja o
   prawach książek.
2. Zatwierdzono proponowany 113-widokowy zakres OCR *Chamarande*, wraz z
   wyłączeniem cudzych i anonimowych bloków, muzyki, ilustracji, fotografii i aparatu
   redakcyjnego.
3. Zatwierdzono udokumentowane pobranie polskich obiektów oraz wstępny zakres
   domeny publicznej nazwanych autorów, opisany w osobnym pakiecie nabycia.
4. Właściciel zatwierdził jawny status domeny publicznej podany przez bibliotekę dla
   konkretnego obiektu jako rozstrzygający. Przegląd autorstwa pozostaje elementem
   proweniencji, ale nie blokuje importu.
5. Właściciel zatwierdził trwałe przechowywanie książek, warstw tekstowych i surowego OCR-u
   w ignorowanym przez Git `artifacts/` przy repozytorium na Group Storage.

## Gotowe formuły decyzji

> Zatwierdzam użycie strony Komisji Historycznej Chorągwi Śląskiej wyłącznie do odczytu
> podstawowych metadanych bibliograficznych i odkrywania jawnych linków. Nie zatwierdzam
> kopiowania treści, automatycznego pobierania plików ani zbiorczej presumpcji prawnej.

> Zatwierdzam proponowany zakres 113 widoków OCR *Chamarande* opisany w
> `vault/reviews/accepted/chamarande-1934-prose-scope.md`, z obowiązkiem wyłączenia wskazanych
> cudzych i anonimowych bloków oraz wszystkich osobnych składników niewchodzących w
> zatwierdzony zakres prozy Jacques’a Sevina.

> Zatwierdzam formułę decyzji z `vault/reviews/accepted/v3-polish-sources-acquisition.md`,
> obejmującą tymczasowe pobranie dziesięciu obiektów, własną prozę wymienionych autorów oraz
> wyłączenie nieustalonych i osobno chronionych składników. Zatwierdzam również zakres
> dostępu z `vault/reviews/accepted/v3-regional-library-access.md`, w tym pobrania per-item z
> Polony i dozwolonych bezpośrednich PDF-ów oraz zakaz automatycznego pobierania trzech
> ZIP-ów PBC Rzeszów blokowanych przez `robots.txt`.

Samo zatwierdzenie tych trzech bramek nie zatwierdza wynikowych aktywności ani końcowej
publikacji. Te decyzje pozostają widoczne w jednym raporcie i końcowym PR-ze V3-R1.

## Stan końcowy 8 września 2026

- Osiem dostępnych polskich książek zostało pobranych, przeniesionych do trwałego
  `artifacts/` i zinwentaryzowanych.
- Mistral OCR przetworzył 540 polskich widoków za koszt referencyjny 2,160 USD. Razem ze 113
  widokami *Chamarande* OCR objął 653 widoki za 2,616 USD. Nie wystąpił `429`.
- W ośmiu książkach znaleziono 867 lokalizatorów kandydatów na gry. Pełna treść nie trafiła
  do repozytorium; raporty zawierają tylko metadane, lokalizatory i hashe.
- *Chamarande* zakończyło się prawidłowym wynikiem zero-yield: zatwierdzona proza opisuje
  program i wspomina gry, lecz nie zawiera samodzielnych reguł gry.
- Dwa źródła PBC Rzeszów są pominięte w tym runie decyzją właściciela. Zakaz automatycznego
  ZIP-u jest respektowany; bezpośrednie adresy zwróciły tylko indeksy pośredniego DjVu, a nie
  kompletne książki. Zgoda na te adresy pozostaje zapisana do ewentualnego osobnego runu.
- Właściciel zatwierdził oznaczenie konkretnego obiektu przez bibliotekę cyfrową jako
  rozstrzygający dowód domeny publicznej. Decyzja i skutek dla ośmiu zinwentaryzowanych
  książek są zapisane w `vault/reviews/accepted/v3-component-authorship-2026-09.md`.
- Zaimportowano 715 nowych gier i ich angielskie tłumaczenia, co zwiększyło korpus do 999
  aktywności, w tym 914 gier i 85 prób, z 12 źródeł domeny publicznej.
- Mapa V3 obejmuje dokładnie 914 gier. Powstał dwujęzyczny pakiet 50 kandydatur podobieństwa;
  żadna nie została automatycznie opublikowana jako relacja produkcyjna.
- Audyty uczestników i 12 praktycznych faset obejmują pełne 914 gier i pozostają propozycjami
  wymagającymi decyzji człowieka przed zmianą schematu lub filtrów.
- Pełny zestaw przeszedł `275/275` na CPU node w jobie Slurm `22127543`. Końcowy build w
  jobie `22127572` utworzył 2014 stron, sprawdził 60 887 linków i assetów oraz zakończył
  powodzeniem `scripts/validate.py`.

Wszystkie jednostki i bramki runu mają wynik terminalny. Do decyzji człowieka pozostają
pakiet kandydatur podobnych gier oraz wybór skal uczestników i faset, które warto poddać
ręcznej anotacji. Nie blokuje to publikacji V3-R1: końcowy PR jest jedynym PR-em runu.
