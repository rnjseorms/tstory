"""프롬프트 자동 생성"""
import json
import os
from datetime import date


PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prompts", "master_prompt_v2.txt")


def load_template() -> str:
    if not os.path.exists(PROMPT_PATH):
        return ""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def determine_scope(org: str, situation: str, fund_type: str, keyword: str) -> tuple[str, str]:
    """(범위_설명, 제외_범위) 반환 — 키워드/기관/상황 조합에 따라 정밀 판단"""
    kw = keyword

    # 1) 총정리·전체 키워드 → 모든 경로 다루기
    if any(w in kw for w in ["총정리", "전체", "모든", "완전 가이드", "한눈에", "정리"]):
        scope = (
            "소상공인이 이용 가능한 정책자금 전체 경로 "
            "(소진공 직접대출, 기보 기술보증, 신보 신용보증, 신용보증재단, 대환대출, 중진공 포함)"
        )
        exclude = "무역보험공사(수출기업 전용)·농신보(농림수산업자 전용)는 해당 없으면 제외"
        return scope, exclude

    # 2) 비교 키워드
    if any(w in kw for w in [" vs ", "VS", "차이", "비교", "versus"]):
        scope = f"키워드에 언급된 두 기관/제도의 직접 비교"
        exclude = "비교 대상 외 기관 언급 최소화"
        return scope, exclude

    # 3) 기업인증 키워드
    cert_words = ["벤처기업", "이노비즈", "메인비즈", "특허", "ISO", "인증"]
    if any(w in kw for w in cert_words):
        cert = next((w for w in cert_words if w in kw), "기업인증")
        scope = f"{cert} 취득 기업의 정책자금 우대 혜택 및 신청 방법"
        exclude = "인증과 무관한 일반 정책자금 상세 내용은 간략히"
        return scope, exclude

    # 4) 상황별 특수 범위
    situation_scope_map = {
        "창업": (
            "창업 3년 이내 소상공인·스타트업 대상 정책자금 (소진공 창업패키지, 기보 창업보증 등)",
            "운영자금 중심 제품, 업력 3년 이상 전용 상품 제외"
        ),
        "폐업위기": (
            "경영난·연체 위기 소상공인 대상 긴급 정책자금 및 재기 지원 (소진공 긴급경영안정자금 등)",
            "정상 영업 중인 기업 대상 일반 성장 자금은 제외"
        ),
        "매출감소": (
            "매출 감소·경영위기 소상공인 대상 특례 보증 및 긴급자금",
            "고성장 기업 대상 스케일업 자금 제외"
        ),
        "시설투자": (
            "설비·기계 구매, 점포 리모델링 등 시설자금 전반",
            "순수 운영자금 제품은 간략 언급만"
        ),
        "기술개발": (
            "R&D·기술개발 자금 (기보 기술보증, 중진공 기술개발 자금 등)",
            "기술 요소 없는 일반 운영자금은 제외"
        ),
    }
    for sit_key, (s, e) in situation_scope_map.items():
        if sit_key in (situation or "") or sit_key in kw:
            return s, e

    # 5) 특정 기관 지정
    if org and org != "전체":
        scope = f"{org}의 {fund_type} 관련 정책자금 신청 방법 및 조건"
        exclude = f"{org} 외 다른 기관은 '다른 방법도 있다' 수준으로만 언급"
        return scope, exclude

    # 6) 기본
    scope = f"소상공인 {fund_type} 정책자금 전반"
    exclude = "특별히 제외 없음 — 관련 기관 모두 포함"
    return scope, exclude


def extract_knowledge(knowledge_base: dict, org: str, situation: str = "", keyword: str = "") -> str:
    """지식 베이스에서 관련 데이터 추출 — 기관 특정 시 해당 기관 전체, 전체 시 핵심 요약"""

    # 기업인증 관련 키워드면 기업인증 섹션 추가
    cert_words = ["벤처기업", "이노비즈", "메인비즈", "특허", "ISO", "인증"]
    include_cert = any(w in keyword for w in cert_words)

    if org and org != "전체" and org in knowledge_base:
        data = dict(knowledge_base[org])
        if include_cert and "기업인증" in knowledge_base:
            data["기업인증_우대"] = knowledge_base["기업인증"]
        return json.dumps(data, ensure_ascii=False, indent=2)

    # 전체 or 특수 주제: 주요 기관 핵심 요약 + 인증 섹션
    orgs = ["중진공", "소진공", "기보", "신보", "신용보증재단"]
    result = {}
    for o in orgs:
        if o not in knowledge_base:
            continue
        kb = knowledge_base[o]
        summary = {
            "정식명칭": kb.get("정식명칭", ""),
            "대상": kb.get("대상", ""),
            "한도": kb.get("융자한도") or kb.get("보증한도_최고", ""),
            "금리": kb.get("금리") or kb.get("보증료율", ""),
            "특징": kb.get("특징") or kb.get("주요_특징", ""),
        }
        # None 값 제거
        result[o] = {k: v for k, v in summary.items() if v}

    if include_cert and "기업인증" in knowledge_base:
        result["기업인증"] = knowledge_base["기업인증"]

    return json.dumps(result, ensure_ascii=False, indent=2)


def generate_prompt(
    keyword: str,
    org: str,
    situation: str,
    fund_type: str,
    knowledge_base: dict,
    landing_url: str,
    tone_guide: list,
) -> str:
    template = load_template()
    if not template:
        return "프롬프트 템플릿 파일을 찾을 수 없습니다. data/prompts/master_prompt_v2.txt 확인 바랍니다."

    current_year = date.today().year
    scope, exclude = determine_scope(org, situation, fund_type, keyword)
    kb_data = extract_knowledge(knowledge_base, org, situation, keyword)
    tone_text = "\n".join(f'"{t}"' for t in tone_guide)

    # 키워드에 연도 없으면 현재 연도 자동 추가
    if str(current_year) not in keyword and str(current_year - 1) not in keyword:
        keyword_with_year = f"{keyword} {current_year}"
    else:
        keyword_with_year = keyword

    prompt = template
    prompt = prompt.replace("{키워드}", keyword_with_year)
    prompt = prompt.replace("{범위_설명}", scope)
    prompt = prompt.replace("{제외_범위}", exclude)
    prompt = prompt.replace("{지식_베이스_데이터}", kb_data)
    prompt = prompt.replace("{랜딩_URL}", landing_url or "https://solutionbk.com/#contact")
    prompt = prompt.replace("{말투_예시}", tone_text)

    # 연도 컨텍스트 주입 (템플릿에 없는 경우 앞에 붙임)
    year_ctx = f"※ 현재 기준 연도: {current_year}년. 제도 변경 가능성 있는 내용은 [확인 필요] 처리.\n\n"
    prompt = year_ctx + prompt

    return prompt
