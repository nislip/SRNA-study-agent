#!/usr/bin/env python3
"""
Monthly DailyMed label refresh for the drug-conversions skill.

What it does
  1. Reads the curated list in drugs.yaml.
  2. For each drug, finds its label on DailyMed (keyless v2 API, GET only).
  3. Compares the label's spl_version with manifest.json. Only labels that
     changed are downloaded and rewritten, so most monthly runs make very few
     requests and produce a small diff.
  4. Writes references/<id>.md (selected sections only) and references/INDEX.md
     into the skill folder, and a change summary used as the PR body.

Design notes
  - Label choice is "sticky": once a setid is picked it is saved in the
    manifest and reused, so a drug never silently jumps to a different
    manufacturer's label. Pin a setid in drugs.yaml to choose one explicitly.
  - Auto-picks are flagged in the summary so you can review and pin them.
  - A failed fetch never deletes or changes an existing reference file.
  - Removing a drug from drugs.yaml deletes its reference file on the next run.
  - Run-to-run output is deterministic (no "last checked" timestamps), so an
    unchanged month produces no diff and therefore no pull request.

Usage
  python update_dailymed.py --skill-dir space/skills/drug-conversions
  python update_dailymed.py --skill-dir ... --only rocuronium sugammadex   # test a few
  python update_dailymed.py --skill-dir ... --force                       # rebuild all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={}"
RX_DOCTYPE = "34391-3"  # LOINC document type: human prescription drug label
NS = "{urn:hl7-org:v3}"

# Label sections to keep (LOINC section codes), in output order.
# Older non-PLR labels use Warnings (34071-1) and Precautions (42232-9)
# instead of Warnings and Precautions (43685-7), so all three are listed;
# a label only ever has one style.
SECTIONS = [
    ("34066-1", "Boxed Warning"),
    ("34067-9", "Indications and Usage"),
    ("34068-7", "Dosage and Administration"),
    ("43678-2", "Dosage Forms and Strengths"),
    ("34089-3", "Description"),          # chemical name, formula, molecular weight, pH, pKa
    ("34070-3", "Contraindications"),
    ("43685-7", "Warnings and Precautions"),
    ("34071-1", "Warnings"),
    ("42232-9", "Precautions"),
    ("43684-0", "Use in Specific Populations"),
    ("34088-5", "Overdosage"),
    ("34090-1", "Clinical Pharmacology"),
]
MAX_SECTION_CHARS = 15000   # keeps any one file small; truncation is noted in the file
SEARCH_PAGE_SIZE = 50       # smaller pages: DailyMed returns 503s on heavy queries (e.g. morphine)
MAX_SEARCH_PAGES = 10       # up to 500 labels; popular generics have hundreds
REQUEST_DELAY = 0.25        # seconds between calls, to be polite to NLM

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- HTTP

def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=3, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = "SugammaRex-skill-refresh/1.0 (monthly DailyMed sync)"
    return s


def get(session: requests.Session, path: str, **params) -> requests.Response:
    r = session.get(f"{API}/{path}", params=params, timeout=60)
    time.sleep(REQUEST_DELAY)
    r.raise_for_status()
    return r


def spl_meta(session, setid: str) -> dict | None:
    """Current version info for one label, or None if the setid no longer exists."""
    data = get(session, "spls.json", setid=setid).json().get("data", [])
    return data[0] if data else None


def parse_date(s: str) -> dt.date:
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            pass
    return dt.date.min


def search_labels(session, entry: dict, defaults: dict) -> list[dict]:
    """Labels matching the drug's search name and title filters, newest first."""
    include = [w.upper() for w in as_list(entry.get("title_contains"))]
    exclude = [w.upper() for w in as_list(defaults.get("exclude")) + as_list(entry.get("exclude"))]

    def fetch(with_doctype: bool) -> list[dict]:
        out, page = [], 1
        while page <= MAX_SEARCH_PAGES:
            params = {"drug_name": entry["search"], "pagesize": SEARCH_PAGE_SIZE, "page": page}
            if with_doctype:
                params["doctype"] = RX_DOCTYPE
            j = get(session, "spls.json", **params).json()
            out += j.get("data", [])
            total = int(j.get("metadata", {}).get("total_pages") or 1)
            if page >= total:
                break
            page += 1
        return out

    # Try with the prescription-label filter first. If that returns nothing, or
    # DailyMed errors on the filtered query, retry once without it.
    try:
        labels = fetch(True)
    except requests.RequestException as e:
        print(f"         {entry['id']}: filtered search failed ({type(e).__name__}); retrying without it")
        labels = []
    labels = labels or fetch(False)
    keep = []
    for lab in labels:
        title = (lab.get("title") or "").upper()
        if all(w in title for w in include) and not any(w in title for w in exclude):
            keep.append(lab)
    keep.sort(key=lambda l: parse_date(l.get("published_date", "")), reverse=True)
    return keep


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ------------------------------------------------------------- SPL XML → markdown

