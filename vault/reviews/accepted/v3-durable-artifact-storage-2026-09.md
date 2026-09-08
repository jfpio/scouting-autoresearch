---
id: v3-durable-artifact-storage-2026-09
recordType: artifact-storage-policy
status: accepted
createdAt: "2026-09-07"
reviewRequired: false
humanApproved: true
approvedAt: "2026-09-07"
approvedBy: repository-owner
runId: v3-source-expansion-2026-09
storage: repository-artifacts-gitignored-group-storage
path: artifacts/
---

# V3 — trwały magazyn książek i OCR-u

Właściciel projektu zatwierdził przechowywanie pobranych książek oraz surowych wyników OCR
w katalogu `artifacts/` znajdującym się przy repozytorium na Group Storage. Katalog jest
w całości ignorowany przez Git: jego pliki nie wchodzą do commitów, PR-ów, buildów ani
publicznej dystrybucji.

Trwały magazyn obejmuje:

- `artifacts/sources/<source-id>/` — pobrane PDF-y, DjVu, obrazy stron i metadane dostawcy,
- `artifacts/ocr/<source-id>/` — niezmienione odpowiedzi OCR,
- `artifacts/inspection/<source-id>/` — wyprowadzone warstwy tekstowe potrzebne do ponownej
  kontroli ekstrakcji.

W Git pozostają konfiguracje, checkpointy, sumy kontrolne, model, receptura i raporty.
Scratch nadal służy do środowisk, logów, buildów, miniaturek i innych łatwo odtwarzalnych
wyników roboczych. Trwałe przechowywanie nie rozszerza praw do publikacji ani zakresu
dozwolonego pobierania; dla każdego źródła nadal obowiązują jego warunki, atrybucja i bramki.

## Zapis decyzji właściciela

> Zależy mi na tym, żeby zocerowane książki były w repozytorium na Group Storage, w osobnym
> folderze objętym `gitignore`.
