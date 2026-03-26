"""탭 1: 지식 베이스 — 기관별 정책자금 데이터 관리"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import ttkbootstrap as tbs
from ttkbootstrap.constants import *

from modules.utils import load_json, save_json
import os

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")

ORG_KEYS = ["중진공", "소진공", "기보", "신보", "신용보증재단", "무역보험공사", "농신보"]


class KnowledgeBaseTab(tk.Frame):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self.kb: dict = {}
        self.current_key = None
        self._fund_rows: list = []       # 자금별 상세 행 위젯 목록
        self._build_ui()
        self._load_kb()

    # ── UI 뼈대 ───────────────────────────────────────────────
    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=8, pady=8)

        # 좌측 트리 + 버튼
        left = ttk.Frame(paned, width=210)
        paned.add(left, weight=0)

        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(left, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill=X, pady=4)
        tbs.Button(btn_f, text="텍스트 가져오기", bootstyle="secondary-outline",
                   command=self._import_text).pack(fill=X, padx=4, pady=2)
        tbs.Button(btn_f, text="JSON 복사 (클립보드)", bootstyle="secondary-outline",
                   command=self._copy_json_clipboard).pack(fill=X, padx=4, pady=2)
        tbs.Button(btn_f, text="JSON 파일 저장", bootstyle="secondary-outline",
                   command=self._export_json).pack(fill=X, padx=4, pady=2)

        # 우측 편집 영역
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        header_row = ttk.Frame(right)
        header_row.pack(fill=X, padx=12, pady=(10, 0))
        self.title_lbl = ttk.Label(header_row, text="기관을 선택하세요", font=("", 13, "bold"))
        self.title_lbl.pack(side=LEFT)
        tbs.Button(header_row, text="저장", bootstyle="primary",
                   command=self._save_current).pack(side=RIGHT)

        # 스크롤 가능 편집 캔버스
        canvas = tk.Canvas(right, bd=0, highlightthickness=0)
        vsb2 = ttk.Scrollbar(right, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.edit_frame = ttk.Frame(canvas)
        self._canvas = canvas
        self._eid = canvas.create_window((0, 0), window=self.edit_frame, anchor=NW)
        self.edit_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._eid, width=e.width))
        # 마우스 휠 스크롤
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self.fields: dict[str, tk.Widget] = {}

    # ── 트리 구성 ──────────────────────────────────────────────
    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        org_node = self.tree.insert("", END, text="▼ 기관", open=True)
        for k in ORG_KEYS:
            filled = "●" if k in self.kb and self.kb[k].get("정식명칭") else "○"
            self.tree.insert(org_node, END, iid=f"org:{k}", text=f" {filled} {k}")
        cert_node = self.tree.insert("", END, text="▼ 기업인증", open=True)
        cert_data = self.kb.get("기업인증", {})
        for k in cert_data:
            self.tree.insert(cert_node, END, iid=f"cert:{k}", text=f" ● {k}")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        if item_id.startswith("org:"):
            key = item_id[4:]
            self.current_key = ("org", key)
            self._render_org_fields(key)
        elif item_id.startswith("cert:"):
            key = item_id[5:]
            self.current_key = ("cert", key)
            self._render_cert_fields(key)

    # ── 공통 필드 헬퍼 ─────────────────────────────────────────
    def _clear_edit_frame(self):
        for w in self.edit_frame.winfo_children():
            w.destroy()
        self.fields = {}
        self._fund_rows = []

    def _add_field(self, parent, label: str, key: str, value: str = "",
                   multiline: bool = False, height: int = 3):
        row = ttk.Frame(parent)
        row.pack(fill=X, padx=0, pady=2)
        ttk.Label(row, text=label, width=13, anchor=E).pack(side=LEFT)
        if multiline:
            txt = tk.Text(row, height=height, wrap=WORD, font=("", 10))
            txt.insert("1.0", value)
            sb = ttk.Scrollbar(row, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            txt.pack(side=LEFT, fill=BOTH, expand=True)
            sb.pack(side=LEFT, fill=Y)
            self.fields[key] = txt
        else:
            var = tk.StringVar(value=value)
            ttk.Entry(row, textvariable=var).pack(side=LEFT, fill=X, expand=True)
            self.fields[key] = var

    def _get_val(self, key: str) -> str:
        w = self.fields.get(key)
        if isinstance(w, tk.StringVar):
            return w.get().strip()
        if isinstance(w, tk.Text):
            return w.get("1.0", END).strip()
        return ""

    def _section(self, text: str) -> ttk.Frame:
        """구분선 + 섹션 제목 + 내용 프레임 반환"""
        ttk.Separator(self.edit_frame).pack(fill=X, padx=8, pady=(8, 4))
        ttk.Label(self.edit_frame, text=text, font=("", 9, "bold")).pack(anchor=W, padx=12)
        f = ttk.Frame(self.edit_frame)
        f.pack(fill=X, padx=12, pady=4)
        return f

    # ── 기관 필드 렌더링 ────────────────────────────────────────
    def _render_org_fields(self, org_key: str):
        self._clear_edit_frame()
        data = self.kb.get(org_key, {})
        self.title_lbl.config(text=f"[{org_key}]  {data.get('정식명칭', '')}")

        # ── 기본 정보 ──
        basic = self._section("기본 정보")
        for lbl, k, default in [
            ("정식명칭",    "정식명칭",       data.get("정식명칭", "")),
            ("약칭",        "약칭",           data.get("약칭", "")),
            ("대상",        "대상",           data.get("대상", "")),
            ("홈페이지",    "홈페이지",       data.get("홈페이지", "")),
            ("융자한도",    "융자한도",       data.get("융자한도") or data.get("보증한도_최고", "")),
            ("우대금리 최대","우대금리_최대", data.get("우대금리_최대", "")),
        ]:
            self._add_field(basic, lbl, k, default)

        self._add_field(basic, "금리구조", "금리구조", data.get("금리구조", ""),
                        multiline=True, height=3)
        self._add_field(basic, "융자절차", "융자절차", data.get("융자절차", ""),
                        multiline=True, height=3)
        self._add_field(basic, "특징",     "특징",     data.get("특징", ""),
                        multiline=True, height=3)

        # ── 우대금리 항목 ──
        prefer_sec = self._section("우대금리 항목 (한 줄: 유형|대상|감면)")
        prefer_items = data.get("우대금리_항목", [])
        prefer_text = "\n".join(
            f"{r.get('유형','')}|{r.get('대상','')}|{r.get('감면','')}"
            for r in prefer_items
        )
        self._add_field(prefer_sec, "우대금리", "우대금리_항목", prefer_text,
                        multiline=True, height=4)

        # ── 자금별 상세 ──
        fund_sec = self._section("자금별 상세")
        fund_data = data.get("자금별", {})
        self._render_fund_section(fund_sec, fund_data)

        # ── 융자 제한 ──
        restrict_sec = self._section("융자 제한 사항 (한 줄에 하나)")
        restrict_text = "\n".join(data.get("융자제한_핵심", []))
        self._add_field(restrict_sec, "제한사항", "융자제한_핵심", restrict_text,
                        multiline=True, height=5)

    def _render_fund_section(self, parent: ttk.Frame, fund_data: dict):
        """자금별 상세 편집 위젯 (동적 추가/삭제 지원)"""
        self._fund_rows = []

        container = ttk.Frame(parent)
        container.pack(fill=X)

        def add_fund_row(name: str = "", row_data: dict = None):
            row_data = row_data or {}
            frame = ttk.LabelFrame(container, text=f" 자금 종류 ")
            frame.pack(fill=X, padx=4, pady=4)

            # 자금명
            name_row = ttk.Frame(frame)
            name_row.pack(fill=X, padx=8, pady=3)
            ttk.Label(name_row, text="자금명:", width=8, anchor=E).pack(side=LEFT)
            name_var = tk.StringVar(value=name)
            ttk.Entry(name_row, textvariable=name_var, width=30).pack(side=LEFT, padx=4)

            def remove():
                self._fund_rows.remove(entry)
                frame.destroy()

            tbs.Button(name_row, text="삭제", bootstyle="danger-outline",
                       width=4, command=remove).pack(side=RIGHT, padx=4)

            # 세부 필드
            detail_frame = ttk.Frame(frame)
            detail_frame.pack(fill=X, padx=8, pady=(0, 6))
            sub_vars = {}
            for col_lbl, col_key in [
                ("대상", "대상"), ("한도", "한도"), ("금리", "금리"),
                ("기간", "기간"), ("방식", "방식"), ("특이사항", "특이사항"),
            ]:
                r = ttk.Frame(detail_frame)
                r.pack(fill=X, pady=1)
                ttk.Label(r, text=f"{col_lbl}:", width=8, anchor=E).pack(side=LEFT)
                v = tk.StringVar(value=row_data.get(col_key, ""))
                ttk.Entry(r, textvariable=v).pack(side=LEFT, fill=X, expand=True)
                sub_vars[col_key] = v

            entry = {"name_var": name_var, "vars": sub_vars, "frame": frame}
            self._fund_rows.append(entry)
            frame.configure(text=f" {name or '새 자금'} ")
            name_var.trace_add("write",
                               lambda *_, nv=name_var, fr=frame: fr.configure(text=f" {nv.get() or '새 자금'} "))

        # 기존 자금 데이터 로드
        for fname, fdata in fund_data.items():
            add_fund_row(fname, fdata)

        # 추가 버튼
        tbs.Button(container, text="+ 자금 종류 추가", bootstyle="success-outline",
                   command=lambda: add_fund_row()).pack(anchor=W, padx=4, pady=4)

    # ── 기업인증 필드 렌더링 ────────────────────────────────────
    def _render_cert_fields(self, cert_key: str):
        self._clear_edit_frame()
        data = self.kb.get("기업인증", {}).get(cert_key, {})
        self.title_lbl.config(text=f"[기업인증]  {cert_key}")

        basic = self._section("인증 정보")
        for lbl, k in [
            ("취득조건", "취득조건"), ("소요기간", "소요기간"),
            ("비용", "비용"), ("자금연계", "정책자금_연계"), ("주의사항", "주의사항"),
        ]:
            self._add_field(basic, lbl, k, data.get(k, ""))

    # ── 저장 ───────────────────────────────────────────────────
    def _save_current(self):
        if not self.current_key:
            messagebox.showwarning("미선택", "저장할 항목을 선택하세요.", parent=self)
            return
        kind, key = self.current_key

        if kind == "org":
            if key not in self.kb:
                self.kb[key] = {}
            for fk in ["정식명칭", "약칭", "대상", "홈페이지", "융자한도",
                        "우대금리_최대", "금리구조", "융자절차", "특징"]:
                self.kb[key][fk] = self._get_val(fk)

            # 우대금리 항목 파싱
            raw_prefer = self._get_val("우대금리_항목")
            items = []
            for line in raw_prefer.split("\n"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) == 3 and any(parts):
                    items.append({"유형": parts[0], "대상": parts[1], "감면": parts[2]})
            self.kb[key]["우대금리_항목"] = items

            # 자금별 상세
            fund_dict = {}
            for row in self._fund_rows:
                fname = row["name_var"].get().strip()
                if fname:
                    fund_dict[fname] = {k: v.get().strip() for k, v in row["vars"].items()}
            self.kb[key]["자금별"] = fund_dict

            # 융자 제한
            raw_restrict = self._get_val("융자제한_핵심")
            self.kb[key]["융자제한_핵심"] = [l.strip() for l in raw_restrict.split("\n") if l.strip()]

        elif kind == "cert":
            if "기업인증" not in self.kb:
                self.kb["기업인증"] = {}
            if key not in self.kb["기업인증"]:
                self.kb["기업인증"][key] = {}
            for fk in ["취득조건", "소요기간", "비용", "정책자금_연계", "주의사항"]:
                self.kb["기업인증"][key][fk] = self._get_val(fk)

        save_json(KB_PATH, self.kb)
        self._populate_tree()
        messagebox.showinfo("저장 완료", f"[{key}] 데이터가 저장됐어요.", parent=self)

    # ── 텍스트 가져오기 (개선) ──────────────────────────────────
    def _import_text(self):
        if not self.current_key:
            messagebox.showwarning("미선택", "먼저 기관/인증을 선택하세요.", parent=self)
            return
        kind, key = self.current_key

        win = tk.Toplevel(self)
        win.title(f"텍스트 가져오기 — {key}")
        win.geometry("600x500")

        ttk.Label(win,
                  text="공문/안내서 텍스트를 붙여넣으세요.\n"
                       "자동으로 주요 필드를 파싱하거나, 전체를 참고용(_imported)으로 저장합니다.",
                  justify=LEFT).pack(padx=12, pady=(10, 4), anchor=W)

        txt = tk.Text(win, wrap=WORD, font=("", 10))
        sb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt_frame = ttk.Frame(win)
        txt_frame.pack(fill=BOTH, expand=True, padx=12, pady=4)
        txt.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)

        btn_row = ttk.Frame(win)
        btn_row.pack(padx=12, pady=6)

        def do_import_raw():
            raw = txt.get("1.0", END).strip()
            if not raw:
                return
            if kind == "org":
                if key not in self.kb:
                    self.kb[key] = {}
                self.kb[key]["_imported"] = raw
            elif kind == "cert":
                if "기업인증" not in self.kb:
                    self.kb["기업인증"] = {}
                if key not in self.kb["기업인증"]:
                    self.kb["기업인증"][key] = {}
                self.kb["기업인증"][key]["_imported"] = raw
            save_json(KB_PATH, self.kb)
            messagebox.showinfo("완료", "참고용(_imported)으로 저장됐어요.", parent=win)
            win.destroy()

        def do_import_parse():
            """텍스트에서 키 패턴 자동 파싱 후 필드 업데이트"""
            raw = txt.get("1.0", END).strip()
            if not raw:
                return
            parsed = _parse_policy_text(raw)
            if kind == "org":
                if key not in self.kb:
                    self.kb[key] = {}
                for fk, fv in parsed.items():
                    if fv:
                        self.kb[key][fk] = fv
                self.kb[key]["_imported"] = raw
            save_json(KB_PATH, self.kb)
            # 현재 화면 갱신
            self._render_org_fields(key)
            messagebox.showinfo("파싱 완료", f"{len(parsed)}개 필드를 파싱했어요.\n화면이 업데이트됐습니다.", parent=win)
            win.destroy()

        tbs.Button(btn_row, text="자동 파싱 후 저장", bootstyle="primary",
                   command=do_import_parse).pack(side=LEFT, padx=6)
        tbs.Button(btn_row, text="참고용으로만 저장", bootstyle="secondary-outline",
                   command=do_import_raw).pack(side=LEFT, padx=6)
        tbs.Button(btn_row, text="취소", bootstyle="light-outline",
                   command=win.destroy).pack(side=LEFT, padx=6)

    # ── JSON 클립보드 복사 ──────────────────────────────────────
    def _copy_json_clipboard(self):
        import subprocess, sys
        text = json.dumps(self.kb, ensure_ascii=False, indent=2)
        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True, creationflags=0x08000000)
            else:
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        except Exception as e:
            messagebox.showerror("복사 실패", str(e), parent=self)
            return
        messagebox.showinfo("복사 완료", "knowledge_base.json 전체가 클립보드에 복사됐어요.", parent=self)

    # ── JSON 파일 저장 ──────────────────────────────────────────
    def _export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="knowledge_base_export.json", parent=self
        )
        if path:
            save_json(path, self.kb)
            messagebox.showinfo("저장 완료", f"파일로 저장됐어요:\n{path}", parent=self)

    def _load_kb(self):
        self.kb = load_json(KB_PATH) or {}
        self._populate_tree()


# ── 텍스트 자동 파싱 헬퍼 ──────────────────────────────────────
def _parse_policy_text(text: str) -> dict:
    """
    공문/안내서 텍스트에서 주요 필드 자동 추출.
    키워드 기반 휴리스틱 파싱.
    """
    import re
    result = {}
    lines = text.split("\n")

    patterns = {
        "대상":         [r"대상\s*[:：]\s*(.+)", r"지원대상\s*[:：]\s*(.+)"],
        "융자한도":     [r"융자한도\s*[:：]\s*(.+)", r"보증한도\s*[:：]\s*(.+)", r"한도\s*[:：]\s*(.+)"],
        "금리구조":     [r"금리\s*[:：]\s*(.+)", r"이자율\s*[:：]\s*(.+)"],
        "우대금리_최대":[r"우대\s*최대\s*[:：]\s*(.+)", r"우대금리.*최대\s*[:：]\s*(.+)"],
        "홈페이지":     [r"홈페이지\s*[:：]\s*(.+)", r"www\.[^\s]+"],
        "대출기간":     [r"대출기간\s*[:：]\s*(.+)", r"기간\s*[:：]\s*(.+)"],
    }

    for key, pats in patterns.items():
        for pat in pats:
            for line in lines:
                m = re.search(pat, line)
                if m:
                    result[key] = m.group(1).strip() if m.lastindex else m.group(0).strip()
                    break
            if key in result:
                break

    # 융자 제한 — "제한" 키워드 이후 줄 수집
    restrict = []
    in_restrict = False
    for line in lines:
        if any(w in line for w in ["융자제한", "지원제외", "취급제외"]):
            in_restrict = True
            continue
        if in_restrict:
            stripped = line.strip()
            if stripped and len(stripped) > 5:
                restrict.append(stripped.lstrip("·-•◦○●▶→"))
            if not stripped:
                in_restrict = False
    if restrict:
        result["융자제한_핵심"] = restrict

    return result
