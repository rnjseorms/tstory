"""이미지 생성 — Pillow 직접 그리기. 항목 수/텍스트 길이에 따라 폰트·간격·레이아웃 자동 조절."""
import os, re, threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "images", "generated")
FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

BLOG_W, BLOG_H = 800, 450
INSTA_W, INSTA_H = 1080, 1080
# OG 이미지 제거 (티스토리에서 설정 기능 없음)

C_MAIN, C_SUB, C_WHITE = '#1B4F72', '#F97316', '#FFFFFF'
C_DARK, C_GRAY, C_BG, C_LINE = '#333333', '#999999', '#F5F7FA', '#EEEEEE'
CARD_COLORS = ['#1B4F72', '#2E86C1', '#117A65', '#B7950B', '#E74C3C', '#8E44AD']

_hex = lambda c: tuple(int(c.lstrip('#')[:6][i:i+2], 16) for i in (0, 2, 4))


def _font(size, bold=False):
    name = 'Pretendard-Bold.otf' if bold else 'Pretendard-Regular.otf'
    path = os.path.join(FONT_DIR, name)
    if not os.path.exists(path):
        path = path.replace('.otf', '.ttf')
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()


def _tw(draw, text, font):
    """텍스트 너비"""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw, text, font):
    """텍스트 높이"""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _wrap(draw, text, font, max_w):
    """글자 단위 자동 줄바꿈 → 줄 리스트 반환"""
    if _tw(draw, text, font) <= max_w:
        return [text]
    lines, cur = [], ""
    for ch in text:
        if _tw(draw, cur + ch, font) > max_w:
            if cur:
                lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or [text]


def _calc_wrapped_heights(draw, items, font, max_w, line_spacing):
    """각 항목의 줄바꿈 후 높이 리스트와 줄바꿈 결과를 함께 반환"""
    results = []  # [(wrapped_lines, total_px_height), ...]
    fh = _th(draw, "가", font)
    for txt in items:
        lines = _wrap(draw, txt, font, max_w)
        h = len(lines) * fh + (len(lines) - 1) * line_spacing
        results.append((lines, h))
    return results


# ── 공통 그리기 ───────────────────────────────────────────────

def _draw_badge(draw, x, y, text, sz):
    f = _font(sz, True)
    bb = draw.textbbox((0, 0), text, font=f)
    bw, bh = bb[2] - bb[0] + 20, bb[3] - bb[1] + 10
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=4, fill=_hex(C_SUB))
    draw.text((x + 10, y + 4), text, fill=_hex(C_WHITE), font=f)
    return bh


def _draw_footer(draw, w, h, dark=False):
    f = _font(max(9, int(w * 0.0125)))
    color = (200, 200, 200) if dark else _hex(C_GRAY)
    if not dark:
        draw.line([20, h - 30, w - 20, h - 30], fill=_hex(C_LINE), width=1)
    draw.text((20, h - 22), 'solutionbk.com', fill=color, font=f)
    rt = '정책자금 전문 컨설팅'
    draw.text((w - 20 - _tw(draw, rt, f), h - 22), rt, fill=color, font=f)


# ── 유형 감지 + KB 추출 ───────────────────────────────────────

def detect_image_types(body):
    types = ["info_card"]
    if any(w in body for w in ["단계", "절차", "순서", "STEP", "step", "①", "신청 방법"]):
        types.append("flowchart")
    if any(w in body for w in ["한도", "금리", "비교", "차이", " vs "]):
        types.append("comparison")
    if any(w in body for w in ["조건", "자격", "해당", "제한", "요건", "체크", "확인 사항"]):
        types.append("checklist")
    return types[:4]


