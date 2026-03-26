"""초안 파싱 — 블로그/인스타/메타/FAQ 분리"""
import json
import re


# 마크다운 기호 제거 패턴
_MD_PATTERNS = [
    (re.compile(r"^#{1,6}\s+"), ""),          # ## 헤더
    (re.compile(r"\*{1,3}(.+?)\*{1,3}"), r"\1"),  # **bold**, *italic*
    (re.compile(r"~~(.+?)~~"), r"\1"),         # ~~strikethrough~~
    (re.compile(r"^>\s+", re.M), ""),          # > blockquote
    (re.compile(r"^[-*+]\s+", re.M), ""),      # - 불릿
    (re.compile(r"^\d+\.\s+", re.M), ""),      # 1. 순서 목록
    (re.compile(r"`{1,3}(.+?)`{1,3}", re.S), r"\1"),  # `code`
    (re.compile(r"\[([^\]]+)\]\([^\)]+\)"), r"\1"),    # [링크](url)
]

# 금지 특수문자 (이모지만 — 한글 범위 U+AC00~U+D7FF 제외)
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"   # Emoticons
    "\U0001F300-\U0001F5FF"   # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"   # Transport and Map
    "\U0001F1E0-\U0001F1FF"   # Flags
    "\U00002702-\U000027B0"   # Dingbats (★은 아래 개별 처리)
    "\U0001FA00-\U0001FAFF"   # Extended symbols
    "★●■▶→※"
    "]+",
    flags=re.UNICODE
)

_FORBIDDEN_WORDS = [
    "다양한", "효과적인", "최적의", "획기적인", "혁신적인",
    "체계적인", "폭넓은", "심도 있는", "종합적인", "선도적인",
]
_FORBIDDEN_REPLACE = {w: "" for w in _FORBIDDEN_WORDS}


def _clean_line(line: str) -> str:
    """한 줄에서 마크다운 기호·이모지 제거"""
    for pattern, repl in _MD_PATTERNS:
        line = pattern.sub(repl, line)
    line = _EMOJI_PATTERN.sub("", line)
    return line.strip()


def _clean_body(text: str) -> str:
    """본문 전체 클리닝"""
    lines = [_clean_line(l) for l in text.split("\n")]
    result = "\n".join(lines)
    # 금지 단어 제거
    for word in _FORBIDDEN_WORDS:
        result = result.replace(word, "")
    # 3줄 이상 연속 빈 줄 → 2줄로
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _split_sections(raw_text: str) -> dict:
    """[블로그]/[인스타]/[메타디스크립션]/[FAQ] 구분자로 섹션 분리"""
    sections: dict[str, list] = {}
    current = None
    markers = {
        "[블로그]": "blog",
        "[인스타]": "instagram",
        "[메타디스크립션]": "meta",
        "[FAQ]": "faq",
    }
    for line in raw_text.split("\n"):
        stripped = line.strip()
        matched = False
        for marker, key in markers.items():
            if stripped.startswith(marker):
                current = key
                sections[current] = []
                matched = True
                break
        if not matched and current is not None:
            sections[current].append(line)
    return sections


def _try_infer_sections(raw_text: str) -> dict:
    """구분자 없을 때 내용으로 섹션 추론 (Claude 자유 형식 출력 대응)"""
    sections = {"blog": [], "instagram": [], "meta": [], "faq": []}
    lines = raw_text.split("\n")

    # FAQ 패턴 탐지
    faq_start = None
    for i, line in enumerate(lines):
        if re.match(r"^Q[\.\s]", line.strip()):
            faq_start = i
            break

    if faq_start is not None:
        sections["faq"] = lines[faq_start:]
        sections["blog"] = lines[:faq_start]
    else:
        sections["blog"] = lines

    return sections


