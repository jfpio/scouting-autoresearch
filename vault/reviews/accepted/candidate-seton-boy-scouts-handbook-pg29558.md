---
id: source-candidate-seton-boy-scouts-handbook-pg29558
recordType: source-candidate
status: accepted
createdAt: "2026-09-04"
reviewedAt: "2026-09-04"
subjectId: ernest-thompson-seton
sourceType: bibliographic-metadata
title: Boy Scouts Handbook — The Games (Chapter VIII)
author:
  name: Ernest Thompson Seton
  lifeDates: 1860-1946
originalLanguage: en
collectionId: project-gutenberg
collectionStatusAtDiscovery: approved-by-policy
allowedMethodUsed: documented-download
canonicalUrl: https://www.gutenberg.org/ebooks/29558
digitalEdition:
  identifier: pg-29558
  releaseDate: "2009-08-01"
  lastUpdated: "2021-01-05"
  catalogEditionStatement: "Boy Scouts Handbook: The First Edition, 1911."
  internalImprint:
    publisher: Doubleday, Page & Company
    place: Garden City, New York
    year: 1911
    copyrightHolder: Boy Scouts of America
  editionIdentityStatus: identified
  digitalCredits:
    - Don Kostuch
rightsReview:
  status: policy-approved
  rightsStatus: public-domain
  jurisdiction: Poland under the harmonized European Union term framework
  humanApproved: true
  approvalPolicyId: project-gutenberg-pd-usa-plus-life-70
  catalogClaim: public-domain-in-the-usa
  approvedScope:
    - English text on printed pages 291-319 under The Games, explicitly attributed to Ernest Thompson Seton
  fullTextEligible: true
  imagesEligible: false
  translationEligible: true
  calculation:
    relevantAuthors:
      - name: Ernest Thompson Seton
        deathDate: "1946-10-23"
        evidenceId: library-of-congress-seton-authority
    lastRelevantAuthorDeathDate: "1946-10-23"
    protectionTerm: life-plus-70-years
    protectionEnded: "2016-12-31"
    publicDomainFrom: "2017-01-01"
  excludedComponents:
    - Project Gutenberg license, header, footer, trademark and digital packaging
    - all handbook chapters and components not explicitly within the approved Seton scope
    - Outdoor Athletic Standards beginning on printed page 320
    - Mumbly Peg, explicitly credited within the chapter to Daniel Carter Beard
    - illustrations, captions, advertisements and editorial apparatus
    - any entry whose item-level attribution conflicts with the chapter attribution
  reuseConditions:
    - Preserve the historical wording and Seton's component-level authorship.
    - Exclude explicit contributions by other authors before extraction.
    - Compare exact and near variants with the existing Scouting for Boys records.
    - Link the Project Gutenberg record and the page-aware digital text.
    - Apply current safety review before practical use of historical instructions.
provenanceEvidence:
  - id: project-gutenberg-catalog-29558
    url: https://www.gutenberg.org/ebooks/29558
    supports:
      - ebook-identifier
      - first-edition-statement
      - release-and-update-dates
      - digitization-credit
      - public-domain-claim-usa
  - id: project-gutenberg-html-29558-title
    url: https://www.gutenberg.org/files/29558/29558-h/29558-h.htm
    supports:
      - internal-title-page
      - 1911-imprint
      - Boy-Scouts-of-America-copyright-notice
      - Project-Gutenberg-transcription-notes
  - id: project-gutenberg-html-29558-seton-games
    url: https://www.gutenberg.org/files/29558/29558-h/29558-h.htm#Page_291
    supports:
      - chapter-VIII-boundary
      - The-Games-attribution-to-Ernest-Thompson-Seton
      - printed-page-boundaries
      - explicit-Daniel-Carter-Beard-contribution
  - id: library-of-congress-seton-authority
    url: https://lccn.loc.gov/n79129037
    supports:
      - Ernest-Thompson-Seton-identity
      - birth-date
      - death-date
  - id: polish-copyright-act-articles-36-and-39
    url: https://isap.sejm.gov.pl/isap.Nsf/download.xsp/WDU20000800904/T/D20000904L.pdf
    supports:
      - Polish-life-plus-70-protection-term
      - full-calendar-year-calculation
  - id: eu-directive-2006-116-ec-article-1
    url: https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32006L0116
    supports:
      - European-Union-life-plus-70-protection-term
discovery:
  discoveredAt: "2026-09-04"
  metadataPagesInspected: 6
  sourceFilesDownloaded: 2
  fullTextCopied: false
  repositoryContentAdded: activity-excerpts
  estimatedCostUsd: 0
