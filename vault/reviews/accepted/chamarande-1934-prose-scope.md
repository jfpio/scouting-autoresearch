---
id: chamarande-1934-prose-scope
recordType: source-component-scope
status: proposed
createdAt: "2026-09-05"
reviewRequired: true
publicationBlocked: true
humanApproved: false
subjectId: jacques-sevin
sourceId: chamarande-1934
collectionId: gallica-bnf
digitalEditionIdentifier: bpt6k3373518k
canonicalUrl: https://gallica.bnf.fr/ark:/12148/bpt6k3373518k
requiredAttribution: Source gallica.bnf.fr / Bibliothèque nationale de France
inspection:
  method: visual-inspection-of-pinned-iiif-views-and-contact-sheets
  titlePageEvidence:
    view: 13
    finding: The title page attributes Chamarande to Jacques Sevin, S.J.
  paginationEvidence:
    viewCount: 188
    numericPrintedPages: 133
    printedPageRange: 9-141
    sha256: 48989b68bd51b00725dbf336f5fbfcbff3d3fe38fc4585078665b8c4daf74277
  contactSheetJob:
    scheduler: slurm
    jobId: "21977902"
    status: complete
    architecture: x86_64
    partition: plgrid
    account: plgcredibleai2026-cpu
    sourceRevision: fa9a28cad3269eee6dac2c2c921c32f385a68019
    outputs:
      - order: gallica-view
        sha256: 1add67f59d63dc75c01d04be389e61c6338c227b7c0a226a17f052d75dc446d9
      - order: numeric-printed-page
        sha256: 09684f92770a924b79c7611f037f84f6ed0471e37a79f9204ac997a9dc82efb9
proposedOcrScope:
  purpose: segment-and-extract-only-jacques-sevin-prose
  executionReady: false
  proposedViewRanges:
    - [19, 26]
    - [29, 36]
    - [39, 46]
    - [49, 64]
    - [67, 70]
    - [83, 84]
    - [87, 94]
    - [97, 104]
    - [107, 107]
    - [109, 109]
    - [111, 114]
    - [117, 123]
    - [127, 134]
    - [137, 144]
    - [147, 154]
    - [157, 170]
  proposedViewCount: 113
  plannedModel: mistral-ocr-4-1
  referencePriceUsdPer1000Pages: 4.0
  referenceCostEstimateUsd: 0.452
  billedCostUsd: null
  proposedPrintedPages:
    - 9-36
    - 47-81
    - "83"
    - 85-95
    - 97-134
  rawOcrStorage: scratch-only
  publicationRule: >-
    A page being eligible for technical OCR does not make every block on that page eligible
    for the corpus. Only blocks attributable to Jacques Sevin may leave scratch and enter a
    transcription or activity record.
  mixedPagesRequiringBlockReview:
    - printedPages: "17"
      views: [29]
      excludeBlocks: [quoted Cantique de la Promesse verse]
    - printedPages: 34-36
      views: [68, 69, 70]
      excludeBlocks:
        - participant testimonials signed M, R, P and J
        - joint telegram attributed to General de Salins, Cornette and Sevin
        - reply signed Delabar
        - beginning of an anonymous letter about the first training course
    - printedPages: 64-65
      views: [64, 87]
      excludeBlocks: [participant testimonials introduced as quotations]
    - printedPages: "81"
      views: [107]
      excludeBlocks: [telegram signed collectively by camp leaders]
    - printedPages: "83"
      views: [109]
      excludeBlocks: [letter signed Robert Baden-Powell]
    - printedPages: 92-93
      views: [120, 121]
      excludeBlocks: [anonymous response quoted from a course evaluation]
excludedScope:
  wholePrintedPageRanges:
    - printedPages: 37-38
      views: [71, 72]
      reason: anonymous letter about the first training course
    - printedPages: 39-46
      views: [73, 74, 77, 78, 79, 80, 81, 82]
      reason: >-
        article signed D. G. with speeches and letters by General de Salins, Robert
        Baden-Powell and Hubert Martin
    - printedPages: "82"
      views: [108]
      reason: blank page
    - printedPages: "84"
      views: [110]
      reason: blank page
    - printedPages: "96"
      views: [124]
      reason: blank page
    - printedPages: 135-141
      views: [171, 172, 173, 174, 175, 176, 177]
      reason: photograph, blank pages, memorial list, music, lyrics and table of contents
  nonnumberedViews: all
  components:
    - photographs, plates, illustrations and cover
    - music and verse
    - text explicitly attributed to another author or an anonymous contributor
    - later editorial apparatus and Gallica digital packaging
humanDecision:
  status: pending
  approvedBy: null
  reviewedAt: null
  approvedViewRanges: []
  notes: null
---

# Proponowany zakres prozy w *Chamarande* (1934)

Strona tytułowa `f13` przypisuje książkę Jacques’owi Sevinowi. Nie wystarcza to jednak do
przypisania mu wszystkich składników tomu: wewnątrz znajdują się cudze listy, przemówienia,
anonimowe świadectwa, fotografia, lista memorialna, nuty i tekst pieśni. Powyższy zakres
obejmuje strony zawierające prozę autorską Sevina, ale sześć grup stron mieszanych wymaga
klasyfikacji bloków po OCR. Pełne wyniki tych stron pozostają wyłącznie w scratch.

Największym zwartym wyłączeniem są strony 39–46. Zaczynają się jako przedruk z *Le Chef*,
tekst główny kończy się podpisem `D. G.`, a w środku i na końcu znajdują się wypowiedzi lub
listy innych osób. Strony 37–38 są dalszym ciągiem anonimowego listu, a strona 83 zawiera
list Baden-Powella. Końcowe strony 135–141 nie są prozą Sevina kwalifikującą się do tego
pipeline’u.

Ten rekord jest propozycją, nie zgodą. Do czasu decyzji właściciela
`config/ocr/chamarande-1934.yaml` zachowuje `executionReady: false` i puste
`approvedViewRanges`. Zatwierdzenie zakresu pozwoli jedynie na sekwencyjny OCR 113 obrazów
do scratch oraz późniejszą recenzję bloków. Nie zatwierdzi automatycznie transkrypcji,
aktywności, tłumaczeń ani publikacji.