def _extract_kb_facts(org, kb):
    r = {"info_lines": [], "steps": [], "funds": [], "checklist": []}
    od = kb.get(org, {}) if kb else {}
    if not od:
        return r
    for key, label in [("정식명칭", "정식명칭"), ("대상", "지원대상"), ("융자한도", "융자한도"),
                        ("보증한도_최고", "보증한도"), ("금리구조", "금리구조"), ("우대금리_최대", "우대금리")]:
        if od.get(key):
            r["info_lines"].append(f"{label}: {od[key]}")

    proc = od.get("융자절차", "") or od.get("역할", "")
    if isinstance(proc, str) and proc:
        r["steps"] = [s.strip() for s in re.split(r"[→>·]|STEP|\d+\.", proc)
                       if s.strip() and len(s.strip()) >= 2][:8]
    if not r["steps"]:
        r["steps"] = ["신청서 접수 및 서류 준비", "정책우선도 평가", "기업 평가 및 심사",
                       "융자 결정 통보", "대출 실행"]

    fd = od.get("자금별", {})
    if fd:
        skip = {"운전기간", "시설기간", "방식_일반", "방식_유망", "신청기간", "금리인하", "특이"}
        rename = {"한도_일반": "한도"}
        for fn, fv in fd.items():
            items = []
            for f in ["대상", "한도", "한도_일반", "금리", "기간", "방식"]:
                if f in fv:
                    items.append(f"{rename.get(f, f)}: {fv[f]}")
            r["funds"].append({"name": fn, "items": items[:4]})

    ck = od.get("융자제한_핵심", [])
    if ck:
        r["checklist"] = [f"제외: {it}" for it in ck[:10]]
    return r


# ══════════════════════════════════════════════════════════════
#  1. 핵심 요약 정보카드 — 완전 자동 조절
# ══════════════════════════════════════════════════════════════

