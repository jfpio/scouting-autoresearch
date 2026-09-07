---
id: v3-regional-library-access-2026-09-06
recordType: source-collection-batch-review
status: accepted
createdAt: "2026-09-06"
reviewRequired: false
humanApproved: true
humanDecision:
  status: approved
  approvedBy: repository-owner
  reviewedAt: "2026-09-06"
  scope: >-
    Per-item downloads from Polona and permitted direct PDFs, with canonical records,
    attribution and initially scratch-only storage. Storage was later superseded by the
    accepted repository-artifacts policy. PBC Rzeszów ZIP endpoints remain prohibited.
runId: v3-source-expansion-2026-09
collectionIds:
  - pbc-rzeszow
  - kpbc
  - pbc-bialystok
  - wbc
  - sbc
sourceFilesDownloaded: 0
repositoryContentAdded: metadata-only
supersededStorageBy: vault/reviews/accepted/v3-durable-artifact-storage-2026-09.md
---

# V3-R1 — dostęp do regionalnych bibliotek cyfrowych

Kontrola objęła wyłącznie przypięte strony metadanych, publiczne strony polityk oraz
`robots.txt`. Nie pobrano żadnego PDF-u, ZIP-u, pliku DjVu ani obrazu książki. Odnośniki do
artefaktów znalezione w HTML są niezaufanymi kandydaturami i po zatwierdzeniu muszą zostać
ponownie rozwiązane, ograniczone do zarejestrowanego hosta oraz sprawdzone po typie, rozmiarze
i sygnaturze pliku.

## Wyniki

### Podkarpacka Biblioteka Cyfrowa

- Rekordy trzech książek deklarują domenę publiczną i prowadzą do zbiorczych ZIP-ów z DjVu.
- `https://www.pbc.rzeszow.pl/robots.txt` dla `User-agent: *` blokuje
  `/Content/*/zip*` i `/zipContent`.
- Podlinkowana strona `dlibra/text?id=polityka` wyświetliła domyślną stronę pomocy dotyczącą
  cookies; nie znaleziono na niej publicznych warunków ponownego użycia.
- Decyzja techniczna: **nie wolno automatycznie pobierać trzech ZIP-ów**. Dla *Gier i zabaw
  w izbie harcerskiej* znaleziono dokładne wydanie drugie z 1934 r. w Polonie pod UUID
  `f8a00528-6a07-4916-9a76-c1e094e317da`. Dla dwóch pozostałych tytułów trzeba znaleźć
  dozwolony artefakt innego typu lub niezależny egzemplarz; alternatywnie właściciel może
  sam dostarczyć legalnie pobrany plik do prywatnego `artifacts/`.

Blokada ZIP dotyczy trzech rekordów PBC, ale alternatywa Polony usuwa ją z krytycznej ścieżki
`dabrowski-indoor-games-1934`. Nadal blokuje `dabrowski-winter-games-1935` oraz
`sedlaczek-fieldcraft-method-1935`.

### Kujawsko-Pomorska Biblioteka Cyfrowa

- `robots.txt` blokuje zbiorcze ścieżki `/zip*` i `/download*`, ale nie blokuje wskazanego
  bezpośredniego PDF-u `/Content/193867/PDF/Magazyn_265_06_HD_008.pdf`.
- Publiczna polityka `https://kpbc.umk.pl/dlibra/text?id=polityka` mówi, że kopię dokumentu
  z domeny publicznej można wykorzystywać bez ograniczeń, przy zachowaniu dokładnego adresu
  bibliograficznego wykorzystanego obiektu.
- Po decyzji człowieka można przygotować per-item adapter dla tego jednego PDF-u.

Dotyczy: `piasecki-movement-games-1922`.

### Podlaska Biblioteka Cyfrowa

- `robots.txt` blokuje ścieżki ZIP i `download`, ale nie blokuje bezpośredniego PDF-u
  `/Content/28922/PDF/Mloda%20druzyna.pdf`.
- Podlinkowana strona polityki nie odpowiedziała przed kontrolowanym timeoutem. Nie jest to
  ani zgoda, ani zakaz; stan pozostaje nierozstrzygnięty.
- Adapter może powstać dopiero po zatwierdzeniu tego jawnego braku publicznej polityki albo
  po uzyskaniu mocniejszego dowodu.

Dotyczy: `pawelek-young-troop-1919`.

### Wielkopolska Biblioteka Cyfrowa

- `robots.txt` blokuje ścieżki ZIP i `download`, ale nie blokuje bezpośredniego PDF-u
  `/Content/440525/PDF/515207.pdf`. Reguły `Disallow: /` dotyczą nazwanych botów, nie
  `User-agent: *`.
- Strona polityki odpowiedziała ekranem `High Load - Verifying Browser`, więc warunków
  ponownego użycia nie udało się zweryfikować.
- Adapter może powstać dopiero po zatwierdzeniu tego jawnego braku publicznej polityki albo
  po uzyskaniu mocniejszego dowodu.

Dotyczy: `piasecki-schreiber-polish-scoutcraft-1917`.

### Śląska Biblioteka Cyfrowa

- `robots.txt` blokuje ścieżki ZIP i `download`, ale nie blokuje bezpośredniego PDF-u
  `/Content/64835/PDF/64835.pdf`.
- Sprawdzona strona `polityka` prowadzi do polityki prywatności. Na stronie rekordu i w tym
  dokumencie nie znaleziono osobnej publicznej polityki ponownego użycia plików.
- Adapter może powstać dopiero po zatwierdzeniu tego jawnego braku publicznej polityki albo
  po uzyskaniu mocniejszego dowodu.

Dotyczy: `sedlaczek-scout-school-1921`.

## Proponowana decyzja

Zatwierdzenie pakietu polskich źródeł może objąć:

1. rozwiązanie po zgodzie i udokumentowane pobranie trzech obiektów Polony;
2. per-item pobranie bezpośredniego PDF-u KPBC zgodnie z jej polityką i z atrybucją;
3. per-item pobranie bezpośrednich PDF-ów PBC Białystok, WBC i ŚBC przy zachowaniu
   kanonicznych rekordów oraz jawnej informacji, że nie znaleziono kompletnej publicznej
   polityki ponownego użycia;
4. dalsze poszukiwanie dozwolonych alternatyw dla trzech obiektów PBC Rzeszów, bez
   automatycznego pobierania zablokowanych ZIP-ów.

Ta decyzja nie rozszerza zakresu publikowanych składników i nie zmienia osobnej analizy praw
autorskich. Brak dozwolonej alternatywy dla PBC Rzeszów będzie prawidłowym wynikiem
`blocked-with-reason`, a nie podstawą do obejścia `robots.txt`.
