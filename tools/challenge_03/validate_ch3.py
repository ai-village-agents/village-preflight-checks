#!/usr/bin/env python3
"""Challenge #3 (Constraint Gauntlet) validator — best-effort.

This script is meant to *accelerate human judging*, not replace it. It will
sometimes produce false positives/negatives on:
- semantics ("theme", "must include color/number/weather/..."),
- pronunciation edge cases (syllables, rhymes),
- poem extraction from markdown.

It validates (best-effort):
1) 12 lines
2) Acrostic "VILLAGECODES"
3) 8–10 syllables per line (CMU via `pronouncing` if installed; else heuristic)
4) Include >=1 each: color, number, weather, animal, instrument (keyword lists)
5) No repeated *content* words (function words exempt; light plural/possessive norm)
6) >=5 distinct words with >=4 syllables
7) Theme discovery/exploration/building (keyword list)
8) Line 12 ends with "?"
9) Couplet rhymes (1–2, 3–4, …) using CMU rhyming part if available
10) >=8 lines contain an exact 5-letter word
11) No line begins with: The/And/But/A/In/It
12) >=4 alliteration lines (>=2 non-function words share same initial)

Usage:
  python3 validate_ch3.py path/to/submission.md --json

Exit codes:
  0 = ok
  2 = failed constraints
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass
from typing import Iterable, Optional

try:
    import pronouncing  # type: ignore
except Exception:  # pragma: no cover
    pronouncing = None

ACROSTIC = "VILLAGECODES"
BANNED_START = {"the", "and", "but", "a", "in", "it"}

# Function-word allowlist for the "no repeated content words" constraint.
# Intentionally broad: pronouns, articles, auxiliaries, common preps/conjunctions.
FUNCTION_WORDS = {
    "a","an","the","and","or","but","nor","so","yet",
    "in","on","at","to","of","for","from","by","with","as","into","onto","over","under","between","among","through","during","after","before","within","without","around","across","near","upon",
    "is","am","are","was","were","be","been","being",
    "do","does","did","doing","done",
    "have","has","had","having",
    "can","could","may","might","must","shall","should","will","would",
    "i","me","my","mine","we","us","our","ours","you","your","yours","he","him","his","she","her","hers","they","them","their","theirs","it","its",
    "this","that","these","those",
    "who","whom","whose","which","what",
    "not","no","yes",
    "up","down","out","off","away","again","still","just","only","also","too","very","more","most","less","least",
    "if","then","than","because","since","while","when","where","why","how",
    "here","there",
}

COLOR_WORDS = {
    "red","blue","green","yellow","orange","purple","violet","indigo","black","white","gray","grey","pink","brown","azure","crimson","scarlet","amber","teal","cyan","magenta","silver","gold","golden",
}
NUMBER_WORDS = {
    "zero","one","two","three","four","five","six","seven","eight","nine","ten","dozen","hundred","thousand",
    "1","2","3","4","5","6","7","8","9","10",
}
WEATHER_WORDS = {
    "rain","rains","rainy","storm","storms","wind","winds","windy","snow","snows","snowy","hail","fog","foggy","cloud","clouds","cloudy","sun","sunny","thunder","lightning","drizzle","gale","breeze",
}
ANIMAL_WORDS = {
    "otter","fox","wolf","eagle","falcon","bear","cat","dog","whale","dolphin","shark","lion","tiger","owl","hare","deer","horse","snake","bee","ant","crow","raven",
}
INSTRUMENT_WORDS = {
    "cello","violin","fiddle","guitar","piano","drum","drums","flute","clarinet","trumpet","trombone","harp","banjo","sax","saxophone","oboe","bass",
}

THEME_WORDS = {
    "discover","discovery","explore","exploration","build","building","craft","forge","map","mapping","cartography","navigate","navigation","seek","search","frontier","survey","design","create","construct","assemble",
}

_word_re = re.compile(r"[A-Za-z0-9']+")


def _clean_token(tok: str) -> str:
    return tok.strip(string.punctuation).lower()


def tokenize(line: str) -> list[str]:
    return [_clean_token(m.group(0)) for m in _word_re.finditer(line) if _clean_token(m.group(0))]


def is_function_word(w: str) -> bool:
    return w in FUNCTION_WORDS


def heuristic_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    # Very rough heuristic: vowel groups minus silent-e.
    groups = re.findall(r"[aeiouy]+", w)
    count = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ye")) and count > 1:
        count -= 1
    return max(1, count)


def syllables_in_word(word: str) -> int:
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return 0
    if pronouncing is not None:
        phones = pronouncing.phones_for_word(w)
        if phones:
            # Take minimum across pronunciations to be lenient.
            return min(pronouncing.syllable_count(p) for p in phones)
    return heuristic_syllables(w)


def syllables_in_line(line: str) -> int:
    toks = tokenize(line)
    return sum(syllables_in_word(t) for t in toks)


def _norm_rhyme(s: str) -> str:
    # Normalize stress digits away so pairs like light/insight don't false-fail.
    return re.sub(r"[0-9]", "", s)


def rhyming_parts(word: str) -> set[str]:
    w = re.sub(r"[^a-z']", "", word.lower())
    if pronouncing is not None:
        phones = pronouncing.phones_for_word(w)
        parts = set()
        for p in phones:
            try:
                parts.add(_norm_rhyme(pronouncing.rhyming_part(p)))
            except Exception:
                pass
        if parts:
            return parts
    # Fallback: last 3 letters.
    w2 = re.sub(r"[^a-z]", "", w)
    return {w2[-3:]} if len(w2) >= 3 else {w2}


def last_content_word(line: str) -> Optional[str]:
    toks = tokenize(line)
    for t in reversed(toks):
        if t and not all(ch.isdigit() for ch in t):
            return t
    return toks[-1] if toks else None


def has_alliteration(line: str) -> bool:
    toks = [t for t in tokenize(line) if t and not is_function_word(t)]
    initials = [re.sub(r"[^a-z]", "", t)[0] for t in toks if re.sub(r"[^a-z]", "", t)]
    counts: dict[str, int] = {}
    for ch in initials:
        counts[ch] = counts.get(ch, 0) + 1
    return any(v >= 2 for v in counts.values())


def five_letter_word_present(line: str) -> bool:
    for t in tokenize(line):
        letters = re.sub(r"[^a-z]", "", t)
        if len(letters) == 5:
            return True
    return False


@dataclass
class ValidationResult:
    ok: bool
    failures: list[str]
    warnings: list[str]
    details: dict


def validate_poem(lines: list[str]) -> ValidationResult:
    failures: list[str] = []
    warnings: list[str] = []
    details: dict = {}

    if pronouncing is None:
        warnings.append("pronouncing not installed; syllables/rhymes use heuristic fallback")

    # 1) 12 lines
    if len(lines) != 12:
        failures.append(f"Expected 12 lines, got {len(lines)}")

    # 2) Acrostic
    ac = "".join((ln.lstrip()[:1] if ln.lstrip() else "") for ln in lines)
    details["acrostic"] = ac
    if ac != ACROSTIC:
        failures.append(f"Acrostic mismatch: got {ac!r}, expected {ACROSTIC!r}")

    # 8) line 12 ends with '?'
    if lines and not lines[-1].rstrip().endswith("?"):
        failures.append("Line 12 must end with '?' ")

    # 11) No line begins with banned words
    bad_starts = []
    for i, ln in enumerate(lines, 1):
        toks = tokenize(ln)
        if toks and toks[0] in BANNED_START:
            bad_starts.append((i, toks[0]))
    if bad_starts:
        failures.append("Banned line starts: " + ", ".join(f"L{i}={w}" for i, w in bad_starts))

    # 3) 8-10 syllables per line
    sylls = [syllables_in_line(ln) for ln in lines]
    details["syllables_per_line"] = sylls
    bad_sylls = [(i, s) for i, s in enumerate(sylls, 1) if s < 8 or s > 10]
    if bad_sylls:
        failures.append("Syllable count out of range (8-10): " + ", ".join(f"L{i}={s}" for i, s in bad_sylls))

    # 9) Couplets rhyme
    rhyme_bad = []
    details["rhyme_pairs"] = []
    for a in range(0, min(len(lines), 12), 2):
        if a + 1 >= len(lines):
            break
        w1 = last_content_word(lines[a])
        w2 = last_content_word(lines[a + 1])
        if not (w1 and w2):
            rhyme_bad.append((a + 1, a + 2, "<missing-last-word>"))
            continue
        rp1 = rhyming_parts(w1)
        rp2 = rhyming_parts(w2)
        ok = bool(rp1.intersection(rp2))
        details["rhyme_pairs"].append({
            "lines": (a + 1, a + 2),
            "w1": w1,
            "w2": w2,
            "intersect": sorted(rp1.intersection(rp2)),
        })
        if not ok:
            rhyme_bad.append((a + 1, a + 2, f"{w1}/{w2}"))
    if rhyme_bad:
        failures.append("Couplet rhyme failures: " + ", ".join(f"({i},{j}) {why}" for i, j, why in rhyme_bad))

    # 10) >=8 lines contain exact 5-letter word
    five_lines = [i for i, ln in enumerate(lines, 1) if five_letter_word_present(ln)]
    details["lines_with_5_letter_word"] = five_lines
    if len(five_lines) < 8:
        failures.append(f"Need >=8 lines with a 5-letter word; got {len(five_lines)}")

    # 12) >=4 alliteration lines
    allit_lines = [i for i, ln in enumerate(lines, 1) if has_alliteration(ln)]
    details["alliteration_lines"] = allit_lines
    if len(allit_lines) < 4:
        failures.append(f"Need >=4 alliteration lines; got {len(allit_lines)}")

    # 5) No repeated content words
    seen: dict[str, int] = {}
    repeats: list[tuple[str, int, int]] = []
    for i, ln in enumerate(lines, 1):
        for t in tokenize(ln):
            if not t or is_function_word(t):
                continue
            # Treat possessive/plural lightly.
            norm = re.sub(r"'s$", "", t)
            norm = re.sub(r"s$", "", norm) if len(norm) > 3 else norm
            if norm in seen:
                repeats.append((norm, seen[norm], i))
            else:
                seen[norm] = i
    if repeats:
        failures.append(
            "Repeated content words: "
            + ", ".join(f"{w}(L{a}&L{b})" for w, a, b in repeats[:20])
            + (" ..." if len(repeats) > 20 else "")
        )

    # 6) >=5 words with 4+ syllables
    four_plus = set()
    for ln in lines:
        for t in tokenize(ln):
            if not t:
                continue
            if syllables_in_word(t) >= 4:
                four_plus.add(t)
    details["four_plus_syllable_words"] = sorted(four_plus)
    if len(four_plus) < 5:
        failures.append(f"Need >=5 words with 4+ syllables; got {len(four_plus)}")

    # 4) semantic categories (best-effort)
    all_text = " ".join(lines).lower()

    def detect(words: set[str]) -> set[str]:
        found = set()
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", all_text):
                found.add(w)
        return found

    found = {
        "color": sorted(detect(COLOR_WORDS)),
        "number": sorted(detect(NUMBER_WORDS)),
        "weather": sorted(detect(WEATHER_WORDS)),
        "animal": sorted(detect(ANIMAL_WORDS)),
        "instrument": sorted(detect(INSTRUMENT_WORDS)),
    }
    details["semantic_detected"] = found
    missing_sem = [k for k, v in found.items() if not v]
    if missing_sem:
        warnings.append("Semantic category not detected (best-effort lists): " + ", ".join(missing_sem))

    # 7) theme (best-effort)
    theme_found = detect(THEME_WORDS)
    details["theme_keywords_detected"] = sorted(theme_found)
    if not theme_found:
        warnings.append("Theme keywords not detected (best-effort): discovery/exploration/building")

    ok = not failures
    return ValidationResult(ok=ok, failures=failures, warnings=warnings, details=details)


def extract_poem_candidates(markdown: str) -> list[list[str]]:
    """Return candidate 12-line poems from markdown.

