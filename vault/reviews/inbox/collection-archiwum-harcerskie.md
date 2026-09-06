---
id: collection-review-archiwum-harcerskie-2026-09-04
recordType: source-collection-review
status: access-review
createdAt: "2026-09-04"
reviewRequired: true
collectionId: archiwum-harcerskie
canonicalUrl: https://archiwumharcerskie.pl/index.php?title=Strona_główna
accessReview:
  status: human-review-required
  humanApproved: false
  recommendation: approve-for-page-and-api-metadata-plus-link-discovery-only
  trustScope: archival-metadata-discovery
  currentRegistryStatus: candidate
  currentAllowedMethods: [metadata-only]
  proposedRegistryStatus: approved-per-item
  proposedAllowedMethods: [page-metadata, api-metadata, link-discovery]
  rateLimitPerMinute: 5
  proposedApiScope:
    endpoint: https://archiwumharcerskie.pl/api.php
    allowedQueries:
      - MediaWiki site information and rights configuration
      - page identifiers, canonical URLs, titles, categories and revision timestamps
      - file-description-page metadata without retrieving the underlying file
    excludedQueries:
      - page or revision content
      - image information containing direct download URLs
      - bulk recursive category traversal
robotsTxt:
  url: https://archiwumharcerskie.pl/robots.txt
  checkedAt: "2026-09-04"
  status: not-found-404
  decision: >-
    Brak pliku nie jest zgodą na crawling. Proponowany adapter ma wykonywać wyłącznie
    jawnie ograniczone zapytania o metadane, bez rekursywnego indeksowania i najwyżej pięć
    żądań na minutę.
termsOfUse:
  checkedAt: "2026-09-04"
  status: all-rights-reserved-and-configured-license-page-missing
  inspectedPages:
    - https://archiwumharcerskie.pl/index.php?title=Archiwum:Informacje_prawne
    - https://archiwumharcerskie.pl/index.php?title=Archiwum:O_ArchiwumHarcerskie.pl
    - https://archiwumharcerskie.pl/index.php?title=Strona_główna
    - https://archiwumharcerskie.pl/index.php?title=Archiwum:Warunki_korzystania_z_archiwaliów
  configuredRightsLabel: Warunki korzystania z archiwaliów
  configuredRightsPageStatus: missing
  legalNotice: all-rights-reserved-no-GFDL-or-CC
  rightsHolderNamedBySite: Fundacja Harcerstwa Jakobstaf
  decision: >-
    Nie wolno interpretować stopki MediaWiki jako otwartej licencji, ponieważ docelowa
    strona warunków nie istnieje, a osobna strona prawna wprost zastrzega prawa. Metadane
    mogą służyć do odkrycia materiału, lecz kopiowanie treści lub pliku wymaga niezależnej
    podstawy prawnej i zgodności z warunkami właściciela serwisu.
reuseDecision:
  pageMetadataAllowed: false
  linkDiscoveryAllowed: false
  fullTextAllowed: false
  directFileDownloadAllowed: false
  imagesAllowed: false
  followExternalLinksAutomatically: false
  externalTargetRule: >-
    Odkryty tytuł należy odszukać w zatwierdzonej instytucji źródłowej albo uzyskać zgodę
    Archiwum. Sam wiek dokumentu, widoczność skanu lub ogólna stopka serwisu nie stanowią
    dowodu praw do ponownego użycia.
unresolved:
  - >-
    Właściciel repozytorium musi zatwierdzić użycie wyłącznie do metadanych stron, zapytań
    MediaWiki API o metadane i odkrywania linków, bez pobierania plików lub treści.
  - >-
    Pełne materiały wymagają item-level researchu oraz w razie potrzeby bezpośredniej zgody
    Archiwum; nie można polegać na brakującej stronie warunków.
provenanceEvidence:
  - id: archiwum-about
    url: https://archiwumharcerskie.pl/index.php?title=Archiwum:O_ArchiwumHarcerskie.pl
    supports:
      - collection-purpose-and-scope
      - digitization-history
      - operator-history
      - public-contact-route
  - id: archiwum-legal
    url: https://archiwumharcerskie.pl/index.php?title=Archiwum:Informacje_prawne
    supports:
      - rights-holder-named-by-site
      - all-rights-reserved-notice
      - explicit-exclusion-of-GFDL-and-CC
  - id: archiwum-mediawiki-rightsinfo
    url: https://archiwumharcerskie.pl/api.php?action=query&format=json&formatversion=2&meta=siteinfo&siprop=general%7Crightsinfo
    supports:
      - official-MediaWiki-metadata-API
      - configured-rights-label-and-URL
      - current-MediaWiki-site-identity
  - id: archiwum-configured-license-page
    url: https://archiwumharcerskie.pl/index.php?title=Archiwum:Warunki_korzystania_z_archiwaliów
    supports:
      - configured-license-page-is-missing-on-review-date
  - id: archiwum-robots
    url: https://archiwumharcerskie.pl/robots.txt
    supports:
      - robots-file-not-found-404-on-review-date
  - id: archiwum-home
    url: https://archiwumharcerskie.pl/index.php?title=Strona_główna
    supports:
      - collection-categories
      - file-and-press-holdings
      - configured-rights-label-in-footer
discovery:
  discoveredAt: "2026-09-04"
  metadataPagesInspected: 7
  sourceFilesDownloaded: 0
  fullTextCopied: false
  repositoryContentAdded: metadata-only
  estimatedCostUsd: 0
---

# Ocena kolekcji: ArchiwumHarcerskie.pl

ArchiwumHarcerskie.pl jest prowadzonym w MediaWiki repozytorium skanów prasy, dokumentów,
fotografii i innych archiwaliów. Portal powstał przy projekcie digitalizacyjnym Niezależnego
Wydawnictwa Harcerskiego i ZHR, a następnie został wydzielony jako samodzielne archiwum.
Jego zakres obejmuje zarówno materiały przedwojenne, jak i liczne materiały z drugiej połowy
XX wieku, więc nie można stosować do całej kolekcji jednej presumpcji prawnej.

Strona „Informacje prawne” wskazuje Fundację Harcerstwa Jakobstaf jako właściciela praw do
serwisu, zastrzega wszystkie prawa i stwierdza, że materiał nie jest objęty GFDL ani CC.
Stopka MediaWiki wyświetla etykietę „Warunki korzystania z archiwaliów”, lecz wskazana strona
nie istnieje zarówno w interfejsie, jak i według API. Nie można zatem wywieść otwartej
licencji ze standardowej stopki wiki.

Serwis udostępnia oficjalne MediaWiki API, które nadaje się do ograniczonego adaptera
metadanych. Rekomendowany zakres obejmuje tytuł, kategorie, kanoniczny URL, identyfikator i
czas rewizji strony opisu. Nie obejmuje treści strony, danych prowadzących do bezpośredniego
pobrania obrazu lub PDF-a ani rekursywnego indeksowania kategorii.

Przed użyciem pełnego materiału należy ustalić prawa do konkretnego utworu i jego składników,
a także warunki dotyczące cyfrowej reprodukcji i opisu. Bezpośrednie pobranie z tej domeny
pozostaje wyłączone; materiał w domenie publicznej można w pierwszej kolejności odszukać w
instytucji z jednoznacznymi warunkami albo uzyskać zgodę Archiwum.
