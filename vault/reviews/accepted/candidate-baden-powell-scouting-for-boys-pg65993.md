---
id: source-candidate-baden-powell-scouting-for-boys-pg65993
recordType: source-candidate
status: accepted
createdAt: "2026-09-03"
reviewedAt: "2026-09-03"
subjectId: robert-baden-powell
sourceType: bibliographic-metadata
title: Scouting for Boys
author:
  name: Robert Stephenson Smyth Baden-Powell, Baron Baden-Powell of Gilwell
  lifeDates: 1857-1941
originalLanguage: en
collectionId: project-gutenberg
collectionStatusAtDiscovery: candidate
allowedMethodUsed: documented-download
canonicalUrl: https://www.gutenberg.org/ebooks/65993
digitalEdition:
  identifier: pg-65993
  releaseDate: "2021-08-05"
  lastUpdated: "2024-10-18"
  catalogEditionStatement: "United States: Dover Publications, Inc., 1908, reprint 2007."
  internalImprint:
    publisher: Horace Cox
    place: London
    year: 1908
    form: six fortnightly parts
  editionIdentityStatus: ambiguous
  digitalCredits:
    - Chris Curnow
    - Greg Weeks
    - David King
    - Online Distributed Proofreading Team
rightsReview:
  status: human-approved
  rightsStatus: public-domain
  jurisdiction: Poland under the harmonized European Union term framework
  humanApproved: true
  approvalPolicyId: project-gutenberg-pd-usa-plus-life-70
  catalogClaim: public-domain-in-the-usa
  approvedScope:
    - original English text demonstrably present in the 1908 Horace Cox six-part edition
  fullTextEligible: true
  imagesEligible: false
  translationEligible: true
  humanDecision:
    date: "2026-09-03"
    approvedBy: repository-owner
    basis: >-
      The repository owner approved the original 1908 text after applying the Polish and EU
      life-plus-70 rule to Baden-Powell's documented death in 1941.
  calculation:
    relevantAuthors:
      - name: Robert Stephenson Smyth Baden-Powell, Baron Baden-Powell of Gilwell
        deathDate: "1941-01-08"
        evidenceId: world-scouting-baden-powell-death
    lastRelevantAuthorDeathDate: "1941-01-08"
    protectionTerm: life-plus-70-years
    protectionEnded: "2011-12-31"
    publicDomainFrom: "2012-01-01"
  excludedComponents:
    - Project Gutenberg license, header, footer, trademark and other digital packaging
    - Dover 2007 editorial additions, if any
    - illustrations and photographs until their authorship is verified per image
    - any later foreword, annotation, translation or editorial apparatus
  reuseConditions:
    - Preserve Baden-Powell's authorship and the historical wording of the source.
    - Extract only material verified against the 1908 edition; do not import later additions.
    - Link the Project Gutenberg record and the page or scan used for verification.
    - Apply current safety review before turning historical instructions into activities.
provenanceEvidence:
  - id: project-gutenberg-catalog-65993
    url: https://www.gutenberg.org/ebooks/65993
    supports:
      - author
      - title
      - catalog-edition-statement
      - ebook-identifier
      - release-and-update-dates
      - digitization-credits
      - public-domain-claim-usa
  - id: project-gutenberg-html-65993
    url: https://www.gutenberg.org/files/65993/65993-h/65993-h.htm
    supports:
      - internal-title-pages
      - horace-cox-imprint
      - 1908-copyright-notices
      - image-presence
      - project-gutenberg-license-and-jurisdiction-warning
  - id: polish-copyright-act-articles-36-and-39
    url: https://isap.sejm.gov.pl/isap.Nsf/download.xsp/WDU20000800904/T/D20000904L.pdf
    supports:
      - Polish life-plus-70 protection term
      - full-calendar-year calculation
  - id: eu-directive-2006-116-ec-article-1
    url: https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32006L0116
    supports:
      - European Union life-plus-70 protection term
  - id: world-scouting-baden-powell-death
    url: https://www.scout.org/who-we-are/scout-movement/scoutings-history
    supports:
      - Baden-Powell death date
  - id: scoutscan-scouting-for-boys-index
    url: https://thedump.scoutscan.com/s4b.html
    supports:
      - 1908 publication in fortnightly installments
      - table of camp-fire yarns
      - attribution of illustrations to Baden-Powell
  - id: scoutscan-terms
    url: https://thedump.scoutscan.com/nonfict.html
    supports:
      - link-instead-of-copy request
      - CC-BY-NC-ND-3.0 site notice
      - historical-content and current-safety warning
