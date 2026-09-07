#!/usr/bin/env python3
"""Import reviewed games from Piasecki's pinned 1922 embedded-text layer."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, dump_markdown, persisted_artifact_path, read_json, source_hash, write_json
from inventory_piasecki_movement_games import logical_lines, normalize_space


SOURCE_ID = "piasecki-movement-games-1922"
PREFIX = "zgr"
SOURCE_URL = "https://kpbc.umk.pl/dlibra/publication/183639/edition/193867"
PDF_URL = "https://kpbc.umk.pl/Content/193867/PDF/Magazyn_265_06_HD_008.pdf"
REPORT_PATH = ROOT / "data" / "reports" / f"{SOURCE_ID}-candidates.json"
INSPECTION_PATH = ROOT / "data" / "checkpoints" / "source-inspection" / f"{SOURCE_ID}.json"


REJECTED_REASONS = {
    2: "cross-reference-only variant of game 1 without a self-contained setup",
    16: "cross-reference-only variant of game 15 whose only supplied difference is a song outside this corpus scope",
    18: "song-dependent movement sequence without a self-contained procedure after lyrics are excluded",
    20: "song-dependent occupational movement sequence without a self-contained procedure after lyrics are excluded",
    38: "cross-reference-only variant of game 37 without a self-contained setup",
    39: "cross-reference-only variant of game 38 without a self-contained setup",
    41: "cross-reference-only variant of game 40 without a self-contained setup",
    43: "cross-reference-only variant of game 42 without a self-contained setup",
    45: "cross-reference-only variant of game 44 without a self-contained setup",
    46: "variant that imports its complete playing-area setup from game 45",
    53: "variant of the preceding blindfold game without a self-contained base procedure",
    58: "cross-reference-only tag variant without a self-contained procedure",
    68: "variant defined only by its difference from game 67",
    92: "variant expressed only as amendments to game 91 rather than a self-contained procedure",
    126: "variant defined as changes to game 124b rather than a self-contained procedure",
    132: "variant defined as amendments to game 131 rather than a self-contained procedure",
}


TITLE_OVERRIDES = {
    1: "Ptaszek",
    2: "Bąk",
    3: "Chusteczka jedwabna",
    4: "Stoi różyczka",
    6: "Na około wciąż wędruję",
    8: "Konopki",
    9: "Zameczek",
    10: "Jawor",
    12: "Zelman",
    13: "Ogroduszek",
    14: "Nawlekanie igły",
    15: "Ojciec Wirgiljusz",
    17: "Rzemiosła (Muzykant)",
    18: "Mak",
    19: "Królewna",
    20: "Wybór",
    21: "Wdowa na wydaniu",
    22: "Przepiórka",
    23: "Gąska",
    24: "Pasterz",
    25: "Róża",
    27: "Swaty",
    29: "Kokoszka",
    31: "Zajączki",
    32: "Bóbr",
    33: "Krycie",
    35: "Sitko",
    37: "Kółko",
    41: "Poczta",
    48: "Gąsior",
    49: "Koło",
    54: "Derkacz",
    59: "Topiec",
    61: "Król",
    64: "Kot i mysz",
    67: "Klapanka",
    69: "Wąż",
    71: "Płótno",
    73: "Fabjan",
    75: "Żóraw",
    78: "Wójt",
    80: "Plinje",
    84: "Klasy",
    94: "Złota kula",
    96: "Kamyczki",
    97: "Bierki",
    100: "Ducza",
    101: "Pikier",
    104: "Kolbiki",
    106: "Śnieżki",
    112: "Kowal",
    114: "Stójka",
    116: "Dotki",
    117: "Trójmetki",
    118: "Ekstra (Ekstrameta)",
    119: "Zbijany",
    120: "Wyścig pił w dwuszeregu",
    121: "Koszykowa",
    123: "Krąg",
    124: "Kiczka prosta",
    125: "Kiczka z matkami",
    126: "Kiczka rzymska",
    127: "Stręk",
    128: "Matka i córka",
    129: "Wieko",
    130: "Palant prosty",
    131: "Palant z matkami, bez galenia",
    132: "Palant z galeniem",
    133: "Pięstówka",
}


# Inclusive global logical-line ranges removed from otherwise accepted records.
# They contain musical notation, song lyrics or isolated illustration text.
OMITTED_RANGES = {
    1: (("p0060-l0017", "p0061-l0011"),),
    3: (("p0062-l0005", "p0062-l0015"),),
    4: (("p0063-l0002", "p0063-l0005"),),
    5: (("p0063-l0014", "p0063-l0020"),),
    6: (("p0064-l0005", "p0064-l0020"),),
    7: (("p0065-l0008", "p0065-l0011"),),
    8: (("p0065-l0020", "p0066-l0001"),),
    9: (("p0066-l0028", "p0067-l0009"),),
    10: (("p0068-l0001", "p0068-l0011"),),
    11: (
        ("p0069-l0001", "p0069-l0001"),
        ("p0069-l0006", "p0069-l0015"),
        ("p0069-l0018", "p0070-l0005"),
    ),
    12: (("p0070-l0016", "p0071-l0016"),),
    13: (("p0072-l0005", "p0072-l0006"), ("p0072-l0010", "p0072-l0021")),
    15: (("p0073-l0030", "p0074-l0010"),),
    19: (("p0077-l0014", "p0078-l0007"),),
    21: (("p0080-l0004", "p0080-l0022"), ("p0080-l0027", "p0080-l0030")),
    22: (("p0081-l0015", "p0083-l0005"),),
    23: (("p0084-l0016", "p0084-l0021"),),
    25: (
        ("p0085-l0009", "p0085-l0017"),
        ("p0085-l0021", "p0085-l0023"),
        ("p0086-l0002", "p0086-l0004"),
        ("p0086-l0019", "p0086-l0028"),
    ),
    26: (("p0087-l0007", "p0087-l0011"), ("p0087-l0014", "p0087-l0015")),
    27: (("p0088-l0001", "p0088-l0024"),),
    28: (("p0089-l0004", "p0089-l0012"),),
    29: (("p0090-l0008", "p0090-l0014"),),
    30: (("p0091-l0018", "p0091-l0032"),),
    31: (("p0092-l0024", "p0094-l0032"),),
    32: (("p0095-l0004", "p0095-l0008"),),
    35: (("p0097-l0012", "p0097-l0015"),),
    50: (("p0102-l0023", "p0103-l0013"),),
    63: (("p0109-l0015", "p0109-l0027"),),
    64: (("p0110-l0021", "p0111-l0010"),),
    69: (("p0114-l0014", "p0114-l0023"),),
    75: (("p0119-l0012", "p0119-l0016"),),
    85: (("p0134-l0020", "p0134-l0026"),),
}


ILLUSTRATION_RANGES = {
    77: (("p0121-l0014", "p0121-l0020"),),
    80: (("p0123-l0010", "p0123-l0010"), ("p0123-l0026", "p0123-l0026")),
    84: (("p0133-l0011", "p0133-l0011"),),
    91: (("p0156-l0002", "p0156-l0003"),),
    97: (("p0173-l0008", "p0173-l0009"),),
    103: (
        ("p0178-l0011", "p0178-l0011"),
        ("p0178-l0016", "p0178-l0016"),
        ("p0178-l0028", "p0178-l0028"),
        ("p0178-l0031", "p0178-l0031"),
        ("p0179-l0004", "p0179-l0037"),
    ),
    121: (("p0199-l0001", "p0199-l0001"), ("p0201-l0007", "p0201-l0008")),
    131: (("p0219-l0029", "p0219-l0029"), ("p0219-l0033", "p0219-l0033")),
    133: (
        ("p0229-l0035", "p0229-l0035"),
        ("p0230-l0025", "p0230-l0025"),
        ("p0231-l0001", "p0231-l0001"),
    ),
}


# The automatic title locator missed the printed heading for game 131 because its
# first rule begins on the next page with the word "Palant". Keep the detector's
# original span hash as an audit check, then widen the reviewed import here.
START_OVERRIDES = {131: "p0218-l0013"}


# Footnotes occur in the middle of the PDF layout stream. Remove them from that
# position and append their exact text after the game so they do not split a rule.
RELOCATED_FOOTNOTE_RANGES = {
    66: (("p0112-l0031", "p0112-l0033"),),
    97: (("p0172-l0031", "p0172-l0032"),),
    100: (("p0175-l0029", "p0175-l0030"),),
    121: (("p0200-l0029", "p0200-l0034"),),
    131: (("p0219-l0036", "p0219-l0036"),),
}

RELOCATED_FOOTNOTES = {
    66: (
        "¹) W Krakowskiem grywają tu i ówdzie tę odmianę pod nazwą „Sitko“, "
        "w Kutnowskiem pod nazwą „Pasterz“."
    ),
    97: "¹) U Gołębiowskiego figury te noszą nazwy króla, ekonoma, pana, wójta, gospodarza, parobka itd.",
    100: "¹) Podobną grę opisuje Gołębiowski pod nazwą „G r e l e“ lub „K r e l e“.",
    121: (
        "¹) Jak widać na rycinie, uczestniczki ustawiają się parami, złożonemi każda z dwóch "
        "przeciwniczek, np.: obrona czerwonych (przy własnym koszyku) i napad białych, środek "
        "czerwonych i białych, napad czerwonych i obrona białych. Przeciwniczki każdej pary "
        "„pilnują się“ nawzajem, przeszkadzając rzutom ruchami rąk i tułowia."
    ),
    131: "¹) Patrz Cz. ogólna, V a.",
}


# These source lines combine prose retained in the corpus with an excluded song lead-in.
LINE_REPLACEMENTS = {
    "p0060-l0016": "w środku koła.",
    "p0062-l0004": "żąc.",
    "p0062-l0026": "częta, krążąc w koło.",
    "p0065-l0007": "niczka“.",
    "p0066-l0027": "siebie, postępujące wprzód i wtył.",
    "p0069-l0017": "5, 4, 3, 2, 1 na rycinie).",
    "p0072-l0009": "czyna taki sam pochód i t. d.",
    "p0073-l0029": "ciec Wirgiljusz). Wszystkie, krążąc wkoło.",
    "p0080-l0003": "wśród śpiewu; w środku koła wdowa, na obwodzie jej córki.",
    "p0080-l0026": "przy poprzednich zwrotkach, poskakuje.",
    "p0081-l0014": "wym.",
    "p0085-l0008": "wnątrz koła.",
    "p0087-l0006": "kiem tanecznym.",
    "p0087-l0030": "gdy się cofają.",
    "p0097-l0011": "kredą.",
    "p0109-l0014": "Dzieci tworzą koło, trzymając się za ręce.",
    "p0109-l0028": "Po odśpiewaniu piosenki dzieci rozbiegają",
    "p0112-l0010": "pod nazwą „Pytki“¹), odpowiednia dla szkół",
    "p0112-l0015": "dopóki jej komu nie poda misternie; ten bije",
    "p0112-l0030": "niają miejsca¹).",
    "p0113-l0001": "",
    "p0113-l0007": "Podczas obchodzenia lisa dzieci wołają:",
    "p0119-l0011": "tworzy koło i krąży dokoła żórawia.",
    "p0120-l0017": "ludowi. Gra idzie tak dłu­",
    "p0120-l0018": "go z ciągłą zmianą met,",
    "p0120-l0020": "się w niewolę. Ostatni schwytany jest cz. lu­",
    "p0121-l0025": "regoś z biegaczy (uderzając go piłką, lub dło­",
    "p0121-l0031": "½ godziny) dostarczył mniej królów.",
    "p0123-l0009": "Opierając się",
    "p0123-l0023": "boków a na 3 m.",
    "p0123-l0024": "ku środkowi bo­",
    "p0123-l0025": "iska, kreśli się obie",
    "p0132-l0011": "podłodze (długość boku każdego",
    "p0132-l0014": "czek do „klasy“ 1. Potem wska­",
    "p0132-l0017": "skakuje tak samo. Jeśli kamy­",
    "p0132-l0020": "na obie nogi, próba liczy się",
    "p0132-l0023": "miast 2). Gdy wszyscy spróbują",
    "p0133-l0003": "z zamkniętemi oczyma, 3) prze­",
    "p0133-l0005": "b) Klasy z „niebem“, „pie­",
    "p0133-l0006": "kłem“ i „morzem“. Podobnie",
    "p0133-l0007": "jak a), tylko skacze się częścią",
    "p0133-l0008": "obunóż (w rozkroku), częścią",
    "p0133-l0014": "tem wstecz w poskoku, a po­",
    "p0133-l0028": "czyli Ślimak (Lwów). Gra­",
    "p0133-l0030": "do ślimacznicy nakreślonej",
    "p0133-l0033": "spiralnie aż do środka;",
    "p0133-l0035": "tem. Komu uda się odbyć",
    "p0134-l0019": "i wrysowuje w nie krzyż.",
    "p0156-l0006": "Zwykłe jego miejsce jest na 1—1½ m przed",
    "p0172-l0013": "nież mało ruchu, lecz wiele sposobności do",
    "p0172-l0018": "z drzewa, długości 1½—8 cm., szerokości",
    "p0172-l0019": "½—2 cm. Wszystkie bierki, używane przy da­",
    "p0172-l0024": "„bydlęta“ (lub „liszki“¹).",
    "p0173-l0015": "1) Technika chwytów jest trojaka: albo po",
    "p0178-l0010": "kręgle jednej strony są ozna­",
    "p0178-l0012": "czone obwódką barwną, albo",
    "p0178-l0015": "nych o średnicy 18 cm. Każdy",
    "p0178-l0017": "obóz liczy przy zawodach 8",
    "p0178-l0018": "uczestników; w grach ćwi­",
    "p0178-l0019": "czebnych liczba jest dowolna,",
    "p0178-l0020": "bo miarą równości obozów",
    "p0178-l0025": "swojej woli, pilnując tylko,",
    "p0178-l0026": "a b y: 1) przynajmniej jeden,",
    "p0178-l0027": "a nie więcej niż 6 kręgli",
    "p0178-l0029": "stało na mecie, 2) by całe",
    "p0178-l0030": "ustawienie nie było nigdzie",
    "p0183-l0005": "Chłopcy stają każdy w odległości 5½ m",
    "p0183-l0020": "stępnie kolejno z 5½-metrowej odległości",
    "p0188-l0018": "Uczestnicy, w liczbie 5—20, wybierają je­",
    "p0179-l0002": "grających tak, aby wykluczyć przewagę jednego",
    "p0216-l0023": "Palant, w swoich licznych odmianach, z któ­",
    "p0217-l0010": "Gra powszechna wśród chłopców miejskich,",
    "p0217-l0015": "a) B e z  w y k u p n a. Wybrany („wymie­",
    "p0217-l0033": "mykiem, chorągiewką i. t. p.) „metę“, podbi­",
    "p0218-l0015": "Przysłowie z w. XIV.",
    "p0218-l0019": "1) P o l e  g r y jest prostokątem, którego",
    "p0218-l0028": "najmniej 1½ m., silnie wkopane w ziemię.",
    "p0220-l0011": "lestwa. Obóz traci królestwo: a) gdy gracz",
    "p0220-l0013": "lantem w ręce wyjdzie lub wybiegnie poza",
    "p0220-l0025": "kupnika: 2 podbić, u matki: 3) przysługuje",
    "p0221-l0024": "jest nieważne, jeśli ten w czasie skucia doty­",
    "p0222-l0007": "stwo z początkiem gry, utrzymał się na niem",
    "p0222-l0012": "danego obozu podbijali i wykupili się, obóz",
    "p0222-l0016": "dwie kreski.",
    "p0224-l0008": "Dla chwytów piłki podbitej nieodzownem jest",
    "p0224-l0030": "3—4 m., m i o t a m y piłkę, wyprostowawszy",
    "p0225-l0019": "z boku, trzeba mierzyć nieco p r z e d jego",
    "p0225-l0020": "tułów.",
    "p0226-l0021": "kończyć, że równocześnie biegnie kilku w różne",
    "p0226-l0022": "strony i po obu bokach boiska: to rozstrzela",
    "p0226-l0032": "być prawidłem bezwzględnem. Musi bowiem",
    "p0227-l0014": "po piłkę i. t. p., nigdy jednak nie wchodząc",
    "p0227-l0015": "w drogę swoim towarzyszom.",
    "p0219-l0011": "gły o 3½ cm. średni­",
    "p0219-l0015": "o 3×4 cm. P i ł k a ma",
    "p0219-l0016": "mieć średnicę 7 cm.",
    "p0219-l0017": "i wagę 80 gr.",
    "p0219-l0023": "niem¹) na palancie",
    "p0219-l0031": "wykupnika i 9",
    "p0219-l0032": "g r a c z y d z i e c i a k ó w. Gdy",
    "p0219-l0034": "obóz dany jest na",
    "p0223-l0005": "tułów zaś skręca się w lewo; palant uderza",
    "p0223-l0009": "w górę, zbyt łatwo chwytaną przez przeciwni­",
    "p0223-l0011": "po ziemi. Gracz wprawny posyła piłkę tak, że",
    "p0223-l0014": "„parzy“. Nadto stara się skierować ją przez",
    "p0223-l0019": "królestwo; gdy tak chwyci piłkę, jest „skuty“ (pr. 7).",
    "p0223-l0021": "tylko na szybkość biegu. Nie wolno mu spu­",
    "p0223-l0028": "kuje; gdy w górną część tułowia lub głowę —",
    "p0230-l0008": "graczy i ustawiają się w szachownicę, biali po",
    "p0230-l0015": "piłkę (jak nożna, tylko okrywa",
    "p0230-l0022": "piłkę (też pięścią lub przedra­",
    "p0230-l0023": "mieniem) z lotu lub po",
    "p0230-l0024": "p i e r w s z y m koźle (odbiciu",
    "p0230-l0029": "niem piłkę podbijano kilkakrotnie na tern samem",
    "p0230-l0030": "polu, byle po każdem podbiciu piłka nie uczyniła",
    "p0230-l0032": "Jeśli odbicie się uda, biali starają się piłkę",
    "p0230-l0035": "gracz uderzy piłkę zgóry lub oburącz, użyje",
    "p0231-l0003": "złapie piłkę, 3) gdy wejdzie na pole przeciwni­",
    "p0231-l0004": "ków, 4) gdy piłka przy zagrywaniu spadnie na",
    "p0231-l0005": "to samo pole, 5) gdy piłka dotknie się innej",
    "p0231-l0007": "gracza, 6) gdy piłka uczyni na danem polu dwa",
    "p0231-l0008": "kozły lub potoczy się, 7) gdy piłka przejdzie",
    "p0231-l0011": "Obóz winien błędu, zagrywa. Piłkę do",
}


# Exclusive boundaries remove the following section heading and its epigraph from a game block.
TRUNCATE_BEFORE = {
    21: "p0081-l0001",
    30: "p0092-l0001",
    34: "p0097-l0002",
    48: "p0101-l0026",
    51: "p0104-l0005",
    80: "p0128-l0002",
    82: "p0131-l0001",
    86: "p0136-l0001",
    92: "p0167-l0001",
    95: "p0171-l0001",
    121: "p0208-l0001",
    130: "p0218-l0013",
}


def locator_key(locator: str) -> tuple[int, int]:
    match = re.fullmatch(r"p(\d{4})-l(\d{4})", locator)
    if not match:
        raise ValueError(f"Invalid logical-line locator: {locator}")
    return int(match.group(1)), int(match.group(2))


def in_omitted_range(locator: str, ranges: tuple[tuple[str, str], ...]) -> bool:
    key = locator_key(locator)
    return any(locator_key(start) <= key <= locator_key(end) for start, end in ranges)


def render_source_lines(lines: list[dict[str, Any]]) -> str:
    """Join layout lines without lexical modernization while retaining rule structure."""
    paragraphs: list[str] = []
    current = ""
    heading_pattern = re.compile(
        r"^(?:Prawidła|Technika i taktyka\.?|Wskazówki (?:techniczne|taktyczne)|\d+\)|[a-z]\)\s+)"
    )
    for item in lines:
        text = normalize_space(str(item["text"]))
        if not text or text == "■" or re.fullmatch(r"\d{1,3}\*?", text):
            continue
        if heading_pattern.match(text) and current:
            paragraphs.append(current.strip())
            current = ""
        if not current:
            current = text
        elif current.endswith("\u00ad"):
            current = current[:-1] + text
        elif current.endswith("-") and re.match(r"^[a-ząćęłńóśźż]", text):
            current = current[:-1] + text
        else:
            current += " " + text
    if current:
        paragraphs.append(current.strip())
    body = "\n\n".join(paragraphs)
    body = re.sub(r"\s+([,.;:!?])", r"\1", body)
    if not body:
        raise ValueError("Source block contains no prose after deterministic exclusions")
    return body


def source_block(
    candidate: dict[str, Any],
    all_lines: list[dict[str, Any]],
    positions: dict[str, int],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
    str,
    str,
]:
    number = int(candidate["number"])
    detected_start = positions[str(candidate["startLine"])]
    end = positions[str(candidate["endLine"])] + 1
    detected_raw = all_lines[detected_start:end]
    detected_hash = hashlib.sha256(
        ("\n".join(normalize_space(str(line["text"])) for line in detected_raw) + "\n").encode("utf-8")
    ).hexdigest()
    if detected_hash != candidate.get("sourceBlockSha256"):
        raise ValueError(f"Pinned block hash differs for candidate {number}")
    reviewed_start_line = START_OVERRIDES.get(number, str(candidate["startLine"]))
    start = positions[reviewed_start_line]
    raw = all_lines[start:end]
    boundary = TRUNCATE_BEFORE.get(number)
    if boundary:
        end_position = positions[boundary]
        raw = [line for line in raw if positions[str(line["lineId"])] < end_position]
    reviewed_hash = hashlib.sha256(
        ("\n".join(normalize_space(str(line["text"])) for line in raw) + "\n").encode("utf-8")
    ).hexdigest()
    ranges = OMITTED_RANGES.get(number, ())
    illustration_ranges = ILLUSTRATION_RANGES.get(number, ())
    relocated_ranges = RELOCATED_FOOTNOTE_RANGES.get(number, ())
    omissions = [
        {"startLine": start_line, "endLine": end_line, "reason": "music-or-song-lyrics-outside-corpus-scope"}
        for start_line, end_line in ranges
    ]
    omissions.extend(
        {"startLine": start_line, "endLine": end_line, "reason": "illustration-text-outside-corpus-scope"}
        for start_line, end_line in illustration_ranges
    )
    relocations = [
        {"startLine": start_line, "endLine": end_line, "reason": "source-footnote-relocated-after-game"}
        for start_line, end_line in relocated_ranges
    ]
    kept: list[dict[str, Any]] = []
    for index, line in enumerate(raw):
        locator = str(line["lineId"])
        if index == 0:
            continue
        if (
            in_omitted_range(locator, ranges)
            or in_omitted_range(locator, illustration_ranges)
            or in_omitted_range(locator, relocated_ranges)
        ):
            continue
        replacement = LINE_REPLACEMENTS.get(locator)
        kept.append({**line, "text": replacement if replacement is not None else line["text"]})
    return kept, omissions, relocations, reviewed_hash, reviewed_start_line


def build_import() -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any], str]], dict[str, Any]]:
    report = read_json(REPORT_PATH)
    inspection = read_json(INSPECTION_PATH)
    embedded = inspection.get("embeddedText") or {}
    text_path = persisted_artifact_path(embedded)
    payload = text_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != embedded.get("sha256"):
        raise ValueError("Pinned embedded-text hash mismatch")
    pages = payload.decode("utf-8", errors="strict").split("\f")
    all_lines = logical_lines(pages)
    positions = {str(line["lineId"]): index for index, line in enumerate(all_lines)}
    candidates = report.get("candidates") or []
    if [int(item["number"]) for item in candidates] != list(range(1, 134)):
        raise ValueError("Piasecki candidate report no longer contains the pinned 1-133 sequence")

    outputs: list[tuple[Path, dict[str, Any], str]] = []
    activities: list[dict[str, Any]] = []
    body_hashes: dict[str, int] = {}
    revision = f"sha256:{embedded['sha256']}"
    for candidate in candidates:
        number = int(candidate["number"])
        if number in REJECTED_REASONS:
            continue
        kept, omissions, relocations, reviewed_hash, reviewed_start_line = source_block(
            candidate, all_lines, positions
        )
        source_body = render_source_lines(kept)
        if number in RELOCATED_FOOTNOTES:
            source_body = f"{source_body}\n\n{RELOCATED_FOOTNOTES[number]}"
        normalized_hash = hashlib.sha256(normalize_space(source_body).encode("utf-8")).hexdigest()
        if normalized_hash in body_hashes:
            raise ValueError(
                f"Exact source-body duplicate: candidate {number} and candidate {body_hashes[normalized_hash]}"
            )
        body_hashes[normalized_hash] = number
        title = TITLE_OVERRIDES.get(number, normalize_space(str(candidate["titleRaw"])))
        pdf_start = int(all_lines[positions[reviewed_start_line]]["pdfPage"])
        last_line = kept[-1]
        pdf_end = int(last_line["pdfPage"])
        printed_start = int(candidate["printedPageStart"])
        printed_end = max(printed_start, pdf_end - 5)
        activity_id = f"{PREFIX}-{number:03d}"
        facsimile_url = f"{PDF_URL}#page={pdf_start}"
        editorial_notes = []
        if number in OMITTED_RANGES:
            editorial_notes.append(
                "*Zakres transkrypcji: zapis nutowy i tekst pieśni pominięto jako materiał poza zakresem korpusu; dokładne granice zapisano w raporcie ekstrakcji.*"
            )
        if number in ILLUSTRATION_RANGES:
            editorial_notes.append(
                "*Zakres transkrypcji: tekst należący do ilustracji pominięto; dokładne granice zapisano w raporcie ekstrakcji.*"
            )
        if number == 103:
            editorial_notes.append(
                "*Atrybucja w przedmowie: opis gry „Kręgle polskie” przypisano Kazimierzowi Lutosławskiemu.*"
            )
        source_note = (
            "---\n\n"
            + ("\n\n".join(editorial_notes) + "\n\n" if editorial_notes else "")
            + f"*Źródło skanu: [Kujawsko-Pomorska Biblioteka Cyfrowa]({SOURCE_URL}), "
            + f"oznaczenie „Domena publiczna”. [Zobacz PDF — strona {pdf_start}]({facsimile_url}).*"
        )
        body = f"{source_body}\n\n{source_note}"
        metadata: dict[str, Any] = {
            "id": activity_id,
            "kinds": ["game"],
            "sourceId": SOURCE_ID,
            "originalLanguage": "pl",
            "title": title,
            "traits": [],
            "section": candidate["section"],
            "printedPages": list(range(printed_start, printed_end + 1)),
            "pdfPages": list(range(pdf_start, pdf_end + 1)),
            "transcriptionStatus": "embedded-text-unreviewed",
            "safetyStatus": "historical-unreviewed",
            "rightsStatus": "public-domain",
            "sourceUrl": SOURCE_URL,
            "digitalEditionUrl": SOURCE_URL,
            "facsimileUrl": facsimile_url,
            "sourceRevision": revision,
            "participantScales": ["unknown"],
            "participantScaleBasis": "unknown",
        }
        content_omissions = []
        if number in OMITTED_RANGES:
            content_omissions.extend(["musical-notation", "song-lyrics"])
        if number in ILLUSTRATION_RANGES:
            content_omissions.append("illustration-text")
        if content_omissions:
            metadata["contentOmissions"] = content_omissions
        if number == 103:
            metadata["sourceContributor"] = "Kazimierz Lutosławski"
        metadata["sourceHash"] = source_hash(title, body)
        outputs.append((VAULT / "activities" / f"{activity_id}.md", metadata, body))
        item: dict[str, Any] = {
            "id": activity_id,
            "candidateNumber": number,
            "title": title,
            "startLine": reviewed_start_line,
            "endLine": str(last_line["lineId"]),
            "pdfPages": metadata["pdfPages"],
            "printedPages": metadata["printedPages"],
            "sourceBlockSha256": reviewed_hash,
            "publishedSourceHash": metadata["sourceHash"],
        }
        if reviewed_start_line != candidate["startLine"]:
            item["detectorStartLine"] = candidate["startLine"]
            item["detectorSourceBlockSha256"] = candidate["sourceBlockSha256"]
        if omissions:
            item["omittedSourceRanges"] = omissions
        if relocations:
            item["relocatedSourceRanges"] = relocations
        if number == 103:
            item["sourceContributor"] = "Kazimierz Lutosławski"
        activities.append(item)

    extraction = {
        "schemaVersion": 1,
        "sourceId": SOURCE_ID,
        "sourceSha256": embedded["sha256"],
        "parserVersion": "piasecki-1922-embedded-text-game-import-v2",
        "reviewRequired": False,
        "activityCount": len(activities),
        "wholeSourceCopiedToRepository": False,
        "selection": {
            "candidateCount": len(candidates),
            "acceptedGameCount": len(activities),
            "rejectedCount": len(REJECTED_REASONS),
            "basis": "source-numbered entries with an executable procedure after music, lyrics, illustrations and following-section furniture are removed",
            "rejectedCandidates": [
                {"candidateNumber": number, "reason": reason}
                for number, reason in sorted(REJECTED_REASONS.items())
            ],
        },
        "transcriptionEvidence": {
            "sourceStatement": "Pinned embedded text from the KPBC PDF stored in private repository artifacts.",
            "sourceLocation": PDF_URL,
            "deterministicNormalization": [
                "omit the numbered activity heading represented in frontmatter",
                "omit isolated printed-page numbers",
                "omit pinned music, song-lyric and illustration ranges",
                "truncate pinned following-section headings and epigraphs",
                "retain pinned prose fragments from lines that also introduce excluded songs",
                "relocate pinned source footnotes that interrupt a continued rule",
                "join layout soft wraps and dehyphenate line-break continuations",
                "preserve spelling, punctuation and paragraph order without lexical modernization",
            ],
            "lexicalModernization": False,
        },
        "deduplication": {"exactBodyMatches": [], "nearDuplicateCandidates": []},
        "activities": activities,
    }

    rights_evidence = report["selection"]["rightsEvidence"]
    source_metadata = {
        "id": SOURCE_ID,
        "activityPrefix": PREFIX,
        "author": "Eugeniusz Piasecki",
        "title": "Zabawy i gry ruchowe dzieci i młodzieży",
        "year": 1922,
        "edition": "wydanie 3 poprawione i rozszerzone",
        "publicationPlace": "Lwów — Warszawa",
        "publisher": "Książnica Polska Towarzystwa Nauczycieli Szkół Wyższych",
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": "„Domena publiczna (public domain)” — oznaczenie konkretnego obiektu w KPBC",
        "rightsEvidenceUrl": SOURCE_URL,
        "rightsEvidence": rights_evidence,
        "sourceUrl": SOURCE_URL,
        "digitalEditionUrl": SOURCE_URL,
        "pdfUrl": PDF_URL,
        "accessedOn": "2026-09-07",
        "sourceRevision": revision,
        "extractionReport": f"data/reports/{SOURCE_ID}-extraction.json",
        "translationPolicy": {
            "targetLocale": "en",
            "modelRequested": "mistral-large-2512",
            "reasoningMode": "disabled",
            "promptVersion": "translation-pl-en-v5",
            "usageRequired": True,
            "requestBudgetRequired": True,
            "billingMode": "education-credit",
            "enforceReferenceCostLimit": True,
            "maxReferenceCostUsd": 10,
            "report": f"data/reports/{SOURCE_ID}-translation-pl-en.json",
            "priceAccessedOn": "2026-09-04",
            "smokeTestActivityIds": [
                "zgr-001",
                "zgr-031",
                "zgr-091",
                "zgr-103",
                "zgr-121",
                "zgr-131",
            ],
        },
    }
    return extraction, outputs, source_metadata


def execute_import() -> dict[str, Any]:
    extraction, outputs, source_metadata = build_import()
    expected_names = {path.name for path, _metadata, _body in outputs}
    for path, metadata, body in outputs:
        dump_markdown(path, metadata, body)
    for stale in (VAULT / "activities").glob(f"{PREFIX}-*.md"):
        if stale.name not in expected_names:
            stale.unlink()
    source_body = (
        "# Zabawy i gry ruchowe dzieci i młodzieży\n\n"
        "Źródło bibliograficzne dla gier wyodrębnionych z obiektu KPBC jawnie oznaczonego "
        "jako domena publiczna. PDF i jego warstwa tekstowa są przechowywane lokalnie w "
        "ignorowanym przez Git katalogu `artifacts/`; publikowany korpus zawiera tylko "
        "wybrane, udokumentowane rekordy.\n\n"
        f"- [Rekord cyfrowy w KPBC]({SOURCE_URL})\n"
        f"- [PDF wydania]({PDF_URL})\n"
    )
    dump_markdown(VAULT / "sources" / f"{SOURCE_ID}.md", source_metadata, source_body)
    write_json(ROOT / "data" / "reports" / f"{SOURCE_ID}-extraction.json", extraction)

    report = read_json(REPORT_PATH)
    accepted = {item["candidateNumber"] for item in extraction["activities"]}
    for candidate in report["candidates"]:
        number = int(candidate["number"])
        candidate["recordReviewStatus"] = (
            "accepted-game" if number in accepted else "rejected-not-game"
        )
        if number in REJECTED_REASONS:
            candidate["recordReviewReason"] = REJECTED_REASONS[number]
        else:
            candidate.pop("recordReviewReason", None)
        candidate["separateLyricsOrVerseReviewRequired"] = number in OMITTED_RANGES
    report["status"] = "record-review-complete-original-imported-translation-pending"
    report["selection"]["importedActivityCount"] = len(outputs)
    report["selection"]["recordReviewRequired"] = False
    report["selection"]["musicOrLyricsOmittedCandidateCount"] = len(OMITTED_RANGES)
    write_json(REPORT_PATH, report)
    return extraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    extraction, _outputs, _source = build_import()
    if args.execute:
        extraction = execute_import()
    print(
        json.dumps(
            {
                "mode": "execute" if args.execute else "dry-run",
                "sourceId": SOURCE_ID,
                **extraction["selection"],
                "activityPrefix": PREFIX,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
