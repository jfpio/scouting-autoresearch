---
id: pbc-direct-djvu-alternatives
recordType: source-artifact-batch-review
status: proposed
createdAt: "2026-09-06"
reviewRequired: true
humanApproved: false
runId: v3-source-expansion-2026-09
sourceIds:
  - dabrowski-winter-games-1935
  - sedlaczek-fieldcraft-method-1935
collectionId: pbc-rzeszow
repositoryContentAdded: metadata-only
sourceFilesDownloaded: 0
---

# Bezpośrednie pliki DjVu jako alternatywa dla zablokowanych ZIP-ów PBC

Po zatwierdzonym dalszym wyszukiwaniu alternatyw oficjalne strony czytnika PBC ujawniły dwa
bezpośrednie pliki DjVu używane przez przeglądarkowy czytnik:

- *Harce zimowe w polu*: `https://www.pbc.rzeszow.pl/Content/10620/DjVu/harce_zimowe.djvu`,
  znaleziony na `https://www.pbc.rzeszow.pl/dlibra/publication/edition/10620/content`;
- *Metodyka harców w przykładach*:
  `https://www.pbc.rzeszow.pl/Content/10606/DjVu/metodyka_harcow.djvu`, znaleziony na
  `https://www.pbc.rzeszow.pl/dlibra/publication/edition/10606/content`.

Sprawdzony 6 września 2026 r. `robots.txt` blokuje `/zipContent`, `/Content/*/zip*` oraz
wybrane endpointy wyników, lecz nie blokuje ścieżek `/Content/*/DjVu/*.djvu`. Nie znaleziono
jednak publicznej polityki ponownego wykorzystania PBC. Dotychczasowa zgoda właściciela
obejmowała dalsze szukanie alternatyw, nie zaś pobranie nowo odkrytego typu artefaktu.
Dlatego pliki nie zostały pobrane, a istniejący zakaz automatycznego pobierania ZIP-ów
pozostaje bez zmian.

## Proponowana decyzja

> Zatwierdzam tymczasowe pobranie do `$SCRATCH` dwóch bezpośrednich plików DjVu wskazanych
> w `pbc-direct-djvu-alternatives.md`, wyłącznie dla jednostek
> `dabrowski-winter-games-1935` i `sedlaczek-fieldcraft-method-1935`, z zachowaniem
> kanonicznych rekordów PBC, kontroli sygnatury i rozmiaru oraz bez kopiowania plików do
> repozytorium. Zgoda nie obejmuje żadnego ZIP-u ani innych obiektów PBC i nie rozszerza
> zatwierdzonego zakresu publikowanych składników.
