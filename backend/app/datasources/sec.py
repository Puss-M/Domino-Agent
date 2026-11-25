"""SEC EDGAR connector.

The SEC asks automated clients to identify themselves and to stay below
10 requests/second. Both rules are enforced here. XBRL "company facts" are
useful because they preserve the filing date (`filed`) next to each value,
which makes a point-in-time reconstruction possible; the convenience API does
not, so it is labelled as revised data.
"""

from __future__ import annotations

import html
import re
from datetime import date

from .base import BaseConnector, DataSourceError

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def html_to_text(raw: str) -> str:
    raw = _SCRIPT_RE.sub(" ", raw)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", raw, flags=re.IGNORECASE)
    text = html.unescape(_TAG_RE.sub(" ", raw))
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


class SecEdgar(BaseConnector):
    name = "sec"
    base_url = "https://data.sec.gov"
    min_interval = 0.13

    def __init__(self, settings):
        super().__init__(settings)
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )

    def _get_sec_json(self, url: str, cache_key: str, ttl_seconds: int = 7 * 86400):
        # data.sec.gov and www.sec.gov use different Host headers.
        headers = {"User-Agent": self.settings.user_agent, "Accept": "application/json"}
        return self.get_json(url, cache_key=cache_key, ttl_seconds=ttl_seconds, headers=headers)

    def company_tickers(self) -> dict[str, dict]:
        response = self._get_sec_json(
            "https://www.sec.gov/files/company_tickers.json",
            "company_tickers",
            ttl_seconds=30 * 86400,
        )
        payload = response.payload
        result = {}
        for row in payload.values():
            result[str(row["ticker"]).upper()] = {
                "cik": int(row["cik_str"]),
                "title": row["title"],
            }
        return result

    def cik_for(self, ticker: str) -> int:
        tickers = self.company_tickers()
        try:
            return tickers[ticker.upper()]["cik"]
        except KeyError as exc:
            raise DataSourceError(f"unknown ticker {ticker!r}") from exc

    def submissions(self, cik: int) -> dict:
        url = f"{self.base_url}/submissions/CIK{cik:010d}.json"
        return self._get_sec_json(url, f"submissions:{cik}").payload

    def recent_filings(self, cik: int, form: str | None = None, limit: int = 10) -> list[dict]:
        payload = self.submissions(cik)
        recent = payload.get("filings", {}).get("recent", {})
        rows = []
        for idx, form_type in enumerate(recent.get("form", [])):
            if form and form_type != form:
                continue
            rows.append(
                {
                    "form": form_type,
                    "filing_date": recent["filingDate"][idx],
                    "report_date": recent["reportDate"][idx],
                    "accession": recent["accessionNumber"][idx],
                    "primary_document": recent["primaryDocument"][idx],
                    "description": recent.get("primaryDocDescription", [""] * len(recent["form"]))[idx],
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def filing_index(self, cik: int, accession: str) -> dict:
        accession_nodash = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/index.json"
        )
        return self._get_sec_json(url, f"index:{cik}:{accession}").payload

    def filing_document_url(self, cik: int, accession: str, document: str) -> str:
        accession_nodash = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{document}"

    def filing_text(self, cik: int, accession: str, document: str) -> str:
        url = self.filing_document_url(cik, accession, document)
        response = self.get_text(
            url,
            cache_key=f"filing:{cik}:{accession}:{document}",
            ttl_seconds=30 * 86400,
            headers={"User-Agent": self.settings.user_agent, "Accept": "text/html"},
        )
        return html_to_text(response.payload)

    def press_release(self, ticker: str, limit: int = 1) -> list[dict]:
        """Return the text of the latest 8-K exhibit(s), usually an earnings release."""
        cik = self.cik_for(ticker)
        releases = []
        for filing in self.recent_filings(cik, form="8-K", limit=12):
            index = self.filing_index(cik, filing["accession"])
            items = index.get("directory", {}).get("item", [])
            candidates = [
                item["name"]
                for item in items
                if item["name"].lower().endswith((".htm", ".html"))
                and ("ex99" in item["name"].lower() or "exhibit99" in item["name"].lower())
            ]
            if not candidates:
                candidates = [
                    filing["primary_document"]
                    if filing["primary_document"].lower().endswith((".htm", ".html"))
                    else ""
                ]
            document = next((c for c in candidates if c), "")
            if not document:
                continue
            text = self.filing_text(cik, filing["accession"], document)
            if len(text) < 500:
                continue
            releases.append(
                {
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "accession": filing["accession"],
                    "filing_date": filing["filing_date"],
                    "document": document,
                    "url": self.filing_document_url(cik, filing["accession"], document),
                    "text": text,
                }
            )
            if len(releases) >= limit:
                break
        return releases

    def company_facts(self, cik: int) -> dict:
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik:010d}.json"
        return self._get_sec_json(url, f"facts:{cik}", ttl_seconds=7 * 86400).payload

    def metric_history(
        self,
        ticker: str,
        tag: str = "Revenues",
        unit: str = "USD",
        limit: int = 12,
    ) -> list[dict]:
        """Extract a revenue/EPS history with the date each value was filed."""
        cik = self.cik_for(ticker)
        facts = self.company_facts(cik)
        units = (
            facts.get("facts", {})
            .get("us-gaap", {})
            .get(tag, {})
            .get("units", {})
            .get(unit, [])
        )
        rows = []
        for row in units:
            if "filed" not in row or row.get("form") not in {"10-K", "10-Q", "8-K"}:
                continue
            rows.append(
                {
                    "ticker": ticker.upper(),
                    "tag": tag,
                    "end": row.get("end"),
                    "start": row.get("start"),
                    "value": row.get("val"),
                    "fy": row.get("fy"),
                    "fp": row.get("fp"),
                    "form": row.get("form"),
                    "filed": row.get("filed"),
                    "frame": row.get("frame"),
                }
            )
        rows.sort(key=lambda item: (item["filed"] or "", item["end"] or ""))
        return rows[-limit:]

    def latest_filing_date(self, ticker: str) -> date | None:
        cik = self.cik_for(ticker)
        filings = self.recent_filings(cik, limit=1)
        if not filings:
            return None
        return date.fromisoformat(filings[0]["filing_date"])
