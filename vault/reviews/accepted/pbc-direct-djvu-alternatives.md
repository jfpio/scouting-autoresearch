---
id: pbc-direct-djvu-alternatives
recordType: source-artifact-batch-review
status: accepted
createdAt: "2026-09-06"
reviewRequired: false
humanApproved: true
approvedAt: "2026-09-07"
approvedBy: repository-owner
runId: v3-source-expansion-2026-09
sourceIds:
  - dabrowski-winter-games-1935
  - sedlaczek-fieldcraft-method-1935
collectionId: pbc-rzeszow
repositoryContentAdded: metadata-only
sourceFilesDownloaded: 0
currentRunDisposition: skipped-with-reason
---

# Bezpośrednie pliki DjVu jako alternatywa dla zablokowanych ZIP-ów PBC

Oficjalne strony czytnika PBC ujawniły dwa bezpośrednie pliki DjVu:

- *Harce zimowe w polu*: `https://www.pbc.rzeszow.pl/Content/10620/DjVu/harce_zimowe.djvu`,
  znaleziony na `https://www.pbc.rzeszow.pl/dlibra/publication/edition/10620/content`;
- *Metodyka harców w przykładach*:
  `https://www.pbc.rzeszow.pl/Content/10606/DjVu/metodyka_harcow.djvu`, znaleziony na
  `https://www.pbc.rzeszow.pl/dlibra/publication/edition/10606/content`.

Sprawdzony 6 września 2026 r. `robots.txt` blokuje `/zipContent`, `/Content/*/zip*` oraz
wybrane endpointy wyników, lecz nie blokuje ścieżek `/Content/*/DjVu/*.djvu`. Właściciel
ręcznie sprawdził działanie linków i 7 września 2026 r. zatwierdził pobranie obu plików do
scratch. Zakaz automatycznego pobierania ZIP-ów pozostaje bez zmian.

Próba kontrolna wykazała, że oba adresy zwracają jedynie małe indeksy pośredniego,
wieloplikowego DjVu (485 i 290 bajtów), a nie kompletne książki. Właściciel następnie
polecił pominąć oba źródła PBC w bieżącym runie V3. Zgoda na te dwa adresy pozostaje
udokumentowana do ewentualnego osobnego runu; w V3 nie pobieramy plików stron, nie wykonujemy
OCR-u i nie importujemy rekordów z tych książek.

## Zatwierdzona decyzja

> Zatwierdzam tymczasowe pobranie do `$SCRATCH` dwóch bezpośrednich plików DjVu wskazanych
> w `pbc-direct-djvu-alternatives.md`, wyłącznie dla jednostek
> `dabrowski-winter-games-1935` i `sedlaczek-fieldcraft-method-1935`, z zachowaniem
> kanonicznych rekordów PBC, kontroli sygnatury i rozmiaru oraz bez kopiowania plików do
> repozytorium. Zgoda nie obejmuje żadnego ZIP-u ani innych obiektów PBC.
