---
id: collection-review-historyczna-slaska-2026-09-04
recordType: source-collection-review
status: access-review
createdAt: "2026-09-04"
reviewRequired: true
collectionId: historyczna-slaska-zhp
canonicalUrl: https://historyczna.slaska.zhp.pl/?page_id=210
accessReview:
  status: human-review-required
  humanApproved: false
  recommendation: approve-for-page-metadata-and-link-discovery-only
  trustScope: bibliographic-link-directory
  currentRegistryStatus: candidate
  currentAllowedMethods: [metadata-only]
  proposedRegistryStatus: approved-per-item
  proposedAllowedMethods: [page-metadata, link-discovery]
  rateLimitPerMinute: 5
robotsTxt:
  url: https://historyczna.slaska.zhp.pl/robots.txt
  checkedAt: "2026-09-04"
  status: not-found-404
  decision: >-
    Brak pliku nie jest zgodą na crawling. Proponowany adapter ma pobierać wyłącznie jawnie
    wskazane strony indeksowe, bez rekursywnego skanowania i najwyżej pięć żądań na minutę.
termsOfUse:
  checkedAt: "2026-09-04"
  status: no-public-reuse-license-found
  inspectedPages:
    - https://historyczna.slaska.zhp.pl/
    - https://historyczna.slaska.zhp.pl/?page_id=210
    - https://historyczna.slaska.zhp.pl/?page_id=600
  contactPage: https://historyczna.slaska.zhp.pl/?page_id=600
  decision: >-
    Nie znaleziono publicznej licencji ponownego użycia na sprawdzonych stronach. Można
    zachowywać podstawowe metadane bibliograficzne i odnośniki, lecz nie kopiować opisów,
    artykułów, plików ani obrazów bez odrębnej podstawy prawnej.
reuseDecision:
  pageMetadataAllowed: false
  linkDiscoveryAllowed: false
  fullTextAllowed: false
  directFileDownloadAllowed: false
  imagesAllowed: false
  followExternalLinksAutomatically: false
  externalTargetRule: >-
    Każda domena docelowa musi najpierw mieć własny wpis w rejestrze, a konkretny dokument
    musi zachować kanoniczny rekord instytucji i przejść niezależną ocenę praw.
unresolved:
  - >-
    Właściciel repozytorium musi zatwierdzić użycie wyłącznie do metadanych stron i
    odkrywania linków, bez kopiowania treści oraz bez zbiorczej presumpcji prawnej.
provenanceEvidence:
  - id: historyczna-repetytorium
    url: https://historyczna.slaska.zhp.pl/?page_id=210
    supports:
      - collection-title-and-maintainer
      - bibliographic-index-purpose
      - outbound-links-to-independent-digital-libraries
      - titles-authors-editions-and-publication-years
  - id: historyczna-robots
    url: https://historyczna.slaska.zhp.pl/robots.txt
    supports:
      - robots-file-not-found-404-on-review-date
  - id: historyczna-home
    url: https://historyczna.slaska.zhp.pl/
    supports:
      - site-identity
      - no-public-reuse-license-found-on-inspected-page
  - id: historyczna-contact
    url: https://historyczna.slaska.zhp.pl/?page_id=600
    supports:
      - public-contact-route
      - no-public-reuse-license-found-on-inspected-page
discovery:
  discoveredAt: "2026-09-04"
  metadataPagesInspected: 5
  sourceFilesDownloaded: 0
  fullTextCopied: false
  repositoryContentAdded: metadata-only
  estimatedCostUsd: 0
---

# Ocena kolekcji: Repetytorium cyfrowe Komisji Historycznej Chorągwi Śląskiej ZHP

Repetytorium przedstawia się jako uporządkowany katalog odnośników do wartościowych książek,
dokumentów, czasopism i filmów dostępnych w internecie. Wskazuje tytuły, autorów, wydania i
lata, ale zdecydowana większość materiałów prowadzi do niezależnych instytucji, przede
wszystkim Polony oraz regionalnych bibliotek cyfrowych. Jest więc wartościowym punktem
odkrywania, a nie źródłem zbiorczej zgody na ponowne użycie dokumentów.

Na dzień kontroli adres `robots.txt` zwracał 404. Nie znaleziono publicznej licencji ani
regulaminu ponownego użycia na stronie głównej, stronie repertorium ani stronie kontaktowej.
Brak zakazu nie oznacza zgody na kopiowanie. Bezpieczny zakres proponowany do zatwierdzenia
obejmuje wyłącznie metadane stron i odkrywanie odnośników, przy limicie pięciu żądań na
minutę, bez rekursywnego crawlowania.

Każdy odkryty odnośnik musi zostać rozpatrzony w kontekście serwisu docelowego. Adapter nie
powinien automatycznie pobierać PDF-ów ani przechodzić na niezarejestrowane domeny. Autorstwo,
status prawny, wydanie i warunki dostępu pozostają decyzją dotyczącą konkretnego dokumentu.
