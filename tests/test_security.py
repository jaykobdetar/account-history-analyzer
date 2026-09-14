"""OUT-03/04: hostile supplied prose stays inert in real report templates."""
from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]


class ResourceAudit(HTMLParser):
    """Parse actual elements/attributes rather than matching escaped source text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.violations = []
        self.style_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "iframe", "object", "embed", "base", "form", "foreignobject", "animate", "set"}:
            self.violations.append("active element: " + tag)
        if tag == "style":
            self.style_depth += 1
        attributes = dict(attrs)
        for key, value in attrs:
            value = value or ""
            if key.startswith("on") or key == "srcdoc":
                self.violations.append("active attribute: " + key)
            if key in {"href", "xlink:href", "src", "action", "formaction"} and re.match(r"\s*(?:javascript|vbscript|data:text/html):", value, re.I):
                self.violations.append("unsafe URL: " + value)
            if key in {"src", "srcset", "poster", "background"} or tag in {"link", "image", "use"} and key in {"href", "xlink:href"}:
                if re.search(r"(?:https?:|//)", value, re.I):
                    self.violations.append("remote asset: " + value)
            if key == "style":
                self._css(value)
        if tag == "meta" and attributes.get("http-equiv", "").lower() == "refresh":
            self.violations.append("meta refresh")

    def handle_endtag(self, tag):
        if tag == "style":
            self.style_depth = max(0, self.style_depth - 1)

    def handle_data(self, data):
        if self.style_depth:
            self._css(data)

    def _css(self, source):
        if re.search(r"@import|url\s*\(\s*['\"]?(?:https?:|//)|expression\s*\(", source, re.I):
            self.violations.append("remote/active CSS")


def make_hostile_report(directory: Path):
    """Create real supplied records and render their actual evidence excerpts."""
    from account_history_analyzer.artifacts import write_artifacts
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.pipeline import analyze
    source = (
        '<script>window.__AHAS_EXECUTED=true;alert("source executed")</script>\n\n'
        '![tracking](https://ahas-tracker.invalid/pixel.png) '
        '[unsafe](javascript:alert(1)) </details><iframe src="https://ahas-tracker.invalid/frame"></iframe>\n\n'
        'ordinary retained prose includes enough complete words for literal reuse evidence and inspectable source context. ' * 3
    )
    records = [{
        "schema_version": "1.0.0", "id": f'../../hostile-{index}<img src=x onerror="window.__AHAS_EXECUTED=true">',
        "account_id": "supplied-account", "kind": "comment", "text": source, "status": "present",
        "created_utc": f"2025-01-01T00:00:0{index}Z", "permalink": "javascript:alert(1)",
    } for index in range(2)]
    manifest = {
        "schema_version": "1.0.0", "snapshot_id": 'source </details><img src="https://ahas-tracker.invalid/id.png" onerror="alert(1)">',
        "account_id": "supplied-account", "source_category": "synthetic", "text_format": "markdown",
        "default_language": "en", "coverage": {"status": "unknown"},
    }
    directory.mkdir(parents=True, exist_ok=True)
    input_path, manifest_path = directory / "records.jsonl", directory / "snapshot.json"
    input_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    analysis = analyze(load_snapshot(input_path, manifest_path))
    destination = directory / "report"
    write_artifacts(analysis, destination)
    return analysis, destination


def test_out03_hostile_markdown_and_html_have_no_active_source_markup(tmp_path):
    _, destination = make_hostile_report(tmp_path)
    html = (destination / "report.html").read_text(encoding="utf-8")
    markdown = (destination / "report.md").read_text(encoding="utf-8")
    # CommonMark raw HTML is enabled deliberately: escaped source must remain
    # inert even in a normal Markdown viewer supporting template disclosure tags.
    for document in (html, MarkdownIt("commonmark", {"html": True}).render(markdown)):
        audit = ResourceAudit()
        audit.feed(document)
        assert audit.violations == []
    assert "ahas-tracker.invalid" in html  # Actual source, not merely an empty safe report.
    assert "&lt;" in html or "&#60;" in html


def test_out12_excerpt_omission_does_not_change_measurements(tmp_path):
    from account_history_analyzer.io import canonical_bytes, thaw
    from account_history_analyzer.reporting import render_html, render_markdown
    analysis, _ = make_hostile_report(tmp_path)
    result = thaw(analysis.results)
    before = canonical_bytes(result)
    evidence = [json.loads(line) for line in analysis.files["evidence.jsonl"].splitlines()]
    for renderer in (render_html, render_markdown):
        document = renderer(result, evidence, excerpts="none")
        assert "ordinary retained prose includes enough complete words" not in document
        assert "Remaining identifiers" in document or "may still identify" in document
        assert canonical_bytes(result) == before


def test_out04_real_browser_remote_requests_intercepted(tmp_path):
    if os.environ.get("AHAS_NETWORK_ISOLATION") == "linux_seccomp_socket_denial":
        pytest.skip("Analyzer seccomp forbids Chrome Unix IPC; run browser audit separately with browser_offline_exec.py")
    if not shutil.which("google-chrome") or not shutil.which("node"):
        pytest.skip("Installed Chrome and Node are required for the separate real-browser audit")
    if not os.environ.get("AHAS_RUN_BROWSER_AUDIT"):
        pytest.skip("Set AHAS_RUN_BROWSER_AUDIT=1 for the separate browser seccomp/CDP audit")
    _, destination = make_hostile_report(tmp_path)
    completed = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "browser_offline_exec.py"), "node",
        str(ROOT / "scripts" / "check_report_browser.cjs"), str(destination / "report.html"),
    ], capture_output=True, text=True, timeout=45, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["isolation"] == "linux_seccomp_nonunix_socket_denial"
    assert result["remoteRequests"] == []
    assert result["sourceExecuted"] is False
