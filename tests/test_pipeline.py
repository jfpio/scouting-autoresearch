import tempfile
import unittest
import hashlib
import io
import urllib.error
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from unittest.mock import patch

import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_content import (
    activity_page,
    apply_filter_traits,
    authors_page,
    explorer_page,
    load_records,
    sources_page,
    strip_trailing_whitespace,
)
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
    advance_failed_translation_usage,
    combine_usage_records,
    current_translation,
    deterministic_translation_repairs,
    ensure_models_available,
    parse_json_content,
    protect_translation_body,
    request_translation_preserving_paragraphs,
    request_translation_in_chunks,
    request_reference_cost_upper_bound,
    restore_translation_body,
    retry_at_from_headers,
    safe_http_diagnostics,
    translation_fidelity_checks,
    translation_output_token_budget,
    translation_attempt_reference_cost_upper_bound,
    translation_target,
    translation_targets,
    usage_record,
)


class PipelineTests(unittest.TestCase):
    def test_filter_traits_normalize_case_and_preserve_source_terms(self):
        records = [
            {"id": "a", "locale": "pl", "traits": ["Spryt"], "_sourceTraits": ["Spryt"], "_sourceTraitLocale": "pl"},
            {"id": "b", "locale": "pl", "traits": ["spryt"], "_sourceTraits": ["spryt"], "_sourceTraitLocale": "pl"},
        ]
        apply_filter_traits(records)
        self.assertEqual(records[0]["filterTraits"], ["Spryt"])
        self.assertEqual(records[1]["filterTraits"], ["Spryt"])
        self.assertEqual(records[0]["traits"], ["Spryt"])
        self.assertEqual(records[1]["traits"], ["spryt"])

    def test_filter_traits_expand_approved_compounds(self):
        records = [
            {
                "id": "a",
                "locale": "pl",
                "traits": ["Siła woli cierpliwość", "opanowanie się pomysłowość"],
                "_sourceTraits": ["Siła woli cierpliwość", "opanowanie się pomysłowość"],
                "_sourceTraitLocale": "pl",
            },
            {
                "id": "a",
                "locale": "en",
                "traits": ["Willpower and patience", "Self-control and ingenuity"],
                "_sourceTraits": ["Siła woli cierpliwość", "opanowanie się pomysłowość"],
                "_sourceTraitLocale": "pl",
            },
        ]
        apply_filter_traits(records)
        self.assertEqual(records[0]["filterTraits"], ["Siła woli", "Cierpliwość", "Opanowanie", "Pomysłowość"])
        self.assertEqual(records[1]["filterTraits"], ["Willpower", "Patience", "Composure", "Ingenuity"])

    def test_explorer_pages_and_catalogs_publish_courses_books_and_authors(self):
        source = {
            "id": "source-1",
            "title": "Książka",
            "author": "Autor",
            "year": 1930,
            "publicationPlace": "Poznań",
            "publisher": "Wydawca",
            "rightsStatement": "Domena publiczna",
            "sourceUrl": "https://example.test/source",
            "digitalEditionUrl": "https://example.test/book",
        }
        record = {"sourceId": "source-1"}
        self.assertIn('kind="scout-course"', explorer_page("pl", activity_count=1, source_count=1, kind="scout-course"))
        self.assertIn('title: "Książki"', sources_page("pl", {"source-1": source}, [record]))
        self.assertIn('title: "Autorzy"', authors_page("pl", {"source-1": source}, [record]))

    def test_generated_text_strips_only_trailing_whitespace(self):
        value = "first  \n  second\t\n   \n"
        self.assertEqual(strip_trailing_whitespace(value), "first\n  second\n\n")

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

    def test_translation_protected_tokens_round_trip_exact_values(self):
        source = (
            "Biegnij 400—1500 kroków, potem 1/2 drogi. "
            "Skan: https://example.test/view/40?part=1."
        )
        protected, replacements = protect_translation_body(source)
        self.assertNotRegex(protected, r"\d")
        self.assertNotIn("https://", protected)
        self.assertEqual(len(replacements), 3)
        translated = protected.replace("Biegnij", "Run").replace("kroków", "paces")
        self.assertEqual(
            restore_translation_body(
                translated,
                replacements,
                reject_unprotected_digits=True,
            ),
            "Run 400—1500 paces, potem 1/2 drogi. "
            "Skan: https://example.test/view/40?part=1.",
        )

    def test_translation_protected_tokens_reject_missing_marker(self):
        protected, replacements = protect_translation_body("Idź 1/2 drogi.")
        marker = next(iter(replacements))
        with self.assertRaisesRegex(ValueError, "expected exactly once"):
            restore_translation_body(protected.replace(marker, ""), replacements)

    def test_translation_protected_tokens_reject_new_digits(self):
        protected, replacements = protect_translation_body("Trzy kroki.")
        with self.assertRaisesRegex(ValueError, "introduced a digit"):
            restore_translation_body(
                f"{protected} 2",
                replacements,
                reject_unprotected_digits=True,
            )

    def test_translation_protected_tokens_reject_invented_outer_wrapper(self):
        protected, replacements = protect_translation_body("Idź 3 kroki.")
        wrapped = protected.replace("ZXQNUMAQXZ", "ZXQZXQNUMAQXZQXZ")
        with self.assertRaisesRegex(ValueError, "malformed protected-token wrapper"):
            restore_translation_body(
                wrapped,
                replacements,
                reject_unprotected_digits=True,
            )

    def test_translation_protected_tokens_preserve_superscript_footnotes(self):
        protected, replacements = protect_translation_body("Goniec¹ i łącznik².")
        self.assertNotIn("¹", protected)
        self.assertNotIn("²", protected)
        self.assertEqual(len(replacements), 2)
        self.assertEqual(
            restore_translation_body(protected, replacements, reject_unprotected_digits=True),
            "Goniec¹ i łącznik².",
        )

    def test_translation_protected_tokens_preserve_roman_numerals(self):
        protected, replacements = protect_translation_body("W wieku XVI, część V a.")
        self.assertNotIn("XVI", protected)
        self.assertNotRegex(protected, r"(?<!\w)V(?!\w)")
        self.assertEqual(
            restore_translation_body(protected, replacements, reject_unprotected_digits=True),
            "W wieku XVI, część V a.",
        )

    def test_translation_retry_can_protect_paragraph_breaks(self):
        source = "Pierwszy akapit.\n\nDrugi akapit."
        protected, replacements = protect_translation_body(
            source, protect_paragraph_breaks=True
        )
        self.assertRegex(protected, r"ZXQBR[A-Z]+QXZ")
        self.assertEqual(
            restore_translation_body(
                protected.replace("Drugi", "\n\nDrugi"),
                replacements,
                reject_unprotected_digits=True,
                normalize_unprotected_paragraph_breaks=True,
            ),
            source,
        )

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

        nested = combine_usage_records([combined, first])
        self.assertEqual(nested["requestAttempts"], 3)
        self.assertEqual(nested["requestMaxOutputTokens"], 640)
        self.assertEqual(nested["requestMaxOutputTokensTotal"], 1664)

    def test_paragraph_retry_preserves_full_context_and_combines_usage(self):
        metadata = {
            "id": "a",
            "sourceId": "test-source",
            "title": "Tytuł",
            "traits": [],
            "section": "Gry",
            "originalLanguage": "pl",
        }
        replies = [(
            {"title": "Title", "traits": [], "section": "Games", "body": "First.\n\nSecond."},
            "mistral-large-2512",
            usage_record(
                {"prompt_tokens": 100, "completion_tokens": 20},
                request_max_output_tokens=512,
            ),
        )]
        with patch("translate.request_translation", side_effect=replies) as request:
            translated, actual_model, usage = request_translation_preserving_paragraphs(
                "secret",
                "mistral-large-2512",
                "a",
                metadata,
                "Pierwszy.\n\nDrugi.",
                "pl",
                "en",
                "translation-pl-en-v5",
            )
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[4], "Pierwszy.\n\nDrugi.")
        self.assertTrue(request.call_args.kwargs["protect_paragraph_breaks"])
        self.assertEqual(translated["body"], "First.\n\nSecond.")
        self.assertEqual(actual_model, "mistral-large-2512")
        self.assertNotIn("requestAttempts", usage)

    def test_oversized_translation_fallback_uses_multi_paragraph_chunks(self):
        metadata = {
            "id": "a",
            "sourceId": "test-source",
            "title": "Długa gra",
            "traits": [],
            "section": "Gry",
            "originalLanguage": "pl",
        }
        body = f"{'A' * 3000}\n\n{'B' * 3000}\n\n{'C' * 100}"

        def reply(*args, **kwargs):
            chunk = args[4]
            return (
                {"title": "Long Game", "traits": [], "section": "Games", "body": chunk},
                "mistral-large-2512",
                usage_record(
                    {"prompt_tokens": 100, "completion_tokens": 20},
                    request_max_output_tokens=512,
                ),
            )

        with patch("translate.request_translation", side_effect=reply) as request:
            translated, actual_model, usage = request_translation_in_chunks(
                "secret",
                "mistral-large-2512",
                "a",
                metadata,
                body,
                "pl",
                "en",
                "translation-pl-en-v5",
            )
        self.assertEqual(request.call_count, 2)
        self.assertEqual(translated["body"], body)
        self.assertEqual(actual_model, "mistral-large-2512")
        self.assertEqual(usage["requestAttempts"], 2)
        self.assertTrue(
            all(call.kwargs["protect_paragraph_breaks"] for call in request.call_args_list)
        )

    def test_translation_cost_reservation_covers_full_and_paragraph_retries(self):
        metadata = {
            "originalLanguage": "pl",
            "id": "a",
            "title": "Tytuł",
            "traits": [],
            "section": "Gry",
        }
        body = "Pierwszy.\n\nDrugi."
        full = request_reference_cost_upper_bound(
            metadata, body, "mistral-large-2512", "en"
        )
        self.assertEqual(
            translation_attempt_reference_cost_upper_bound(
                metadata, body, "mistral-large-2512", "en"
            ),
            round(6 * full, 8),
        )

    def test_failed_translation_usage_is_counted_without_marking_activity_complete(self):
        state = {
            "selectedActivityIds": ["a"],
            "completedActivityIds": [],
            "pendingActivityIds": ["a"],
            "models": [],
            "usage": {
                "promptTokens": 0,
                "completionTokens": 0,
                "requestMaxOutputTokens": 0,
                "referenceCostUsd": 0.0,
                "billingMode": "education-credit",
            },
        }
        usage = combine_usage_records(
            [
                usage_record(
                    {"prompt_tokens": 100, "completion_tokens": 50},
                    request_max_output_tokens=512,
                ),
                usage_record(
                    {"prompt_tokens": 120, "completion_tokens": 60},
                    request_max_output_tokens=640,
                ),
            ]
        )
        advance_failed_translation_usage(state, "mistral-large-2512", usage)
        self.assertEqual(state["completedActivityIds"], [])
        self.assertEqual(state["failedRequestUsage"]["requestAttempts"], 2)
        self.assertEqual(state["usage"]["promptTokens"], 220)
        self.assertEqual(state["usage"]["requestMaxOutputTokens"], 1152)

    def test_translation_output_budget_scales_and_is_bounded(self):
        self.assertEqual(translation_output_token_budget({"body": "short"}), MIN_OUTPUT_TOKENS)
        scaled = translation_output_token_budget({"body": "x" * 4000})
        self.assertGreater(scaled, MIN_OUTPUT_TOKENS)
        self.assertLess(scaled, MAX_OUTPUT_TOKENS)
        self.assertEqual(
            translation_output_token_budget({"body": "x" * 100_000}),
            MAX_OUTPUT_TOKENS,
        )

    def test_translation_repair_restores_a_source_digit_without_touching_urls(self):
        source = "Idź 40 kroków. https://example.test/40"
        translated = {
            "title": "Test",
            "section": "Games",
            "traits": ["invented"],
            "body": "Walk forty paces. https://example.test/40",
        }
        repaired, repairs = deterministic_translation_repairs(
            {"traits": []}, source, translated, "en"
        )
        self.assertEqual(repaired["traits"], [])
        self.assertEqual(repaired["body"], "Walk 40 paces. https://example.test/40")
        self.assertEqual(
            repairs,
            ["reset-invented-empty-traits", "restore-source-digit:40:1"],
        )
        protected_repaired, protected_repairs = deterministic_translation_repairs(
            {"traits": []},
            source,
            translated,
            "en",
            repair_number_words=False,
        )
        self.assertEqual(protected_repaired["body"], translated["body"])
        self.assertEqual(protected_repairs, ["reset-invented-empty-traits"])

    def test_french_source_requires_an_explicit_supported_target(self):
        self.assertEqual(translation_targets("fr"), ("pl", "en"))
        self.assertEqual(translation_target("fr", "pl"), "pl")
        self.assertEqual(translation_target("fr", "en"), "en")
        with self.assertRaisesRegex(ValueError, "multiple targets"):
            translation_target("fr")
        with self.assertRaisesRegex(ValueError, "fr->fr"):
            translation_target("fr", "fr")

    def test_french_feminine_scout_terms_are_not_flagged_as_invented(self):
        checks = translation_fidelity_checks(
            {"originalLanguage": "fr", "traits": []},
            "Deux éclaireuses commencent le jeu.",
            {
                "title": "Gra harcerek",
                "section": "Gry",
                "traits": [],
                "body": "Dwie harcerki rozpoczynają grę.",
            },
            "pl",
        )
        self.assertTrue(checks["noInventedFemaleScout"])

    def test_translation_url_fidelity_ignores_only_surrounding_punctuation(self):
        metadata = {"originalLanguage": "pl", "traits": []}
        source = "Zobacz [skan](https://example.test/item/123)."
        translated = {
            "title": "Scan",
            "section": "Source",
            "traits": [],
            "body": "See the scan: https://example.test/item/123, now.",
        }
        self.assertTrue(
            translation_fidelity_checks(metadata, source, translated, "en")[
                "urlsPreserved"
            ]
        )
        translated["body"] += " https://invented.test"
        self.assertFalse(
            translation_fidelity_checks(metadata, source, translated, "en")[
                "urlsPreserved"
            ]
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

        range_spacing_checks = translation_quality_checks(
            {"traits": [], "originalLanguage": "pl"},
            "Obozy są odległe o 5 — 10 km.",
            {
                "title": "Camps",
                "section": "Games",
                "traits": [],
                "body": "The camps are 5–10 km apart.",
            },
            "en",
        )
        self.assertTrue(range_spacing_checks["numbersPreserved"])

        retained_source_grouping_checks = translation_quality_checks(
            {"traits": [], "originalLanguage": "pl"},
            "Użyj mapy 1 : 100.000.",
            {
                "title": "Map",
                "section": "Games",
                "traits": [],
                "body": "Use a 1 : 100.000 map.",
            },
            "en",
        )
        self.assertTrue(retained_source_grouping_checks["numbersPreserved"])

    def test_mojmir_translation_evaluation_pins_v5_protected_values(self):
        root = Path(__file__).resolve().parents[1]
        config = load_evaluation_config(
            root / "config" / "v3-mojmir-translation-model-evaluation.yaml"
        )
        self.assertEqual(config["promptVersion"], "translation-pl-en-v5")
        self.assertEqual(config["promptEncoding"], "protected-values-v2")
        self.assertEqual(config["productionCandidate"], "mistral-large-2512")
        self.assertEqual(len(config["activityIds"]), 6)

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
        self.assertIn("Tekst źródłowy po angielsku", rendered)
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

    def test_french_source_is_embedded_on_both_translation_pages(self):
        record = {
            "id": "cha-001",
            "kinds": ["game"],
            "sourceId": "chamarande-1934",
            "author": "Jacques Sevin",
            "sourceTitle": "Chamarande",
            "sourceActivityTitle": "Jeu de piste",
            "sourceText": "Texte source français.",
            "year": 1934,
            "printedPages": [10],
            "pdfPages": [],
            "sourceUrl": "https://gallica.bnf.fr/ark:/12148/bpt6k3373518k",
            "digitalEditionUrl": "https://gallica.bnf.fr/ark:/12148/bpt6k3373518k",
            "facsimileUrl": "https://gallica.bnf.fr/ark:/12148/bpt6k3373518k/f10.item",
            "transcriptionStatus": "ocr-corrected",
            "safetyStatus": "historical-unreviewed",
            "originalLanguage": "fr",
            "locale": "pl",
            "title": "Gra tropicielska",
            "body": "Polskie tłumaczenie.",
            "summary": "Polskie tłumaczenie.",
            "traits": [],
            "translationStatus": "machine-translation",
            "translationModel": "mistral-large-2512",
        }
        polish = activity_page(record, locale="pl")
        english = activity_page(
            {
                **record,
                "locale": "en",
                "title": "Tracking game",
                "body": "English translation.",
                "summary": "English translation.",
            },
            locale="en",
        )
        self.assertIn('href="#source-text"', polish)
        self.assertIn("Tekst źródłowy po francusku", polish)
        self.assertIn('<span id="source-text"></span>', polish)
        self.assertIn("Francuski tekst źródłowy", polish)
        self.assertIn("Texte source français.", polish)
        self.assertIn("Source text in French", english)
        self.assertIn("French source text", english)
        self.assertIn("Texte source français.", english)

    def test_load_records_pairs_a_french_source_with_two_translations(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            source = {
                "id": "source-fr",
                "author": "Auteur",
                "title": "Livre",
                "year": 1934,
                "publisher": "Éditeur",
            }
            activity = {
                "id": "fr-001",
                "kinds": ["game"],
                "sourceId": "source-fr",
                "originalLanguage": "fr",
                "title": "Titre source",
                "traits": [],
                "section": "Section",
                "printedPages": [1],
                "sourceUrl": "https://example.test/source",
                "digitalEditionUrl": "https://example.test/text",
                "facsimileUrl": "https://example.test/text#page=1",
                "sourceRevision": "sha256:source",
                "sourceHash": "hash",
                "rightsStatus": "public-domain",
                "transcriptionStatus": "ocr-corrected",
                "safetyStatus": "historical-unreviewed",
            }
            translations = {
                "pl": ("Tytuł", "Polskie tłumaczenie."),
                "en": ("Title", "English translation."),
            }
            dump_markdown(vault / "sources" / "source-fr.md", source, "Source.")
            dump_markdown(vault / "activities" / "fr-001.md", activity, "Texte français.")
            for locale, (title, body) in translations.items():
                dump_markdown(
                    vault / "translations" / locale / "fr-001.md",
                    {
                        "activityId": "fr-001",
                        "locale": locale,
                        "title": title,
                        "traits": [],
                        "section": "Section",
                        "model": "mistral-large-2512",
                        "promptVersion": f"translation-fr-{locale}-v1",
                        "generatedAt": "2026-09-06",
                        "sourceHash": "hash",
                        "status": "machine-translation",
                    },
                    body,
                )
            with patch("build_content.VAULT", vault):
                polish, english, _ = load_records(include_similarities=False)
            self.assertEqual(polish[0]["sourceText"], "Texte français.")
            self.assertEqual(english[0]["sourceText"], "Texte français.")
            self.assertEqual(polish[0]["translationStatus"], "machine-translation")
            self.assertEqual(english[0]["translationStatus"], "machine-translation")

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
                polish, english, sources = load_records(include_similarities=False)
            self.assertEqual(set(sources), {"source-1"})
            self.assertEqual(polish[0]["translationStatus"], "machine-translation")
            self.assertEqual(polish[0]["title"], "Tytuł tłumaczenia")
            self.assertEqual(english[0]["translationStatus"], "source-text")
            self.assertEqual(english[0]["title"], "Source title")

            translation["activityId"] = "wrong-id"
            dump_markdown(vault / "translations" / "pl" / "test-001.md", translation, "Polskie tłumaczenie.")
            with patch("build_content.VAULT", vault), self.assertRaisesRegex(RuntimeError, "activity ID mismatch"):
                load_records(include_similarities=False)

    def test_approved_similar_games_are_linked_bidirectionally(self):
        polish, english, _ = load_records()
        for records in (polish, english):
            by_id = {record["id"]: record for record in records}
            self.assertEqual(
                [item["activityId"] for item in by_id["bsh-037"]["similarActivities"]],
                ["hwp-041"],
            )
            self.assertEqual(
                [item["activityId"] for item in by_id["hwp-041"]["similarActivities"]],
                ["bsh-037"],
            )
            rendered = activity_page(by_id["bsh-037"], locale=records[0]["locale"])
            self.assertIn("hwp-041", rendered)
            self.assertIn(escape(by_id["hwp-041"]["title"]), rendered)
            self.assertIn(
                "Bardzo podobne gry" if records[0]["locale"] == "pl" else "Highly similar games",
                rendered,
            )

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

    def test_gutenberg_uses_the_machine_readable_metadata_catalog(self):
        root = Path(__file__).resolve().parents[1]
        registry = yaml.safe_load((root / "config" / "source-registry.yaml").read_text(encoding="utf-8"))
        gutenberg = next(item for item in registry["collections"] if item["id"] == "project-gutenberg")
        self.assertEqual(gutenberg["metadataAdapter"], "scripts/gutenberg_metadata.py")
        self.assertEqual(
            gutenberg["metadataUrlTemplate"],
            "https://www.gutenberg.org/cache/epub/{ebookId}/pg{ebookId}.rdf",
        )
        self.assertEqual(
            gutenberg["robotPolicyUrl"],
            "https://www.gutenberg.org/policy/robot_access.html",
        )


if __name__ == "__main__":
    unittest.main()
