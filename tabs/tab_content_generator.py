"""탭 2: 콘텐츠 생성기 — 키워드→프롬프트→초안→편집→이미지→발행"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tbs
from ttkbootstrap.constants import *
import threading
import webbrowser
import os

from modules.keyword_analyzer import build_keyword_candidates, analyze_keywords_async
from modules.prompt_generator import generate_prompt
from modules.content_parser import parse_draft, generate_faq_schema
from modules.landing_matcher import match_landing_page
from modules.image_generator import generate_image_async
from modules.clipboard_publisher import ClipboardPublisher
from modules.instagram_publisher import InstagramPublisher
from modules import db_manager
from modules.utils import load_json
from modules.topic_mixer import ORGS, SITUATIONS, FUND_TYPES

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")
LP_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "landing_pages.json")


class ContentGeneratorTab(tk.Frame):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self.keyword_results = {}
        self.selected_keyword = ""
        self.parsed = {}
        self.blog_image_path = None
        self.blog_image_paths = []
        self.insta_image_path = None
        self._clipboard_pub = ClipboardPublisher()
        self._build_ui()

    def set_topic(self, topic: dict):
        """주제 Mix 탭에서 주제 전달 시 자동 설정"""
        org_name = topic.get("org", "")
        sit_name = topic.get("situation", "")
        fund_name = topic.get("fund_type", "")
        if org_name in [o["name"] for o in ORGS]:
            self.org_var.set(org_name)
        if sit_name in [s["name"] for s in SITUATIONS]:
            self.sit_var.set(sit_name)
        if fund_name in [f["name"] for f in FUND_TYPES]:
            self.fund_var.set(fund_name)
        kws = topic.get("keywords", [])
        if kws:
            self.keyword_direct_var.set(kws[0])

    def _build_ui(self):
        # ── 상단: 주제 선택 ──────────────────────────────────
        top = ttk.LabelFrame(self, text=" 주제 선택 ")
        top.pack(fill=X, padx=8, pady=(8, 4))

        r1 = ttk.Frame(top)
        r1.pack(fill=X, padx=8, pady=4)
        ttk.Label(r1, text="기관:").pack(side=LEFT)
        self.org_var = tk.StringVar(value="전체")
        ttk.Combobox(r1, textvariable=self.org_var, state="readonly",
                     values=["전체"] + [o["name"] for o in ORGS], width=12).pack(side=LEFT, padx=(2, 12))
        ttk.Label(r1, text="상황:").pack(side=LEFT)
        self.sit_var = tk.StringVar(value="전체")
        ttk.Combobox(r1, textvariable=self.sit_var, state="readonly",
                     values=["전체"] + [s["name"] for s in SITUATIONS], width=16).pack(side=LEFT, padx=(2, 12))
        ttk.Label(r1, text="자금유형:").pack(side=LEFT)
        self.fund_var = tk.StringVar(value="운영자금")
        ttk.Combobox(r1, textvariable=self.fund_var, state="readonly",
                     values=[f["name"] for f in FUND_TYPES], width=10).pack(side=LEFT, padx=(2, 12))

        r2 = ttk.Frame(top)
        r2.pack(fill=X, padx=8, pady=(0, 6))
        ttk.Label(r2, text="직접 입력:").pack(side=LEFT)
        self.keyword_direct_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.keyword_direct_var, width=40).pack(side=LEFT, padx=(2, 12))
        tbs.Button(r2, text="키워드 분석", bootstyle="info-outline",
                   command=self._do_keyword_analysis).pack(side=LEFT, padx=4)
        tbs.Button(r2, text="프롬프트 생성", bootstyle="primary-outline",
                   command=self._do_generate_prompt).pack(side=LEFT, padx=4)

        # ── 좌/우 PanedWindow ────────────────────────────────
        paned = ttk.PanedWindow(self, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        # ── 좌측: 키워드 테이블 + 프롬프트 + 초안 ──────────────
        kw_frame = ttk.LabelFrame(left, text=" 키워드 분석 결과 ")
        kw_frame.pack(fill=X, padx=4, pady=4)
        cols = ("키워드", "검색량", "경쟁", "추천")
        self.kw_tree = ttk.Treeview(kw_frame, columns=cols, show="headings", height=7)
        for col in cols:
            self.kw_tree.heading(col, text=col)
            self.kw_tree.column(col, width=80 if col != "키워드" else 160, anchor=CENTER)
        self.kw_tree.column("키워드", anchor=W)
        self.kw_tree.pack(fill=X, padx=4, pady=4)
        self.kw_tree.bind("<<TreeviewSelect>>", self._on_kw_select)

        prompt_frame = ttk.LabelFrame(left, text=" 프롬프트 ")
        prompt_frame.pack(fill=BOTH, expand=True, padx=4, pady=4)
        self.prompt_text = tk.Text(prompt_frame, wrap=WORD, height=12, font=("", 9))
        psb = ttk.Scrollbar(prompt_frame, command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=psb.set)
        self.prompt_text.pack(side=LEFT, fill=BOTH, expand=True, padx=2, pady=2)
        psb.pack(side=RIGHT, fill=Y)
        tbs.Button(left, text="클립보드 복사", bootstyle="secondary-outline",
                   command=self._copy_prompt).pack(padx=4, pady=2)

        draft_frame = ttk.LabelFrame(left, text=" Claude 결과 붙여넣기 / 자동 생성 ")
        draft_frame.pack(fill=BOTH, expand=True, padx=4, pady=4)
        self.draft_text = tk.Text(draft_frame, wrap=WORD, height=10, font=("", 9))
        dsb = ttk.Scrollbar(draft_frame, command=self.draft_text.yview)
        self.draft_text.configure(yscrollcommand=dsb.set)
        self.draft_text.pack(side=LEFT, fill=BOTH, expand=True, padx=2, pady=2)
        dsb.pack(side=RIGHT, fill=Y)

        draft_btn_row = ttk.Frame(left)
        draft_btn_row.pack(fill=X, padx=4, pady=2)
        self.auto_gen_btn = tbs.Button(draft_btn_row, text="Claude API 자동 생성",
                                       bootstyle="success", command=self._do_auto_generate)
        self.auto_gen_btn.pack(side=LEFT, padx=(4, 2))
        tbs.Button(draft_btn_row, text="초안 분석", bootstyle="primary",
                   command=self._do_parse_draft).pack(side=LEFT, padx=2)
        self.auto_gen_label = ttk.Label(draft_btn_row, text="", font=("", 8), foreground="gray")
        self.auto_gen_label.pack(side=LEFT, padx=8)

        # ── 우측: 블로그/인스타/메타 탭 ─────────────────────────
        self.edit_notebook = ttk.Notebook(right)
        self.edit_notebook.pack(fill=BOTH, expand=True, padx=4, pady=4)

        self._build_blog_tab()
        self._build_insta_tab()
        self._build_meta_tab()

        # ── 이미지 영역 ──────────────────────────────────────
        img_frame = ttk.LabelFrame(right, text=" 이미지 생성 ")
        img_frame.pack(fill=X, padx=4, pady=(0, 4))
        img_row = ttk.Frame(img_frame)
        img_row.pack(fill=X, padx=8, pady=6)
        tbs.Button(img_row, text="이미지 생성", bootstyle="info",
                   command=self._do_generate_image).pack(side=LEFT, padx=4)
        tbs.Button(img_row, text="다시 생성", bootstyle="info-outline",
                   command=lambda: self._do_generate_image(reseed=True)).pack(side=LEFT, padx=4)
        self.img_status = ttk.Label(img_row, text="이미지 없음", font=("", 9))
        self.img_status.pack(side=LEFT, padx=12)

        # ── 티스토리 발행 영역 ───────────────────────────────
        tistory_frame = ttk.LabelFrame(right, text=" 티스토리 발행 (수동 붙여넣기) ")
        tistory_frame.pack(fill=X, padx=4, pady=(0, 4))

        tistory_row1 = ttk.Frame(tistory_frame)
        tistory_row1.pack(fill=X, padx=8, pady=(6, 2))
        self.copy_html_btn = tbs.Button(tistory_row1, text="본문 HTML 복사", bootstyle="primary",
                                        command=self._copy_blog_html)
        self.copy_html_btn.pack(side=LEFT, padx=4)
        tbs.Button(tistory_row1, text="제목 복사", bootstyle="secondary-outline",
                   command=self._copy_title).pack(side=LEFT, padx=4)
        tbs.Button(tistory_row1, text="태그 복사", bootstyle="secondary-outline",
                   command=self._copy_tags).pack(side=LEFT, padx=4)
        tbs.Button(tistory_row1, text="이미지 저장", bootstyle="secondary-outline",
                   command=self._save_image_file).pack(side=LEFT, padx=4)

        tistory_row2 = ttk.Frame(tistory_frame)
        tistory_row2.pack(fill=X, padx=8, pady=(2, 6))
        tbs.Button(tistory_row2, text="티스토리 글쓰기 열기", bootstyle="light-outline",
                   command=self._open_tistory_editor).pack(side=LEFT, padx=4)
        ttk.Label(tistory_row2,
                  text="① HTML 복사 → ② 글쓰기 열기 → ③ HTML 모드 전환 → ④ 붙여넣기 → ⑤ 발행",
                  font=("", 8), foreground="gray").pack(side=LEFT, padx=12)

        # ── 인스타그램 발행 영역 ─────────────────────────────
        insta_frame = ttk.LabelFrame(right, text=" 인스타그램 발행 ")
        insta_frame.pack(fill=X, padx=4, pady=(0, 4))
        insta_row = ttk.Frame(insta_frame)
        insta_row.pack(fill=X, padx=8, pady=6)

        self.insta_api_btn = tbs.Button(insta_row, text="인스타 API 발행",
                                        bootstyle="warning", command=self._publish_insta_api)
        self.insta_api_btn.pack(side=LEFT, padx=4)
        tbs.Button(insta_row, text="인스타 텍스트 복사", bootstyle="warning-outline",
                   command=self._copy_insta_text).pack(side=LEFT, padx=4)
        tbs.Button(insta_row, text="인스타 이미지 저장", bootstyle="warning-outline",
                   command=self._save_insta_image).pack(side=LEFT, padx=4)
        ttk.Label(insta_row, text="(API 없으면 텍스트/이미지 복사 후 수동 업로드)",
                  font=("", 8), foreground="gray").pack(side=LEFT, padx=8)

        # ── 발행 완료 기록 ────────────────────────────────────
        done_frame = ttk.LabelFrame(right, text=" 발행 완료 기록 ")
        done_frame.pack(fill=X, padx=4, pady=(0, 6))
        done_row = ttk.Frame(done_frame)
        done_row.pack(fill=X, padx=8, pady=6)
        self.record_btn = tbs.Button(done_row, text="발행 완료 기록",
                                     bootstyle="success", command=self._record_published)
        self.record_btn.pack(side=LEFT, padx=4)
        ttk.Label(done_row,
                  text="클릭 시 발행 기록 저장 + 주제 Mix 탭 발행 완료 표시",
                  font=("", 8), foreground="gray").pack(side=LEFT, padx=12)

        # 상태바
        self.status_lbl = ttk.Label(right, text="", font=("", 9))
        self.status_lbl.pack(padx=4, pady=2, anchor=W)

        self._update_insta_btn_state()

    def _build_blog_tab(self):
        f = ttk.Frame(self.edit_notebook)
        self.edit_notebook.add(f, text="블로그")

        ttk.Label(f, text="제목:").pack(anchor=W, padx=8, pady=(8, 0))
        self.blog_title_var = tk.StringVar()
        self.blog_title_var.trace_add("write", self._update_char_counts)
        ttk.Entry(f, textvariable=self.blog_title_var, width=70).pack(fill=X, padx=8)
        self.title_count_lbl = ttk.Label(f, text="0/60자", font=("", 8))
        self.title_count_lbl.pack(anchor=E, padx=8)

        ttk.Label(f, text="본문:").pack(anchor=W, padx=8, pady=(4, 0))
        self.blog_body = tk.Text(f, wrap=WORD, height=14, font=("", 10))
        self.blog_body.tag_configure("check", foreground="red", background="#fff0f0")
        self.blog_body.bind("<KeyRelease>", self._update_char_counts)
        bsb = ttk.Scrollbar(f, command=self.blog_body.yview)
        self.blog_body.configure(yscrollcommand=bsb.set)
        body_frame = ttk.Frame(f)
        body_frame.pack(fill=BOTH, expand=True, padx=8)
        self.blog_body.pack(side=LEFT, fill=BOTH, expand=True)
        bsb.pack(side=RIGHT, fill=Y)

        row = ttk.Frame(f)
        row.pack(fill=X, padx=8, pady=4)
        ttk.Label(row, text="태그:").pack(side=LEFT)
        self.tag_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.tag_var, width=50).pack(side=LEFT, padx=4)
        ttk.Label(row, text="카테고리:").pack(side=LEFT, padx=(12, 0))
        self.category_var = tk.StringVar(value="소상공인 정책자금")
        ttk.Combobox(row, textvariable=self.category_var, state="readonly", width=16,
                     values=["소상공인 정책자금", "기관별 가이드", "기업인증", "자주 묻는 질문", "정책자금 뉴스"]
                     ).pack(side=LEFT, padx=4)

        self.body_count_lbl = ttk.Label(f, text="본문: 0자 (목표 2000~3000자)", font=("", 8))
        self.body_count_lbl.pack(anchor=E, padx=8)

        # CTA 미리보기
        cta_frame = ttk.LabelFrame(f, text=" CTA 미리보기 ")
        cta_frame.pack(fill=X, padx=8, pady=4)
        cta = self.settings.get("cta", {})
        self.cta_preview_lbl = ttk.Label(
            cta_frame,
            text=f"{cta.get('text', '')} → {cta.get('url', '')}",
            font=("", 9), foreground="white"
        )
        self.cta_preview_lbl.pack(padx=8, pady=4)

    def _build_insta_tab(self):
        f = ttk.Frame(self.edit_notebook)
        self.edit_notebook.add(f, text="인스타")

        ttk.Label(f, text="텍스트:").pack(anchor=W, padx=8, pady=(8, 0))
        self.insta_text = tk.Text(f, wrap=WORD, height=14, font=("", 10))
        self.insta_text.bind("<KeyRelease>", self._update_char_counts)
        isb = ttk.Scrollbar(f, command=self.insta_text.yview)
        self.insta_text.configure(yscrollcommand=isb.set)
        iframe = ttk.Frame(f)
        iframe.pack(fill=BOTH, expand=True, padx=8)
        self.insta_text.pack(side=LEFT, fill=BOTH, expand=True)
        isb.pack(side=RIGHT, fill=Y)
        self.insta_count_lbl = ttk.Label(f, text="0/2200자", font=("", 8))
        self.insta_count_lbl.pack(anchor=E, padx=8)

        ttk.Label(f, text="해시태그:").pack(anchor=W, padx=8)
        self.hashtag_var = tk.StringVar(
            value=self.settings.get("publish", {}).get("defaultHashtags", ""))
        ttk.Entry(f, textvariable=self.hashtag_var, width=70).pack(fill=X, padx=8, pady=(0, 8))

    def _build_meta_tab(self):
        f = ttk.Frame(self.edit_notebook)
        self.edit_notebook.add(f, text="메타/FAQ")

        for lbl, attr in [("SEO 제목:", "meta_title_var"), ("URL 슬러그:", "meta_slug_var")]:
            ttk.Label(f, text=lbl).pack(anchor=W, padx=8, pady=(8, 0))
            var = tk.StringVar()
            setattr(self, attr, var)
            ttk.Entry(f, textvariable=var, width=60).pack(fill=X, padx=8)

        ttk.Label(f, text="메타 디스크립션 (155자):").pack(anchor=W, padx=8, pady=(8, 0))
        self.meta_desc = tk.Text(f, wrap=WORD, height=4, font=("", 10))
        self.meta_desc.bind("<KeyRelease>", self._update_char_counts)
        self.meta_desc.pack(fill=X, padx=8)
        self.meta_count_lbl = ttk.Label(f, text="0/155자", font=("", 8))
        self.meta_count_lbl.pack(anchor=E, padx=8)

        ttk.Label(f, text="FAQ 스키마 (JSON-LD):").pack(anchor=W, padx=8, pady=(8, 0))
        self.faq_schema_text = tk.Text(f, wrap=NONE, height=10, font=("Courier", 9))
        fsb = ttk.Scrollbar(f, command=self.faq_schema_text.yview)
        self.faq_schema_text.configure(yscrollcommand=fsb.set)
        ff = ttk.Frame(f)
        ff.pack(fill=BOTH, expand=True, padx=8)
        self.faq_schema_text.pack(side=LEFT, fill=BOTH, expand=True)
        fsb.pack(side=RIGHT, fill=Y)

    # ── 태그 자동 생성 ───────────────────────────────────────
    def _build_tags(self) -> str:
        """초안 분석 시 기관·자금유형·상황·키워드 기반 7~10개 태그 자동 생성"""
        # 기관명 → 정식명칭 매핑
        org_fullname = {
            "중진공": "중소벤처기업진흥공단",
            "소진공": "소상공인시장진흥공단",
            "기보":   "기술보증기금",
            "신보":   "신용보증기금",
            "신용보증재단": "지역신용보증재단",
            "무역보험공사": "한국무역보험공사",
            "농신보": "농업신용보증기금",
        }
        # 상황 → 핵심 키워드 매핑
        sit_keyword_map = {
            "창업":     "창업자금",
            "폐업위기": "긴급경영자금",
            "매출감소": "매출감소자금",
            "시설투자": "시설자금",
            "기술개발": "기술개발자금",
            "운영자금부족": "운영자금",
            "대환대출": "대환대출",
            "기업인증": "기업인증우대",
            "수출": "수출자금",
        }

        org = self.org_var.get()
        sit = self.sit_var.get()
        fund = self.fund_var.get()
        kw  = self.keyword_direct_var.get().strip()

        tags = []

        # 1) 직접 입력 키워드
        if kw:
            tags.append(kw)

        # 2) 기관명 + 정식명칭
        if org and org != "전체":
            tags.append(org)
            fullname = org_fullname.get(org)
            if fullname and fullname not in tags:
                tags.append(fullname)

        # 3) 정책자금 (공통)
        tags.append("정책자금")

        # 4) 자금유형
        if fund and fund != "전체":
            tags.append(fund)

        # 5) 상황 키워드
        sit_kw = sit_keyword_map.get(sit)
        if sit_kw:
            tags.append(sit_kw)

        # 6) 소상공인대출 vs 중소기업대출
        if org == "중진공":
            tags.append("중소기업대출")
        else:
            tags.append("소상공인대출")

        # 7) 부광솔루션즈 (항상 포함)
        tags.append("부광솔루션즈")

        # 8) 보조 태그 — 10개 미만이면 추가
        extra = ["소상공인", "정책자금신청", "저금리대출", "사업자대출"]
        for e in extra:
            if len(tags) >= 10:
                break
            if e not in tags:
                tags.append(e)

        # 중복 제거, 순서 유지
        seen = set()
        result = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                result.append(t)

        return ", ".join(result[:10])

    # ── 키워드 분석 ──────────────────────────────────────────
    def _do_keyword_analysis(self):
        org = self.org_var.get()
        sit_name = self.sit_var.get()
        fund = self.fund_var.get()
        direct = self.keyword_direct_var.get().strip()
        sit = next((s for s in SITUATIONS if s["name"] == sit_name), {})
        sit_kws = sit.get("keywords", [])
        keywords = [direct] if direct else build_keyword_candidates(
            org if org != "전체" else "소상공인", sit_kws, fund
        )
        self._set_status("키워드 분석 중...")
        analyze_keywords_async(keywords, self.settings.get("api", {}), self._on_kw_result)

    def _on_kw_result(self, result: dict):
        self.keyword_results = result
        self.kw_tree.delete(*self.kw_tree.get_children())
        sorted_kws = sorted(result.items(), key=lambda x: x[1]["total"], reverse=True)
        naver_cnt = sum(1 for d in result.values() if d.get("source") == "naver")
        google_cnt = sum(1 for d in result.values() if d.get("source") == "google")
        for kw, data in sorted_kws:
            star = "★" if data["competition"] == "낮음" and data["total"] > 500 else ""
            src_tag = " (G)" if data.get("source") == "google" else ""
            self.kw_tree.insert("", END, iid=kw, values=(
                f"{kw}{src_tag}", f"{data['total']:,}", data["competition"], star))
        src_note = f" (네이버 {naver_cnt}개 + Google서제스트 {google_cnt}개)" if google_cnt else ""
        self._set_status(f"키워드 분석 완료 — {len(result)}개{src_note}")

    def _on_kw_select(self, event):
        sel = self.kw_tree.selection()
        if sel:
            self.selected_keyword = sel[0]
            self.keyword_direct_var.set(self.selected_keyword)

    # ── 프롬프트 생성 ────────────────────────────────────────
    def _do_generate_prompt(self):
        keyword = self.keyword_direct_var.get().strip() or self.selected_keyword
        if not keyword:
            messagebox.showwarning("키워드 없음", "키워드를 입력하거나 선택하세요.", parent=self)
            return
        kb = load_json(KB_PATH) or {}
        lps = load_json(LP_PATH) or []
        landing_url = match_landing_page(keyword, lps)
        prompt = generate_prompt(
            keyword, self.org_var.get(), self.sit_var.get(), self.fund_var.get(),
            kb, landing_url, self.settings.get("toneGuide", [])
        )
        self.prompt_text.delete("1.0", END)
        self.prompt_text.insert("1.0", prompt)
        self._set_status("프롬프트 생성 완료 — Claude 채팅에 복사하세요.")

    def _copy_prompt(self):
        text = self.prompt_text.get("1.0", END).strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("프롬프트가 클립보드에 복사됐어요.")

    # ── 초안 파싱 ────────────────────────────────────────────
    def _do_parse_draft(self):
        raw = self.draft_text.get("1.0", END).strip()
        if not raw:
            messagebox.showwarning("초안 없음", "Claude 결과를 붙여넣으세요.", parent=self)
            return
        self.parsed = parse_draft(raw)
        blog = self.parsed.get("blog", {})
        self.blog_title_var.set(blog.get("title", ""))
        self.blog_body.delete("1.0", END)
        self.blog_body.insert("1.0", blog.get("body", ""))
        self._highlight_check_needed()
        self.tag_var.set(self._build_tags())

        insta = self.parsed.get("instagram", {})
        self.insta_text.delete("1.0", END)
        self.insta_text.insert("1.0", insta.get("text", ""))
        if insta.get("hashtags"):
            self.hashtag_var.set(insta["hashtags"])

        meta = self.parsed.get("meta", {})
        self.meta_desc.delete("1.0", END)
        self.meta_desc.insert("1.0", meta.get("description", ""))
        self.meta_title_var.set(blog.get("title", ""))

        faqs = self.parsed.get("faq", [])
        if faqs:
            schema = generate_faq_schema(faqs)
            self.faq_schema_text.delete("1.0", END)
            self.faq_schema_text.insert("1.0", schema)

        self._update_char_counts()
        self._highlight_check_needed()

        if self._has_check_needed():
            self._set_status("⚠ [확인 필요] 항목이 있어요 — 빨간 표시 확인 후 수정하면 버튼이 활성화됩니다.")
        else:
            self._set_status("초안 분석 완료.")

    def _highlight_check_needed(self):
        """블로그 본문 + 인스타 텍스트 + 메타 디스크립션에서 [확인 필요] 빨간 하이라이트"""
        for widget in [self.blog_body, self.insta_text, self.meta_desc]:
            widget.tag_configure("check", foreground="red", background="#fff0f0")
            widget.tag_remove("check", "1.0", END)
            start = "1.0"
            while True:
                pos = widget.search("[확인 필요", start, stopindex=END)
                if not pos:
                    break
                end_pos = widget.search("]", pos, stopindex=END)
                end_pos = f"{end_pos}+1c" if end_pos else f"{pos}+8c"
                widget.tag_add("check", pos, end_pos)
                start = end_pos

    def _has_check_needed(self) -> bool:
        """전체 편집 영역에 [확인 필요] 존재 여부"""
        for widget in [self.blog_body, self.insta_text, self.meta_desc]:
            if "[확인 필요" in widget.get("1.0", END):
                return True
        return False

    def _update_record_btn_state(self):
        has_check = self._has_check_needed()
        state = DISABLED if has_check else NORMAL
        self.record_btn.configure(state=state)
        if hasattr(self, "copy_html_btn"):
            self.copy_html_btn.configure(state=state)
        if has_check:
            self._set_status("⚠ [확인 필요] 항목 있음 — 빨간 표시 확인 후 수정하면 버튼이 활성화됩니다.")

    def _update_char_counts(self, *_):
        title = self.blog_title_var.get()
        self.title_count_lbl.config(
            text=f"{len(title)}/60자",
            foreground="red" if len(title) > 60 else "gray")
        body = self.blog_body.get("1.0", END)
        count = len(body.strip())
        color = "green" if 2000 <= count <= 3000 else ("red" if count > 3000 else "gray")
        self.body_count_lbl.config(text=f"본문: {count:,}자 (목표 2000~3000자)", foreground=color)
        insta = self.insta_text.get("1.0", END)
        self.insta_count_lbl.config(text=f"{len(insta.strip())}/2200자")
        meta = self.meta_desc.get("1.0", END)
        mcount = len(meta.strip())
        self.meta_count_lbl.config(
            text=f"{mcount}/155자",
            foreground="red" if mcount > 155 else "gray")
        self._highlight_check_needed()
        self._update_record_btn_state()

    # ── 이미지 생성 ──────────────────────────────────────────
    def _do_generate_image(self, reseed=False):
        import random
        title = self.blog_title_var.get()
        body = self.blog_body.get("1.0", END)
        if not title:
            messagebox.showwarning("제목 없음", "제목을 먼저 입력하세요.", parent=self)
            return
        brand = self.settings.get("brand", {})
        seed = random.randint(0, 9999) if reseed else None
        org = self.org_var.get() if hasattr(self, "org_var") else ""
        kb_data = load_json(KB_PATH) or {}
        self.img_status.config(text="이미지 생성 중... (본문 분석 중)")
        generate_image_async(
            title, body,
            brand.get("mainColor", "#1B4F72"),
            brand.get("subColor", "#F97316"),
            seed=seed,
            kb_data=kb_data,
            org=org if org != "전체" else "",
            callback=self._on_image_done,
        )

    def _on_image_done(self, blog_paths, insta_path):
        # blog_paths는 list[str] 또는 None
        self.blog_image_paths = blog_paths or []
        self.blog_image_path = self.blog_image_paths[0] if self.blog_image_paths else None
        self.insta_image_path = insta_path
        n = len(self.blog_image_paths)
        if n:
            total = n + 1  # blog + insta
            self.after(0, lambda: self.img_status.config(
                text=f"이미지 생성 완료 — 블로그 {n}장 + 인스타 1장 (총 {total}장)"
            ))
        else:
            self.after(0, lambda: self.img_status.config(text="이미지 생성 실패"))

    # ── 티스토리 발행 (클립보드) ──────────────────────────────
    def _get_publish_context(self) -> dict:
        lps = load_json(LP_PATH) or []
        keyword = self.keyword_direct_var.get().strip() or self.selected_keyword
        landing_url = match_landing_page(keyword, lps)
        faqs = self.parsed.get("faq", [])
        faq_schema = generate_faq_schema(faqs) if faqs else ""
        cta = self.settings.get("cta", {})
        author = self.settings.get("author", {})
        brand = self.settings.get("brand", {})
        return {
            "keyword": keyword,
            "landing_url": landing_url,
            "faq_schema": faq_schema,
            "cta_text": cta.get("text", ""),
            "cta_url": landing_url,
            "author_name": author.get("name", ""),
            "author_title": author.get("title", ""),
            "author_career": author.get("career", ""),
            "main_color": brand.get("mainColor", "#1B4F72"),
            "sub_color": brand.get("subColor", "#F97316"),
        }

    def _copy_blog_html(self):
        title = self.blog_title_var.get().strip()
        body = self.blog_body.get("1.0", END).strip()
        if not title or not body:
            messagebox.showwarning("내용 없음", "제목과 본문을 먼저 입력하세요.", parent=self)
            return
        ctx = self._get_publish_context()
        html = self._clipboard_pub.copy_blog_html(
            body, title, ctx["keyword"], ctx["faq_schema"],
            ctx["cta_text"], ctx["cta_url"],
            ctx["author_name"], ctx["author_title"], ctx["author_career"],
            ctx["main_color"], ctx["sub_color"],
            self.blog_image_path
        )
        self._set_status(f"HTML 복사 완료 ({len(html):,}자) — 티스토리 에디터에 붙여넣으세요.")

    def _copy_title(self):
        title = self.blog_title_var.get().strip()
        if not title:
            messagebox.showwarning("제목 없음", "제목을 입력하세요.", parent=self)
            return
        self._clipboard_pub.copy_title(title)
        self._set_status("제목 복사 완료.")

    def _copy_tags(self):
        tags = self.tag_var.get().strip()
        if not tags:
            messagebox.showwarning("태그 없음", "태그를 입력하세요.", parent=self)
            return
        self._clipboard_pub.copy_tags(tags)
        self._set_status("태그 복사 완료.")

    def _save_image_file(self):
        blog_paths = getattr(self, "blog_image_paths", [])
        if not blog_paths and not self.blog_image_path:
            messagebox.showwarning("이미지 없음", "이미지를 먼저 생성하세요.", parent=self)
            return
        save_dir = filedialog.askdirectory(title="이미지 저장 폴더 선택", parent=self)
        if not save_dir:
            return
        import shutil, os as _os
        saved = []
        for i, src in enumerate(blog_paths, start=1):
            if src and _os.path.exists(src):
                ext = _os.path.splitext(src)[1] or ".webp"
                dest = _os.path.join(save_dir, f"blog_{i}{ext}")
                shutil.copy2(src, dest)
                saved.append(f"blog_{i}{ext}")
        if self.insta_image_path and _os.path.exists(self.insta_image_path):
            ext = _os.path.splitext(self.insta_image_path)[1] or ".webp"
            dest = _os.path.join(save_dir, f"insta_1{ext}")
            shutil.copy2(self.insta_image_path, dest)
            saved.append(f"insta_1{ext}")
        # OG 이미지도 함께 저장
        og_dir = _os.path.join(_os.path.dirname(__file__), "..", "images", "generated")
        og_files = [f for f in _os.listdir(og_dir) if f.startswith("og_")] if _os.path.exists(og_dir) else []
        if og_files:
            og_latest = sorted(og_files)[-1]
            shutil.copy2(_os.path.join(og_dir, og_latest), _os.path.join(save_dir, og_latest))
            saved.append(og_latest)
        if saved:
            n = len(saved)
            self._set_status(f"이미지 {n}장이 WebP 형식으로 저장되었습니다. (폴더: {save_dir})")
        else:
            self._set_status("저장할 이미지 파일을 찾을 수 없습니다.")

    def _open_tistory_editor(self):
        api = self.settings.get("api", {})
        url = api.get("tistory_write_url", "https://bksolution.tistory.com/manage/newpost")
        webbrowser.open(url)
        self._set_status("티스토리 글쓰기 페이지를 브라우저로 열었어요.")

    # ── 인스타그램 발행 ──────────────────────────────────────
    def _update_insta_btn_state(self):
        api = self.settings.get("api", {})
        meta = api.get("meta", {})
        has_token = bool(meta.get("accessToken", "").strip())
        state = NORMAL if has_token else DISABLED
        if hasattr(self, "insta_api_btn"):
            self.insta_api_btn.configure(state=state)

    def _publish_insta_api(self):
        api = self.settings.get("api", {})
        meta = api.get("meta", {})
        access_token = meta.get("accessToken", "").strip()
        ig_user_id = meta.get("ig_user_id", "").strip()
        imgur_client_id = meta.get("imgurClientId", "").strip()

        if not access_token or not ig_user_id:
            messagebox.showwarning(
                "설정 필요",
                "설정 탭 > API 설정에서\n"
                "Meta Access Token과 IG User ID를 먼저 입력하세요.",
                parent=self
            )
            return

        caption = self.insta_text.get("1.0", END).strip()
        hashtags = self.hashtag_var.get().strip()
        if not caption:
            messagebox.showwarning("내용 없음", "인스타 텍스트를 먼저 입력하세요.", parent=self)
            return

        if not self.insta_image_path or not os.path.exists(self.insta_image_path):
            messagebox.showwarning(
                "이미지 필요",
                "Meta API 발행에는 인스타 이미지가 반드시 필요합니다.\n"
                "먼저 '이미지 생성' 버튼으로 이미지를 만들어주세요.",
                parent=self
            )
            return

        if not imgur_client_id:
            messagebox.showwarning(
                "Imgur 설정 필요",
                "이미지를 Meta API에 전송하려면 Imgur Client ID가 필요해요.\n"
                "설정 탭 > API 설정 > Meta 섹션에서 Imgur Client ID를 입력하세요.\n"
                "(imgur.com/oauth2/addclient 에서 무료 발급)",
                parent=self
            )
            return

        self.insta_api_btn.configure(state=DISABLED)
        self._set_status("인스타 이미지 업로드 중...")

        from modules.instagram_publisher import InstagramPublisher
        pub = InstagramPublisher(ig_user_id, access_token)
        pub.publish_from_local(
            self.insta_image_path, caption, hashtags,
            imgur_client_id,
            callback=self._on_insta_published
        )

    def _on_insta_published(self, result: dict):
        self.insta_api_btn.configure(state=NORMAL)
        if result["success"]:
            self._set_status(f"인스타 발행 완료! media_id: {result['media_id']}")
            messagebox.showinfo("발행 완료", f"인스타그램 발행 성공!\nmedia_id: {result['media_id']}", parent=self)
            # DB 기록 업데이트
            from modules import db_manager
            records = db_manager.fetch_all()
            if records:
                latest = records[0]
                db_manager.update_status(latest["id"], insta_status="success")
        else:
            self._set_status(f"인스타 발행 실패: {result['error'][:60]}")
            messagebox.showerror("발행 실패", f"오류: {result['error']}", parent=self)

    def _copy_insta_text(self):
        text = self.insta_text.get("1.0", END).strip()
        hashtags = self.hashtag_var.get().strip()
        if not text:
            messagebox.showwarning("내용 없음", "인스타 텍스트를 먼저 입력하세요.", parent=self)
            return
        self._clipboard_pub.copy_insta_text(text, hashtags)
        self._set_status("인스타 텍스트 복사 완료.")

    def _save_insta_image(self):
        if not self.insta_image_path:
            messagebox.showwarning("이미지 없음", "이미지를 먼저 생성하세요.", parent=self)
            return
        save_dir = filedialog.askdirectory(title="인스타 이미지 저장 폴더 선택", parent=self)
        if save_dir:
            self._clipboard_pub.save_image(self.insta_image_path, save_dir)
            self._set_status(f"인스타 이미지 저장 완료 → {save_dir}")

    # ── 발행 완료 기록 ────────────────────────────────────────
    def _record_published(self):
        title = self.blog_title_var.get().strip()
        if not title:
            messagebox.showwarning("내용 없음", "발행할 콘텐츠가 없어요.", parent=self)
            return

        # 하루 1편 경고
        max_per_day = self.settings.get("publish", {}).get("maxPerDay", 1)
        today_count = db_manager.count_today_published()
        if today_count >= max_per_day:
            if not messagebox.askyesno(
                "발행 권장 초과",
                f"오늘 이미 {today_count}편 기록했어요.\n"
                f"하루 1편 발행을 권장합니다. 그래도 기록하시겠어요?",
                parent=self
            ):
                return

        ctx = self._get_publish_context()
        db_manager.insert_record({
            "org": self.org_var.get(),
            "keyword": ctx["keyword"],
            "title": title,
            "blog_status": "success",
            "insta_status": "pending",
            "landing_url": ctx["landing_url"],
            "category": self.category_var.get(),
        })
        messagebox.showinfo("기록 완료", "발행 기록이 저장됐어요.\n발행 관리 탭에서 확인하세요.", parent=self)
        self._set_status("발행 완료 기록됨.")

    # ── Claude API 자동 생성 ─────────────────────────────────
    def _do_auto_generate(self):
        api_key = self.settings.get("api", {}).get("claude", {}).get("apiKey", "").strip()
        if not api_key:
            messagebox.showwarning(
                "API Key 없음",
                "설정 탭 > API 설정에서 Claude API Key를 먼저 입력하세요.\n"
                "API 없이 쓰려면 '클립보드 복사' → Claude 채팅 수동 붙여넣기를 사용하세요.",
                parent=self
            )
            return

        prompt = self.prompt_text.get("1.0", END).strip()
        if not prompt:
            messagebox.showwarning("프롬프트 없음", "먼저 '프롬프트 생성'을 눌러 프롬프트를 만드세요.", parent=self)
            return

        self.auto_gen_btn.configure(state=DISABLED)
        self.auto_gen_label.config(text="생성 중... (30~60초 소요)", foreground="orange")
        self._set_status("Claude API 호출 중...")

        def run():
            import requests as req
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            try:
                resp = req.post(
                    "https://api.anthropic.com/v1/messages",
                    json=body, headers=headers, timeout=120
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["content"][0]["text"]
                    self.after(0, lambda: self._on_auto_generate_done(text, None))
                else:
                    err = resp.json().get("error", {}).get("message", resp.text[:120])
                    self.after(0, lambda: self._on_auto_generate_done(None, err))
            except Exception as e:
                self.after(0, lambda: self._on_auto_generate_done(None, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_auto_generate_done(self, text, error):
        self.auto_gen_btn.configure(state=NORMAL)
        if error:
            self.auto_gen_label.config(text=f"오류: {error[:60]}", foreground="red")
            self._set_status(f"Claude API 오류: {error[:80]}")
            return
        self.draft_text.delete("1.0", END)
        self.draft_text.insert("1.0", text)
        self.auto_gen_label.config(text="생성 완료! 자동 분석 중...", foreground="#4CAF50")
        self._set_status("Claude 초안 생성 완료 — 자동 분석 시작.")
        self._do_parse_draft()

    def _set_status(self, msg: str):
        self.status_lbl.config(text=msg)
