# Kolejka recenzji

Tu trafiają propozycje źródeł, aktywności, tłumaczeń i decyzji prawnych. Wpis nie jest
zatwierdzeniem. Pierwsze kierunki badawcze opisuje `config/research-queue.yaml`.

Rekordy `candidate-*.md` dokumentują etap `discover` dla jednej konkretnej edycji. W tym
katalogu pozostają `rights-review`, używają metody dozwolonej w
`config/source-registry.yaml`, wskazują dowody proweniencji i blokują pełny tekst, ilustracje,
tłumaczenie oraz publikację do czasu decyzji człowieka albo dopasowania zatwierdzonej polityki
kolekcji. Dla Project Gutenberg stosuje się politykę
`project-gutenberg-pd-usa-plus-life-70`: wymaga ona zarówno oznaczenia `Public domain in the
USA`, jak i udokumentowanego upływu 70 pełnych lat od śmierci ostatniego właściwego autora.

Niejasność nie kończy researchu. Przed przekazaniem decyzji człowiekowi agent sprawdza
autora, datę śmierci, zasady liczenia okresu ochrony, tożsamość wydania i odrębne prawa do
tekstu, ilustracji, tłumaczenia oraz cyfrowego opakowania w dostępnych wiarygodnych źródłach.
Po decyzji człowieka lub jednoznacznym dopasowaniu zatwierdzonej polityki rekord trafia do
`../accepted/` albo `../rejected/` wraz z zakresem rozstrzygnięcia.

Rekordy `source-component-scope` dokumentują proponowany zakres stron lub bloków już
zatwierdzonego źródła. Sam zapis propozycji nie odblokowuje OCR-u ani publikacji; właściwa
konfiguracja wykonawcza może zostać uzupełniona dopiero po jawnej decyzji człowieka.

`semantic-map-v3-pair-review.md` jest deterministycznym pakietem porównawczym par wskazanych
przez embeddingi, niewłączanym do publicznej strony. Zawarte w nim podobieństwo, rangi i
fragmenty są materiałem do recenzji, nie relacją produkcyjną. Decyzję zapisuje się osobno;
dopiero zatwierdzona para może trafić do `config/similar-activities.yaml` jako symetryczny
link.