processing:
  sourceId: bsh-1911-seton-games
  sourceSha256: f6ba6ea041a93d91c060b64bbc39b7361bab94085466b1ad39d27512f48b4791
  parserVersion: gutenberg-text-paragraphs-v1
  extractionReport: data/reports/pg-29558-extraction.json
  curatedCandidateCount: 39
  importedActivityCount: 33
  importedKinds: [game]
  wholeSourceCopiedToRepository: false
  imagesCopiedToRepository: false
  excludedAttributionRanges:
    - Lion Hunting through Hare and Hounds, explicitly attributed to General Baden-Powell
    - Mumbly Peg, explicitly attributed to Daniel Carter Beard
  excludedExistingVariants:
    - {candidateId: bsh-028, existingId: sfb-001, title: Arctic Expedition, wordShingleJaccard: 0.681159}
    - {candidateId: bsh-029, existingId: sfb-041, title: Dragging Race, wordShingleJaccard: 0.405}
    - {candidateId: bsh-030, existingId: sfb-015, title: Far and Near, wordShingleJaccard: 0.527897}
    - {candidateId: bsh-031, existingId: sfb-049, title: Fire-lighting Race, wordShingleJaccard: 0.5}
    - {candidateId: bsh-033, existingId: sfb-027, title: Mountain Scouting, wordShingleJaccard: 0.895833}
    - {candidateId: bsh-034, existingId: sfb-036, title: Knight Errantry, wordShingleJaccard: 0.852941}
  postExclusionDeduplication:
    exactBodyMatches: 0
    nearDuplicateThreshold: 0.45
    nearDuplicateCandidates: 0
  translation:
    status: complete
    productionCandidate: mistral-large-2512
    cheaperCandidate: mistral-small-2603
    evaluationConfig: config/translation-model-evaluations/bsh-1911-large-vs-small.yaml
    evaluationActivityCount: 5
    reasoningMode: disabled
    decision: retain-mistral-large-2512
    evaluation:
      status: complete
      completedAt: "2026-09-04"
      large:
        automaticFailures: 0
        promptTokens: 4103
        completionTokens: 3606
        referenceCostUsd: 0.0074605
      small:
        automaticFailures: 1
        failedActivityIds: [bsh-023]
        promptTokens: 4103
        completionTokens: 3670
        referenceCostUsd: 0.00281745
        observedLanguageIssues:
          - changed-number-words-to-digits
          - "mataami"
          - "Turniej konny i jeździec"
          - "paga"
    productionRun:
      status: complete
      activityCount: 33
      modelRequested: mistral-large-2512
      model: mistral-large-2512
      promptVersion: translation-en-pl-v6
      reasoningMode: disabled
      promptTokens: 19487
      completionTokens: 12957
      referenceCostUsd: 0.029179
      billingMode: education-credit
      billedCostUsd: null
      referenceCostLimitUsd: 10
  buildValidation:
    status: passed
    generatedPolishRecords: 284
    generatedEnglishRecords: 284
    totalGames: 199
    totalTrials: 85
    pagesBuilt: 582
    unitTests: 61
    internalLinksChecked: 15866
    slurm:
      buildJobId: "21946098"
      baseRevision: 9e33a85d233f7d67fe99415a9058d3e60404e3a7
      partition: plgrid
      account: plgcredibleai2026-cpu
      node: x1000c5s7b0n1
      nodeArchitecture: x86_64
      python: "3.12.3"
      nodeJs: "24.20.0"
      astro: "7.2.9"
      elapsed: "00:00:50"
      maxRss: "1551488K"
reviewRequired: false
publicationBlocked: false
---

# Zaakceptowany zakres: rozdział gier Setona z *Boy Scouts Handbook* (1911)

Project Gutenberg opisuje eBook 29558 jako pierwsze wydanie *Boy Scouts Handbook* z 1911 r.
i oznacza go jako „Public domain in the USA”. Wewnątrz książki rozdział VIII rozpoczyna na
stronie 291 część „The Games” z bezpośrednim podpisem „By Ernest Thompson Seton, Chief
Scout”. Następna część, „Outdoor Athletic Standards”, zaczyna się na stronie 320 i nie jest
objęta zakresem.

Library of Congress identyfikuje Setona jako autora żyjącego w latach 1860–1946 i podaje
datę śmierci 23 października 1946 r. Zgodnie z zatwierdzoną polityką Project Gutenberg oraz
zasadą życia autora i 70 pełnych lat ochrona jego tekstu wygasła 31 grudnia 2016 r.; zakres
jest w domenie publicznej w Polsce i UE od 1 stycznia 2017 r.

Podręcznik jest dziełem zbiorowym, dlatego decyzja nie obejmuje go jako całości. Import może
objąć wyłącznie wskazaną część Setona po kontroli atrybucji każdej gry. „Mumbly Peg” jest
wewnątrz rozdziału jawnie przypisane Danielowi Carterowi Beardowi i pozostaje wyłączone.
Ilustracje, podpisy, reklamy, standardy sportowe i cyfrowa warstwa Project Gutenberg również
nie wchodzą do korpusu.

Rozdział powtarza lub wariantuje liczne gry obecne już w *Scouting for Boys*. Przed importem
trzeba więc porównać pełne teksty, odrzucić dokładne duplikaty i jawnie raportować bliskie
warianty zamiast mnożyć rekordy bez informacji o relacji.