def _create_info_card(title, items, w, h):
    is_insta = (w == INSTA_W and h == INSTA_H)  # 인스타 여부 판별
    img = Image.new('RGB', (w, h), _hex(C_WHITE))
    draw = ImageDraw.Draw(img)

    # 상단 브랜드 라인
    line_h = max(5, int(h * 0.013))
    draw.rectangle([0, 0, w, line_h], fill=_hex(C_MAIN))

    px = int(w * 0.035)
    footer_h = 34

    # ── 인스타 CTA 영역 사전 계산 ──────────────────────────
    cta_h = 0
    if is_insta:
        cta_h = int(h * 0.18)  # 하단 18%를 CTA에 할당

    # 배지
    badge_sz = max(10, int(w * 0.014))
    badge_y = line_h + int(h * 0.025)
    badge_h = _draw_badge(draw, px, badge_y, '부광솔루션즈 정책자금', badge_sz)

    # 제목 — 인스타 48px, og 30px, blog 24px
    if is_insta:
        title_sz = 48
    elif h >= 600:
        title_sz = 30
    else:
        title_sz = 24
    tf = _font(title_sz, True)
    title_y = badge_y + badge_h + int(h * 0.015)
    title_max_w = w - px * 2
    title_lines = _wrap(draw, title, tf, title_max_w)
    for tl in title_lines:
        draw.text((px, title_y), tl, fill=_hex(C_MAIN), font=tf)
        title_y += title_sz + 4

    # ── 항목 영역 ──────────────────────────────────────────
    items_top = title_y + int(h * 0.02)
    items_bottom = h - footer_h - cta_h
    avail_h = items_bottom - items_top
    n = len(items)

    # 인스타 26px, og 18px, blog 15px (기본값), 항목 수에 따라 자동 축소
    if is_insta:
        item_sz = max(18, min(26, int(avail_h / max(n, 1) * 0.42)))
    elif h >= 600:
        item_sz = max(13, min(18, int(avail_h / max(n, 1) * 0.45)))
    else:
        item_sz = max(11, min(15, int(avail_h / max(n, 1) * 0.45)))

    ifn = _font(item_sz)
    line_sp = max(2, int(item_sz * 0.15))
    dr = max(3, int(item_sz * 0.3))
    text_x = px + dr * 2 + 16
    text_max_w = w - text_x - px

    # 줄바꿈 후 높이 계산
    wrapped_data = _calc_wrapped_heights(draw, items, ifn, text_max_w, line_sp)
    total_content_h = sum(wh for _, wh in wrapped_data)

    # 균등 배분 간격
    remaining = avail_h - total_content_h
    gap = remaining / max(n + 1, 2)
    gap = max(6, min(gap, item_sz * 2.5))

    # 배치
    cur_y = items_top + gap * 0.5
    fh = _th(draw, "가", ifn)

    for i, (lines, content_h) in enumerate(wrapped_data):
        if i > 0:
            line_y = int(cur_y - gap * 0.4)
            draw.line([px, line_y, w - px, line_y], fill=_hex(C_LINE), width=1)

        dot_cy = int(cur_y + fh * 0.5)
        draw.ellipse([px + 4, dot_cy - dr, px + 4 + dr * 2, dot_cy + dr], fill=_hex(C_SUB))

        ty = cur_y
        for ln in lines:
            draw.text((text_x, ty), ln, fill=_hex(C_DARK), font=ifn)
            ty += fh + line_sp
        cur_y += content_h + gap

    # ── 인스타 CTA 블록 ───────────────────────────────────
    if is_insta and cta_h > 0:
        cta_top = h - footer_h - cta_h + 10
        # 구분선
        draw.line([px, cta_top, w - px, cta_top], fill=_hex(C_MAIN), width=2)
        # CTA 텍스트
        cta_f1 = _font(max(20, int(cta_h * 0.22)), True)
        cta_f2 = _font(max(16, int(cta_h * 0.16)))
        cta_txt1 = '내 상황 기준 가능 여부 확인하기'
        cta_txt2 = 'solutionbk.com/#contact'
        # 중앙 정렬
        t1w = _tw(draw, cta_txt1, cta_f1)
        t2w = _tw(draw, cta_txt2, cta_f2)
        t1y = cta_top + int(cta_h * 0.2)
        t2y = t1y + int(cta_h * 0.35)
        draw.text(((w - t1w) // 2, t1y), cta_txt1, fill=_hex(C_MAIN), font=cta_f1)
        draw.text(((w - t2w) // 2, t2y), cta_txt2, fill=_hex(C_SUB), font=cta_f2)

    _draw_footer(draw, w, h)
    return img


# ══════════════════════════════════════════════════════════════
#  2. 신청 절차 플로우차트 — 항목 수 기반 자동 레이아웃
# ══════════════════════════════════════════════════════════════

def _create_flowchart(title, steps, w, h):
    img = Image.new('RGB', (w, h), _hex(C_MAIN))
    draw = ImageDraw.Draw(img)

    # 배지
    bf = _font(max(10, int(w * 0.014)), True)
    btxt = '신청 절차 가이드'
    bw = _tw(draw, btxt, bf) + 20
    bx = (w - bw) // 2
    draw.rounded_rectangle([bx, 12, bx + bw, 30], radius=4, fill=_hex(C_SUB))
    draw.text((bx + 10, 14), btxt, fill=_hex(C_WHITE), font=bf)

    # 제목
    tf = _font(max(16, int(w * 0.025)), True)
    tw = _tw(draw, title, tf)
    draw.text(((w - tw) // 2, 36), title, fill=_hex(C_WHITE), font=tf)

    # ── 레이아웃 자동 결정 ─────────────────────────────────
    n = len(steps)
    px = int(w * 0.025)
    start_y = 62
    footer_h = 28
    avail_h = h - start_y - footer_h

    # 항목 5개 이하: 1열, 6개 이상: 2열
    # 단, 텍스트가 길면 1열 유지하고 폰트 축소
    use_two_col = n > 5
    if use_two_col:
        col_gap = int(w * 0.015)
        col_w = (w - px * 2 - col_gap) // 2
        half = (n + 1) // 2
        rows = half
    else:
        col_w = w - px * 2
        col_gap = 0
        half = n
        rows = n

    # 행당 사용 가능 높이 → 카드 높이 & 간격 자동
    slot_h = avail_h / rows
    card_gap = max(3, min(int(slot_h * 0.12), 10))
    card_h = int(slot_h - card_gap)

    # 폰트 크기 자동 (카드 높이의 35~45%)
    step_sz = min(20, max(11, int(card_h * 0.4)))
    sf = _font(step_sz)
    nf = _font(max(10, int(step_sz * 0.85)), True)
    csz = min(int(card_h * 0.6), int(w * 0.032))

    for i, step in enumerate(steps):
        if use_two_col:
            if i < half:
                x = px
                y = start_y + i * (card_h + card_gap)
            else:
                x = px + col_w + col_gap
                y = start_y + (i - half) * (card_h + card_gap)
        else:
            x = px
            y = start_y + i * (card_h + card_gap)

        draw.rounded_rectangle([x, y, x + col_w, y + card_h], radius=6, fill=_hex(C_WHITE))

        # 번호 원
        cx = x + 10
        cy = y + (card_h - csz) // 2
        draw.ellipse([cx, cy, cx + csz, cy + csz], fill=_hex(C_SUB))
        nt = str(i + 1)
        nbb = draw.textbbox((0, 0), nt, font=nf)
        draw.text((cx + (csz - (nbb[2] - nbb[0])) // 2,
                   cy + (csz - (nbb[3] - nbb[1])) // 2 - 1),
                  nt, fill=_hex(C_WHITE), font=nf)

        # 텍스트 줄바꿈
        tx = cx + csz + 10
        tmax = x + col_w - tx - 8
        wrapped = _wrap(draw, step, sf, tmax)
        fh = _th(draw, "가", sf)
        total_th = len(wrapped) * (fh + 2)
        ty = y + (card_h - total_th) // 2
        for ln in wrapped:
            draw.text((tx, ty), ln, fill=_hex(C_DARK), font=sf)
            ty += fh + 2

    _draw_footer(draw, w, h, dark=True)
    return img


# ══════════════════════════════════════════════════════════════
#  3. 자금별 비교표 — 카드 높이 자동 통일
# ══════════════════════════════════════════════════════════════

def _create_comparison(title, funds, w, h):
    img = Image.new('RGB', (w, h), _hex(C_BG))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, w, max(4, int(h * 0.01))], fill=_hex(C_MAIN))

    bf = _font(max(10, int(w * 0.014)), True)
    btxt = '자금 비교 가이드'
    bw = _tw(draw, btxt, bf) + 20
    bx = (w - bw) // 2
    draw.rounded_rectangle([bx, 10, bx + bw, 28], radius=4, fill=_hex(C_SUB))
    draw.text((bx + 10, 12), btxt, fill=_hex(C_WHITE), font=bf)

    tf = _font(max(16, int(w * 0.022)), True)
    tbb = draw.textbbox((0, 0), title, font=tf)
    draw.text(((w - (tbb[2] - tbb[0])) // 2, 34), title, fill=_hex(C_MAIN), font=tf)

    px = int(w * 0.02)
    csy = 58
    cg = max(5, int(w * 0.008))
    footer_h = 20
    avail_h = h - csy - footer_h
    n = len(funds)
    cols = 3 if n >= 3 else 2
    rows = (n + cols - 1) // cols
    cw = (w - px * 2 - cg * (cols - 1)) // cols
    ch = (avail_h - cg * (rows - 1)) // rows
    hh = max(18, int(ch * 0.16))

    # 폰트 크기 자동 — 카드 본문 영역 높이 기반
    body_h = ch - hh - 6
    # 가장 항목이 많은 카드의 항목 수
    max_items = max((len(f.get('items', [])) for f in funds), default=1)
    detail_sz = min(14, max(9, int(body_h / max(max_items, 1) * 0.55)))
    header_sz = min(14, max(10, detail_sz + 2))
    lf = _font(header_sz, True)
    df = _font(detail_sz)

    for idx, fund in enumerate(funds):
        col, row = idx % cols, idx // cols
        x = px + col * (cw + cg)
        y = csy + row * (ch + cg)
        draw.rounded_rectangle([x, y, x + cw, y + ch], radius=6, fill=_hex(C_WHITE))
        color = _hex(CARD_COLORS[idx % len(CARD_COLORS)])
        draw.rounded_rectangle([x, y, x + cw, y + hh], radius=6, fill=color)
        draw.rectangle([x, y + hh - 6, x + cw, y + hh], fill=color)
        draw.text((x + 8, y + 3), fund['name'], fill=_hex(C_WHITE), font=lf)

        dy = y + hh + 4
        tmax = cw - 16
        for it in fund.get('items', []):
            wrapped = _wrap(draw, it, df, tmax)
            for ln in wrapped:
                if dy > y + ch - 4:
                    break
                draw.text((x + 8, dy), ln, fill=_hex(C_DARK), font=df)
                dy += detail_sz + 3

    ff = _font(max(9, int(w * 0.01)))
    draw.text((px, h - 16), 'solutionbk.com · 정책자금 전문 컨설팅', fill=_hex(C_GRAY), font=ff)
    return img


# ══════════════════════════════════════════════════════════════
#  4. 체크리스트 — 항목 수 기반 자동 1열/2열 + 높이 맞춤
# ══════════════════════════════════════════════════════════════

def _create_checklist(title, items, w, h):
    img = Image.new('RGB', (w, h), _hex(C_WHITE))
    draw = ImageDraw.Draw(img)

    hdr_h = max(50, int(h * 0.125))
    draw.rectangle([0, 0, w, hdr_h], fill=_hex(C_MAIN))

    bf = _font(max(9, int(w * 0.012)), True)
    badge_w = int(_tw(draw, '자격 요건 체크리스트', bf) + 18)
    draw.rounded_rectangle([16, 8, 16 + badge_w, 24], radius=4, fill=_hex(C_SUB))
    draw.text((24, 9), '자격 요건 체크리스트', fill=_hex(C_WHITE), font=bf)

    tsz = max(14, int(w * 0.022))
    tf = _font(tsz, True)
    draw.text((16, 28), title, fill=_hex(C_WHITE), font=tf)

    # ── 레이아웃 자동 결정 ─────────────────────────────────
    n = len(items)
    px = 16
    col_gap = int(w * 0.025)
    footer_h = 30
    sy = hdr_h + 6
    avail_h = h - sy - footer_h

    use_two_col = n > 5
    if use_two_col:
        col_w = (w - px * 2 - col_gap) // 2
        half = (n + 1) // 2
        left_items = items[:half]
        right_items = items[half:]
    else:
        col_w = w - px * 2
        left_items = items
        right_items = []

    rows_per_col = len(left_items)  # 좌측 기준 (항상 >= 우측)

    # 행당 높이 → 폰트 크기
    rh_base = avail_h / rows_per_col
    item_sz = min(16, max(9, int(rh_base * 0.4)))
    ifn = _font(item_sz)
    ck_sz = max(14, int(item_sz * 1.4))
    ck_f = _font(max(8, int(ck_sz * 0.55)), True)
    text_max = col_w - ck_sz - 16
    fh = _th(draw, "가", ifn)
    line_sp = fh + 2

    # ── 각 항목의 실제 높이 사전 계산 ──────────────────────
    def _item_heights(item_list):
        heights = []
        for txt in item_list:
            lines = _wrap(draw, txt, ifn, text_max)
            h_px = len(lines) * line_sp
            heights.append((lines, h_px))
        return heights

    left_data = _item_heights(left_items)
    right_data = _item_heights(right_items)

    left_content_h = sum(hp for _, hp in left_data)
    right_content_h = sum(hp for _, hp in right_data)

    # ── 좌우 높이 맞춤: 각 열의 간격을 별도 계산 ──────────
    def _calc_gaps(data_list, total_h):
        content = sum(hp for _, hp in data_list)
        n_items = len(data_list)
        remaining = total_h - content
        if n_items <= 1:
            return remaining / 2  # 위아래 패딩
        g = remaining / (n_items + 1)
        return max(4, min(g, item_sz * 2.5))

    left_gap = _calc_gaps(left_data, avail_h)
    right_gap = _calc_gaps(right_data, avail_h) if right_data else left_gap

    # ── 열 그리기 함수 ────────────────────────────────────
    def _draw_col(x, data, gap_val):
        cur_y = sy + gap_val * 0.5
        for idx, (lines, content_h) in enumerate(data):
            if idx > 0:
                ly = int(cur_y - gap_val * 0.35)
                draw.line([x, ly, x + col_w, ly], fill=_hex(C_LINE), width=1)

            ck_y = int(cur_y + (content_h - ck_sz) / 2)
            if ck_y < cur_y:
                ck_y = int(cur_y)
            draw.rounded_rectangle([x, ck_y, x + ck_sz, ck_y + ck_sz], radius=3, fill=_hex(C_MAIN))
            draw.text((x + 3, ck_y + 1), '✓', fill=_hex(C_WHITE), font=ck_f)

            ty = cur_y
            for ln in lines:
                draw.text((x + ck_sz + 8, int(ty)), ln, fill=_hex(C_DARK), font=ifn)
                ty += line_sp
            cur_y += content_h + gap_val

    _draw_col(px, left_data, left_gap)
    if use_two_col and right_data:
        _draw_col(px + col_w + col_gap, right_data, right_gap)

    _draw_footer(draw, w, h)
    return img


# ══════════════════════════════════════════════════════════════
#  공개 API
# ══════════════════════════════════════════════════════════════

def _type_title(tp, org):
    return {"info_card": "{org} 정책자금 핵심 요약", "flowchart": "{org} 신청 절차",
            "comparison": "{org} 자금별 조건 비교", "checklist": "{org} 신청 전 확인사항",
            }.get(tp, "{org} 정책자금").format(org=org or "정책자금")


def generate_image_async(
    title, blog_body, main_color, sub_color,
    image_type=None, seed=None, kb_data=None, org="", callback=None,
):
    def run():
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        facts = _extract_kb_facts(org, kb_data) if kb_data else {}
        types = [image_type] if image_type else detect_image_types(blog_body)
        blog_paths, errors = [], []

        titles = {t: _type_title(t, org) for t in ["info_card", "flowchart", "comparison", "checklist"]}

        for i, it in enumerate(types, 1):
            p = os.path.join(OUTPUT_DIR, f"blog_{ts}_{i}.webp")
            try:
                if it == "flowchart":
                    img = _create_flowchart(titles[it], facts.get("steps") or ["신청", "심사", "결정", "실행", "관리"], BLOG_W, BLOG_H)
                elif it == "comparison":
                    img = _create_comparison(titles[it], facts.get("funds") or [{"name": "자금A", "items": ["정보 없음"]}], BLOG_W, BLOG_H)
                elif it == "checklist":
                    img = _create_checklist(titles[it], facts.get("checklist") or ["항목 정보 없음"], BLOG_W, BLOG_H)
                else:
                    img = _create_info_card(titles["info_card"], facts.get("info_lines") or ["정보 없음"], BLOG_W, BLOG_H)
                img.save(p, 'WEBP', quality=90)
                blog_paths.append(p)
            except Exception as e:
                errors.append(f"blog_{i}: {e}")

        ip = os.path.join(OUTPUT_DIR, f"insta_{ts}_1.webp")
        try:
            img = _create_info_card(titles["info_card"], facts.get("info_lines") or ["정보 없음"], INSTA_W, INSTA_H)
            img.save(ip, 'WEBP', quality=90)
        except Exception as e:
            errors.append(f"insta: {e}"); ip = None

        if errors:
            print(f"[image_generator] {errors}")
        if callback:
            callback(blog_paths or None, ip)

    threading.Thread(target=run, daemon=True).start()