We look for any 12-line window whose acrostic matches VILLAGECODES,
prioritizing fenced code blocks if present.
"""

    lines = markdown.splitlines()

    def windows(src: list[str]) -> Iterable[list[str]]:
        # Keep non-empty lines and exclude obvious markdown structure lines.
        filtered = [ln.rstrip("\n") for ln in src if ln.strip()]
        filtered2 = [ln for ln in filtered if not re.match(r"^\s*(#{1,6}\s|[-*+]\s|>\s)", ln)]
        for i in range(0, len(filtered2) - 12 + 1):
            yield filtered2[i : i + 12]

    candidates: list[list[str]] = []

    # Parse fenced code blocks.
    blocks: list[str] = []
    in_code = False
    buf: list[str] = []
    for ln in lines:
        m = re.match(r"^\s*```+\s*(\w+)?\s*$", ln)
        if m:
            if not in_code:
                in_code = True
                buf = []
            else:
                in_code = False
                blocks.append("\n".join(buf))
                buf = []
            continue
        if in_code:
            buf.append(ln)

    # 1) Search in code blocks.
    for blk in blocks:
        src = blk.splitlines()
        for win in windows(src):
            ac = "".join((ln.lstrip()[:1] if ln.lstrip() else "") for ln in win)
            if ac == ACROSTIC:
                candidates.append(win)

    # 2) Search in whole document.
    for win in windows(lines):
        ac = "".join((ln.lstrip()[:1] if ln.lstrip() else "") for ln in win)
        if ac == ACROSTIC:
            candidates.append(win)

    # De-duplicate.
    uniq: list[list[str]] = []
    seen = set()
    for c in candidates:
        key = "\n".join(c)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def extract_poem(markdown: str) -> tuple[list[str], list[str]]:
    cands = extract_poem_candidates(markdown)
    if not cands:
        return [], ["No 12-line candidate found with acrostic VILLAGECODES"]
    if len(cands) > 1:
        return cands[0], [f"Multiple candidates found ({len(cands)}); using the first"]
    return cands[0], []


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Markdown file containing the poem")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = open(args.path, "r", encoding="utf-8").read()
    poem, notes = extract_poem(text)
    res = validate_poem(poem) if poem else ValidationResult(False, ["Poem extraction failed"], notes, {})
    res.warnings = notes + res.warnings

    if args.json:
        out = {"ok": res.ok, "failures": res.failures, "warnings": res.warnings, "details": res.details, "poem": poem}
        import sys

        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if res.ok else 2

    print("OK" if res.ok else "FAIL")
    if poem:
        print("Poem lines:", len(poem))
    for f in res.failures:
        print("FAIL:", f)
    for w in res.warnings:
        print("WARN:", w)
    return 0 if res.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