def parse_draft(raw_text: str) -> dict:
    """
    구분자 [블로그], [인스타], [메타디스크립션], [FAQ]로 분리 후 파싱.
    구분자 없으면 내용 기반 추론.
    반환:
    {
        "blog":      {"title": str, "body": str, "has_check_needed": bool},
        "instagram": {"text": str, "hashtags": str},
        "meta":      {"description": str},
        "faq":       [{"q": str, "a": str}, ...]
    }
    """
    result = {
        "blog": {"title": "", "body": "", "has_check_needed": False},
        "instagram": {"text": "", "hashtags": ""},
        "meta": {"description": ""},
        "faq": [],
    }

    # 구분자 존재 여부 확인
    has_markers = any(
        m in raw_text for m in ["[블로그]", "[인스타]", "[메타디스크립션]", "[FAQ]"]
    )
    sections = _split_sections(raw_text) if has_markers else _try_infer_sections(raw_text)

    # ── 블로그 파싱 ──
    if "blog" in sections:
        lines = sections["blog"]
        non_empty = [l for l in lines if l.strip()]
        if non_empty:
            raw_title = _clean_line(non_empty[0])
            # 제목 후보: 짧고 문장 같은 첫 줄
            result["blog"]["title"] = raw_title

            body_lines = lines[lines.index(non_empty[0]) + 1:]
            body = _clean_body("\n".join(body_lines))

            # FAQ가 본문에 섞여 있으면 분리
            if not sections.get("faq") and "Q." in body:
                blog_part, faq_part = _split_faq_from_body(body)
                result["blog"]["body"] = blog_part
                if faq_part:
                    result["faq"] = _parse_faq_text(faq_part)
            else:
                result["blog"]["body"] = body

            result["blog"]["has_check_needed"] = "[확인 필요" in body

    # ── 인스타 파싱 ──
    if "instagram" in sections:
        insta_lines = sections["instagram"]
        hashtag_lines = [l for l in insta_lines if l.strip().startswith("#")]
        text_lines = [l for l in insta_lines if not l.strip().startswith("#")]
        text = _clean_body("\n".join(text_lines))
        hashtags = " ".join(h.strip() for h in hashtag_lines)
        result["instagram"] = {"text": text, "hashtags": hashtags}

    # ── 메타 파싱 ──
    if "meta" in sections:
        meta_text = _clean_line("\n".join(sections["meta"]).strip())
        # 155자 초과 시 자르기
        result["meta"]["description"] = meta_text[:155]

    # ── FAQ 파싱 ──
    if "faq" in sections and sections["faq"] and not result["faq"]:
        faq_text = "\n".join(sections["faq"])
        result["faq"] = _parse_faq_text(faq_text)

    return result


def _split_faq_from_body(body: str) -> tuple[str, str]:
    """본문에서 FAQ 부분 분리"""
    lines = body.split("\n")
    faq_start = None
    for i, line in enumerate(lines):
        if re.match(r"^Q[\.\s]", line.strip()):
            faq_start = i
            break
    if faq_start is None:
        return body, ""
    return "\n".join(lines[:faq_start]).strip(), "\n".join(lines[faq_start:]).strip()


def _parse_faq_text(faq_text: str) -> list:
    """Q./A. 형식 FAQ 파싱"""
    faqs = []
    current_q = None
    current_a_lines = []

    for line in faq_text.split("\n"):
        stripped = _clean_line(line)
        if not stripped:
            continue
        if re.match(r"^Q[\.\:\s]", stripped):
            if current_q and current_a_lines:
                faqs.append({"q": current_q, "a": " ".join(current_a_lines).strip()})
            current_q = re.sub(r"^Q[\.\:\s]+", "", stripped).strip()
            current_a_lines = []
        elif re.match(r"^A[\.\:\s]", stripped):
            a_text = re.sub(r"^A[\.\:\s]+", "", stripped).strip()
            current_a_lines = [a_text] if a_text else []
        elif current_q is not None and stripped:
            current_a_lines.append(stripped)

    if current_q and current_a_lines:
        faqs.append({"q": current_q, "a": " ".join(current_a_lines).strip()})

    return faqs


def generate_faq_schema(faqs: list) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["q"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["a"]}
            }
            for faq in faqs
        ]
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


# HTML 변환은 modules/clipboard_publisher.py의 ClipboardPublisher.build_full_html() 사용