discovery:
  discoveredAt: "2026-09-03"
  metadataPagesInspected: 7
  sourceFilesDownloaded: 2
  fullTextCopied: false
  repositoryContentAdded: activity-excerpts
  estimatedCostUsd: 0
processing:
  sourceId: sfb-1908
  sourceSha256: 46826e0cc47e2d923c36c699c68c91e106e49b4c46d6bcf1475a9924e1781634
  parserVersion: gutenberg-html-blocks-v2
  extractionReport: data/reports/pg-65993-extraction.json
  importedActivityCount: 49
  importedKinds: [game]
  wholeSourceCopiedToRepository: false
  imagesCopiedToRepository: false
  excludedNonGameTitles: ["Debates, Trials, Etc.", "Scouts' War Dance"]
  discoveryApi:
    status: superseded-by-deterministic-curation
    modelRequested: mistral-medium-2604
    model: mistral-medium-2604
    promptVersion: gutenberg-activity-locators-v1
    successfulRequests: 1
    transientRateLimits: 1
    promptTokens: 24281
    completionTokens: 5637
    billingMode: experimental-no-charge
    billedCostUsd: 0
    referenceCostUsd: 0.078699
    priceSource: https://docs.mistral.ai/inference/pricing
    priceAccessedOn: "2026-09-03"
  translation:
    status: complete
    productionCandidate: mistral-large-2512
    evaluationConfig: config/translation-model-evaluation.yaml
    evaluationActivityCount: 5
    reasoningMode: disabled
    modelDecisionApprovedBy: repository-owner
    modelDecisionApprovedAt: "2026-09-04"
    previousAttemptModel: mistral-medium-2604
    previousAttemptCompletedActivities: 0
    previousAttemptStatus: transient-http-429
    resolvedBlocker: previous-api-key-tier-and-rate-limits
    blockerObservedAt: "2026-09-04T14:53:48Z"
    blockerResolvedAt: "2026-09-04"
    blockerResolution: use-new-education-api-key-with-mistral-large-2512-without-reasoning
    priorSmall4Attempt:
      status: transient-http-429
      attemptedAt: "2026-09-04T15:12:02Z"
      supersededNextRetryAt: "2026-09-04T16:12:02.725081Z"
      providerType: rate_limited
      providerCode: "1300"
      rateLimitRequestsPerMinute: 0
      rateLimitRequestsRemaining: 0
    priorMinistral14bEvaluation:
      status: automatic-quality-checks-failed
      attemptedOn: "2026-09-04"
      modelRequested: ministral-14b-2512
      evaluatedActivities: 5
      automaticFailures: 5
      referenceCostUsd: 0.000973
    latestAttempt:
      status: chat-completions-access-smoke-passed
      attemptedOn: "2026-09-04"
      modelRequested: mistral-large-2512
    qualitySmokeV2:
      evaluationId: sfb-1908-large-quality-v2
      status: automatic-checks-passed
      evaluatedActivities: 5
      automaticFailures: 0
      promptVersion: translation-en-pl-v2
      promptTokens: 2522
      completionTokens: 2385
      referenceCostUsd: 0.0048385
      humanReviewRequired: true
    promptV3Reason: preserve-clock-notation-and-participant-terms-after-sfb-027-failure
    promptV4Reason: prevent-inclusive-expansion-of-historical-masculine-participant-terms
    promptV5Reason: reject-any-invented-female-scout-term-when-source-has-no-girl
    promptV6Reason: preserve-word-versus-digit-number-representation-after-sfb-050-failure
    qualitySmokeV6:
      evaluationId: sfb-1908-large-quality-v6
      status: automatic-checks-passed
      evaluatedActivities: 5
      automaticFailures: 0
      referenceCostUsd: 0.005577
      humanReviewRequired: true
    productionRun:
      status: complete
      activityCount: 49
      promptVersion: translation-en-pl-v6
      promptTokens: 24896
      completionTokens: 12742
      referenceCostUsd: 0.031561
      billingMode: education-credit
      billedCostUsd: null
      referenceCostLimitUsd: 10
    largeVsMediumQualityV5:
      status: retain-owner-approved-large
      activityCountPerModel: 5
      large:
        automaticFailures: 0
        promptTokens: 3025
        completionTokens: 2345
        referenceCostUsd: 0.00503
        observedLanguageIssues:
          - "Trzech zające"
          - "każdemu z harcowników"
      medium:
        automaticFailures: 1
        promptTokens: 3025
        completionTokens: 2343
        referenceCostUsd: 0.02211
        observedLanguageIssues:
          - merged-indented-score-table-lines
          - "Trzy zające wyrusza się"
          - "co najmniej dwóch patrolowych"
    providerCode: "1910"
    accessiblePinnedAlternativesObserved:
      - mistral-medium-2604
      - mistral-small-2603
      - ministral-14b-2512
    billingMode: education-credit
    billedCostUsd: null
    maxReferenceCostUsd: 10
  buildValidation:
    status: passed
    generatedPolishRecords: 251
    generatedEnglishRecords: 251
    pagesBuilt: 516
    unitTests: 59
    internalLinksChecked: 14051
    slurm:
      initialSmokeJobId: "21945103"
      initialSmokeFailureReason: node-20-below-astro-minimum
      successfulSmokeJobId: "21945104"
      buildJobId: "21945121"
      partition: plgrid
      account: plgcredibleai2026-cpu
      nodeArchitecture: x86_64
      python: "3.12.3"
      node: "24.20.0"
      astro: "7.2.9"
      elapsed: "00:00:35"
      maxRss: "1324332K"