def local(tag) -> str:
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def inline(el) -> str:
    """Flatten an element's text, keeping super/subscripts readable."""
    parts = [el.text or ""]
    for ch in el:
        t = local(ch.tag)
        if t == "br":
            parts.append(" ")
        elif t == "renderMultiMedia":
            parts.append(" [figure omitted] ")
        elif t == "sup":
            parts.append("^" + inline(ch))
        elif t == "sub":
            parts.append(inline(ch))  # C32H53BrN2O4 reads better than C_32H_53...
        elif t == "footnote":
            pass  # footnotes clutter dosing tables; full text is on DailyMed
        else:
            parts.append(inline(ch))
        parts.append(ch.tail or "")
    return "".join(parts)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def render_table(tbl) -> list[str]:
    rows = []
    for tr in tbl.iter(f"{NS}tr"):
        cells = [clean(inline(td)).replace("|", "\\|") for td in tr
                 if local(td.tag) in ("td", "th")]
        if any(cells):
            rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = []
    cap = tbl.find(f"{NS}caption")
    if cap is not None and clean(inline(cap)):
        out.append(f"*{clean(inline(cap))}*")
        out.append("")
    out.append("| " + " | ".join(rows[0]) + " |")
    out.append("|" + "---|" * width)
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    out.append("")
    return out


def render_block(el) -> list[str]:
    """Render the children of a <text> (or similar) element."""
    out = []
    if el.text and el.text.strip():
        out += [clean(el.text), ""]
    for ch in el:
        t = local(ch.tag)
        if t == "paragraph":
            txt = clean(inline(ch))
            if txt:
                out += [txt, ""]
        elif t == "list":
            ordered = ch.get("listType") == "ordered"
            for i, item in enumerate(ch.findall(f"{NS}item"), 1):
                txt = clean(inline(item))
                if txt:
                    out.append(f"{i}. {txt}" if ordered else f"- {txt}")
            out.append("")
        elif t == "table":
            out += render_table(ch)
        elif t == "renderMultiMedia":
            out += ["[figure omitted, see full label]", ""]
        else:
            txt = clean(inline(ch))
            if txt:
                out += [txt, ""]
        if ch.tail and ch.tail.strip():
            out += [clean(ch.tail), ""]
    return out


def render_section(sec, depth: int, fallback_title: str = "") -> list[str]:
    title_el = sec.find(f"{NS}title")
    title = clean(inline(title_el)) if title_el is not None else ""
    out = [f"{'#' * min(depth, 6)} {title or fallback_title}", ""]
    text = sec.find(f"{NS}text")
    if text is not None:
        out += render_block(text)
    for sub in sec.findall(f"{NS}component/{NS}section"):
        out += render_section(sub, depth + 1)
    return out


def render_ingredients(root) -> list[str]:
    """DailyMed's "Ingredients and Appearance" data: each product's form, route,
    active ingredient strength, and inactive ingredients. This comes from the
    label's structured product data, not its text, so it is reliable for math."""
    def strength(ing) -> str:
        q = ing.find(f"{NS}quantity")
        if q is None:
            return ""
        num, den = q.find(f"{NS}numerator"), q.find(f"{NS}denominator")
        def fmt(x):
            if x is None or not x.get("value"):
                return ""
            unit = x.get("unit", "")
            return f"{x.get('value')} {unit if unit != '1' else ''}".strip()
        n, d = fmt(num), fmt(den)
        return f"{n} in {d}" if n and d and d != "1" else n

    rows, inactive_sets, seen = [], {}, set()
    for subj in root.iter(f"{NS}subject"):
        prod = subj.find(f"{NS}manufacturedProduct/{NS}manufacturedProduct")
        if prod is None:
            continue
        name_el, form_el = prod.find(f"{NS}name"), prod.find(f"{NS}formCode")
        name = clean(inline(name_el)) if name_el is not None else ""
        form = (form_el.get("displayName") or "").title() if form_el is not None else ""
        routes = sorted({(r.get("displayName") or "").title()
                         for r in subj.iter(f"{NS}routeCode") if r.get("displayName")})
        active, inactive = [], []
        for ing in prod.findall(f"{NS}ingredient"):
            sub = ing.find(f"{NS}ingredientSubstance")
            if sub is None:
                continue
            iname = clean(inline(sub.find(f"{NS}name"))) if sub.find(f"{NS}name") is not None else ""
            code = sub.find(f"{NS}code")
            unii = code.get("code") if code is not None else ""
            if ing.get("classCode", "").startswith("ACT"):
                active.append(f"{iname} ({strength(ing)})" + (f" [UNII {unii}]" if unii else ""))
            else:
                amt = strength(ing)
                inactive.append(f"{iname} {amt}".strip())
        if not active:
            continue
        key = (name, form, tuple(active))
        if key in seen:  # same product in several package sizes
            continue
        seen.add(key)
        rows.append([name, form, ", ".join(routes), "; ".join(active)])
        if inactive:
            inactive_sets.setdefault(tuple(inactive), []).append(name or form)

    if not rows:
        return []
    out = ["## Ingredients and Composition", "",
           "_From DailyMed's structured product data. Strength is per the stated volume or unit._", "",
           "| product | form | route | active ingredient (strength) |", "|---|---|---|---|"]
    out += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows]
    out.append("")
    for ingredients, prods in inactive_sets.items():
        label = "Inactive ingredients" + (f" ({', '.join(sorted(set(prods)))})" if len(inactive_sets) > 1 else "")
        out += [f"**{label}:** " + "; ".join(ingredients), ""]
    return out


