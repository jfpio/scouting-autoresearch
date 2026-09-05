---
id: source-candidate-jacques-sevin-chamarande-gallica-bpt6k3373518k
recordType: source-candidate
status: rights-review
createdAt: "2026-09-04"
reviewRequired: true
publicationBlocked: true
subjectId: jacques-sevin
sourceType: bibliographic-metadata
title: Chamarande
author:
  name: Jacques Sevin
  lifeDates: 1882-1951
originalLanguage: fr
collectionId: gallica-bnf
collectionStatusAtDiscovery: candidate
allowedMethodUsed: metadata-only
canonicalUrl: https://gallica.bnf.fr/ark:/12148/bpt6k3373518k
digitalEdition:
  identifier: bpt6k3373518k
  oaiIdentifier: oai:bnf.fr:gallica/ark:/12148/bpt6k3373518k
  oaiDatestamp: "2023-12-29"
  catalogRecordIdentifier: FRBNF31358554
  catalogUrl: https://catalogue.bnf.fr/ark:/12148/cb313585549
  physicalEdition:
    publisher: Éditions Spes
    place: Paris
    year: 1934
    extent: 1 volume, 141 printed pages
    otherMaterial: music, plates and color cover
    notes: Chronicles first published in Le Chef in November-December 1922 and 1923.
  holding:
    institution: Bibliothèque nationale de France, département Sciences et techniques
    shelfmark: 8-V-51412
  editionIdentityStatus: identified
rightsReview:
  status: human-review-required
  humanApproved: false
  proposedRightsStatus: public-domain
  jurisdiction: Poland under the harmonized European Union term framework
  catalogClaim: domaine-public-and-public-domain
  proposedScope:
    - original French prose explicitly attributable to Jacques Sevin in the 1934 edition
  fullTextEligible: false
  imagesEligible: false
  translationEligible: false
  calculation:
    relevantAuthors:
      - name: Jacques Sevin
        deathDate: "1951-07-19"
        evidenceId: bnf-jacques-sevin-authority
    lastRelevantAuthorDeathDate: "1951-07-19"
    protectionTerm: life-plus-70-years
    protectionEnded: "2021-12-31"
    publicDomainFrom: "2022-01-01"
  proposedExcludedComponents:
    - music until its authorship is established separately
    - plates, illustrations and color cover until their authorship is established separately
    - later editions, introductions, selections, annotations and editorial apparatus
    - Gallica site, database, viewer and digital packaging
  gallicaReuseConditions:
    classification: noncommercial-reuse-free-with-attribution
    requiredAttribution: Source gallica.bnf.fr / Bibliothèque nationale de France
    commercialReuse: paid-license-required
  accessDecision:
    status: human-approved-for-controlled-download
    date: "2026-09-05"
    approvedBy: repository-owner
    useMode: noncommercial-research-and-publication
    requiredAttribution: Source gallica.bnf.fr / Bibliothèque nationale de France
    approvedScope:
      - documented download to temporary scratch storage for extraction and verification
      - original French prose explicitly attributable to Jacques Sevin in the 1934 edition
    excludes:
      - music until its authorship and rights are established separately
      - plates, illustrations and color cover until their authorship and rights are established separately
      - later editions, introductions, selections, annotations and editorial apparatus
      - Gallica site, database, viewer and digital packaging
      - directly revenue-generating reuse without a separate Gallica commercial license
    basis: >-
      The repository owner confirmed that the project is non-profit and approved
      noncommercial download and reuse under Gallica's attribution condition for this
      item and scope.
  unresolved:
    - >-
      Page-level attribution must still be checked after download before prose is extracted;
      components not explicitly attributable to Jacques Sevin remain excluded.
    - >-
      Any directly revenue-generating publication would require a separate Gallica
      commercial-reuse license and must not inherit this decision.
  alternativeAccessResearch:
    checkedAt: "2026-09-04"
    status: no-equivalent-digital-edition-found-in-approved-metadata-searches
    interpretation: negative-search-result-not-proof-of-absence
    sourceFilesDownloaded: 0
    queries:
      - collectionId: internet-archive
        method: metadata-only
        endpoint: https://archive.org/advancedsearch.php
        parameters:
          q: 'title:(Chamarande) AND creator:(Jacques Sevin)'
          fields: [identifier, title, creator, date, year, collection, mediatype]
          rows: 20
          output: json
        result:
          numFound: 0
      - collectionId: internet-archive
        method: metadata-only
        endpoint: https://archive.org/advancedsearch.php
        parameters:
          q: 'title:(Chamarande)'
          fields: [identifier, title, creator, date, year, collection, mediatype]
          rows: 50
          output: json
        result:
          numFound: 5
          relevantToEdition: 0
          note: Results concerned the place or surname Chamarande, not Sevin's book.
      - collectionId: internet-archive
        method: metadata-only
        endpoint: https://archive.org/advancedsearch.php
        parameters:
          q: 'creator:("Sevin, Jacques" OR "Jacques Sevin") AND mediatype:texts'
          fields: [identifier, title, creator, date, year, collection, mediatype]
          rows: 50
          output: json
        result:
          numFound: 1
          relevantToEdition: 0
          returnedIdentifier: lechansonsdescou00jacq
          returnedTitle: le chansons de scounts de france
          returnedYear: 1936
          accessClass: printdisabled-inlibrary
          note: The only creator match is a different songbook and was not opened or downloaded.
      - collectionId: wikisource
        method: metadata-only
        endpoint: https://fr.wikisource.org/w/api.php
        parameters:
          action: query
          list: search
          srsearch: '"Chamarande" "Jacques Sevin"'
          srnamespace: '0|106'
          srlimit: 20
          format: json
          formatversion: 2
        result:
          totalHits: 0
      - collectionId: scoutscan-the-dump
        method: link-discovery
        endpoint: https://thedump.scoutscan.com/nonfict.html
        parameters:
          literalTerms: [Sevin, Chamarande]
        result:
          matchingEntries: 0
      - collectionId: project-gutenberg
        method: metadata-only
        endpoint: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv
        catalogDocumentation: https://www.gutenberg.org/ebooks/offline_catalogs.html
        parameters:
          literalTerms: [Jacques Sevin, 'Sevin, Jacques', Chamarande]
        result:
          matchingRows: 0
          catalogLastModifiedAtCheck: "2026-08-30T21:32:16Z"
          contentLengthAtCheck: 21196613
          persistedCatalogFile: false
    conclusion: >-
      The approved metadata and link-discovery searches, including the official Project
      Gutenberg offline catalog, did not identify the 1934 Chamarande edition outside
      Gallica. They therefore do not remove the existing Gallica reuse-terms decision gate.
      The searches may be repeated if the indexed collections change, but a missing result
      must not be treated as proof that no other copy exists.
