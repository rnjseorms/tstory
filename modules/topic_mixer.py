"""주제 자동 Mix 엔진 — 3축 조합으로 전체 주제 생성"""

ORGS = [
    {"id": "jungjin",  "name": "중진공",       "full": "중소벤처기업진흥공단"},
    {"id": "sojin",    "name": "소진공",       "full": "소상공인시장진흥공단"},
    {"id": "gibo",     "name": "기보",         "full": "기술보증기금"},
    {"id": "sinbo",    "name": "신보",         "full": "신용보증기금"},
    {"id": "jaedan",   "name": "신용보증재단",  "full": "지역신용보증재단"},
    {"id": "muyeok",   "name": "무역보험공사",  "full": "한국무역보험공사"},
    {"id": "nongsin",  "name": "농신보",        "full": "농림수산업자신용보증기금"},
    {"id": "jiyeok",   "name": "지역육성자금",  "full": "지역별 육성자금"},
]

SITUATIONS = [
    {"id": "startup",       "name": "창업 초기 자금 부족",  "keywords": ["창업자금", "창업초기", "사업시작"]},
    {"id": "rejected",      "name": "대출 거절 후 방법",    "keywords": ["대출거절", "대출거부", "은행거절"]},
    {"id": "low_credit",    "name": "신용 낮을 때",          "keywords": ["신용낮은", "저신용", "신용점수"]},
    {"id": "existing_loan", "name": "기대출 많을 때",        "keywords": ["기대출", "대출많은", "다중채무"]},
    {"id": "facility",      "name": "시설투자 필요",         "keywords": ["시설투자", "설비구입", "공장"]},
    {"id": "interest",      "name": "이자 부담 줄이기",      "keywords": ["이자절감", "금리인하", "이자부담"]},
    {"id": "cert_link",     "name": "인증 취득 후 자금 연계","keywords": ["벤처인증", "이노비즈", "인증혜택"]},
    {"id": "industry",      "name": "업종별 맞춤 자금",      "keywords": ["업종별", "제조업", "서비스업"]},
    {"id": "retry",         "name": "부결 후 재신청",        "keywords": ["재신청", "부결후", "탈락후"]},
]

FUND_TYPES = [
    {"id": "operating",         "name": "운영자금"},
    {"id": "facility",          "name": "시설자금"},
    {"id": "interest_subsidy",  "name": "이차보전"},
    {"id": "all",               "name": "전체"},
]

CERTIFICATIONS = [
    {"id": "patent",    "name": "특허",         "keywords": ["특허출원", "특허등록", "지식재산"]},
    {"id": "venture",   "name": "벤처기업인증",  "keywords": ["벤처인증", "벤처기업", "벤처확인"]},
    {"id": "innobiz",   "name": "이노비즈 인증", "keywords": ["이노비즈", "기술혁신", "INNOBIZ"]},
    {"id": "mainbiz",   "name": "메인비즈 인증", "keywords": ["메인비즈", "경영혁신", "MAINBIZ"]},
    {"id": "iso",       "name": "ISO 인증",      "keywords": ["ISO9001", "ISO14001", "품질인증"]},
]

SPECIAL_TOPICS = [
    {"id": "q_all_policy",   "type": "질문형",  "title": "소상공인 정책자금 종류, 어디서 얼마나 받을 수 있나요?"},
    {"id": "q_reject_next",  "type": "질문형",  "title": "정책자금 부결 후 다시 신청하면 되나요?"},
    {"id": "q_credit_low",   "type": "질문형",  "title": "신용점수 낮으면 정책자금 아예 불가능한가요?"},
    {"id": "cmp_gibo_sinbo", "type": "비교형",  "title": "기보 vs 신보, 뭐가 다른가요?"},
    {"id": "cmp_jungjin_sojin","type": "비교형","title": "중진공 vs 소진공, 내 회사는 어디가 맞나요?"},
    {"id": "sum_2026",       "type": "총정리형","title": "2026년 소상공인 정책자금 총정리"},
    {"id": "sum_startup",    "type": "총정리형","title": "창업자 정책자금 총정리 (2026 최신)"},
]

BASE_VOLUMES = {
    "중진공": 3200, "소진공": 4800, "기보": 2100, "신보": 1800,
    "신용보증재단": 1200, "무역보험공사": 600, "농신보": 400, "지역육성자금": 900
}

SIT_MULTIPLIER = {
    "startup": 1.8, "rejected": 1.5, "low_credit": 1.6,
    "existing_loan": 1.1, "facility": 1.0, "interest": 1.2,
    "cert_link": 0.9, "industry": 1.1, "retry": 1.7
}

FUND_MULTIPLIER = {
    "operating": 1.3, "facility": 0.9, "interest_subsidy": 0.7, "all": 1.5
}

COMPETITION_TABLE = {
    "중진공": "보통", "소진공": "낮음", "기보": "낮음", "신보": "보통",
    "신용보증재단": "낮음", "무역보험공사": "낮음", "농신보": "낮음", "지역육성자금": "낮음"
}


def _simulate_volume(org_name: str, sit_id: str, fund_id: str) -> int:
    base = BASE_VOLUMES.get(org_name, 500)
    sv = base * SIT_MULTIPLIER.get(sit_id, 1.0) * FUND_MULTIPLIER.get(fund_id, 1.0)
    return int(sv)


def calculate_priority(search_volume: int, competition: str) -> int:
    weight = {"높음": 1, "보통": 2, "낮음": 3}
    return search_volume * weight.get(competition, 1)


