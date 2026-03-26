"""탭 0: 주제 Mix — 3축 조합 자동 생성 및 추천"""
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tbs
from ttkbootstrap.constants import *

from modules.topic_mixer import generate_all_topics, get_top5, ORGS, SITUATIONS, FUND_TYPES
from modules.utils import load_json, save_json
import os

PUBLISHED_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "topic_published.json")
COMPETITION_COLORS = {"낮음": "success", "보통": "warning", "높음": "danger"}


class TopicMixTab(tk.Frame):
    def __init__(self, parent, settings: dict, switch_to_content_tab=None):
        super().__init__(parent)
        self.settings = settings
        self.switch_to_content_tab = switch_to_content_tab
        self.topics = []
        self.filtered = []
        self.show_published = False
        self._build_ui()
        self.refresh()

    # ── UI 구성 ──────────────────────────────────────────────
    def _build_ui(self):
        # 통계 카드 행
        stat_frame = ttk.Frame(self)
        stat_frame.pack(fill=X, padx=10, pady=(10, 0))
        self.lbl_total   = tbs.Label(stat_frame, text="전체: 0",       bootstyle="info",    font=("", 12, "bold"))
        self.lbl_done    = tbs.Label(stat_frame, text="발행 완료: 0",  bootstyle="success", font=("", 12, "bold"))
        self.lbl_remain  = tbs.Label(stat_frame, text="미발행: 0",     bootstyle="warning", font=("", 12, "bold"))
        for lbl in (self.lbl_total, self.lbl_done, self.lbl_remain):
            lbl.pack(side=LEFT, padx=20, pady=6)

        # TOP 5 추천 프레임
        top5_outer = ttk.LabelFrame(self, text=" ★ 오늘의 추천 주제 TOP 5 ")
        top5_outer.pack(fill=X, padx=10, pady=8)
        self.top5_frame = ttk.Frame(top5_outer)
        self.top5_frame.pack(fill=X, padx=6, pady=6)

        # 필터 바
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=X, padx=10, pady=4)

        ttk.Label(filter_frame, text="검색:").pack(side=LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Entry(filter_frame, textvariable=self.search_var, width=18).pack(side=LEFT, padx=(2, 8))

        ttk.Label(filter_frame, text="기관:").pack(side=LEFT)
        org_names = ["전체"] + [o["name"] for o in ORGS]
        self.org_var = tk.StringVar(value="전체")
        self.org_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Combobox(filter_frame, textvariable=self.org_var, values=org_names, width=10, state="readonly").pack(side=LEFT, padx=(2, 8))

        ttk.Label(filter_frame, text="자금유형:").pack(side=LEFT)
        fund_names = ["전체"] + [f["name"] for f in FUND_TYPES]
        self.fund_var = tk.StringVar(value="전체")
        self.fund_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Combobox(filter_frame, textvariable=self.fund_var, values=fund_names, width=8, state="readonly").pack(side=LEFT, padx=(2, 8))

        ttk.Label(filter_frame, text="유형:").pack(side=LEFT)
        self.type_var = tk.StringVar(value="전체")
        self.type_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Combobox(filter_frame, textvariable=self.type_var,
                     values=["전체", "3축조합", "기업인증", "질문형", "비교형", "총정리형"],
                     width=8, state="readonly").pack(side=LEFT, padx=(2, 8))

        self.show_pub_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="발행 완료 포함", variable=self.show_pub_var,
                        command=self._apply_filter).pack(side=LEFT, padx=8)

        self.result_lbl = ttk.Label(filter_frame, text="결과: 0개")
        self.result_lbl.pack(side=RIGHT, padx=8)

        # 테이블
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

        cols = ("#", "주제", "기관", "유형", "검색량", "경쟁", "발행")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        widths = [40, 320, 70, 70, 80, 60, 50]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=CENTER if w < 100 else W)
        self.tree.column("주제", anchor=W)

        vsb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)

        self.tree.bind("<Double-1>", self._on_double_click)

    # ── 데이터 로드 & 갱신 ────────────────────────────────────
    def refresh(self):
        published_ids = load_json(PUBLISHED_PATH) or []
        self.topics = generate_all_topics(published_ids)
        self._update_stats()
        self._render_top5()
        self._apply_filter()

    def _update_stats(self):
        total = len(self.topics)
        done  = sum(1 for t in self.topics if t["published"])
        remain = total - done
        self.lbl_total.config(text=f"전체: {total:,}")
        self.lbl_done.config(text=f"발행 완료: {done:,}")
        self.lbl_remain.config(text=f"미발행: {remain:,}")

    def _render_top5(self):
        for w in self.top5_frame.winfo_children():
            w.destroy()
        top5 = get_top5(self.topics)
        for i, t in enumerate(top5):
            card = ttk.LabelFrame(self.top5_frame, text=f"#{i+1} {t['org']}", cursor="hand2")
            card.pack(side=LEFT, padx=6, pady=4, fill=Y)
            ttk.Label(card, text=t["title"][:22] + ("…" if len(t["title"]) > 22 else ""),
                      wraplength=140, font=("", 9), cursor="hand2").pack(padx=8, pady=(4, 0))
            ttk.Label(card, text=f"검색량 {t['search_volume']:,}", font=("", 9)).pack()
            ttk.Label(card, text=f"경쟁 {t['competition']}", font=("", 9)).pack(pady=(0, 4))
            # 카드 전체 + 자식 위젯 클릭 → 상세 팝업
            for widget in [card] + card.winfo_children():
                widget.bind("<Button-1>", lambda e, topic=t: self._show_detail(topic))

    def _apply_filter(self):
        search = self.search_var.get().strip().lower()
        org_f  = self.org_var.get()
        fund_f = self.fund_var.get()
        type_f = self.type_var.get()
        show_pub = self.show_pub_var.get()

        result = []
        for t in self.topics:
            if not show_pub and t["published"]:
                continue
            if org_f  != "전체" and t["org"] != org_f:
                continue
            if fund_f != "전체" and t["fund_type"] != fund_f:
                continue
            if type_f != "전체" and t["type"] != type_f:
                continue
            if search and search not in t["title"].lower():
                continue
            result.append(t)

        # 기본 정렬: 추천순
        result.sort(key=lambda x: x["priority"], reverse=True)
        self.filtered = result[:200]  # 상위 200개
        self._populate_tree()
        self.result_lbl.config(text=f"결과: {len(result):,}개")

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, t in enumerate(self.filtered, 1):
            pub_mark = "✅" if t["published"] else ""
            self.tree.insert("", END, iid=str(t["id"]), values=(
                i, t["title"][:40], t["org"], t["type"],
                f"{t['search_volume']:,}", t["competition"], pub_mark
            ))

    def _sort_by(self, col):
        key_map = {"검색량": "search_volume", "경쟁": "competition",
                   "기관": "org", "#": "priority"}
        key = key_map.get(col, "priority")
        self.filtered.sort(key=lambda x: x.get(key, 0), reverse=True)
        self._populate_tree()

    # ── 더블클릭 상세 팝업 ────────────────────────────────────
    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        topic_id = int(sel[0])
        topic = next((t for t in self.topics if t["id"] == topic_id), None)
        if topic:
            self._show_detail(topic)

    def _show_detail(self, topic: dict):
        win = tk.Toplevel(self)
        win.title(f"주제 상세 — {topic['org']}")
        win.geometry("500x560")
        win.resizable(False, False)

        ttk.Label(win, text=f"[{topic['org']}]", font=("", 11, "bold")).pack(padx=20, pady=(16, 4))
        ttk.Label(win, text=topic["title"], font=("", 10), wraplength=460).pack(padx=20)
        ttk.Separator(win).pack(fill=X, padx=20, pady=8)

        info = f"유형: {topic['type']}  |  자금: {topic.get('fund_type', '')}  |  카테고리: {topic['category']}"
        ttk.Label(win, text=info).pack(padx=20)

        ttk.Separator(win).pack(fill=X, padx=20, pady=8)
        ttk.Label(win, text="SEO 키워드 후보", font=("", 9, "bold")).pack(padx=20, anchor=W)
        kw_frame = ttk.Frame(win)
        kw_frame.pack(fill=X, padx=20)
        for kw in topic.get("keywords", [])[:8]:
            lbl = ttk.Label(kw_frame, text=kw, relief="solid",
                            padding=(6, 2), font=("", 9))
            lbl.pack(side=LEFT, padx=2, pady=2)

        ttk.Separator(win).pack(fill=X, padx=20, pady=8)
        ttk.Label(win, text="블로그 제목 후보", font=("", 9, "bold")).pack(padx=20, anchor=W)
        for idx, tc in enumerate(topic.get("title_candidates", []), 1):
            lbl = ttk.Label(win, text=f"{idx}. {tc}", wraplength=460, cursor="hand2", foreground="white")
            lbl.pack(padx=20, anchor=W)
            lbl.bind("<Button-1>", lambda e, t=tc: self._copy_to_clipboard(t))

        ttk.Separator(win).pack(fill=X, padx=20, pady=8)
        btn_frame = ttk.Frame(win)
        btn_frame.pack(padx=20, pady=8)

        def mark_published():
            self._toggle_published(topic)
            win.destroy()
            self.refresh()

        tbs.Button(btn_frame, text="발행 완료 표시", bootstyle="success-outline",
                   command=mark_published).pack(side=LEFT, padx=6)

        if self.switch_to_content_tab:
            def go_content():
                self.switch_to_content_tab(topic)
                win.destroy()
            tbs.Button(btn_frame, text="콘텐츠 생성 →", bootstyle="primary",
                       command=go_content).pack(side=LEFT, padx=6)

        tbs.Button(btn_frame, text="닫기", bootstyle="secondary-outline",
                   command=win.destroy).pack(side=LEFT, padx=6)

    def _toggle_published(self, topic: dict):
        published_ids = load_json(PUBLISHED_PATH) or []
        if topic["id"] not in published_ids:
            published_ids.append(topic["id"])
            save_json(PUBLISHED_PATH, published_ids)

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("복사 완료", f"클립보드에 복사됐어요:\n{text[:60]}", parent=self)
