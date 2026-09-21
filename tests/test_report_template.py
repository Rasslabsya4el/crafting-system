"""Focused contract checks for the standalone report asset."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


TEMPLATE = Path(__file__).parents[1] / "src" / "craftoracle" / "report_assets" / "template.html"


def test_template_contains_safe_offline_rendering_contract() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "{{REPORT_TITLE}}" in content
    assert "{{REPORT_DATA}}" in content
    assert 'type="application/json"' in content
    assert "safeLocalPath" in content
    assert "textContent" in content
    assert "https://" not in content
    assert "http://" not in content


def test_pure_javascript_formats_probabilities_escapes_values_and_keeps_duplicate_keys() -> None:
    content = TEMPLATE.read_text(encoding="utf-8")
    script = content.split('<script>\n  "use strict";', 1)[1].split("// START_APP", 1)[0]
    fixture = {"routes": [{"key": "same-60", "id": "same"}, {"key": "same-100", "id": "same"}]}
    program = """
      global.document = {getElementById: () => ({textContent: %s})};
      global.location = {hash: '#same-100'};
      %s
      const t = globalThis.ReportTemplate;
      const result = {
        probability: t.probability(0.000024282),
        zero: t.probability(0),
        rounded_zero: t.numeric(-1e-12),
        cost: t.numeric(1927.479966),
        escaped: t.escapeText('</script><img src=x onerror=1>'),
        valid: t.safeLocalPath('proof/pytest.xml'),
        rejected: t.safeLocalPath('../secret'),
        scheme: t.safeLocalPath('https://example.invalid/proof'),
        selected: t.routeByKey('same-100').key
      };
      console.log(JSON.stringify(result));
    """ % (json.dumps(json.dumps(fixture, ensure_ascii=False)), script)

    completed = subprocess.run(["node", "-e", program], check=True, text=True, capture_output=True)
    result = json.loads(completed.stdout)
    assert result["probability"] == "&lt;0,1% (примерно 1 из 41\u00a0183)"
    assert result["zero"] == "0,0%"
    assert result["rounded_zero"] == "0,0"
    assert result["cost"] == "1\u00a0927,5"
    assert result["escaped"] == "&lt;/script&gt;&lt;img src=x onerror=1&gt;"
    assert result["valid"] == "proof/pytest.xml"
    assert result["rejected"] is None
    assert result["scheme"] is None
    assert result["selected"] == "same-100"
