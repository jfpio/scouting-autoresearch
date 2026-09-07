import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "styles" / "site.css").read_text(encoding="utf-8")


def block(selector: str) -> dict[str, str]:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", CSS)
    if not match:
        raise AssertionError(f"Missing CSS block: {selector}")
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", match.group(1)))


def luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(left: str, right: str) -> float:
    brighter, darker = sorted((luminance(left), luminance(right)), reverse=True)
    return (brighter + 0.05) / (darker + 0.05)


class ThemeContrastTests(unittest.TestCase):
    def test_dark_theme_overrides_starlight_neutrals_with_readable_text(self):
        dark = block(":root[data-theme='dark']")
        self.assertEqual(dark["--sl-color-black"], dark["--paper"])
        for variable in ("--sl-color-white", "--sl-color-gray-2", "--ink", "--muted"):
            self.assertGreaterEqual(contrast(dark[variable], dark["--paper"]), 4.5)


if __name__ == "__main__":
    unittest.main()
