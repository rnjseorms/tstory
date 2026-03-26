"""BK 콘텐츠 허브 — 부광솔루션즈 진입점"""
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tbs
from ttkbootstrap.constants import *
import os
import sys

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from modules.utils import load_json, save_json
from modules import db_manager
from tabs.tab_topic_mix import TopicMixTab
from tabs.tab_knowledge_base import KnowledgeBaseTab
from tabs.tab_content_generator import ContentGeneratorTab
from tabs.tab_publish_manager import PublishManagerTab
from tabs.tab_settings import SettingsTab

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "config", "settings.json")


class BKContentHub(tbs.Window):
    def __init__(self):
        super().__init__(
            title="BK 콘텐츠 허브 — 부광솔루션즈",
            themename="darkly",
            size=(1280, 800),
            minsize=(1024, 700),
        )
        self.resizable(True, True)
        self.settings = load_json(SETTINGS_PATH) or {}
        db_manager.init_db()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # 메뉴바
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="새로고침 (F5)", command=self._refresh_all)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self._on_close)
        menubar.add_cascade(label="파일", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="정보", command=self._show_about)
        menubar.add_cascade(label="도움말", menu=help_menu)
        self.config(menu=menubar)

        # 헤더
        header = ttk.Frame(self)
        header.pack(fill=X, padx=0, pady=0)
        tbs.Label(
            header,
            text="  BK 콘텐츠 허브",
            font=("", 14, "bold"),
            bootstyle="inverse-dark",
        ).pack(side=LEFT, padx=10, pady=8)
        tbs.Label(
            header,
            text="부광솔루션즈 | 권대근 대표",
            font=("", 10),
            bootstyle="inverse-dark",
        ).pack(side=RIGHT, padx=16, pady=8)

        ttk.Separator(self).pack(fill=X)

        # 탭 Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True, padx=0, pady=0)

        # 탭 0: 주제 Mix
        self.tab_topic = TopicMixTab(
            self.notebook,
            self.settings,
            switch_to_content_tab=self._switch_to_content,
        )
        self.notebook.add(self.tab_topic, text="  주제 Mix  ")

        # 탭 1: 지식 베이스
        self.tab_kb = KnowledgeBaseTab(self.notebook, self.settings)
        self.notebook.add(self.tab_kb, text="  지식 베이스  ")

        # 탭 2: 콘텐츠 생성기
        self.tab_content = ContentGeneratorTab(self.notebook, self.settings)
        self.notebook.add(self.tab_content, text="  콘텐츠 생성기  ")

        # 탭 3: 발행 관리
        self.tab_publish = PublishManagerTab(self.notebook, self.settings)
        self.notebook.add(self.tab_publish, text="  발행 관리  ")

        # 탭 4: 설정
        self.tab_settings = SettingsTab(self.notebook, self.settings)
        self.notebook.add(self.tab_settings, text="  설정  ")

        # 키 바인딩
        self.bind("<F5>", lambda e: self._refresh_all())
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # 상태바
        statusbar = ttk.Frame(self)
        statusbar.pack(fill=X, side=BOTTOM)
        ttk.Separator(statusbar).pack(fill=X)
        self.status_lbl = ttk.Label(statusbar, text="준비", font=("", 9))
        self.status_lbl.pack(side=LEFT, padx=10, pady=3)

    def _switch_to_content(self, topic: dict):
        """주제 Mix 탭에서 콘텐츠 생성기 탭으로 전환 + 주제 자동 설정"""
        self.tab_content.set_topic(topic)
        self.notebook.select(2)

    def _on_tab_changed(self, event):
        tab_idx = self.notebook.index(self.notebook.select())
        names = ["주제 Mix", "지식 베이스", "콘텐츠 생성기", "발행 관리", "설정"]
        if tab_idx < len(names):
            self.status_lbl.config(text=f"현재 탭: {names[tab_idx]}")
        # 발행 관리 탭 진입 시 자동 새로고침
        if tab_idx == 3:
            self.tab_publish.refresh()

    def _refresh_all(self):
        self.tab_topic.refresh()
        self.tab_publish.refresh()
        self.status_lbl.config(text="새로고침 완료")

    def _on_close(self):
        save_json(SETTINGS_PATH, self.settings)
        self.destroy()

    def _show_about(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "BK 콘텐츠 허브",
            "버전: 1.0 (Phase 0)\n"
            "부광솔루션즈 정책자금 콘텐츠 반자동 생성 도구\n\n"
            "개발: Claude Code (Anthropic)\n"
            "사용자: 권대근 대표",
            parent=self,
        )


if __name__ == "__main__":
    app = BKContentHub()
    app.mainloop()