def truncate(lines: list[str], url: str) -> list[str]:
    text = "\n".join(lines)
    if len(text) <= MAX_SECTION_CHARS:
        return lines
    cut = text.rfind("\n", 0, MAX_SECTION_CHARS)
    text = text[: cut if cut > 0 else MAX_SECTION_CHARS]
    return text.split("\n") + ["", f"_[Section truncated for length. Full text: {url}]_", ""]


def label_to_markdown(xml_bytes: bytes, drug: dict, meta: dict) -> str:
    root = ET.fromstring(xml_bytes)
    url = LABEL_URL.format(meta["setid"])

    found = {}
    for sec in root.iter(f"{NS}section"):  # document order: parents before children
        code_el = sec.find(f"{NS}code")
        code = code_el.get("code") if code_el is not None else None
        if code and code not in found:
            found[code] = sec

    title_el = root.find(f"{NS}title")
    doc_title = clean(inline(title_el)) if title_el is not None else meta.get("title", "")

    header = [
        "---",
        f"drug: {drug['id']}",
        f"aliases: {', '.join(as_list(drug.get('aliases'))) or 'none'}",
        f"label: {meta.get('title', '').strip()}",
        f"setid: {meta['setid']}",
        f"spl_version: {meta.get('spl_version')}",
        f"published: {meta.get('published_date')}",
        f"source: {url}",
        "---",
        "",
        f"# {drug['id']}: FDA label excerpt",
        "",
        "> Selected sections of the FDA-approved label, from DailyMed (National Library of Medicine). "
        "Sections not shown were omitted to save space. Label dosing can differ from anesthesia "
        "practice and institutional protocols. Study use only.",
        "",
    ]
    if doc_title:
        header += [f"**Label title:** {doc_title}", ""]

    body, missing = [], []
    for code, name in SECTIONS:
        sec = found.get(code)
        if sec is None:
            missing.append(name)
            continue
        body += truncate(render_section(sec, depth=2, fallback_title=name), url)
        if code == "34089-3":
            body += truncate(render_ingredients(root), url)

    if "34089-3" not in found:  # no Description section: still include the ingredients table
        body += truncate(render_ingredients(root), url)
    if not body:
        raise ValueError("no recognised sections in label XML")
    tail = []
    present_style_missing = [m for m in missing if m not in ("Warnings", "Precautions", "Warnings and Precautions")]
    if present_style_missing:
        tail = ["---", "", f"_Not present on this label: {', '.join(present_style_missing)}._", ""]
    return "\n".join(header + body + tail).rstrip() + "\n"


# ----------------------------------------------------------------------- main loop

