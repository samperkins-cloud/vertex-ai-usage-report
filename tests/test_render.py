import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import render

VALUES = {
    "BILLING_TABLE": "my-proj.billing.gcp_billing_export_resource_v1_XXXXXX_XXXXXX_XXXXXX",
    "AUDIT_DATASET": "my-proj.vertex_audit",
    "AUDIT_TABLE": "cloudaudit_googleapis_com_data_access_*",
    "OUT_DATASET": "my-proj.ai_usage",
    "PROJECT_ID": "my-proj",
    "START_DATE": "2026-01-01",
    "TIMEZONE": "UTC",
}


class RenderTests(unittest.TestCase):
    def test_substitutes(self):
        self.assertEqual(render.render("a ${PROJECT_ID} b ${PROJECT_ID}", VALUES), "a my-proj b my-proj")

    def test_missing_value_raises(self):
        with self.assertRaises(KeyError):
            render.render("${NOPE}", VALUES)

    def test_every_query_renders_clean(self):
        files = render.sql_files()
        self.assertEqual(len(files), 4)
        for f in files:
            text = render.render(f.read_text(), VALUES)
            self.assertEqual(render.leftover(text), [], f.name)
            self.assertIn("my-proj", text)

    def test_queries_only_use_known_placeholders(self):
        known = set(render.REQUIRED) | set(render.DEFAULTS)
        for f in render.sql_files():
            self.assertLessEqual(set(render.leftover(f.read_text())), known, f.name)

    def test_cli_writes_files(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = render.main(["--billing-table", "p.b.t", "--audit-dataset", "p.a",
                                  "--out-dataset", "p.o", "--project-id", "p", "--out", d])
            self.assertEqual(rc, 0)
            written = sorted(x.name for x in Path(d).glob("*.sql"))
            self.assertEqual(len(written), 4)
            self.assertNotIn("${", (Path(d) / written[0]).read_text())

    def test_cli_requires_values(self):
        with self.assertRaises(SystemExit):
            render.main(["--project-id", "p"])


class SqlParseTests(unittest.TestCase):
    def test_parses_as_bigquery(self):
        try:
            import sqlglot
        except ImportError:
            self.skipTest("sqlglot not installed")
        for f in render.sql_files():
            text = render.render(f.read_text(), VALUES)
            sqlglot.parse(text, dialect="bigquery")


if __name__ == "__main__":
    unittest.main()
