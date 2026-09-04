import tempfile
import unittest
import hashlib
import io
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_content import activity_page, load_records
from common import dump_markdown, load_markdown, source_hash
from import_sources import clean_game_body
from gutenberg import Block, fetch, parse_html, parse_text
from import_gutenberg import extract_activity, load_manifest
from evaluate_translation_models import (
    load_evaluation_config,
    summary_payload,
    translation_quality_checks,
)
from translate import (
    MAX_OUTPUT_TOKENS,
    MIN_OUTPUT_TOKENS,
    PermanentTranslationError,
    available_model_ids,
    advance_translation_state,
    combine_usage_records,
    current_translation,
    ensure_models_available,
    parse_json_content,
    retry_at_from_headers,
    safe_http_diagnostics,
    translation_output_token_budget,
    usage_record,
)


class PipelineTests(unittest.TestCase):
    def test_markdown_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.md"
            metadata = {"id": "test-001", "title": "Żuraw", "traits": ["spryt"]}
            dump_markdown(path, metadata, "Treść **próby**.")
            loaded, body = load_markdown(path)
            self.assertEqual(loaded, metadata)
            self.assertEqual(body, "Treść **próby**.")

    def test_source_hash_is_stable_and_title_sensitive(self):
        self.assertEqual(source_hash(" Tytuł ", " Treść "), source_hash("Tytuł", "Treść"))
        self.assertNotEqual(source_hash("Tytuł", "Treść"), source_hash("Inny", "Treść"))

    def test_game_cleanup_removes_source_chrome_and_absolutizes_assets(self):
        raw = """---\ntitle: Test\n---\n\n> **Transkrypcja OCR — wersja beta.** Tekst.\n\nAkapit.\n\n![x](/harcerz-w-polu/book/assets/x.jpeg)\n\n<p class=\"source-note\">Źródło</p>\n"""
        cleaned = clean_game_body(raw)
        self.assertNotIn("Transkrypcja OCR", cleaned)
        self.assertNotIn("source-note", cleaned)
        self.assertIn("https://jfpio.github.io/harcerz-w-polu/book/assets/x.jpeg", cleaned)

    def test_translation_json_contract(self):
        payload = parse_json_content('{"title":"Fire","body":"Text","traits":["patience"],"section":"Trials"}')
        self.assertEqual(payload["title"], "Fire")
        with self.assertRaises(ValueError):
            parse_json_content('{"title":"Fire","body":"Text","traits":[],"section":"Trials","extra":true}')

    def test_translation_cooldown_uses_provider_value_or_one_hour_fallback(self):
        now = datetime(2026, 9, 3, tzinfo=UTC)
        self.assertEqual(retry_at_from_headers({}, now), now + timedelta(hours=1))
        self.assertEqual(
            retry_at_from_headers({"Retry-After": "60"}, now),
            now + timedelta(seconds=60),
        )
        self.assertEqual(
            retry_at_from_headers({"Retry-After": "50000"}, now),
            now + timedelta(seconds=50000),
        )

    def test_translation_usage_separates_billed_and_reference_cost(self):
        usage = usage_record(
            {"prompt_tokens": 1000, "completion_tokens": 200},
            "mistral-large-2512",
            request_max_output_tokens=640,
        )
        self.assertIsNone(usage["billedCostUsd"])
        self.assertEqual(usage["billingMode"], "education-credit")
        self.assertEqual(usage["referenceCostUsd"], 0.0008)
        self.assertEqual(usage["requestMaxOutputTokens"], 640)
        self.assertEqual(
            usage_record(
                {"prompt_tokens": 1000, "completion_tokens": 200},
                "mistral-small-2603",
            )["referenceCostUsd"],
            0.00027,
        )
        self.assertEqual(
            usage_record(
                {"prompt_tokens": 1000, "completion_tokens": 200},
                "ministral-14b-2512",
            )["referenceCostUsd"],
            0.00024,
        )
        with self.assertRaisesRegex(ValueError, "positive prompt/completion"):
            usage_record({})

    def test_translation_retry_usage_is_combined_without_claiming_a_billed_amount(self):
        first = usage_record(
            {"prompt_tokens": 100, "completion_tokens": 50},
            request_max_output_tokens=512,
        )
        second = usage_record(
            {"prompt_tokens": 120, "completion_tokens": 60},
            request_max_output_tokens=640,
        )
        combined = combine_usage_records([first, second])
        self.assertEqual(combined["promptTokens"], 220)
        self.assertEqual(combined["completionTokens"], 110)
        self.assertEqual(combined["requestAttempts"], 2)
        self.assertEqual(combined["requestMaxOutputTokens"], 640)
        self.assertEqual(combined["requestMaxOutputTokensTotal"], 1152)
        self.assertIsNone(combined["billedCostUsd"])

    def test_translation_output_budget_scales_and_is_bounded(self):
        self.assertEqual(translation_output_token_budget({"body": "short"}), MIN_OUTPUT_TOKENS)
        scaled = translation_output_token_budget({"body": "x" * 4000})
        self.assertGreater(scaled, MIN_OUTPUT_TOKENS)
        self.assertLess(scaled, MAX_OUTPUT_TOKENS)
        self.assertEqual(
            translation_output_token_budget({"body": "x" * 100_000}),
            MAX_OUTPUT_TOKENS,
        )

    def test_translation_http_diagnostics_are_allowlisted(self):
        error = urllib.error.HTTPError(
            "https://api.mistral.ai/private",
            429,
            "rate limited",
            {
                "Retry-After": "60",
                "X-RateLimit-Remaining-Tokens": "0",
                "Authorization": "Bearer secret",
            },
            io.BytesIO(
                b'{"type":"rate_limit_error","code":"rate_limit",'
                b'"param":"tokens","message":"do not persist this"}'
            ),
        )
        diagnostics = safe_http_diagnostics(error)
        serialized = str(diagnostics)
        self.assertEqual(diagnostics["httpStatus"], 429)
        self.assertEqual(diagnostics["headers"]["retry-after"], "60")
        self.assertEqual(diagnostics["error"]["code"], "rate_limit")
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("do not persist", serialized)

    def test_translation_model_access_preflight_uses_exact_pinned_ids(self):
        response = io.BytesIO(
            b'{"data":[{"id":"mistral-medium-2604"},{"id":"mistral-small-2603"}]}'
        )
        with patch("translate.urllib.request.urlopen", return_value=response):
            self.assertEqual(
                available_model_ids("not-logged"),
                {"mistral-medium-2604", "mistral-small-2603"},
            )
        with patch(
            "translate.available_model_ids", return_value={"mistral-small-2603"}
        ):
            with self.assertRaisesRegex(
                PermanentTranslationError, "models-not-available-for-account"
            ) as raised:
                ensure_models_available(
                    "not-logged", {"mistral-large-2512", "mistral-small-2603"}
                )
        self.assertEqual(
            raised.exception.diagnostics,
            {"missingModels": ["mistral-large-2512"]},
        )

    def test_translation_cache_respects_source_policy_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-001.md"
            metadata = {
                "activityId": "test-001",
                "locale": "pl",
                "modelRequested": "mistral-medium-2604",
                "promptVersion": "translation-en-pl-v1",
                "sourceHash": "expected",
                "status": "machine-translation",
                "usage": usage_record(
                    {"prompt_tokens": 100, "completion_tokens": 50},
                    "mistral-medium-2604",
                    request_max_output_tokens=512,
                ),
            }
            dump_markdown(path, metadata, "Tłumaczenie.")
            expectations = {
                "expected_locale": "pl",
                "expected_model": "mistral-medium-2604",
                "expected_prompt": "translation-en-pl-v1",
                "usage_required": True,
                "request_budget_required": True,
            }
            self.assertTrue(current_translation(path, "expected", **expectations))
            self.assertFalse(current_translation(path, "expected", **{**expectations, "expected_model": "other"}))
            metadata["usage"] = {}
            dump_markdown(path, metadata, "Tłumaczenie.")
            self.assertFalse(current_translation(path, "expected", **expectations))

    def test_translation_checkpoint_state_advances_in_source_order(self):
        state = {
            "selectedActivityIds": ["sfb-001", "sfb-002"],
            "completedActivityIds": [],
            "pendingActivityIds": ["sfb-001", "sfb-002"],
            "models": [],
            "usage": {
                "promptTokens": 0,
                "completionTokens": 0,
                "referenceCostUsd": 0,
            },
        }
        advance_translation_state(
            state,
            "sfb-002",
            "mistral-medium-2604",
            {"promptTokens": 20, "completionTokens": 10, "referenceCostUsd": 0.000105},
        )
        self.assertEqual(state["completedActivityIds"], ["sfb-002"])
        self.assertEqual(state["pendingActivityIds"], ["sfb-001"])
        self.assertEqual(state["models"], ["mistral-medium-2604"])
        self.assertEqual(state["usage"]["referenceCostUsd"], 0.000105)
        self.assertEqual(state["usage"]["requestMaxOutputTokens"], 0)

    def test_translation_model_evaluation_is_bounded_and_quality_checks_normalize_decimals(self):
        root = Path(__file__).resolve().parents[1]
        config = load_evaluation_config(root / "config" / "translation-model-evaluation.yaml")
        self.assertEqual(config["productionCandidate"], "mistral-large-2512")
        self.assertEqual(config["candidates"], ["mistral-large-2512"])
        self.assertEqual(config["reasoningMode"], "disabled")
        self.assertEqual(config["execution"]["billingMode"], "education-credit")
        self.assertEqual(config["execution"]["maxReferenceCostUsd"], 10)
        self.assertEqual(len(config["activityIds"]), 5)
        checks = translation_quality_checks(
            {"traits": ["accuracy"]},
            "Walk 2.5 miles. See https://example.test/a",
            {
                "title": "Marsz",
                "section": "Droga",
                "traits": ["dokladnosc"],
                "body": "Przejdź 2,5 mili. Zobacz https://example.test/a",
            },
        )
        self.assertTrue(checks["numbersPreserved"])
        self.assertTrue(checks["urlsPreserved"])
        grouped_checks = translation_quality_checks(
            {"traits": [], "originalLanguage": "en"},
            "A force of 5,000 lost 3,500 on March 17th, 1812.",
            {
                "title": "Bitwa",
                "section": "Historia",
                "traits": [],
                "body": "Siła 5 000 straciła 3 500 dnia 17 marca 1812.",
            },
        )
        self.assertTrue(grouped_checks["numbersPreserved"])

    def test_translation_model_evaluation_checkpoints_permanent_provider_errors(self):
        config = {
            "id": "evaluation",
            "sourceId": "source",
            "productionCandidate": "mistral-large-2512",
            "candidates": ["mistral-large-2512", "mistral-small-2603"],
            "activityIds": ["activity"],
        }
        checkpoint = summary_payload(
            config,
            "config-hash",
            "results/evaluation.json",
            [],
            status="failed-permanent",
            current_pair="mistral-large-2512:activity",
            permanent_error=PermanentTranslationError(
                "permanent-http-403",
                {"httpStatus": 403, "error": {"type": "tier_not_allowed", "code": "1910"}},
            ),
        )
        self.assertEqual(checkpoint["status"], "failed-permanent")
        self.assertEqual(checkpoint["providerError"]["error"]["type"], "tier_not_allowed")
        self.assertNotIn("nextRetryAt", checkpoint)

    def test_polish_translation_of_english_source_links_back_to_english(self):
        record = {
            "id": "sfb-001",
            "kinds": ["game"],
            "sourceId": "sfb-1908",
            "author": "Robert Baden-Powell",
            "sourceTitle": "Scouting for Boys",
            "year": 1908,
            "printedPages": [52],
            "pdfPages": [],
            "sourceUrl": "https://www.gutenberg.org/ebooks/65993",
            "digitalEditionUrl": "https://www.gutenberg.org/files/65993/65993-h/65993-h.htm",
            "facsimileUrl": "https://www.gutenberg.org/files/65993/65993-h/65993-h.htm#Page_52",
            "transcriptionStatus": "digital-proofread",
            "safetyStatus": "historical-unreviewed",
            "originalLanguage": "en",
            "locale": "pl",
            "title": "Wyprawa arktyczna",
            "body": "Polski tekst.",
            "summary": "Polski tekst.",
            "traits": [],
            "translationStatus": "machine-translation",
            "translationModel": "mistral-medium-2604",
        }
        rendered = activity_page(record, locale="pl")
        self.assertIn("Tłumaczenie automatyczne.", rendered)
        self.assertIn("nie został zweryfikowany przez człowieka", rendered)
        self.assertIn("/scouting-autoresearch/en/activities/sfb-001/", rendered)
        self.assertIn("Przeczytaj tekst źródłowy po angielsku", rendered)
        self.assertIn("[Wydanie cyfrowe]", rendered)
        self.assertIn("[Rekord źródłowy]", rendered)
        self.assertIn("[s. 52]", rendered)

    def test_english_source_page_links_to_polish_automatic_translation(self):
        record = {
            "id": "sfb-001",
            "kinds": ["game"],
            "sourceId": "sfb-1908",
            "author": "Robert Baden-Powell",
            "sourceTitle": "Scouting for Boys",
            "year": 1908,
            "printedPages": [52],
            "pdfPages": [],
            "sourceUrl": "https://www.gutenberg.org/ebooks/65993",
            "digitalEditionUrl": "https://www.gutenberg.org/files/65993/65993-h/65993-h.htm",
            "facsimileUrl": "https://www.gutenberg.org/files/65993/65993-h/65993-h.htm#Page_52",
            "transcriptionStatus": "digital-proofread",
            "safetyStatus": "historical-unreviewed",
            "originalLanguage": "en",
            "locale": "en",
            "title": "Arctic Expedition",
            "body": "English source text.",
            "summary": "English source text.",
            "traits": [],
            "translationStatus": "source-text",
        }
        rendered = activity_page(record, locale="en")
        self.assertNotIn("Automatic translation.", rendered)
        self.assertIn("/scouting-autoresearch/activities/sfb-001/", rendered)
        self.assertIn("Read the automatic translation", rendered)
        self.assertIn("[Digital edition]", rendered)
        self.assertIn("[Source record]", rendered)
        self.assertIn("[p. 52]", rendered)

    def test_load_records_pairs_an_english_source_with_its_polish_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            source = {
                "id": "source-1",
                "author": "Author",
                "title": "Book",
                "year": 1908,
                "publisher": "Publisher",
            }
            activity = {
                "id": "test-001",
                "kinds": ["game"],
                "sourceId": "source-1",
                "originalLanguage": "en",
                "title": "Source title",
                "traits": [],
                "section": "Section",
                "printedPages": [1],
                "sourceUrl": "https://example.test/source",
                "digitalEditionUrl": "https://example.test/text",
                "facsimileUrl": "https://example.test/text#Page_1",
                "sourceRevision": "sha256:source",
                "sourceHash": "hash",
                "rightsStatus": "public-domain",
                "transcriptionStatus": "digital-proofread",
                "safetyStatus": "historical-unreviewed",
            }
            translation = {
                "activityId": "test-001",
                "locale": "pl",
                "title": "Tytuł tłumaczenia",
                "traits": [],
                "section": "Dział",
                "model": "mistral-medium-2604",
                "promptVersion": "translation-en-pl-v1",
                "generatedAt": "2026-09-03",
                "sourceHash": "hash",
                "status": "machine-translation",
            }
            dump_markdown(vault / "sources" / "source-1.md", source, "Source.")
            dump_markdown(vault / "activities" / "test-001.md", activity, "English source text.")
            dump_markdown(vault / "translations" / "pl" / "test-001.md", translation, "Polskie tłumaczenie.")
            with patch("build_content.VAULT", vault):
                polish, english, sources = load_records()
            self.assertEqual(set(sources), {"source-1"})
            self.assertEqual(polish[0]["translationStatus"], "machine-translation")
            self.assertEqual(polish[0]["title"], "Tytuł tłumaczenia")
            self.assertEqual(english[0]["translationStatus"], "source-text")
            self.assertEqual(english[0]["title"], "Source title")

            translation["activityId"] = "wrong-id"
            dump_markdown(vault / "translations" / "pl" / "test-001.md", translation, "Polskie tłumaczenie.")
            with patch("build_content.VAULT", vault), self.assertRaisesRegex(RuntimeError, "activity ID mismatch"):
                load_records()

    def test_gutenberg_parser_tracks_printed_pages_and_omits_images(self):
        html = b"""<div><span class='pageno' id='Page_52'>52</span><h5>GAME</h5></div>
        <p><span class='sc'>Start.</span> First <i>instruction</i>.</p>
        <p>Second <span class='pageno' id='Page_53'>53</span>instruction.</p>
        <div class='figcenter'><img src='image.jpg'><p>Caption</p></div>
        <p>Text after an unclosed void image tag.</p>"""
        blocks = parse_html(html)
        self.assertEqual(
            [block.text for block in blocks],
            ["GAME", "Start. First instruction.", "Second instruction.", "Text after an unclosed void image tag."],
        )
        self.assertEqual((blocks[-2].page_start, blocks[-2].page_end), (52, 53))
        self.assertEqual(blocks[1].leading_small_caps, "Start.")

    def test_gutenberg_parser_keeps_blocks_after_plain_br(self):
        html = b"""<span class='pageno' id='Page_1'>1</span><p>First<br>second.</p><p>Next.</p>"""
        self.assertEqual([block.text for block in parse_html(html)], ["First second.", "Next."])

    def test_gutenberg_text_parser_tracks_braced_pages_and_omits_illustrations(self):
        text = b"""Header without a page.

{291}

Game Title

First wrapped
instruction.

[Illustration: Do not import this caption.]

Second instruction crosses {292} the page.

{293 continued}

Next Game
"""
        blocks = parse_text(text)
        self.assertEqual(
            [block.text for block in blocks],
            ["Game Title", "First wrapped instruction.", "Second instruction crosses the page.", "Next Game"],
        )
        self.assertEqual((blocks[2].page_start, blocks[2].page_end), (291, 292))
        self.assertEqual((blocks[-1].page_start, blocks[-1].page_end), (293, 293))

    def test_gutenberg_manifest_rejects_yaml_flow_mapping_spillover(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yaml"
            path.write_text(
                """schemaVersion: 1
source:
  id: sfb-test
activities:
  - {id: sfb-001, title: Debates, Trials, Etc., section: Test, start: {page: 1, text: A}, endBefore: {page: 1, text: B}}
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unexpected keys"):
                load_manifest(path)

    def test_gutenberg_manifest_covers_the_curated_full_book_scope(self):
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(root / "config" / "imports" / "pg-65993.yaml")
        activities = manifest["activities"]
        self.assertEqual(len(activities), 49)
        self.assertEqual(
            next(item for item in activities if item["id"] == "sfb-028")["title"],
            "Games in Pathfinding",
        )
        seton_group = next(
            group for group in manifest["selection"]["excludedGroups"] if group["label"] == "Seton-derived games"
        )
        self.assertIn("Old Spotty-face", seton_group["examples"])

    def test_gutenberg_manifest_supports_text_sources_and_source_specific_ids(self):
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(root / "config" / "imports" / "pg-29558.yaml")
        self.assertEqual(manifest["download"]["format"], "text")
        self.assertEqual(manifest["source"]["activityPrefix"], "bsh")
        self.assertEqual(len(manifest["activities"]), 33)
        self.assertTrue(all(item["id"].startswith("bsh-") for item in manifest["activities"]))
        excluded = {
            example
            for group in manifest["selection"]["excludedGroups"]
            for example in group["examples"]
        }
        self.assertIn("Mumbly Peg", excluded)
        self.assertIn("Arctic Expedition", excluded)

    def test_gutenberg_extraction_can_preserve_a_start_label(self):
        blocks = [
            Block("p", '"Wrist Pushing" by one man alone.', 1, 1, "Wrist Pushing"),
            Block("h5", "NEXT", 1, 1),
        ]
        _, body = extract_activity(
            blocks,
            {
                "id": "sfb-001",
                "title": "Wrist Pushing",
                "section": "Test",
                "start": {"page": 1, "text": "Wrist Pushing"},
                "endBefore": {"page": 1, "text": "NEXT"},
                "preserveStartLabel": True,
            },
        )
        self.assertEqual(body, '"Wrist Pushing" by one man alone.')

    def test_gutenberg_fetch_reuses_matching_cached_file(self):
        data = b"cached source"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.htm"
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(fetch("https://invalid.test/unused", path, digest), digest)

    def test_azymut_is_approved_for_editorial_discovery_only(self):
        root = Path(__file__).resolve().parents[1]
        registry = yaml.safe_load((root / "config" / "source-registry.yaml").read_text(encoding="utf-8"))
        azymut = next(item for item in registry["collections"] if item["id"] == "azymut-zhr")
        self.assertEqual(azymut["baseUrl"], "https://azymut.zhr.pl/")
        self.assertEqual(azymut["status"], "approved-per-item")
        self.assertEqual(azymut["trustScope"], "editorial-discovery")
        self.assertEqual(azymut["allowedMethods"], ["article-metadata", "link-discovery"])


if __name__ == "__main__":
    unittest.main()
