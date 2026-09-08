---
id: v3-component-authorship-2026-09
recordType: component-authorship-batch
status: accepted
createdAt: "2026-09-07"
reviewRequired: false
humanApproved: true
approvedAt: "2026-09-07"
approvedBy: repository-owner
runId: v3-source-expansion-2026-09
candidateCount: 760
importedActivityCount: 0
decision: explicit-library-public-domain-status-is-ground-truth
---

# V3-R1 — status prawny cyfrowych wydań

OCR i ekstrakcja dały 760 lokalizatorów kandydatów w ośmiu książkach. Raporty kandydatów
zawierają wyłącznie tytuły, numery stron lub widoków, cechy techniczne i hashe; pełna treść
OCR pozostaje w prywatnym, ignorowanym przez Git `artifacts/` także po imporcie, aby umożliwić
ponowną kontrolę.

## Zatwierdzona reguła

Właściciel repozytorium 7 września 2026 r. zatwierdził jawne oznaczenie konkretnego wydania
przez bibliotekę, archiwum lub zbiór cyfrowy jako rozstrzygający dowód domeny publicznej
udostępnionej zawartości. Jeżeli takie oznaczenie występuje, projekt nie wylicza ponownie
terminów ochrony poszczególnych wkładów i nie blokuje opisów z powodu informacji o
współpracownikach lub wcześniejszych źródłach. Nadal trzeba zachować dokładne wydanie,
kanoniczny URL, brzmienie statusu, atrybucję i warunki użycia reprodukcji.

Dopiero przy braku jednoznacznego oznaczenia instytucji stosuje się analizę autorstwa i
upływu 70 pełnych lat od śmierci autora. Ta reguła nie pozwala zgadywać statusu, rozszerzać
go na inne wydanie ani omijać warunków dostępu dostawcy.

## Skutek dla ośmiu zinwentaryzowanych książek

| Źródło | Kandydaci | Dowód instytucjonalny | Skutek |
| --- | ---: | --- | --- |
| J. Jasiński, *Gry i ćwiczenia terenowe* (1938) | 181 | Polona: konkretny obiekt oznaczony jako niechroniony i możliwy do pobrania | Opisy gier w obiekcie kwalifikują się do przeglądu i importu. |
| H. Mojmir, *Ćwiczenia i zabawy skautowe* (1912) | 85 | Polona: konkretny obiekt oznaczony jako niechroniony i możliwy do pobrania | Wskazanie wcześniejszych zbiorów nie blokuje importu opisów. |
| J. Dąbrowski, *Gry i zabawy w izbie harcerskiej* (1934) | 183 | Polona: `Domena publiczna` / obiekt niechroniony | Wkłady harcerzy, W. Dehnela i materiał związany ze zbiorem Ewy Grodeckiej nie są osobną bramką prawną dla tego wydania. |
| E. Piasecki, *Zabawy i gry ruchowe dzieci i młodzieży* (1922) | 133 | KPBC: `Domena publiczna (public domain)` | Opisy kwalifikują się; muzykę, teksty pieśni i ilustracje pomijamy jako elementy poza zakresem produktu. |
| A. Pawełek, *Młoda drużyna* (1919) | 115 | Podlaska Biblioteka Cyfrowa: `Domena publiczna` | Przegląd akapitów wyodrębnił 61 samodzielnych gier i ćwiczeń współzawodniczych; pozostałe kandydatury zachowano w raporcie jako skróty, ćwiczenia techniczne, zadania obserwacyjne albo opisy zależne od innych reguł. |
| *W gromadzie zuchów* (1945) | 74 | Polona: konkretny obiekt oznaczony jako niechroniony i możliwy do pobrania | Zakres podpisu Hanny Kopciówny pozostaje informacją o atrybucji, ale nie blokuje prawnie opisów z tego obiektu. |
| M. Schreiber i E. Piasecki, *Harce młodzieży polskiej* (1917) | 40 | WBC: `Domena publiczna` i otwarty dostęp do wskazanego wydania | Wkłady współpracowników nie są osobną bramką prawną dla tego wydania. |
| S. Sedlaczek, *Szkoła harcerza* (1921) | 40 | ŚBC: `Domena publiczna` | Gry pochodzące od Mojmira, Cenara i Jaroszyńskiego kwalifikują się z zachowaniem atrybucji. |

Status domeny publicznej nie zmienia zakresu V3: importujemy samodzielne gry, nie okładki,
fotografie, nuty ani całe książki. Nie rekonstruujemy brakujących lub uszkodzonych stron.
Sygnały autorstwa są zachowywane jako proweniencja i materiał do badań podobieństwa, a nie
jako mechanizm blokujący publikację.

## Zapis decyzji właściciela

> Traktujemy informacje z bibliotek i cyfrowych zbiorów jako ground truth. Jeżeli konkretne
> wydanie jest przez instytucję oznaczone jako domena publiczna, projekt przyjmuje ten status.
> Jeżeli takiej informacji nie ma, dopiero wtedy wnioskujemy na podstawie autorstwa i daty
> śmierci.
