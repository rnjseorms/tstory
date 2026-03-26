"""랜딩페이지 자동 매칭"""


DEFAULT_URL = "https://solutionbk.com/#contact"


def match_landing_page(keyword: str, landing_pages: list) -> str:
    """
    키워드 토큰 겹침 수 기반으로 가장 관련도 높은 랜딩페이지 URL 반환
    매칭 없으면 기본 URL 반환
    """
    best_match = None
    best_score = 0

    for lp in landing_pages:
        lp_keywords = [k.strip() for k in lp.get("keywords", "").split(",")]
        score = sum(1 for k in lp_keywords if k and k in keyword)
        if score > best_score:
            best_score = score
            best_match = lp.get("url")

    return best_match or DEFAULT_URL
