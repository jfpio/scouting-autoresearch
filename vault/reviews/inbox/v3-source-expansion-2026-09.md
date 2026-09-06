---
id: v3-source-expansion-2026-09
recordType: research-run-review
status: prepared-human-gates-pending
createdAt: "2026-09-06"
reviewRequired: true
manifest: config/v3-source-expansion.yaml
milestone: V3-R1
sourceUnitCount: 11
pullRequestPolicy: one-at-end-of-run
reportPath: data/reports/v3-source-expansion-2026-09.json
pendingHumanDecisions:
  - id: historyczna-directory-access
    reviewRecord: vault/reviews/inbox/collection-historyczna-slaska.md
  - id: chamarande-ocr-page-scope
    reviewRecord: vault/reviews/inbox/chamarande-1934-prose-scope.md
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

## Bramki przed wykonaniem

1. Zatwierdzić użycie katalogu Komisji Historycznej Chorągwi Śląskiej wyłącznie do metadanych
   strony i odkrywania linków. Nie jest to zgoda na kopiowanie treści ani zbiorcza decyzja o
   prawach książek.
2. Zatwierdzić lub skorygować proponowany 113-widokowy zakres OCR *Chamarande*, wraz z
   wyłączeniem cudzych i anonimowych bloków, muzyki, ilustracji, fotografii i aparatu
   redakcyjnego.
3. W toku runu przed publikacją pełnego tekstu przedstawić zbiorczo do kontroli ustalone
   wydania, autorstwo poszczególnych składników i decyzje prawne dla polskich książek.

## Gotowe formuły decyzji

> Zatwierdzam użycie strony Komisji Historycznej Chorągwi Śląskiej wyłącznie do odczytu
> podstawowych metadanych bibliograficznych i odkrywania jawnych linków. Nie zatwierdzam
> kopiowania treści, automatycznego pobierania plików ani zbiorczej presumpcji prawnej.

> Zatwierdzam proponowany zakres 113 widoków OCR *Chamarande* opisany w
> `vault/reviews/inbox/chamarande-1934-prose-scope.md`, z obowiązkiem wyłączenia wskazanych
> cudzych i anonimowych bloków oraz wszystkich osobnych składników niewchodzących w
> zatwierdzony zakres prozy Jacques’a Sevina.

Samo zatwierdzenie tych dwóch bramek nie zatwierdza wynikowych aktywności ani końcowej
publikacji. Te decyzje pozostają widoczne w jednym raporcie i końcowym PR-ze V3-R1.