def write_index(skill_dir: Path, drugs: list[dict], manifest: dict) -> None:
    lines = [
        "# Drug reference index",
        "",
        "Generated monthly from DailyMed. Open `references/<file>` for the drug you need. "
        "Match on the id or any alias. Drugs not listed here are not bundled; use a live label lookup instead.",
        "",
        "| id | file | aliases | label | version | published |",
        "|---|---|---|---|---|---|",
    ]
    for d in sorted(drugs, key=lambda d: d["id"]):
        m = manifest.get(d["id"])
        if not m:
            continue
        aliases = ", ".join(as_list(d.get("aliases"))) or ""
        lines.append(f"| {d['id']} | {m['file']} | {aliases} | {m['title'].replace('|', '/')} "
                     f"| {m['spl_version']} | {m['published_date']} |")
    (skill_dir / "references" / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill-dir", required=True, help="folder containing the skill's SKILL.md")
    ap.add_argument("--config", default=str(HERE / "drugs.yaml"))
    ap.add_argument("--manifest", default=str(HERE / "manifest.json"))
    ap.add_argument("--summary", default="dailymed_summary.md", help="markdown change report (keep outside the repo)")
    ap.add_argument("--only", nargs="*", help="process only these drug ids (testing)")
    ap.add_argument("--force", action="store_true", help="rebuild files even if versions match")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir)
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    drugs, defaults = cfg.get("drugs", []), cfg.get("defaults", {}) or {}
    ids = [d["id"] for d in drugs]
    if len(ids) != len(set(ids)):
        sys.exit("drugs.yaml has duplicate ids")

    mpath = Path(args.manifest)
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    session = make_session()

    updated, auto_picked, failed, removed = [], [], [], []
    unchanged = 0
    todo = [d for d in drugs if not args.only or d["id"] in args.only]

    for n, d in enumerate(todo, 1):
        did = d["id"]
        prev = manifest.get(did, {})
        print(f"[{n}/{len(todo)}] {did}")
        try:
            pinned = d.get("setid")
            meta, note = None, ""
            if pinned:
                meta = spl_meta(session, pinned)
                if not meta:
                    raise LookupError(f"pinned setid {pinned} not found on DailyMed")
            elif prev.get("setid"):
                meta = spl_meta(session, prev["setid"])  # sticky choice
                if not meta:
                    note = "previous label was withdrawn; re-selected"
            if not meta:
                cands = search_labels(session, d, defaults)
                if not cands:
                    raise LookupError(f"no labels matched search '{d['search']}' with the title filters")
                meta = cands[0]
                auto_picked.append((did, meta, len(cands), note))

            setid, version = meta["setid"], str(meta.get("spl_version"))
            fname = f"{did}.md"
            if (not args.force and prev.get("setid") == setid and str(prev.get("spl_version")) == version
                    and (ref_dir / fname).exists()):
                unchanged += 1
                print(f"         unchanged (v{version})")
                continue

            xml = get(session, f"spls/{setid}.xml").content
            md = label_to_markdown(xml, d, meta)
            (ref_dir / fname).write_text(md, encoding="utf-8")
            manifest[did] = {
                "setid": setid,
                "spl_version": version,
                "published_date": meta.get("published_date", ""),
                "title": (meta.get("title") or "").strip(),
                "file": fname,
            }
            updated.append((did, prev.get("spl_version"), version, meta))
            print(f"updated  {did}: v{prev.get('spl_version', '-')} -> v{version}")
        except Exception as e:  # keep going; never touch the existing file on failure
            failed.append((did, str(e)))
            print(f"FAILED   {did}: {e}", file=sys.stderr)

    if not args.only:  # drop drugs removed from drugs.yaml
        for did in sorted(set(manifest) - set(ids)):
            f = ref_dir / manifest[did]["file"]
            if f.exists():
                f.unlink()
            del manifest[did]
            removed.append(did)

    mpath.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n", encoding="utf-8")
    write_index(skill_dir, drugs, manifest)

    # ---- summary (used as the pull request body)
    s = [f"## DailyMed label refresh ({dt.date.today():%B %Y})", "",
         f"Checked {len(todo)} drugs: {len(updated)} updated, {unchanged} unchanged, "
         f"{len(failed)} failed, {len(removed)} removed.", ""]
    if updated:
        s += ["### Updated labels", "", "| drug | version | published | label |", "|---|---|---|---|"]
        s += [f"| {i} | {o or 'new'} → {n} | {m.get('published_date','')} | [{(m.get('title') or '').strip()}]({LABEL_URL.format(m['setid'])}) |"
              for i, o, n, m in updated]
        s.append("")
    if auto_picked:
        s += ["### Auto-selected labels (please review)", "",
              "These were chosen automatically as the newest matching label. If one is wrong "
              "(wrong route, a repackager, a combination product), copy the correct setid from DailyMed "
              "into `drugs.yaml` as `setid:` to pin it.", ""]
        s += [f"- **{i}**: {(m.get('title') or '').strip()} (`{m['setid']}`), picked from {n} matches"
              + (f". {note}" if note else "") for i, m, n, note in auto_picked]
        s.append("")
    if failed:
        s += ["### Failed (existing files left unchanged)", ""] + [f"- **{i}**: {e}" for i, e in failed] + [""]
    if removed:
        s += ["### Removed (no longer in drugs.yaml)", ""] + [f"- {i}" for i in removed] + [""]
    s += ["Review the diffs for dosing changes before merging into `test`."]
    Path(args.summary).write_text("\n".join(s) + "\n", encoding="utf-8")
    print("\n".join(s))

    # Red run in GitHub if nothing worked (likely an outage or API change).
    return 1 if todo and len(failed) == len(todo) else 0


if __name__ == "__main__":
    sys.exit(main())