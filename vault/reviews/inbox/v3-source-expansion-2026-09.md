---
id: v3-source-expansion-2026-09
recordType: research-run-review
status: active
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
candidateCount: 760
importedActivityCount: 0
ocrReferenceCostUsd: 2.48
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
3. Zatwierdzono udokumentowane pobranie polskich obiektów do scratch oraz wstępny zakres
   domeny publicznej nazwanych autorów, opisany w osobnym pakiecie nabycia.
4. Właściciel zatwierdził jawny status domeny publicznej podany przez bibliotekę dla
   konkretnego obiektu jako rozstrzygający. Przegląd autorstwa pozostaje elementem
   proweniencji, ale nie blokuje importu.

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

## Stan wykonania 7 września 2026

- Osiem dostępnych polskich książek zostało pobranych do scratch i zinwentaryzowanych.
- Mistral OCR przetworzył 506 polskich widoków za koszt referencyjny 2,024 USD. Razem ze 113
  widokami *Chamarande* OCR objął 619 widoków za 2,480 USD. Nie wystąpił `429`.
- W ośmiu książkach znaleziono 760 lokalizatorów kandydatów na gry. Pełna treść nie trafiła
  do repozytorium; raporty zawierają tylko metadane, lokalizatory i hashe.
- *Chamarande* zakończyło się prawidłowym wynikiem zero-yield: zatwierdzona proza opisuje
  program i wspomina gry, lecz nie zawiera samodzielnych reguł gry.
- Dwa źródła PBC Rzeszów są pominięte w tym runie decyzją właściciela. Zakaz automatycznego
  ZIP-u jest respektowany; bezpośrednie adresy zwróciły tylko indeksy pośredniego DjVu, a nie
  kompletne książki. Zgoda na te adresy pozostaje zapisana do ewentualnego osobnego runu.
- Właściciel zatwierdził oznaczenie konkretnego obiektu przez bibliotekę cyfrową jako
  rozstrzygający dowód domeny publicznej. Decyzja i skutek dla ośmiu zinwentaryzowanych
  książek są zapisane w `vault/reviews/accepted/v3-component-authorship-2026-09.md`.
- Ukierunkowane testy V3 przeszły `25/25`, pełny zestaw przeszedł `220/220` na CPU node w
  jobie Slurm `22097463`, a `python scripts/validate.py` zakończył się powodzeniem.

Wszystkie bramki są rozstrzygnięte. Agent może przejść do przeglądu granic i importu gier z
ośmiu pozyskanych polskich książek, tłumaczeń, relacji podobieństwa, skal liczby uczestników
oraz przebudowy embeddingów i mapy semantycznej. PR nadal powstanie tylko jeden, po
osiągnięciu stanu terminalnego przez wszystkie jednostki manifestu.