def _make_title_candidates(org_name: str, sit_name: str, fund_name: str) -> list[str]:
    return [
        f"{org_name} {fund_name}, 신청 전에 꼭 확인해야 할 조건 총정리",
        f"{sit_name}? {org_name} {fund_name} 이렇게 준비하세요",
        f"2026년 {org_name} {fund_name} 신청방법, 자격부터 한도까지",
    ]


def _make_cert_title_candidates(cert_name: str, org_name: str) -> list[str]:
    return [
        f"{cert_name} 받으면 {org_name} 자금이 달라집니다",
        f"{cert_name} 취득 후 {org_name} 우대 혜택 총정리 2026",
    ]


def _make_keywords(org_name: str, sit: dict, fund_name: str) -> list[str]:
    kws = [
        f"{org_name} {fund_name}",
        f"{org_name} {fund_name} 신청방법",
        f"{org_name} {fund_name} 조건",
        f"{org_name} {fund_name} 한도",
        f"{org_name} {fund_name} 금리",
        f"{org_name} 정책자금 2026",
        f"소상공인 {org_name} {fund_name}",
    ]
    for sk in sit.get("keywords", [])[:2]:
        kws.append(f"{sk} 정책자금")
    return kws


def generate_all_topics(published_ids: list = None) -> list[dict]:
    """3축 조합 + 기업인증 + 질문형 전체 주제 생성"""
    published_ids = set(published_ids or [])
    topics = []
    idx = 1

    # 3축 조합
    for org in ORGS:
        for sit in SITUATIONS:
            for fund in FUND_TYPES:
                vol = _simulate_volume(org["name"], sit["id"], fund["id"])
                comp = COMPETITION_TABLE.get(org["name"], "보통")
                topic = {
                    "id": idx,
                    "type": "3축조합",
                    "org": org["name"],
                    "org_id": org["id"],
                    "situation": sit["name"],
                    "situation_id": sit["id"],
                    "fund_type": fund["name"],
                    "fund_type_id": fund["id"],
                    "title": f"{org['name']} {sit['name']} {fund['name']}",
                    "title_candidates": _make_title_candidates(org["name"], sit["name"], fund["name"]),
                    "keywords": _make_keywords(org["name"], sit, fund["name"]),
                    "category": "소상공인 정책자금",
                    "search_volume": vol,
                    "competition": comp,
                    "priority": calculate_priority(vol, comp),
                    "published": idx in published_ids,
                }
                topics.append(topic)
                idx += 1

    # 기업인증 조합
    for cert in CERTIFICATIONS:
        for org in ORGS:
            vol = int(BASE_VOLUMES.get(org["name"], 500) * 0.8)
            comp = "낮음"
            topic = {
                "id": idx,
                "type": "기업인증",
                "org": org["name"],
                "org_id": org["id"],
                "certification": cert["name"],
                "cert_id": cert["id"],
                "situation": "인증 취득 후 자금 연계",
                "situation_id": "cert_link",
                "fund_type": "전체",
                "fund_type_id": "all",
                "title": f"{cert['name']} {org['name']} 연계",
                "title_candidates": _make_cert_title_candidates(cert["name"], org["name"]),
                "keywords": cert["keywords"] + [f"{org['name']} {cert['name']}", f"{cert['name']} 정책자금"],
                "category": "기업인증",
                "search_volume": vol,
                "competition": comp,
                "priority": calculate_priority(vol, comp),
                "published": idx in published_ids,
            }
            topics.append(topic)
            idx += 1

    # 질문형/비교형/총정리형
    for sp in SPECIAL_TOPICS:
        topic = {
            "id": idx,
            "type": sp["type"],
            "org": "전체",
            "org_id": "all",
            "situation": "",
            "situation_id": "",
            "fund_type": "전체",
            "fund_type_id": "all",
            "title": sp["title"],
            "title_candidates": [sp["title"], sp["title"] + " (2026년 최신 기준)"],
            "keywords": [sp["title"]],
            "category": "자주 묻는 질문" if sp["type"] == "질문형" else "소상공인 정책자금",
            "search_volume": 2000,
            "competition": "낮음",
            "priority": calculate_priority(2000, "낮음"),
            "published": idx in published_ids,
        }
        topics.append(topic)
        idx += 1

    return topics


def get_top5(topics: list[dict]) -> list[dict]:
    """
    기관별 1개씩 골고루 추천 (발행 완료 제외):
    소진공, 중진공, 기보, 신보 각 1개 + 나머지 기관 중 최고 1개.
    """
    unpublished = [t for t in topics if not t["published"]]
    by_priority = sorted(unpublished, key=lambda x: x["priority"], reverse=True)

    priority_orgs = ["소진공", "중진공", "기보", "신보"]
    result = []
    used_orgs = set()

    # 우선 기관 각 1개씩
    for org in priority_orgs:
        for t in by_priority:
            if t["org"] == org and org not in used_orgs:
                result.append(t)
                used_orgs.add(org)
                break

    # 나머지 기관 중 가장 높은 1개
    for t in by_priority:
        if t["org"] not in used_orgs:
            result.append(t)
            used_orgs.add(t["org"])
            break

    # 5개 미만이면 우선순위 높은 것으로 채움
    for t in by_priority:
        if len(result) >= 5:
            break
        if t not in result:
            result.append(t)

    return result[:5]
