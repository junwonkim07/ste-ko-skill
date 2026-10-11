#!/usr/bin/env python3
"""STE-KO 검사기. 기계로 셀 수 있는 규칙만 본다.

beamonic/ste-ko 의 scripts/lint.py (MIT) 를 고쳐 쓴 것이다. 바꾼 점은 README.md 에 있다.

  python3 scripts/ste-ko-lint.py 문서.md --surface 문서
  python3 scripts/ste-ko-lint.py 'docs/**/*.md' --all
  echo "고칠 글" | python3 scripts/ste-ko-lint.py -
  python3 scripts/ste-ko-lint.py --self-test

등급은 셋이다.
  hard  어기면 종료 코드 1 을 낸다. 3.2 이중피동, 8.1 범위 물결표.
  warn  고칠 신호다. 문맥상 맞으면 그대로 둔다.
  info  근거가 있을 때만 구체화한다. 기본 출력에서 숨기고 --all 로 본다.

의존성 없음. 표준 라이브러리만 쓴다.
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "references" / "upstream" / "dictionary.md"

# 10.2 표면별 신호값. 원본은 상한이지만 여기서는 다시 읽어 볼 신호로 쓴다.
SURFACES = {
    "문서": {"eojeol": 25, "para": 6},
    "대화": {"eojeol": 25, "para": 4},
    "코딩": {"eojeol": 20, "para": 4},
    "UI": {"eojeol": 12, "para": 2},
}

# dictionary.md 절마다 등급을 정한다. B 절은 3.2 이중피동 검사가 따로 잡으므로 건너뛴다.
SECTION_LEVEL = {
    "A": "warn", "B2": "warn", "C": "warn", "D": "warn", "F": "warn", "I": "warn",
    "E": "info", "G": "info", "G2": "info", "H": "info",
}

# 어간 끝 음절에 어미가 붙으면 모음이 줄고 받침이 생긴다. `되` + `-었다` 는 `됐다` 가 된다.
_CONTRACT = {0: 1, 4: 5, 8: 9, 11: 12, 13: 14, 20: 6}  # ㅏ→ㅐ, ㅓ→ㅔ, ㅗ→ㅘ, ㅚ→ㅙ, ㅜ→ㅝ, ㅣ→ㅕ
# 어미가 만드는 받침은 ㄴ ㄹ ㅁ ㅆ 과 ㅂ 뿐이다. 원본은 받침 28개를 다 열어서
# `대하-` 가 `대학` 을, `통하-` 가 `통합` 을 잡았다.
_JONG_OK = (0, 4, 8, 16, 20)
_JONG_B = 17  # ㅂ 은 `-ㅂ니다`, `-ㅂ시다` 에서만 생긴다.

# 앞말에 붙는 조사는 받침에 따라 모양이 바뀐다. 사전은 한쪽만 적는다.
_PARTICLE_ALT = {
    "을": "[을를]", "를": "[을를]", "이": "[이가]", "가": "[이가]",
    "은": "[은는]", "는": "[은는]", "와": "[와과]", "과": "[와과]", "로": "(?:으로|로)",
}

# 사전 항목 중 그대로 검사하면 다른 뜻까지 잡는 것을 고쳐 적는다.
_REWRITE = {
    "-에 있어-": "-에 있어서",  # `서버에 있어요` 를 잡지 않게 한다.
}

# 한 음절짜리 접미 항목은 다른 낱말 속에서도 나온다. `-내에` 는 `안내에`, `-간의` 는 `시간의`,
# `-로의` 는 `도로의` 를 잡는다. 오탐이 적은 것만 검사한다.
_SAFE_SUFFIX = {"-로부터", "-에서의", "-와의"}

# 명사 항목 뒤에 올 수 있는 조사와 `-하다`, `-되다` 활용. `이슈가`, `개선될` 을 잡고
# `등급`, `여러분`, `일부러` 는 잡지 않는다.
_NOUN_TAIL = (
    r"(?:에서|에게|으로|이나|이다|입니다|이고|이며|"
    r"하[가-힣]{0,4}|해[가-힣]{0,3}|했[가-힣]{0,3}|한|할|함|합니다|"
    r"되[가-힣]{0,4}|돼[가-힣]{0,3}|됐[가-힣]{0,3}|된|될|됨|됩니다|시키[가-힣]{0,3}|"
    r"[이가은는을를의에로와과도만])"
)


def syllable_class(ch):
    """어간 끝 음절을 활용형까지 덮는 정규식으로 편다."""
    if not ("가" <= ch <= "힣"):
        return re.escape(ch)
    code = ord(ch) - 0xAC00
    cho, jung, jong = code // 588, (code % 588) // 28, code % 28
    if jong:
        return re.escape(ch)  # 받침이 있는 어간은 모양이 바뀌지 않는다.
    jungs = sorted({jung} | ({_CONTRACT[jung]} if jung in _CONTRACT else set()))
    ok = "".join(chr(0xAC00 + cho * 588 + j * 28 + t) for j in jungs for t in _JONG_OK)
    b = "".join(chr(0xAC00 + cho * 588 + j * 28 + _JONG_B) for j in jungs)
    return f"(?:[{ok}]|[{b}](?=[니시]))"


def base_stem(term):
    """기본형 `-다` 를 어간으로 바꾼다. `된다` → `되`, `나타났다` → `나타나`, `있다` → `있`."""
    body = term[:-1]
    if body.endswith("는"):
        return body[:-1]
    last = body[-1:]
    if len(body) >= 2 and "가" <= last <= "힣" and last != "있":
        code = ord(last) - 0xAC00
        if code % 28 in (4, 20):  # 현재형 `-ㄴ다` 의 ㄴ, 과거형 `-았다` 의 ㅆ 을 뗀다.
            return body[:-1] + chr(0xAC00 + code - code % 28)
    return body


def term_pattern(term):
    """사전 항목 하나를 정규식으로 만든다. 검사하지 않을 항목이면 None."""
    term = _REWRITE.get(term, term)
    suffix = term.startswith("-")
    raw = term.strip("-").strip()
    if not raw:
        return None
    if suffix and len(raw.split()) == 1 and term not in _SAFE_SUFFIX:
        return None
    open_ended = term.endswith("-") or (raw.endswith("다") and len(raw) > 2)
    if raw.endswith("다") and open_ended and not term.endswith("-"):
        raw = base_stem(raw)
    tokens = raw.split()
    parts = []
    for i, tok in enumerate(tokens):
        if i == 0 and suffix and tok in _PARTICLE_ALT:
            parts.append(_PARTICLE_ALT[tok])
            continue
        if i == 0 and suffix and tok[:1] in _PARTICLE_ALT and len(tok) > 1:
            # `-와의` 같은 붙은 조사도 받침 짝을 함께 잡는다.
            parts.append(_PARTICLE_ALT[tok[0]] + re.escape(tok[1:]))
            continue
        last = i == len(tokens) - 1
        parts.append("".join(
            syllable_class(c) if (last and j == len(tok) - 1 and open_ended) else re.escape(c)
            for j, c in enumerate(tok)
        ))
    body = r"\s*".join(parts)
    # 한글에는 \b 가 없다. 앞에 한글이 붙으면 다른 낱말이다. 접미 항목은 앞말에 붙으므로 예외다.
    head = "" if suffix else r"(?<![가-힣])"
    tail = r"[가-힣]*" if open_ended else _NOUN_TAIL + r"?(?![가-힣])"
    return head + body + tail


def load_dictionary(path=None):
    """dictionary.md 를 (정규식, 항목, 승인 표현, 절, 등급) 목록으로 읽는다."""
    path = Path(path) if path else DICTIONARY
    if not path.exists():
        return []
    out, section = [], None
    for line in path.read_text(encoding="utf-8").split("\n"):
        h = re.match(r"^#{2,3}\s+([A-Z])(?:-(\d))?\.", line)
        if h:
            section = h.group(1) + (h.group(2) or "")
            continue
        if line.startswith("## "):
            section = None
            continue
        level = SECTION_LEVEL.get(section)
        if not level:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) < 2:
            continue
        first, good = cells[0], cells[1].replace("`", "")
        terms = re.findall(r"`([^`]+)`", first)
        # 괄호 단서가 붙은 항목(`해당` (남용))은 문맥이 있어야 판단할 수 있다.
        if not terms or re.sub(r"`[^`]+`", "", first).replace("/", "").strip():
            continue
        for t in terms:
            pat = term_pattern(t)
            if pat:
                out.append((re.compile(pat), t, good, section, level))
    return out


def suffix_stem(stem):
    """앞말에 붙어 쓰는 어간. `변경되어졌다` 처럼 앞에 한글이 있어도 잡는다."""
    return re.escape(stem[:-1]) + syllable_class(stem[-1]) + r"[가-힣]*"


# 3.2 이중피동 — dictionary.md B 절과 같은 목록이다.
DOUBLE_PASSIVE = re.compile("|".join(
    suffix_stem(s) for s in (
        "되어지", "보여지", "불려지", "쓰여지", "읽혀지", "잊혀지", "나뉘어지",
        "모여지", "짜여지", "열려지", "닫혀지", "놓여지", "믿겨지", "걸려지", "풀려지",
    )
))
# 2.5 동작을 명사로 바꾸고 빈 동사를 붙인 형태. 사전 C 절의 일반형이다.
_NOMINAL_NOUNS = (
    "검토|확인|삭제|배포|테스트|점검|분석|수정|검증|설치|업데이트|적용|변경|구현|조사|"
    "논의|정리|작성|리뷰|실행|측정|비교|교체|백업|복구|재시작|설정|등록|승인|요청|보고|"
    "공유|전달|안내|개발|빌드|롤백|머지|마이그레이션|모니터링|디버깅|리팩터링"
)
NOMINALIZED = re.compile(
    rf"(?<![가-힣])(?:{_NOMINAL_NOUNS})[을를이가]\s*(?:진행|수행|실시|시행|실행)"
    + syllable_class("하") + r"[가-힣]*"
    + rf"|(?<![가-힣])(?:{_NOMINAL_NOUNS})[이가]\s*이루어[가-힣]*"
)
# 8.1 범위 물결표
TILDE_RANGE = re.compile(r"\d\s*~\s*\d")
# 8.5 말줄임표 종결
ELLIPSIS_END = re.compile(r"(?:\.\.\.|…)\s*$")
# 10.4 앞 턴 되풀이 문두 (`대화` 표면)
ECHO_OPEN = re.compile(r"^(좋은 질문|정확한 지적|말씀하신|말씀해 주신|확인해 보겠|살펴보겠|알겠습니다)")


def strip_noise(line):
    """검사에서 뺄 것 — 인라인 코드, 링크 URL, 마크다운 강조."""
    line = re.sub(r"`[^`]*`", " ", line)
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"[*_#]", "", line)
    return line


def prose_lines(text):
    """산문 줄만 (번호, 원문 문자열)로 낸다. 코드 펜스·표·인용·frontmatter는 건너뛴다."""
    fence = None
    in_front = False
    for i, raw in enumerate(text.split("\n"), 1):
        mark = re.match(r"^\s*(```|~~~)", raw)
        if mark:
            if fence is None:
                fence = mark.group(1)
            elif mark.group(1) == fence:
                fence = None
            continue
        if i == 1 and raw.strip() == "---":
            in_front = True
            continue
        if in_front:
            if raw.strip() == "---":
                in_front = False
            continue
        if fence or not raw.strip():
            continue
        if raw.lstrip().startswith(("|", ">", "<")) or raw.startswith(("    ", "\t")):
            continue
        yield i, raw


def sentences(line):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]


def check_text(text, surface, vocab):
    """(줄, 규칙, 등급, 설명) 목록을 낸다."""
    limit = SURFACES[surface]
    hits = []
    tails, tail_lines = [], []

    for lineno, raw in prose_lines(text):
        clean = strip_noise(raw)
        is_heading = raw.lstrip().startswith("#")
        is_list = bool(re.match(r"\s*(?:[-*+]|\d+\.)\s", raw))
        stripped = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", clean)

        for sent in sentences(stripped):
            n = len(sent.split())
            if n > limit["eojeol"]:
                hits.append((lineno, "4.1", "warn",
                             f"{n}어절 (신호 {limit['eojeol']}). 뜻이 둘이면 나눈다 — {sent[:30]}…"))
            words = sent.split()
            if words and not is_heading and not is_list:
                tails.append(words[-1].rstrip(".!?"))
                tail_lines.append(lineno)

        spans = []

        def add(m, rule, level, msg):
            s, e = m.span()
            if any(s < pe and ps < e for ps, pe in spans):
                return
            spans.append((s, e))
            hits.append((lineno, rule, level, msg))

        for m in DOUBLE_PASSIVE.finditer(clean):
            add(m, "3.2", "hard", f"이중피동 `{m.group()}`")
        for m in TILDE_RANGE.finditer(clean):
            add(m, "8.1", "hard", f"범위에 물결표 `{m.group()}` — 마크다운이 취소선으로 읽는다. `-` 를 쓴다")
        for m in NOMINALIZED.finditer(clean):
            add(m, "2.5", "warn", f"동작을 명사로 씀 `{m.group()}` → 동사로 (`검토를 진행했다` → `검토했다`)")
        for pat, bad, good, section, level in vocab:
            for m in pat.finditer(clean):
                add(m, "1.3", level, f"`{m.group()}` ({section}절 {bad}) → {good}")
        if ELLIPSIS_END.search(clean.rstrip()):
            hits.append((lineno, "8.5", "warn", "말줄임표로 문장을 끝냈다"))
        if surface == "대화" and ECHO_OPEN.match(clean.strip()):
            hits.append((lineno, "10.4", "warn", "앞 턴을 되풀이하며 시작한다"))

    # 4.8 같은 종결어절 3연속. 자연스러우면 그대로 둔다.
    run = 1
    for i in range(1, len(tails)):
        run = run + 1 if tails[i] == tails[i - 1] else 1
        if run == 3:
            hits.append((tail_lines[i], "4.8", "info", f"`{tails[i]}` 로 끝나는 문장이 3개 연속"))

    # 4.7 문단 문장 수
    for block in re.split(r"\n\s*\n", text):
        if re.match(r"\s*(?:```|~~~|\||>|#|[-*+]\s|\d+\.\s)", block):
            continue
        joined = " ".join(l for _, l in prose_lines(block))
        n = len(sentences(strip_noise(joined)))
        if n > limit["para"]:
            first = block.strip().split("\n")[0][:28]
            hits.append((0, "4.7", "info", f"문단에 {n}문장 (신호 {limit['para']}) — {first}…"))

    return sorted(hits, key=lambda h: (h[0], h[1]))


def self_test():
    vocab = load_dictionary()
    assert vocab, f"사전을 읽지 못했다: {DICTIONARY}"

    def rules(text, surface="문서"):
        return {(r, lv) for _, r, lv, _ in check_text(text, surface, vocab)}

    def flagged(text):
        return [m for _, _, _, m in check_text(text, "문서", vocab)]

    must_hit = {
        "결과가 화면에 보여집니다.": ("3.2", "hard"),
        "설정이 되어졌다.": ("3.2", "hard"),
        "항목은 3~5개다.": ("8.1", "hard"),
        "이 문제에 대해 설명한다.": ("1.3", "warn"),
        "이를 통해 해결했다.": ("1.3", "warn"),
        "장애로 인해 늦어졌다.": ("1.3", "warn"),
        "고객과 관련된 데이터다.": ("1.3", "warn"),
        "운영에 있어서 중요하다.": ("1.3", "warn"),
        "배포에 30분이 소요됩니다.": ("1.3", "warn"),
        "요청하신 건은 처리되었습니다.": ("1.3", "warn"),
        "삭제를 진행했습니다.": ("2.5", "warn"),
        "코드 리뷰를 수행합니다.": ("2.5", "warn"),
        "배포 관련하여 공유합니다.": ("1.3", "info"),
        "이슈가 있습니다.": ("1.3", "info"),
        "성능이 개선될 것이다.": ("1.3", "info"),
        "원인일 수도 있습니다.": ("1.3", "info"),
    }
    for text, want in must_hit.items():
        got = rules(text)
        assert want in got, f"{want} 를 못 잡았다: {text!r} → {got}"

    must_pass = [
        "파일이 서버에 있어요.",
        "서울에 대학이 있다.",
        "두 기능을 통합했다.",
        "시간의 흐름을 본다.",
        "안내에 따라 설치한다.",
        "등급을 올렸다.",
        "여러분께 알립니다.",
        "일부러 남겼다.",
        "이상의 값은 버린다.",
        "도로의 폭을 잰다.",
        "짧게 쓴다.",
        "검사를 통과해야 한다.",
        "`3~5` 는 코드라서 건너뛴다.",
    ]
    for text in must_pass:
        got = flagged(text)
        assert not got, f"오탐: {text!r} → {got}"

    assert ("10.4", "warn") in rules("좋은 질문입니다. 답은 이렇다.", "대화")
    long = "이 문장은 " + "아주 " * 30 + "길다."
    assert ("4.1", "warn") in rules(long)
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser(description="STE-KO 검사기")
    ap.add_argument("paths", nargs="*", help="검사할 마크다운 파일. `-` 는 표준 입력")
    ap.add_argument("--surface", default="문서", choices=list(SURFACES), help="적용 표면 (기본 문서)")
    ap.add_argument("--all", action="store_true", help="info 등급도 보인다")
    ap.add_argument("--strict", action="store_true", help="warn 이 있어도 종료 코드 1 을 낸다")
    ap.add_argument("--json", action="store_true", help="결과를 JSON 으로 낸다")
    ap.add_argument("--dictionary", help="dictionary.md 경로")
    ap.add_argument("--no-vocab", action="store_true", help="1.3 어휘 검사를 끈다")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        self_test()
        return 0
    if not a.paths:
        ap.error("검사할 파일이 없다. 표준 입력은 `-` 로 준다")

    vocab = [] if a.no_vocab else load_dictionary(a.dictionary)
    results = []
    for p in a.paths:
        if p == "-":
            results.append(("<stdin>", check_text(sys.stdin.read(), a.surface, vocab)))
            continue
        for f in glob.glob(p, recursive=True) or [p]:
            if not Path(f).is_file():
                print(f"{f}: 파일이 없다", file=sys.stderr)
                continue
            results.append((f, check_text(Path(f).read_text(encoding="utf-8"), a.surface, vocab)))

    count = {"hard": 0, "warn": 0, "info": 0}
    rows = []
    for f, hits in results:
        for lineno, rule, level, msg in hits:
            count[level] += 1
            rows.append({"file": f, "line": lineno, "rule": rule, "level": level, "message": msg})

    shown = [r for r in rows if a.all or r["level"] != "info"]
    if a.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
    else:
        for r in shown:
            loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
            print(f"{loc}\t{r['rule']}\t{r['level']}\t{r['message']}")
        hidden = "" if a.all or not count["info"] else " (info 는 --all 로 본다)"
        print(f"\n{len(results)}개 파일 · 표면 {a.surface} · hard {count['hard']} · warn {count['warn']}"
              f" · info {count['info']}{hidden}", file=sys.stderr)

    failed = count["hard"] or (a.strict and count["warn"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