provenanceEvidence:
  - id: bnf-chamarande-catalog
    url: https://catalogue.bnf.fr/ark:/12148/cb313585549
    supports:
      - title
      - author-of-text
      - 1934-Paris-Spes-edition
      - physical-extent
      - music-plates-and-color-cover-presence
      - Gallica-digital-holding-identifier
  - id: gallica-chamarande-oai
    url: https://gallica.bnf.fr/services/OAIRecord?ark=bpt6k3373518k
    supports:
      - digital-edition-identifier
      - BnF-holding-and-shelfmark
      - public-domain-claim-in-French-and-English
      - 188-view-extent
  - id: bnf-jacques-sevin-authority
    url: https://catalogue.bnf.fr/ark:/12148/cb12703053z
    supports:
      - Jacques-Sevin-identity
      - author-role
      - birth-date
      - death-date
  - id: gallica-content-reuse-terms
    url: https://gallica.bnf.fr/edit/und/conditions-dutilisation-des-contenus-de-gallica
    supports:
      - free-noncommercial-reuse
      - source-attribution-requirement
      - paid-license-for-commercial-reuse
      - separate-rights-warning-for-protected-and-partner-content
  - id: bnf-metadata-reuse-terms
    url: https://www.bnf.fr/fr/conditions-de-reutilisations-des-donnees-de-la-bnf
    supports:
      - open-license-for-BnF-bibliographic-and-authority-metadata
      - metadata-source-and-retrieval-date-requirement
  - id: polish-copyright-act-articles-36-and-39
    url: https://isap.sejm.gov.pl/isap.Nsf/download.xsp/WDU20000800904/T/D20000904L.pdf
    supports:
      - Polish-life-plus-70-protection-term
      - full-calendar-year-calculation
  - id: eu-directive-2006-116-ec-article-1
    url: https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32006L0116
    supports:
      - European-Union-life-plus-70-protection-term
  - id: internet-archive-chamarande-metadata-searches
    url: https://archive.org/advancedsearch.php
    supports:
      - no-Chamarande-1934-match-in-three-recorded-metadata-queries-at-check-date
      - one-different-Sevin-songbook-result-not-opened-or-downloaded
  - id: french-wikisource-chamarande-search
    url: https://fr.wikisource.org/w/api.php
    supports:
      - no-title-or-author-match-in-recorded-page-and-index-namespace-query-at-check-date
  - id: scoutscan-nonfiction-directory-search
    url: https://thedump.scoutscan.com/nonfict.html
    supports:
      - no-Sevin-or-Chamarande-entry-in-directory-at-check-date
  - id: project-gutenberg-offline-catalog-search
    url: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv
    supports:
      - no-Jacques-Sevin-or-Chamarande-row-in-official-catalog-at-check-date
      - catalog-response-metadata-and-literal-search-terms
