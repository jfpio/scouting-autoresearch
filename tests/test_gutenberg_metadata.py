import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gutenberg_metadata import build_record, fetch_rdf, metadata_url, parse_rdf


RDF = b'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:pgterms="http://www.gutenberg.org/2009/pgterms/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dcam="http://purl.org/dc/dcam/">
  <pgterms:ebook rdf:about="ebooks/123">
    <dcterms:title>Example Book</dcterms:title>
    <dcterms:issued>2020-01-02</dcterms:issued>
    <dcterms:rights>Public domain in the USA.</dcterms:rights>
    <dcterms:creator>
      <pgterms:agent>
        <pgterms:name>Example, Alice</pgterms:name>
        <pgterms:birthdate>1850</pgterms:birthdate>
        <pgterms:deathdate>1910</pgterms:deathdate>
        <pgterms:alias>Alice Example</pgterms:alias>
        <pgterms:webpage rdf:resource="https://example.test/alice"/>
      </pgterms:agent>
    </dcterms:creator>
    <dcterms:language><rdf:Description><rdf:value>en</rdf:value></rdf:Description></dcterms:language>
    <dcterms:subject><rdf:Description>
      <dcam:memberOf rdf:resource="http://purl.org/dc/terms/LCSH"/>
      <rdf:value>Scouting</rdf:value>
    </rdf:Description></dcterms:subject>
    <pgterms:bookshelf><rdf:Description><rdf:value>Adventure</rdf:value></rdf:Description></pgterms:bookshelf>
    <dcterms:hasFormat><pgterms:file rdf:about="https://www.gutenberg.org/files/123/123-0.txt">
      <dcterms:extent>42</dcterms:extent>
      <dcterms:modified>2026-01-01T00:00:00</dcterms:modified>
      <dcterms:format><rdf:Description><rdf:value>text/plain; charset=utf-8</rdf:value></rdf:Description></dcterms:format>
    </pgterms:file></dcterms:hasFormat>
  </pgterms:ebook>
</rdf:RDF>'''


class GutenbergMetadataTests(unittest.TestCase):
    def test_parse_rdf_normalizes_core_metadata(self):
        record = parse_rdf(RDF, 123)
        self.assertEqual(record["title"], "Example Book")
        self.assertEqual(record["rightsClaim"], "Public domain in the USA.")
        self.assertEqual(record["languages"], ["en"])
        self.assertEqual(record["creators"][0]["deathYear"], 1910)
        self.assertEqual(record["subjects"], [{"value": "Scouting", "scheme": "LCSH"}])
        self.assertEqual(record["formats"][0]["bytes"], 42)

    def test_build_record_is_hash_pinned(self):
        record = build_record(RDF, 123, "2026-09-04T00:00:00+00:00")
        self.assertEqual(record["schemaVersion"], 1)
        self.assertEqual(record["collectionId"], "project-gutenberg")
        self.assertEqual(record["sourceSha256"], hashlib.sha256(RDF).hexdigest())

    def test_requested_id_must_match_rdf(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            parse_rdf(RDF, 124)

    def test_rdf_document_type_is_rejected(self):
        unsafe = b'<!DOCTYPE rdf:RDF [<!ENTITY x "unsafe">]>' + RDF
        with self.assertRaisesRegex(ValueError, "forbidden"):
            parse_rdf(unsafe, 123)

    def test_cached_rdf_is_reused_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "123.rdf"
            cache.write_bytes(RDF)
            expected = hashlib.sha256(RDF).hexdigest()
            data, digest, reused = fetch_rdf(123, cache, expected_sha256=expected)
        self.assertEqual(data, RDF)
        self.assertEqual(digest, expected)
        self.assertTrue(reused)

    def test_metadata_url_rejects_nonpositive_id(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            metadata_url(0)


if __name__ == "__main__":
    unittest.main()
