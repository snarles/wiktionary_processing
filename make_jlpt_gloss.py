"""Build a 4-column gloss (writing, reading, meaning, level) of JLPT vocabulary.

Reads:
  - languages/Japanese/jlpt_source/n{1..5}.csv  (stephenmk/yomitan-jlpt-vocab)
  - languages/Japanese/wiktextract-data.jsonl

Writes:
  - languages/Japanese/jlpt_gloss.tsv
  - languages/Japanese/jlpt_gloss.meta.json

One row per JLPT (writing, reading) pair. Meaning is taken from wiktextract
senses[].glosses when an entry with a matching reading is found; otherwise it
falls back to the JLPT list's own definition column and the row is recorded as
a miss in the sidecar.
"""

from __future__ import annotations

import csv
import json
import re
import datetime as dt
from pathlib import Path
from collections import defaultdict
from typing import Optional

REPO = Path(__file__).resolve().parent
JLPT_DIR = REPO / "languages" / "Japanese" / "jlpt_source"
WIKT_PATH = REPO / "languages" / "Japanese" / "wiktextract-data.jsonl"
OUT_TSV = REPO / "languages" / "Japanese" / "jlpt_gloss.tsv"
OUT_META = REPO / "languages" / "Japanese" / "jlpt_gloss.meta.json"


def kata_to_hira(s: str) -> str:
    out = []
    for ch in s:
        c = ord(ch)
        if 0x30A1 <= c <= 0x30F6:
            out.append(chr(c - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def normalize_reading(s: str) -> str:
    if not s:
        return ""
    return kata_to_hira(s).replace(".", "").replace(" ", "").replace("　", "")


def extract_reading(entry: dict) -> Optional[str]:
    """Pull a reading string out of a wiktextract entry. May return None."""
    hts = entry.get("head_templates") or []
    if hts:
        args = hts[0].get("args") or {}
        # ja-noun / ja-verb / ja-adj: args["1"] is the reading
        v1 = args.get("1")
        if v1 and v1 not in ("adverb", "phrase", "particle", "interjection",
                             "conjunction", "prefix", "suffix", "proper",
                             "counter", "noun", "verb"):
            return v1
        # ja-pos style: args["2"] holds the reading when args["1"] is the POS
        v2 = args.get("2")
        if v2:
            return v2
        # Fallback: the expansion text up to the bullet contains the kana
        # rendering for purely-kana headwords (e.g., エアロゾル • (earozoru))
        exp = hts[0].get("expansion") or ""
        if "•" in exp:
            head = exp.split("•")[0].strip()
            # strip ruby annotations like "妓(ぎ)院(いん)" -> keep parenthesized
            # readings only
            parens = re.findall(r"\(([^()]+)\)", head)
            if parens:
                return "".join(parens)
            return head
    # Last resort: sounds[].other often carries the kana form
    for s in entry.get("sounds") or []:
        if "other" in s:
            return s["other"]
    return None


def is_romanization_only(entry: dict) -> bool:
    hts = entry.get("head_templates") or []
    if not hts:
        return False
    return all((ht.get("args") or {}).get("2") == "romanization" for ht in hts)


def collect_glosses(entry: dict):
    out = []
    for sense in entry.get("senses") or []:
        for g in sense.get("glosses") or []:
            g = g.replace("\t", " ").replace("\n", " ").strip()
            if g and g not in out:
                out.append(g)
    return out


def load_wiktextract():
    by_word = defaultdict(list)
    with WIKT_PATH.open() as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if is_romanization_only(d):
                continue
            w = d.get("word")
            if not w:
                continue
            by_word[w].append(d)
    return by_word


def load_jlpt():
    """Return list of (writing, reading_hiragana, fallback_meaning, level)."""
    rows = []
    for n in (5, 4, 3, 2, 1):  # emit N5 first (easiest)
        level = f"N{n}"
        path = JLPT_DIR / f"n{n}.csv"
        with path.open(newline="") as f:
            for r in csv.DictReader(f):
                kana = r["kana"].strip()
                kanji = r["kanji"].strip()
                writing = kanji if kanji else kana
                reading = normalize_reading(kana)
                meaning = r["waller_definition"].strip()
                rows.append((writing, reading, meaning, level))
    return rows


def main() -> None:
    print(f"loading {WIKT_PATH.name} ...")
    by_word = load_wiktextract()
    print(f"  {len(by_word)} unique headwords")

    print("loading JLPT lists ...")
    jlpt_rows = load_jlpt()
    print(f"  {len(jlpt_rows)} JLPT (writing, reading, level) triples")

    misses = []
    out_rows = []

    def first_glosses(entries):
        out = []
        for e in entries:
            for g in collect_glosses(e):
                if g not in out:
                    out.append(g)
        return out

    for writing, reading, fallback_meaning, level in jlpt_rows:
        entries = by_word.get(writing, [])
        reading_match = [e for e in entries
                         if normalize_reading(extract_reading(e) or "") == reading]

        glosses = first_glosses(reading_match)
        if glosses:
            source = "exact"
        else:
            glosses = first_glosses(entries)
            if glosses:
                source = "writing-only"
            else:
                # Try kana-based lookup (handles soft-redirect headwords like
                # 明い -> 明るい, where the kanji writing in wiktextract is just
                # a redirect stub and the real content lives under the kana).
                kana_entries = by_word.get(reading, [])
                glosses = first_glosses(kana_entries)
                if glosses:
                    source = "kana-fallback"
                else:
                    source = "fallback-definition"

        meaning = "; ".join(glosses) if glosses else fallback_meaning

        if source != "exact":
            misses.append({
                "writing": writing,
                "reading": reading,
                "level": level,
                "source": source,
                "wiktextract_entries_for_word": len(entries),
            })

        meaning = meaning.replace("\t", " ").replace("\n", " ").strip()
        out_rows.append((writing, reading, meaning, level))

    print(f"writing {OUT_TSV} ...")
    with OUT_TSV.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE,
                       escapechar="\\", lineterminator="\n")
        w.writerow(["writing", "reading", "meaning", "level"])
        w.writerows(out_rows)

    meta = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "row_count": len(out_rows),
        "wiktextract_path": str(WIKT_PATH.relative_to(REPO)),
        "jlpt_source": "stephenmk/yomitan-jlpt-vocab (original_data/n{1..5}.csv)",
        "miss_count": len(misses),
        "miss_breakdown": {
            "writing-only": sum(1 for m in misses if m["source"] == "writing-only"),
            "kana-fallback": sum(1 for m in misses if m["source"] == "kana-fallback"),
            "fallback-definition": sum(1 for m in misses if m["source"] == "fallback-definition"),
        },
        "miss_examples": misses[:200],
    }
    with OUT_META.open("w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_TSV} ({len(out_rows)} rows) and {OUT_META.name}")
    print(f"misses: {len(misses)} "
          f"(writing-only: {meta['miss_breakdown']['writing-only']}, "
          f"kana-fallback: {meta['miss_breakdown']['kana-fallback']}, "
          f"fallback: {meta['miss_breakdown']['fallback-definition']})")


if __name__ == "__main__":
    main()
