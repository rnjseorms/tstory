"""키워드 분석 — 네이버 검색광고 API + 구글 서제스트"""
import hashlib
import hmac
import base64
import time
import threading
import requests

_NAVER_API_BASE = "https://api.searchad.naver.com"


def _naver_signature(secret_key: str, timestamp: str, method: str, uri: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    hashed = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(hashed.digest()).decode("utf-8")


def get_naver_search_volume(keywords: list, api_key: str, secret_key: str, customer_id: str) -> dict:
    """
    네이버 검색광고 API 키워드 도구 호출
    반환: {키워드: {"pc": int, "mobile": int, "total": int, "competition": str}}
    """
    if not api_key or not secret_key or not customer_id:
        return {}

    result = {}
    # 네이버 API는 한 번에 최대 5개 → 배치 처리
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        timestamp = str(int(time.time() * 1000))
        uri = "/keywordstool"
        method = "GET"
        sig = _naver_signature(secret_key, timestamp, method, uri)
        headers = {
            "X-API-KEY": api_key,
            "X-CUSTOMER": str(customer_id),
            "X-Timestamp": timestamp,
            "X-SIGNATURE": sig,
        }
        params = {"hintKeywords": ",".join(batch), "showDetail": "1"}
        try:
            resp = requests.get(
                f"{_NAVER_API_BASE}/keywordstool",
                headers=headers, params=params, timeout=10
            )
            data = resp.json()
            comp_map = {"low": "낮음", "mid": "보통", "high": "높음"}
            for item in data.get("keywordList", []):
                kw = item.get("relKeyword", "")
                pc = item.get("monthlyPcQcCnt", 0)
                mobile = item.get("monthlyMobileQcCnt", 0)
                # 네이버 API는 "<10" 같은 문자열도 반환
                try:
                    pc = int(pc) if str(pc).isdigit() else 5
                    mobile = int(mobile) if str(mobile).isdigit() else 5
                except Exception:
                    pc, mobile = 5, 5
                result[kw] = {
                    "pc": pc, "mobile": mobile,
                    "total": pc + mobile,
                    "competition": comp_map.get(item.get("compIdx", "low"), "낮음"),
                    "source": "naver",
                }
        except Exception:
            pass  # 배치 실패 시 해당 배치만 건너뜀

    return result


def get_google_suggest(keyword: str) -> list:
    """구글 자동완성 API 롱테일 키워드 수집"""
    try:
        url = "https://suggestqueries.google.com/complete/search"
        resp = requests.get(url, params={"client": "firefox", "q": keyword, "hl": "ko"}, timeout=5)
        data = resp.json()
        return data[1] if len(data) > 1 else []
    except Exception:
        return []


def enrich_with_google_suggest(result: dict, seed_keyword: str) -> dict:
    """Google Suggest로 result에 없는 롱테일 키워드 보충 (검색량은 시뮬레이션)"""
    suggests = get_google_suggest(seed_keyword)
    for kw in suggests[:8]:
        if kw not in result:
            result[kw] = _simulate_single(kw, source="google")
    return result


def build_keyword_candidates(org: str, situation_keywords: list, fund: str) -> list:
    patterns = [
        f"{org} {fund}",
        f"{org} {fund} 신청방법",
        f"{org} {fund} 조건",
        f"{org} {fund} 한도",
        f"{org} {fund} 금리",
        f"{org} {fund} 필요서류",
        f"{org} 신청 자격",
        f"소상공인 {org} {fund}",
        f"{org} 정책자금 2026",
    ]
    for sk in situation_keywords[:2]:
        patterns.append(f"{sk} 정책자금")
        patterns.append(f"{sk} 방법")
    return patterns


def analyze_keywords_async(keywords: list, api_settings: dict, callback):
    """비동기로 키워드 분석 실행 후 callback(result) 호출"""
    def run():
        naver = api_settings.get("naver", {})
        result = get_naver_search_volume(
            keywords,
            naver.get("apiKey", ""),
            naver.get("secretKey", ""),
            naver.get("customerId", ""),
        )
        # API 미연동 시 시뮬레이션
        if not result:
            result = _simulate_volumes(keywords)

        # Google Suggest로 롱테일 보충 (시드 키워드 기준)
        seed = keywords[0] if keywords else ""
        if seed:
            result = enrich_with_google_suggest(result, seed)

        callback(result)

    t = threading.Thread(target=run, daemon=True)
    t.start()


def _simulate_single(keyword: str, source: str = "sim") -> dict:
    import random
    base_map = {
        "중진공": 3200, "소진공": 4800, "기보": 2100, "신보": 1800,
        "신용보증재단": 1200, "무역보험공사": 600, "농신보": 400,
    }
    vol = 500
    for org, v in base_map.items():
        if org in keyword:
            vol = v
            break
    vol = int(vol * random.uniform(0.6, 1.4))
    comp = random.choice(["낮음", "낮음", "보통"])
    return {"pc": vol // 3, "mobile": vol * 2 // 3, "total": vol, "competition": comp, "source": source}


def _simulate_volumes(keywords: list) -> dict:
    """API 키 없을 때 시뮬레이션 데이터"""
    return {kw: _simulate_single(kw) for kw in keywords}