discovery:
  discoveredAt: "2026-09-04"
  metadataRetrievedAt: "2026-09-04"
  metadataPagesInspected: 12
  sourceFilesDownloaded: 0
  fullTextCopied: false
  repositoryContentAdded: metadata-only
  estimatedCostUsd: 0
---

# Kandydatura: *Chamarande* Jacques’a Sevina (1934)

To jest konkretna, zidentyfikowana edycja ze zbiorów Bibliothèque nationale de France, a nie
nieopisany skan krążący w internecie. Katalog BnF przypisuje tekst Jacques’owi Sevinowi,
podaje wydawcę Éditions Spes, miejsce i rok publikacji oraz wskazuje obecność muzyki, plansz
i kolorowej okładki. Rekord OAI Gallici oznacza obiekt po francusku i angielsku jako domenę
publiczną.

BnF podaje pełną datę śmierci Sevina: 19 lipca 1951 r. Przy okresie życia autora i 70 pełnych
lat prawa do jego tekstu wygasły 31 grudnia 2021 r.; tekst jest w domenie publicznej w Polsce
i UE od 1 stycznia 2022 r. To obliczenie wspiera proponowaną decyzję, ale nie zastępuje
zatwierdzenia konkretnego zakresu wymaganego przez repozytorium.

Gallica pozwala na bezpłatne użycie niekomercyjne treści z zachowaniem wskazanej atrybucji,
natomiast użycie bezpośrednio generujące przychód wymaga odpłatnej licencji. Dlatego przed
pobraniem właściciel potwierdził 5 września 2026 r., że projekt jest non-profit, zaakceptował
niekomercyjny sposób wykorzystania i obowiązek atrybucji Gallici. Zgoda obejmuje wyłącznie
prozę Sevina. Muzyka, plansze, ilustracje, okładka, późniejsze opracowania oraz cyfrowa warstwa
Gallici pozostają wyłączone, dopóki nie zostaną ocenione osobno.

Po zatwierdzeniu pierwszym krokiem będzie małe, udokumentowane pobranie do katalogu scratch,
kontrola stron tytułowych i spisu treści oraz ocena, czy książka rzeczywiście zawiera
samodzielne gry lub próby warte ekstrakcji. Sam tytuł i tematyczna przydatność nie są jeszcze
dowodem, że znajdzie się w niej materiał do importu.

## Poszukiwanie alternatywnego egzemplarza

Żeby nie zatrzymywać analizy na warunkach jednej biblioteki, sprawdzono dozwolonymi metodami
metadane Internet Archive, francuskiego Wikisource, katalog linków The Dump / Scoutscan oraz
oficjalny katalog offline Project Gutenberg.
Trzy zapytania Internet Archive nie zwróciły edycji *Chamarande*: wyszukiwanie dokładnego
tytułu i autora dało zero wyników, pięć wyników samego tytułu dotyczyło miejscowości albo
nazwiska, a jedynym trafieniem dla autora był inny, niedostępny swobodnie śpiewnik z 1936 r.
Wikisource i katalog Scoutscan również nie zwróciły dopasowania. W oficjalnym feedzie CSV
Project Gutenberg nie było wiersza zawierającego nazwisko Jacques’a Sevina ani tytuł
*Chamarande*. Feed został przeszukany strumieniowo i nie zapisano jego kopii w repozytorium
ani w scratch.

To jest udokumentowany wynik negatywny na dzień sprawdzenia, a nie dowód nieistnienia innego
skanu. Nie pobrano żadnego pliku ani treści. Ponieważ nie znaleziono równoważnego egzemplarza
o mniej ograniczających warunkach dostępu, nadal obowiązuje bramka dotycząca warunków Gallici
i zakresu wyłącznie prozy Sevina.
