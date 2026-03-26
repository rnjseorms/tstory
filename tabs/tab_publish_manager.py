"""탭 3: 발행 관리 — 발행 기록 조회 및 통계"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import webbrowser
import csv
from datetime import date, timedelta
import ttkbootstrap as tbs
from ttkbootstrap.constants import *
from modules import db_manager
from modules.topic_mixer import ORGS


class PublishManagerTab(tk.Frame):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self.records = []
        self._sort_col = "publish_date"
        self._sort_rev = True
        db_manager.init_db()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # ── 통계 카드 ────────────────────────────────────────
        stat_frame = ttk.Frame(self)
        stat_frame.pack(fill=X, padx=10, pady=(10, 4))
        self.stat_labels = {}
        for key, text, style in [
            ("total", "총 발행: 0", "info"),
            ("week", "이번 주: 0", "success"),
            ("month", "이번 달: 0", "primary"),
            ("today", "오늘: 0", "warning"),
        ]:
            lbl = tbs.Label(stat_frame, text=text, bootstyle=style, font=("", 12, "bold"))
            lbl.pack(side=LEFT, padx=18)
            self.stat_labels[key] = lbl

        # ── 필터 ─────────────────────────────────────────────
        filter_frame = ttk.LabelFrame(self, text=" 필터 ")
        filter_frame.pack(fill=X, padx=10, pady=4)
        fr = ttk.Frame(filter_frame)
        fr.pack(fill=X, padx=8, pady=6)

        ttk.Label(fr, text="기관:").pack(side=LEFT)
        self.org_var = tk.StringVar(value="전체")
        ttk.Combobox(fr, textvariable=self.org_var, state="readonly",
                     values=["전체"] + [o["name"] for o in ORGS], width=10).pack(side=LEFT, padx=(2, 8))

        ttk.Label(fr, text="상태:").pack(side=LEFT)
        self.status_var = tk.StringVar(value="전체")
        ttk.Combobox(fr, textvariable=self.status_var, state="readonly",
                     values=["전체", "success", "pending", "failed"], width=10).pack(side=LEFT, padx=(2, 8))

        ttk.Label(fr, text="기간:").pack(side=LEFT)
        self.date_from_var = tk.StringVar(value=date.today().replace(day=1).isoformat())
        ttk.Entry(fr, textvariable=self.date_from_var, width=11).pack(side=LEFT, padx=(2, 2))
        ttk.Label(fr, text="~").pack(side=LEFT)
        self.date_to_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(fr, textvariable=self.date_to_var, width=11).pack(side=LEFT, padx=(2, 8))

        # 빠른 기간 버튼
        for lbl, days in [("오늘", 0), ("7일", 7), ("30일", 30), ("전체", -1)]:
            tbs.Button(fr, text=lbl, bootstyle="light-outline", width=4,
                       command=lambda d=days: self._quick_date(d)).pack(side=LEFT, padx=2)

        tbs.Button(fr, text="조회", bootstyle="primary", command=self.refresh).pack(side=LEFT, padx=8)

        # ── 테이블 ────────────────────────────────────────────
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=4)

        cols = ("발행일", "기관", "키워드", "제목", "검색량", "블로그", "인스타", "비고")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        widths = [85, 70, 130, 240, 70, 52, 52, 90]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=CENTER if w < 120 else W)
        self.tree.column("제목", anchor=W)
        self.tree.column("키워드", anchor=W)

        vsb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", lambda e: self._delete_selected())

        # ── 하단 버튼 ─────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=X, padx=10, pady=6)

        tbs.Button(btn_frame, text="블로그 열기", bootstyle="info-outline",
                   command=self._open_url).pack(side=LEFT, padx=4)
        tbs.Button(btn_frame, text="블로그 URL 입력", bootstyle="secondary-outline",
                   command=self._set_blog_url).pack(side=LEFT, padx=4)
        tbs.Button(btn_frame, text="상태 변경", bootstyle="warning-outline",
                   command=self._change_status).pack(side=LEFT, padx=4)
        tbs.Button(btn_frame, text="선택 삭제", bootstyle="danger-outline",
                   command=self._delete_selected).pack(side=LEFT, padx=4)

        tbs.Button(btn_frame, text="CSV 내보내기", bootstyle="secondary-outline",
                   command=self._export_csv).pack(side=RIGHT, padx=4)
        tbs.Button(btn_frame, text="새로고침", bootstyle="light-outline",
                   command=self.refresh).pack(side=RIGHT, padx=4)

        # ── 주간 현황 바 ──────────────────────────────────────
        self.weekly_frame = ttk.LabelFrame(self, text=" 최근 7일 발행 현황 ")
        self.weekly_frame.pack(fill=X, padx=10, pady=(0, 6))
        self.weekly_canvas = tk.Canvas(self.weekly_frame, height=56, bg="#1a1a2e", highlightthickness=0)
        self.weekly_canvas.pack(fill=X, padx=6, pady=6)

    def _quick_date(self, days: int):
        today = date.today()
        if days == 0:
            self.date_from_var.set(today.isoformat())
            self.date_to_var.set(today.isoformat())
        elif days > 0:
            self.date_from_var.set((today - timedelta(days=days)).isoformat())
            self.date_to_var.set(today.isoformat())
        else:  # 전체
            self.date_from_var.set("2024-01-01")
            self.date_to_var.set("2099-12-31")
        self.refresh()

    def refresh(self):
        org_f = self.org_var.get() if hasattr(self, "org_var") else "전체"
        df = self.date_from_var.get() if hasattr(self, "date_from_var") else None
        dt = self.date_to_var.get() if hasattr(self, "date_to_var") else None
        status_f = self.status_var.get() if hasattr(self, "status_var") else "전체"

        self.records = db_manager.fetch_all(
            org_filter=org_f,
            date_from=df,
            date_to=dt,
        )
        # 상태 필터 (DB 쿼리 확장 대신 메모리 필터)
        if status_f != "전체":
            self.records = [r for r in self.records if r.get("blog_status") == status_f]

        self._populate_tree()
        self._update_stats()
        self._draw_weekly_chart()

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        status_map = {"success": "✅", "failed": "❌", "pending": "⏳"}
        for r in self.records:
            blog_s = status_map.get(r.get("blog_status", ""), "⏳")
            insta_s = status_map.get(r.get("insta_status", ""), "⏳")
            self.tree.insert("", END, iid=str(r["id"]), values=(
                r.get("publish_date", ""),
                r.get("org", ""),
                (r.get("keyword", "") or "")[:20],
                (r.get("title", "") or "")[:32],
                f"{r.get('search_volume') or 0:,}",
                blog_s, insta_s,
                r.get("memo", ""),
            ))

    def _update_stats(self):
        today_str = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        month_start = date.today().replace(day=1).isoformat()

        all_records = db_manager.fetch_all()  # 필터 없이 전체 카운트
        total = len(all_records)
        week = sum(1 for r in all_records if r.get("publish_date", "") >= week_ago)
        month = sum(1 for r in all_records if r.get("publish_date", "") >= month_start)
        today = sum(1 for r in all_records if r.get("publish_date", "") == today_str)
        self.stat_labels["total"].config(text=f"총 발행: {total}")
        self.stat_labels["week"].config(text=f"이번 주: {week}")
        self.stat_labels["month"].config(text=f"이번 달: {month}")
        self.stat_labels["today"].config(text=f"오늘: {today}")

    def _draw_weekly_chart(self):
        """최근 7일 발행 수 막대 차트"""
        canvas = self.weekly_canvas
        canvas.delete("all")
        canvas.update_idletasks()
        W = canvas.winfo_width() or 700
        H = 56

        days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        all_records = db_manager.fetch_all()
        counts = {d: sum(1 for r in all_records if r.get("publish_date") == d) for d in days}
        max_count = max(counts.values()) if counts else 1
        if max_count == 0:
            max_count = 1

        bar_w = W // 8
        pad = 4
        colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#00BCD4", "#8BC34A"]
        today_str = date.today().isoformat()

        for i, d in enumerate(days):
            x0 = pad + i * bar_w + bar_w // 8
            bar_height = int((counts[d] / max_count) * (H - 24))
            y1 = H - 18
            y0 = y1 - max(bar_height, 2)
            color = "#F97316" if d == today_str else colors[i % len(colors)]
            canvas.create_rectangle(x0, y0, x0 + bar_w * 3 // 4, y1, fill=color, outline="")
            label = d[5:]  # MM-DD
            canvas.create_text(x0 + bar_w * 3 // 8, H - 8, text=label,
                                fill="#aaa", font=("", 8))
            if counts[d] > 0:
                canvas.create_text(x0 + bar_w * 3 // 8, y0 - 6, text=str(counts[d]),
                                   fill="white", font=("", 9, "bold"))

    def _sort_by(self, col):
        col_map = {
            "발행일": "publish_date", "기관": "org",
            "검색량": "search_volume", "제목": "title", "키워드": "keyword"
        }
        key = col_map.get(col, "publish_date")
        if self._sort_col == key:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = key
            self._sort_rev = True
        self.records.sort(key=lambda x: (x.get(key) or ""), reverse=self._sort_rev)
        self._populate_tree()

    def _selected_record(self):
        sel = self.tree.selection()
        if not sel:
            return None
        rec_id = int(sel[0])
        return next((r for r in self.records if r["id"] == rec_id), None)

    def _on_double_click(self, event):
        rec = self._selected_record()
        if not rec:
            return
        self._open_edit_popup(rec)

    def _open_edit_popup(self, rec: dict):
        win = tk.Toplevel(self)
        win.title("발행 기록 편집")
        win.geometry("460x280")
        win.resizable(False, False)

        ttk.Label(win, text=f"제목: {(rec.get('title',''))[:40]}",
                  font=("", 10, "bold")).pack(padx=16, pady=(12, 4), anchor=W)
        ttk.Label(win, text=f"키워드: {rec.get('keyword','')} | 기관: {rec.get('org','')} | 날짜: {rec.get('publish_date','')}",
                  font=("", 9), foreground="gray").pack(padx=16, pady=(0, 8), anchor=W)

        fields_frame = ttk.Frame(win)
        fields_frame.pack(fill=X, padx=16)

        # 블로그 URL
        ttk.Label(fields_frame, text="블로그 URL:", width=12, anchor=E).grid(row=0, column=0, pady=4, sticky=E)
        url_var = tk.StringVar(value=rec.get("blog_url", ""))
        ttk.Entry(fields_frame, textvariable=url_var, width=42).grid(row=0, column=1, padx=4, pady=4)

        # 블로그 상태
        ttk.Label(fields_frame, text="블로그 상태:", width=12, anchor=E).grid(row=1, column=0, pady=4, sticky=E)
        blog_status_var = tk.StringVar(value=rec.get("blog_status", "pending"))
        ttk.Combobox(fields_frame, textvariable=blog_status_var, state="readonly",
                     values=["success", "pending", "failed"], width=12).grid(row=1, column=1, padx=4, pady=4, sticky=W)

        # 인스타 상태
        ttk.Label(fields_frame, text="인스타 상태:", width=12, anchor=E).grid(row=2, column=0, pady=4, sticky=E)
        insta_status_var = tk.StringVar(value=rec.get("insta_status", "pending"))
        ttk.Combobox(fields_frame, textvariable=insta_status_var, state="readonly",
                     values=["success", "pending", "failed"], width=12).grid(row=2, column=1, padx=4, pady=4, sticky=W)

        # 비고
        ttk.Label(fields_frame, text="비고:", width=12, anchor=E).grid(row=3, column=0, pady=4, sticky=E)
        memo_var = tk.StringVar(value=rec.get("memo", ""))
        ttk.Entry(fields_frame, textvariable=memo_var, width=42).grid(row=3, column=1, padx=4, pady=4)

        btn_row = ttk.Frame(win)
        btn_row.pack(fill=X, padx=16, pady=12)

        def save():
            db_manager.update_status(
                rec["id"],
                blog_status=blog_status_var.get(),
                insta_status=insta_status_var.get(),
                blog_url=url_var.get().strip()
            )
            db_manager.update_memo(rec["id"], memo_var.get())
            self.refresh()
            win.destroy()

        def open_blog():
            url = url_var.get().strip()
            if url:
                webbrowser.open(url)

        tbs.Button(btn_row, text="블로그 열기", bootstyle="info-outline", command=open_blog).pack(side=LEFT)
        tbs.Button(btn_row, text="저장", bootstyle="primary", command=save).pack(side=RIGHT)
        tbs.Button(btn_row, text="취소", bootstyle="secondary-outline",
                   command=win.destroy).pack(side=RIGHT, padx=6)

    def _open_url(self):
        rec = self._selected_record()
        if rec and rec.get("blog_url"):
            webbrowser.open(rec["blog_url"])
        else:
            messagebox.showinfo("URL 없음", "블로그 URL이 없어요. 더블클릭 → URL 입력 후 저장하세요.", parent=self)

    def _set_blog_url(self):
        rec = self._selected_record()
        if not rec:
            messagebox.showwarning("선택 필요", "수정할 항목을 먼저 선택하세요.", parent=self)
            return
        url = simpledialog.askstring(
            "블로그 URL 입력",
            f"제목: {rec.get('title','')[:30]}\n\n블로그 URL:",
            initialvalue=rec.get("blog_url", ""),
            parent=self
        )
        if url is not None:
            db_manager.update_status(rec["id"], blog_url=url.strip())
            if url.strip():
                db_manager.update_status(rec["id"], blog_status="success")
            self.refresh()

    def _change_status(self):
        rec = self._selected_record()
        if not rec:
            messagebox.showwarning("선택 필요", "수정할 항목을 먼저 선택하세요.", parent=self)
            return
        self._open_edit_popup(rec)

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno(
            "삭제 확인", f"선택한 {len(sel)}개 기록을 삭제하시겠어요? 복구 불가.", parent=self
        ):
            return
        with db_manager.get_conn() as conn:
            for iid in sel:
                conn.execute("DELETE FROM publish_history WHERE id = ?", (int(iid),))
            conn.commit()
        self.refresh()

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"publish_history_{date.today().isoformat()}.csv",
            parent=self
        )
        if not path:
            return
        fields = ["id", "publish_date", "org", "keyword", "title",
                  "search_volume", "blog_url", "blog_status", "insta_status",
                  "landing_url", "category", "memo"]
        records = db_manager.fetch_all()  # 전체 내보내기
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        messagebox.showinfo("내보내기 완료", f"저장됐어요:\n{path}", parent=self)