reviewRequired: false
publicationBlocked: false
---

# Zaakceptowany zakres: *Scouting for Boys* (1908)

## Decyzja

Właściciel repozytorium zatwierdził 3 września 2026 r. oryginalny angielski tekst wydania
Horace Cox z 1908 r. jako domenę publiczną w Polsce i zasadniczo w Unii Europejskiej. Decyzja
nie obejmuje automatycznie ilustracji, fotografii, późniejszej redakcji ani cyfrowego
opakowania Project Gutenberg.

Polska ustawa przewiduje dla utworu znanego autora okres życia twórcy i 70 lat, liczony w
pełnych latach po roku zdarzenia. Dyrektywa 2006/116/WE harmonizuje zasadę życia autora plus
70 lat w UE. World Scouting podaje, że Baden-Powell zmarł 8 stycznia 1941 r.; ochrona jego
samodzielnego tekstu wygasła zatem 31 grudnia 2011 r., a tekst jest w domenie publicznej od
1 stycznia 2012 r.

## Tożsamość materiału

- [Rekord Project Gutenberg](https://www.gutenberg.org/ebooks/65993) opisuje obiekt jako
  reprint Dover z 2007 r. tekstu z 1908 r.
- [Treść cyfrowa PG](https://www.gutenberg.org/files/65993/65993-h/65993-h.htm) zawiera karty
  sześciu części wydanych w Londynie przez Horace Cox w 1908 r.
- [Indeks The Dump](https://thedump.scoutscan.com/s4b.html) niezależnie opisuje publikację w
  odcinkach od 15 stycznia 1908 r. i wymienia wszystkie 28 gawęd ogniskowych.

Rozbieżność opisu Dover i wewnętrznych kart tytułowych nie blokuje zatwierdzonego zakresu:
do ekstrakcji kwalifikuje się wyłącznie tekst, którego obecność można potwierdzić w wydaniu
z 1908 r. Ewentualne późniejsze dodatki należy odrzucić.

## Ograniczenia źródeł cyfrowych

Project Gutenberg dodaje własną licencję i warunki używania znaku towarowego; tych elementów
nie należy kopiować jako części książki. The Dump prosi webmasterów o linkowanie zamiast
kopiowania książek i oznacza swoją warstwę serwisu licencją CC BY-NC-ND 3.0. Dlatego ten
serwis służy tutaj do odkrywania i porównywania metadanych, a jego pliki nie są pobierane do
korpusu.

Ilustracje pozostają wyłączone do czasu weryfikacji autorstwa każdego obrazu. Historyczne
porady wymagają również współczesnego przeglądu bezpieczeństwa przed publikacją jako
aktywności.

## Ekstrakcja

Z przypiętego hashem wydania HTML wybrano 49 jawnie opisanych gier z całej książki. Zakres
obejmuje strony drukowane 52–375. Nie skopiowano książki, ilustracji ani warstwy Project
Gutenberg; repozytorium zawiera wyłącznie rekordy aktywności i dowody ich położenia w źródle.

Debaty i próbny proces oraz taniec wojenny pozostają poza korpusem, ponieważ źródło nie
przedstawia ich jako gier, a dodatkowe rodzaje aktywności nadal wymagają decyzji redakcyjnej.
Osobno pominięto gry przypisane Setonowi lub innym autorom oraz grupę, którą książka opisuje
zbiorczo jako zapożyczoną z *Social—to Save*. Same nazwy popularnych sportów i odsyłacze bez
samodzielnych reguł również nie tworzą rekordów aktywności. Szczegółowy zakres, hashe bloków
i wynik deduplikacji zapisuje `data/reports/pg-65993-extraction.json`.
