"""탭 4: 설정"""
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import ttkbootstrap as tbs
from ttkbootstrap.constants import *
from modules.utils import save_json
import os
import threading

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
LP_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "landing_pages.json")


class SettingsTab(tk.Frame):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=BOTH, expand=True, padx=8, pady=8)

        self._build_api_tab(nb)
        self._build_author_tab(nb)
        self._build_tone_tab(nb)
        self._build_content_tab(nb)
        self._build_publish_tab(nb)
        self._build_landing_tab(nb)
        self._build_guide_tab(nb)

    # ── API 설정 ─────────────────────────────────────────────
    def _build_api_tab(self, nb):
        import webbrowser
        f = ttk.Frame(nb)
        nb.add(f, text="API 설정")

        api = self.settings.get("api", {})

        # 티스토리 (API 불필요 — 수동 붙여넣기)
        tistory_lf = ttk.LabelFrame(f, text=" 티스토리 (수동 발행 — API 불필요) ")
        tistory_lf.pack(fill=X, padx=12, pady=6)
        tistory_note = ttk.Label(
            tistory_lf,
            text="티스토리 Open API는 2024.02 종료됨. HTML 클립보드 복사 → 수동 붙여넣기 방식으로 발행합니다.",
            foreground="gray", wraplength=500
        )
        tistory_note.pack(padx=12, pady=(6, 2), anchor=W)

        for lbl, key, default in [
            ("블로그 주소", "tistory_blog_url", "https://bksolution.tistory.com"),
            ("글쓰기 URL",  "tistory_write_url", "https://bksolution.tistory.com/manage/newpost"),
        ]:
            row = ttk.Frame(tistory_lf)
            row.pack(fill=X, padx=12, pady=3)
            ttk.Label(row, text=f"{lbl}:", width=12, anchor=E).pack(side=LEFT)
            var = tk.StringVar(value=api.get(key, default))
            ttk.Entry(row, textvariable=var, width=50).pack(side=LEFT, padx=4)
            if not hasattr(self, "_tistory_vars"):
                self._tistory_vars = {}
            self._tistory_vars[key] = var

        open_row = ttk.Frame(tistory_lf)
        open_row.pack(fill=X, padx=12, pady=(2, 8))
        tbs.Button(
            open_row, text="티스토리 글쓰기 열기", bootstyle="light-outline",
            command=lambda: webbrowser.open(
                self._tistory_vars.get("tistory_write_url",
                                       tk.StringVar(value="https://bksolution.tistory.com/manage/newpost")).get()
            )
        ).pack(side=LEFT)

        # Meta (인스타그램)
        meta_lf = ttk.LabelFrame(f, text=" Meta (인스타그램 Graph API) — 선택사항 ")
        meta_lf.pack(fill=X, padx=12, pady=6)
        meta_note = ttk.Label(
            meta_lf,
            text="API 없으면 텍스트+이미지 복사 후 수동 업로드. API 있으면 자동 발행 가능.",
            foreground="gray"
        )
        meta_note.pack(padx=12, pady=(4, 2), anchor=W)

        meta_data = api.get("meta", {})
        self.api_vars = {"meta": {}}
        for field, lbl in [("appId", "App ID"), ("appSecret", "App Secret"),
                            ("accessToken", "Access Token"), ("ig_user_id", "IG User ID")]:
            row = ttk.Frame(meta_lf)
            row.pack(fill=X, padx=12, pady=3)
            ttk.Label(row, text=f"{lbl}:", width=14, anchor=E).pack(side=LEFT)
            var = tk.StringVar(value=meta_data.get(field, ""))
            show = "*" if any(w in field.lower() for w in ["secret", "token"]) else ""
            entry = ttk.Entry(row, textvariable=var, show=show, width=50)
            entry.pack(side=LEFT, padx=4)
            if show:
                def toggle(e=entry, s=show):
                    e.configure(show="" if e.cget("show") == s else s)
                tbs.Button(row, text="보기", bootstyle="secondary-outline",
                           width=4, command=toggle).pack(side=LEFT)
            self.api_vars["meta"][field] = var

        # Imgur Client ID (인스타 이미지 업로드용)
        imgur_row = ttk.Frame(meta_lf)
        imgur_row.pack(fill=X, padx=12, pady=3)
        ttk.Label(imgur_row, text="Imgur Client ID:", width=14, anchor=E).pack(side=LEFT)
        imgur_var = tk.StringVar(value=meta_data.get("imgurClientId", ""))
        ttk.Entry(imgur_row, textvariable=imgur_var, width=50).pack(side=LEFT, padx=4)
        ttk.Label(imgur_row, text="imgur.com/oauth2/addclient 에서 발급",
                  font=("", 8), foreground="gray").pack(side=LEFT, padx=4)
        self.api_vars["meta"]["imgurClientId"] = imgur_var

        meta_btn_row = ttk.Frame(meta_lf)
        meta_btn_row.pack(fill=X, padx=12, pady=(2, 8))
        self.meta_test_label = ttk.Label(meta_btn_row, text="")
        tbs.Button(
            meta_btn_row, text="연결 테스트", bootstyle="info-outline",
            command=self._test_meta
        ).pack(side=LEFT)
        self.meta_test_label.pack(side=LEFT, padx=8)

        # 네이버 검색광고
        naver_lf = ttk.LabelFrame(f, text=" 네이버 검색광고 API (키워드 검색량 분석) — 선택사항 ")
        naver_lf.pack(fill=X, padx=12, pady=6)
        naver_note = ttk.Label(
            naver_lf,
            text="없으면 시뮬레이션 검색량 사용. searchad.naver.com에서 발급.",
            foreground="gray"
        )
        naver_note.pack(padx=12, pady=(4, 2), anchor=W)

        naver_data = api.get("naver", {})
        self.api_vars["naver"] = {}
        for field, lbl in [("apiKey", "API Key"), ("secretKey", "Secret Key"), ("customerId", "Customer ID")]:
            row = ttk.Frame(naver_lf)
            row.pack(fill=X, padx=12, pady=3)
            ttk.Label(row, text=f"{lbl}:", width=14, anchor=E).pack(side=LEFT)
            var = tk.StringVar(value=naver_data.get(field, ""))
            show = "*" if "secret" in field.lower() else ""
            entry = ttk.Entry(row, textvariable=var, show=show, width=50)
            entry.pack(side=LEFT, padx=4)
            if show:
                def toggle(e=entry, s=show):
                    e.configure(show="" if e.cget("show") == s else s)
                tbs.Button(row, text="보기", bootstyle="secondary-outline",
                           width=4, command=toggle).pack(side=LEFT)
            self.api_vars["naver"][field] = var

        naver_btn_row = ttk.Frame(naver_lf)
        naver_btn_row.pack(fill=X, padx=12, pady=(2, 8))
        self.naver_test_label = ttk.Label(naver_btn_row, text="")
        tbs.Button(
            naver_btn_row, text="연결 테스트", bootstyle="info-outline",
            command=self._test_naver
        ).pack(side=LEFT)
        self.naver_test_label.pack(side=LEFT, padx=8)

        # Claude API
        claude_lf = ttk.LabelFrame(f, text=" Claude API — 선택사항 ")
        claude_lf.pack(fill=X, padx=12, pady=6)
        claude_note = ttk.Label(
            claude_lf,
            text="현재 권장: Claude 맥스 채팅 수동 복붙 (비용 0원).\n"
                 "API 활성화 시 버튼 한 번으로 자동 생성 (글 1편당 약 300~500원).\n"
                 "하루 3~5편 이상 대량 발행 시 API 활용 권장.",
            foreground="gray", justify=LEFT
        )
        claude_note.pack(padx=12, pady=(4, 2), anchor=W)

        claude_data = api.get("claude", {})
        self.api_vars["claude"] = {}
        row = ttk.Frame(claude_lf)
        row.pack(fill=X, padx=12, pady=(4, 8))
        ttk.Label(row, text="API Key:", width=10, anchor=E).pack(side=LEFT)
        var = tk.StringVar(value=claude_data.get("apiKey", ""))
        entry = ttk.Entry(row, textvariable=var, show="*", width=54)
        entry.pack(side=LEFT, padx=4)
        def toggle_claude(e=entry):
            e.configure(show="" if e.cget("show") == "*" else "*")
        tbs.Button(row, text="보기", bootstyle="secondary-outline",
                   width=4, command=toggle_claude).pack(side=LEFT)
        self.api_vars["claude"]["apiKey"] = var

        claude_btn_row = ttk.Frame(claude_lf)
        claude_btn_row.pack(fill=X, padx=12, pady=(0, 8))
        self.claude_test_label = ttk.Label(claude_btn_row, text="")
        tbs.Button(
            claude_btn_row, text="연결 테스트", bootstyle="info-outline",
            command=self._test_claude
        ).pack(side=LEFT)
        self.claude_test_label.pack(side=LEFT, padx=8)

        tbs.Button(f, text="저장", bootstyle="primary", command=self._save_api).pack(pady=10)

    def _test_naver(self):
        api_key = self.api_vars["naver"]["apiKey"].get().strip()
        secret_key = self.api_vars["naver"]["secretKey"].get().strip()
        customer_id = self.api_vars["naver"]["customerId"].get().strip()
        if not all([api_key, secret_key, customer_id]):
            self.naver_test_label.config(text="API Key / Secret / Customer ID를 모두 입력하세요.", foreground="orange")
            return
        self.naver_test_label.config(text="테스트 중...", foreground="gray")

        def run():
            import hashlib, hmac, base64, time, requests
            timestamp = str(int(time.time() * 1000))
            uri = "/keywordstool"
            msg = f"{timestamp}.GET.{uri}"
            signature = base64.b64encode(
                hmac.new(secret_key.encode(), msg.encode(), hashlib.sha256).digest()
            ).decode()
            headers = {
                "X-Timestamp": timestamp, "X-API-KEY": api_key,
                "X-CUSTOMER": str(customer_id), "X-SIGNATURE": signature,
            }
            params = {"hintKeywords": "소상공인대출", "showDetail": "1"}
            try:
                resp = requests.get("https://api.searchad.naver.com/keywordstool",
                                    headers=headers, params=params, timeout=8)
                if resp.status_code == 200:
                    self.after(0, lambda: self.naver_test_label.config(text="연결 성공!", foreground="#4CAF50"))
                else:
                    self.after(0, lambda: self.naver_test_label.config(
                        text=f"오류 {resp.status_code}: {resp.text[:60]}", foreground="red"))
            except Exception as e:
                self.after(0, lambda: self.naver_test_label.config(text=f"연결 실패: {e}", foreground="red"))

        threading.Thread(target=run, daemon=True).start()

    def _test_meta(self):
        token = self.api_vars["meta"]["accessToken"].get().strip()
        ig_user_id = self.api_vars["meta"]["ig_user_id"].get().strip()
        if not token:
            self.meta_test_label.config(text="Access Token을 입력하세요.", foreground="orange")
            return
        self.meta_test_label.config(text="테스트 중...", foreground="gray")

        def run():
            import requests
            try:
                target = ig_user_id if ig_user_id else "me"
                url = f"https://graph.facebook.com/v19.0/{target}"
                resp = requests.get(url, params={"access_token": token, "fields": "id,name"}, timeout=8)
                data = resp.json()
                if "error" in data:
                    msg = data["error"].get("message", "알 수 없는 오류")
                    self.after(0, lambda: self.meta_test_label.config(text=f"오류: {msg[:60]}", foreground="red"))
                else:
                    name = data.get("name", data.get("id", "OK"))
                    self.after(0, lambda: self.meta_test_label.config(text=f"연결 성공! ({name})", foreground="#4CAF50"))
            except Exception as e:
                self.after(0, lambda: self.meta_test_label.config(text=f"연결 실패: {e}", foreground="red"))

        threading.Thread(target=run, daemon=True).start()

    def _test_claude(self):
        api_key = self.api_vars["claude"]["apiKey"].get().strip()
        if not api_key:
            self.claude_test_label.config(text="API Key를 입력하세요.", foreground="orange")
            return
        self.claude_test_label.config(text="테스트 중...", foreground="gray")

        def run():
            import requests
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            }
            try:
                resp = requests.post("https://api.anthropic.com/v1/messages",
                                     json=body, headers=headers, timeout=12)
                if resp.status_code == 200:
                    self.after(0, lambda: self.claude_test_label.config(text="연결 성공! (API 정상)", foreground="#4CAF50"))
                elif resp.status_code == 401:
                    self.after(0, lambda: self.claude_test_label.config(text="인증 실패: API Key를 확인하세요.", foreground="red"))
                else:
                    msg = resp.json().get("error", {}).get("message", resp.text[:60])
                    self.after(0, lambda: self.claude_test_label.config(text=f"오류 {resp.status_code}: {msg}", foreground="red"))
            except Exception as e:
                self.after(0, lambda: self.claude_test_label.config(text=f"연결 실패: {e}", foreground="red"))

        threading.Thread(target=run, daemon=True).start()

    def _save_api(self):
        if "api" not in self.settings:
            self.settings["api"] = {}
        # 티스토리 URL
        if hasattr(self, "_tistory_vars"):
            for key, var in self._tistory_vars.items():
                self.settings["api"][key] = var.get()
        # Meta / Naver / Claude
        for group_key, fields in self.api_vars.items():
            if group_key not in self.settings["api"]:
                self.settings["api"][group_key] = {}
            for field, var in fields.items():
                self.settings["api"][group_key][field] = var.get()
        save_json(SETTINGS_PATH, self.settings)
        messagebox.showinfo("저장 완료", "API 설정이 저장됐어요.", parent=self)

    # ── 저자 프로필 ──────────────────────────────────────────
    def _build_author_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="저자 프로필")
        author = self.settings.get("author", {})
        self.author_vars = {}

        for lbl, key, default in [
            ("이름", "name", "권대근"),
            ("직함", "title", "부광솔루션즈 대표"),
            ("경력 요약", "career", "정책자금 컨설팅 5년, 누적 상담 500건 이상"),
            ("한 줄 소개", "oneLiner", "정책자금 전문 컨설턴트"),
        ]:
            row = ttk.Frame(f)
            row.pack(fill=X, padx=12, pady=4)
            ttk.Label(row, text=f"{lbl}:", width=12, anchor=E).pack(side=LEFT)
            var = tk.StringVar(value=author.get(key, default))
            ttk.Entry(row, textvariable=var, width=52).pack(side=LEFT, padx=4)
            self.author_vars[key] = var

        # 미리보기
        preview_frame = ttk.LabelFrame(f, text=" 미리보기 ")
        preview_frame.pack(fill=X, padx=12, pady=8)
        self.author_preview = ttk.Label(preview_frame, text="", justify=LEFT)
        self.author_preview.pack(padx=12, pady=8)
        for v in self.author_vars.values():
            v.trace_add("write", self._update_author_preview)
        self._update_author_preview()

        tbs.Button(f, text="저장", bootstyle="primary", command=self._save_author).pack(pady=6)

    def _update_author_preview(self, *_):
        name = self.author_vars.get("name", tk.StringVar()).get()
        title = self.author_vars.get("title", tk.StringVar()).get()
        career = self.author_vars.get("career", tk.StringVar()).get()
        self.author_preview.config(text=f"글쓴이: {name}\n{title}\n{career}")

    def _save_author(self):
        if "author" not in self.settings:
            self.settings["author"] = {}
        for key, var in self.author_vars.items():
            self.settings["author"][key] = var.get()
        save_json(SETTINGS_PATH, self.settings)
        messagebox.showinfo("저장 완료", "저자 프로필이 저장됐어요.", parent=self)

    # ── 말투 가이드 ──────────────────────────────────────────
    def _build_tone_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="말투 가이드")
        ttk.Label(f, text="실제 상담 말투 예시 문장들 (프롬프트에 자동 포함됩니다)").pack(padx=12, pady=8, anchor=W)

        list_frame = ttk.Frame(f)
        list_frame.pack(fill=BOTH, expand=True, padx=12)

        self.tone_listbox = tk.Listbox(list_frame, height=10, font=("", 10))
        tsb = ttk.Scrollbar(list_frame, command=self.tone_listbox.yview)
        self.tone_listbox.configure(yscrollcommand=tsb.set)
        self.tone_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        tsb.pack(side=RIGHT, fill=Y)

        for s in self.settings.get("toneGuide", []):
            self.tone_listbox.insert(END, s)

        row = ttk.Frame(f)
        row.pack(fill=X, padx=12, pady=6)
        self.tone_entry_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.tone_entry_var, width=60).pack(side=LEFT, padx=(0, 6))
        tbs.Button(row, text="추가", bootstyle="success-outline",
                   command=self._add_tone).pack(side=LEFT, padx=2)
        tbs.Button(row, text="삭제", bootstyle="danger-outline",
                   command=self._del_tone).pack(side=LEFT, padx=2)
        tbs.Button(f, text="저장", bootstyle="primary", command=self._save_tone).pack(pady=6)

    def _add_tone(self):
        val = self.tone_entry_var.get().strip()
        if val:
            self.tone_listbox.insert(END, val)
            self.tone_entry_var.set("")

    def _del_tone(self):
        sel = self.tone_listbox.curselection()
        if sel:
            self.tone_listbox.delete(sel[0])

    def _save_tone(self):
        items = list(self.tone_listbox.get(0, END))
        self.settings["toneGuide"] = items
        save_json(SETTINGS_PATH, self.settings)
        messagebox.showinfo("저장 완료", "말투 가이드가 저장됐어요.", parent=self)

    # ── 콘텐츠 설정 ─────────────────────────────────────────
    def _build_content_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="콘텐츠 설정")
        cta = self.settings.get("cta", {})
        brand = self.settings.get("brand", {})

        self.cta_text_var = tk.StringVar(value=cta.get("text", "내 상황 기준 가능 여부 확인하기"))
        self.cta_url_var  = tk.StringVar(value=cta.get("url", "https://solutionbk.com/#contact"))
        self.main_color_var = tk.StringVar(value=brand.get("mainColor", "#1B4F72"))
        self.sub_color_var  = tk.StringVar(value=brand.get("subColor", "#F97316"))

        for lbl, var in [("CTA 문구", self.cta_text_var), ("CTA URL", self.cta_url_var)]:
            row = ttk.Frame(f)
            row.pack(fill=X, padx=12, pady=6)
            ttk.Label(row, text=f"{lbl}:", width=14, anchor=E).pack(side=LEFT)
            ttk.Entry(row, textvariable=var, width=52).pack(side=LEFT, padx=4)

        for lbl, var in [("메인 컬러", self.main_color_var), ("서브 컬러", self.sub_color_var)]:
            row = ttk.Frame(f)
            row.pack(fill=X, padx=12, pady=6)
            ttk.Label(row, text=f"{lbl}:", width=14, anchor=E).pack(side=LEFT)
            entry = ttk.Entry(row, textvariable=var, width=12)
            entry.pack(side=LEFT, padx=4)
            def pick_color(v=var, e=entry):
                color = colorchooser.askcolor(color=v.get(), parent=self)
                if color[1]:
                    v.set(color[1])
            tbs.Button(row, text="선택", bootstyle="secondary-outline", command=pick_color).pack(side=LEFT)

        tbs.Button(f, text="저장", bootstyle="primary", command=self._save_content).pack(pady=10)

    def _save_content(self):
        self.settings["cta"] = {"text": self.cta_text_var.get(), "url": self.cta_url_var.get()}
        self.settings["brand"] = {"mainColor": self.main_color_var.get(), "subColor": self.sub_color_var.get()}
        save_json(SETTINGS_PATH, self.settings)
        messagebox.showinfo("저장 완료", "콘텐츠 설정이 저장됐어요.", parent=self)

    # ── 발행 설정 ────────────────────────────────────────────
    def _build_publish_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="발행 설정")
        pub = self.settings.get("publish", {})

        self.delay_var = tk.StringVar(value=pub.get("delay", "random"))
        self.max_per_day_var = tk.IntVar(value=pub.get("maxPerDay", 1))
        self.default_cat_var = tk.StringVar(value=pub.get("defaultCategory", "소상공인 정책자금"))
        self.default_tags_var = tk.StringVar(value=pub.get("defaultHashtags", "#정책자금"))

        for lbl, widget_factory in [
            ("발행 지연", lambda r: ttk.Combobox(r, textvariable=self.delay_var, state="readonly",
                                                values=["random", "immediate"], width=14)),
            ("하루 최대 발행", lambda r: ttk.Spinbox(r, from_=1, to=5, textvariable=self.max_per_day_var, width=6)),
            ("기본 카테고리", lambda r: ttk.Combobox(r, textvariable=self.default_cat_var, state="readonly",
                                                    values=["소상공인 정책자금", "기관별 가이드", "기업인증", "자주 묻는 질문", "정책자금 뉴스"], width=20)),
            ("기본 해시태그", lambda r: ttk.Entry(r, textvariable=self.default_tags_var, width=50)),
        ]:
            row = ttk.Frame(f)
            row.pack(fill=X, padx=12, pady=6)
            ttk.Label(row, text=f"{lbl}:", width=14, anchor=E).pack(side=LEFT)
            widget_factory(row).pack(side=LEFT, padx=4)

        tbs.Button(f, text="저장", bootstyle="primary", command=self._save_publish).pack(pady=10)

    def _save_publish(self):
        self.settings["publish"] = {
            "delay": self.delay_var.get(),
            "maxPerDay": self.max_per_day_var.get(),
            "defaultCategory": self.default_cat_var.get(),
            "defaultHashtags": self.default_tags_var.get(),
        }
        save_json(SETTINGS_PATH, self.settings)
        messagebox.showinfo("저장 완료", "발행 설정이 저장됐어요.", parent=self)

    # ── 랜딩페이지 관리 ─────────────────────────────────────
    def _build_landing_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="랜딩페이지")
        ttk.Label(f, text="키워드 기반 랜딩페이지 자동 매칭 테이블").pack(padx=12, pady=8, anchor=W)

        from modules.utils import load_json
        self.lp_data = load_json(LP_PATH) or []

        cols = ("URL", "매칭 키워드", "설명")
        self.lp_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        for col in cols:
            w = 280 if col == "URL" else (180 if col == "매칭 키워드" else 160)
            self.lp_tree.heading(col, text=col)
            self.lp_tree.column(col, width=w, anchor=W)
        self.lp_tree.pack(fill=BOTH, expand=True, padx=12)
        self._populate_lp_tree()

        row = ttk.Frame(f)
        row.pack(fill=X, padx=12, pady=6)
        for lbl, attr in [("URL:", "lp_url_var"), ("키워드:", "lp_kw_var"), ("설명:", "lp_desc_var")]:
            ttk.Label(row, text=lbl).pack(side=LEFT)
            var = tk.StringVar()
            setattr(self, attr, var)
            ttk.Entry(row, textvariable=var, width=20).pack(side=LEFT, padx=(2, 8))

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=X, padx=12)
        tbs.Button(btn_row, text="추가", bootstyle="success-outline", command=self._lp_add).pack(side=LEFT, padx=4)
        tbs.Button(btn_row, text="삭제", bootstyle="danger-outline", command=self._lp_del).pack(side=LEFT, padx=4)
        tbs.Button(btn_row, text="저장", bootstyle="primary", command=self._lp_save).pack(side=LEFT, padx=4)

    def _populate_lp_tree(self):
        self.lp_tree.delete(*self.lp_tree.get_children())
        for item in self.lp_data:
            self.lp_tree.insert("", END, values=(item.get("url"), item.get("keywords"), item.get("desc")))

    def _lp_add(self):
        url = self.lp_url_var.get().strip()
        kw  = self.lp_kw_var.get().strip()
        desc = self.lp_desc_var.get().strip()
        if url:
            self.lp_data.append({"url": url, "keywords": kw, "desc": desc})
            self._populate_lp_tree()

    def _lp_del(self):
        sel = self.lp_tree.selection()
        if sel:
            idx = self.lp_tree.index(sel[0])
            if 0 <= idx < len(self.lp_data):
                self.lp_data.pop(idx)
                self._populate_lp_tree()

    def _lp_save(self):
        from modules.utils import save_json
        save_json(LP_PATH, self.lp_data)
        messagebox.showinfo("저장 완료", "랜딩페이지 설정이 저장됐어요.", parent=self)

    # ── 티스토리 셋팅 가이드 ─────────────────────────────────
    def _build_guide_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="설정 가이드")
        ttk.Label(f, text="티스토리 초기 설정 체크리스트", font=("", 12, "bold")).pack(padx=12, pady=(12, 8), anchor=W)

        steps = [
            ("step1", "tistory.com 가입 및 블로그 개설"),
            ("step2", "블로그 이름/설명 설정"),
            ("step3", "카테고리 5개 생성"),
            ("step4", "티스토리 API 앱 등록 및 키 발급"),
            ("step5", "Google Search Console 등록 + 사이트맵"),
            ("step6", "네이버 서치어드바이저 등록"),
            ("step7", "Google 비즈니스 프로필 등록"),
        ]
        guide = self.settings.get("setupGuide", {})
        self.guide_vars = {}
        for key, text in steps:
            var = tk.BooleanVar(value=guide.get(key, False))
            chk = ttk.Checkbutton(f, text=text, variable=var,
                                  command=lambda k=key, v=var: self._save_guide_step(k, v))
            chk.pack(anchor=W, padx=20, pady=4)
            self.guide_vars[key] = var

    def _save_guide_step(self, key: str, var: tk.BooleanVar):
        if "setupGuide" not in self.settings:
            self.settings["setupGuide"] = {}
        self.settings["setupGuide"][key] = var.get()
        save_json(SETTINGS_PATH, self.settings)
