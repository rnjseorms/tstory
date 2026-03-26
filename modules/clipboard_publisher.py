"""
클립보드 발행 모듈
티스토리 Open API 종료(2024.02)로 인해 수동 붙여넣기 방식으로 변경.
HTML 생성 → 클립보드 복사 → 대근님이 티스토리 에디터에 직접 붙여넣기.
"""
import os
import shutil
import tkinter as tk


def _copy_to_clipboard(text: str) -> None:
    """클립보드 복사 — Windows clip 명령 사용 (새 Tk 루트 생성 안 함)"""
    import subprocess, sys
    if sys.platform == "win32":
        # clip은 UTF-16 LE 필요
        subprocess.run(
            ["clip"], input=text.encode("utf-16-le"),
            check=True, creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    else:
        # macOS / Linux 폴백
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        except FileNotFoundError:
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()


class ClipboardPublisher:
    """
    티스토리 발행용 HTML을 생성하고 클립보드에 복사.
    수동 붙여넣기 발행 지원.
    """

    def build_full_html(
        self,
        body_text: str,
        title: str,
        keyword: str,
        faq_schema: str,
        cta_text: str,
        cta_url: str,
        author_name: str,
        author_title: str,
        author_career: str,
        main_color: str = "#1B4F72",
        sub_color: str = "#F97316",
        image_path: str = None,
    ) -> str:
        """
        완성 HTML 생성.
        - 본문 텍스트 → HTML 변환 (문장 줄바꿈 처리)
        - CTA 블록 자동 삽입
        - 저자 프로필 자동 삽입
        - FAQ JSON-LD 스키마 자동 삽입
        - 이미지 위치 주석 삽입 (티스토리 에디터에서 직접 업로드)
        """
        html_parts = []

        # 이미지 위치 주석 — 본문 내 H2 소제목 사이에 분산 삽입
        html_parts.append(self._text_to_html_with_images(body_text, main_color))

        # CTA
        html_parts.append(
            f'\n<div style="margin:30px 0;padding:20px 24px;'
            f'background:#f0f4f8;border-left:5px solid {main_color};border-radius:4px;">'
            f'<p style="margin:0;font-size:15px;">'
            f'<a href="{cta_url}" style="color:{main_color};font-weight:bold;text-decoration:none;">'
            f'{cta_text}</a></p></div>'
        )

        # 저자 프로필
        html_parts.append(
            f'\n<div style="margin-top:40px;padding:16px 20px;'
            f'border:1px solid #ddd;border-radius:6px;background:#fafafa;">'
            f'<p style="margin:0 0 4px;font-weight:bold;">글쓴이: {author_name}</p>'
            f'<p style="margin:0 0 2px;color:#555;">{author_title}</p>'
            f'<p style="margin:0;color:#777;font-size:13px;">{author_career}</p>'
            f'</div>'
        )

        # FAQ JSON-LD
        if faq_schema and faq_schema.strip():
            html_parts.append(
                f'\n<script type="application/ld+json">\n{faq_schema}\n</script>'
            )

        return "\n".join(html_parts)

    def _text_to_html_with_images(self, text: str, main_color: str = "#1B4F72") -> str:
        """본문 HTML 변환 + 이미지 위치 주석 4개를 H2 소제목 앞에 분산 삽입"""
        lines = text.split("\n")
        html_lines = []
        in_para = False

        # 1단계: H2 소제목 위치 파악
        h2_indices = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            is_h2 = (
                len(stripped) <= 50
                and not stripped.endswith(("다.", "요.", "니다.", "세요.", "거든요.", "됩니다."))
                and not stripped.startswith(("Q.", "A.", "Q ", "A "))
            )
            if is_h2:
                h2_indices.append(idx)

        # 2단계: 이미지 삽입 위치 결정 (최대 4장)
        # - 1번 이미지: 본문 맨 위
        # - 2~4번: H2 소제목 앞에 균등 배분
        image_labels = [
            "blog_1 — 핵심 요약 정보카드",
            "blog_2 — 신청 절차 플로우차트",
            "blog_3 — 자금별 조건 비교표",
            "blog_4 — 자격요건 체크리스트",
        ]
        img_at_line = {}  # {line_index: image_label}

        if len(h2_indices) >= 3:
            # H2가 3개 이상이면 1번째, 2번째, 3번째 H2 앞에 삽입
            img_at_line[-1] = image_labels[0]  # 본문 맨 위
            for i, h2_idx in enumerate(h2_indices[:3]):
                if i + 1 < len(image_labels):
                    img_at_line[h2_idx] = image_labels[i + 1]
        elif len(h2_indices) >= 1:
            img_at_line[-1] = image_labels[0]
            for i, h2_idx in enumerate(h2_indices[:3]):
                if i + 1 < len(image_labels):
                    img_at_line[h2_idx] = image_labels[i + 1]
        else:
            # H2 없으면 전부 맨 위에 모아놓기
            img_at_line[-1] = " / ".join(image_labels)

        # 3단계: HTML 생성
        # 맨 위 이미지
        if -1 in img_at_line:
            html_lines.append(f'<!-- 여기에 이미지를 업로드하세요: {img_at_line[-1]} -->')
            html_lines.append('')

        for idx, line in enumerate(lines):
            stripped = line.strip()

            # 이미지 삽입 (해당 H2 앞)
            if idx in img_at_line:
                if in_para:
                    html_lines.append("</p>")
                    in_para = False
                html_lines.append(f'\n<!-- 여기에 이미지를 업로드하세요: {img_at_line[idx]} -->')
                html_lines.append('')

            if not stripped:
                if in_para:
                    html_lines.append("</p>")
                    in_para = False
                continue

            is_h2 = (
                len(stripped) <= 50
                and not stripped.endswith(("다.", "요.", "니다.", "세요.", "거든요.", "됩니다."))
                and not stripped.startswith(("Q.", "A.", "Q ", "A "))
            )

            if is_h2 and not in_para:
                html_lines.append(
                    f'<h2 style="color:{main_color};font-size:20px;'
                    f'margin:28px 0 12px;padding-bottom:6px;'
                    f'border-bottom:2px solid {main_color};">{stripped}</h2>'
                )
            else:
                if not in_para:
                    html_lines.append('<p style="margin:0 0 4px;line-height:1.8;">')
                    in_para = True
                html_lines.append(stripped + "<br>")

        if in_para:
            html_lines.append("</p>")

        return "\n".join(html_lines)

    def _text_to_html(self, text: str, main_color: str = "#1B4F72") -> str:
        """
        본문 텍스트 → HTML 변환 규칙:
        - 문장 끝 줄바꿈(\\n) → <br>
        - 빈 줄(\\n\\n) → 단락 구분 </p><p>
        - H2 소제목 패턴 → <h2> 태그 (짧은 단독 줄)
        """
        lines = text.split("\n")
        html_lines = []
        in_para = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                # 빈 줄 → 단락 닫기
                if in_para:
                    html_lines.append("</p>")
                    in_para = False
                continue

            # H2 소제목 감지: 50자 이하, 마침표/요/다 로 끝나지 않는 단독 줄
            is_h2 = (
                len(stripped) <= 50
                and not stripped.endswith(("다.", "요.", "니다.", "세요.", "거든요.", "됩니다."))
                and not stripped.startswith(("Q.", "A.", "Q ", "A "))
            )

            if is_h2 and not in_para:
                html_lines.append(
                    f'<h2 style="color:{main_color};font-size:20px;'
                    f'margin:28px 0 12px;padding-bottom:6px;'
                    f'border-bottom:2px solid {main_color};">{stripped}</h2>'
                )
            else:
                # 일반 문장 — 단락 시작
                if not in_para:
                    html_lines.append('<p style="margin:0 0 4px;line-height:1.8;">')
                    in_para = True
                html_lines.append(stripped + "<br>")

        if in_para:
            html_lines.append("</p>")

        return "\n".join(html_lines)

    # ── 클립보드 복사 메서드 ────────────────────────────────

    def copy_blog_html(
        self,
        body_text: str,
        title: str,
        keyword: str,
        faq_schema: str,
        cta_text: str,
        cta_url: str,
        author_name: str,
        author_title: str,
        author_career: str,
        main_color: str = "#1B4F72",
        sub_color: str = "#F97316",
        image_path: str = None,
    ) -> str:
        """발행용 완성 HTML을 클립보드에 복사. 복사된 HTML 반환."""
        html = self.build_full_html(
            body_text, title, keyword, faq_schema,
            cta_text, cta_url,
            author_name, author_title, author_career,
            main_color, sub_color, image_path
        )
        _copy_to_clipboard(html)
        return html

    def copy_title(self, title: str) -> None:
        """제목만 클립보드에 복사"""
        _copy_to_clipboard(title)

    def copy_tags(self, tags: str) -> None:
        """태그를 쉼표 구분 문자열로 클립보드에 복사"""
        _copy_to_clipboard(tags)

    def copy_insta_text(self, text: str, hashtags: str) -> None:
        """인스타 텍스트 + 해시태그 클립보드 복사"""
        full = f"{text}\n\n{hashtags}" if hashtags else text
        _copy_to_clipboard(full)

    def save_image(self, image_path: str, save_dir: str) -> str | None:
        """생성된 이미지를 지정 폴더에 저장 (티스토리 수동 업로드용)"""
        if not image_path or not os.path.exists(image_path):
            return None
        os.makedirs(save_dir, exist_ok=True)
        dest = os.path.join(save_dir, os.path.basename(image_path))
        shutil.copy2(image_path, dest)
        return dest
