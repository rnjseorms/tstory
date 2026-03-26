"""
Selenium 기반 티스토리 자동 발행 모듈.
카카오 로그인 → 글쓰기 → HTML 입력 → 이미지 업로드 → 태그/카테고리 → 발행.
"""
import os
import json
import time
import random
import threading
import base64
from datetime import date

# 쿠키 저장 경로
_COOKIE_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
_COOKIE_FILE = os.path.join(_COOKIE_DIR, ".tistory_cookies.json")
_PUBLISH_COUNT_FILE = os.path.join(_COOKIE_DIR, ".publish_count.json")


def _obfuscate(text: str) -> str:
    """간단한 base64 인코딩 (평문 저장 방지)"""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def _deobfuscate(text: str) -> str:
    """base64 디코딩"""
    try:
        return base64.b64decode(text.encode("utf-8")).decode("utf-8")
    except Exception:
        return text


def _get_today_count() -> int:
    """오늘 발행 횟수 반환"""
    try:
        with open(_PUBLISH_COUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return 0


def _increment_today_count():
    """오늘 발행 횟수 +1"""
    os.makedirs(_COOKIE_DIR, exist_ok=True)
    count = _get_today_count() + 1
    with open(_PUBLISH_COUNT_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": str(date.today()), "count": count}, f)


def _save_cookies(driver):
    """Selenium 쿠키를 파일에 저장"""
    os.makedirs(_COOKIE_DIR, exist_ok=True)
    cookies = driver.get_cookies()
    with open(_COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f)


def _load_cookies(driver, domain_url: str) -> bool:
    """저장된 쿠키 로드. 성공 여부 반환."""
    if not os.path.exists(_COOKIE_FILE):
        return False
    try:
        with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        driver.get(domain_url)
        time.sleep(1)
        for cookie in cookies:
            # Selenium이 받지 못하는 필드 제거
            for key in ["sameSite", "storeId", "id"]:
                cookie.pop(key, None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                continue
        return True
    except Exception:
        return False


class TistorySeleniumPublisher:
    """
    Selenium 기반 티스토리 자동 발행.
    각 단계를 분리하여 한 단계 실패 시 에러 메시지 반환.
    """

    def __init__(self, blog_url: str, kakao_email: str = "", kakao_password: str = "",
                 headless: bool = True):
        self.blog_url = blog_url.rstrip("/")
        self.kakao_email = kakao_email
        self.kakao_password = kakao_password
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Selenium WebDriver 초기화"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # user-agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(8)

    def _quit_driver(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ── 1단계: 로그인 ────────────────────────────────────────
    def login(self) -> dict:
        """
        카카오 계정으로 티스토리 로그인.
        쿠키가 있으면 쿠키 로그인 시도, 실패 시 ID/PW 로그인.
        반환: {"success": bool, "error": str}
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            self._init_driver()

            # 쿠키 로그인 시도
            if _load_cookies(self.driver, "https://www.tistory.com"):
                self.driver.get(f"{self.blog_url}/manage")
                time.sleep(2)
                # 로그인 상태 확인
                if "/manage" in self.driver.current_url and "login" not in self.driver.current_url:
                    return {"success": True, "error": ""}

            # 카카오 ID/PW 로그인
            if not self.kakao_email or not self.kakao_password:
                return {"success": False, "error": "카카오 이메일/비밀번호가 설정되지 않았습니다."}

            self.driver.get("https://www.tistory.com/auth/login")
            time.sleep(2)

            # "카카오계정으로 로그인" 버튼
            try:
                kakao_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn_login_kakao, .kakao_btn, a[href*='kakao']"))
                )
                kakao_btn.click()
                time.sleep(2)
            except Exception:
                # 직접 카카오 로그인 페이지로
                self.driver.get("https://accounts.kakao.com/login?continue=https://www.tistory.com/auth/login")
                time.sleep(2)

            # 카카오 로그인 폼
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='loginId'], input#loginId--1"))
                )
                email_input.clear()
                email_input.send_keys(self.kakao_email)

                pw_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='password'], input#password--2")
                pw_input.clear()
                pw_input.send_keys(self.kakao_password)

                time.sleep(0.5)
                login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn_g.btn_confirm")
                login_btn.click()
                time.sleep(3)
            except Exception as e:
                return {"success": False, "error": f"카카오 로그인 폼 입력 실패: {e}"}

            # 로그인 결과 확인
            if "accounts.kakao.com" in self.driver.current_url:
                # 아직 카카오 페이지 → 로그인 실패
                return {"success": False, "error": "카카오 로그인 실패. 이메일/비밀번호를 확인하세요."}

            # 동의 페이지 처리
            time.sleep(2)
            if "auth" in self.driver.current_url:
                try:
                    agree_btn = self.driver.find_element(By.CSS_SELECTOR, "button.btn_agree, button[type='submit']")
                    agree_btn.click()
                    time.sleep(2)
                except Exception:
                    pass

            # 쿠키 저장
            _save_cookies(self.driver)
            return {"success": True, "error": ""}

        except Exception as e:
            return {"success": False, "error": f"로그인 중 오류: {e}"}

    # ── 2단계: 글쓰기 페이지 열기 ─────────────────────────────
    def open_editor(self) -> dict:
        """글쓰기 페이지 열기. 반환: {"success": bool, "error": str}"""
        try:
            self.driver.get(f"{self.blog_url}/manage/newpost")
            time.sleep(3)

            if "newpost" not in self.driver.current_url and "post" not in self.driver.current_url:
                return {"success": False, "error": f"글쓰기 페이지 접근 실패. 현재 URL: {self.driver.current_url}"}

            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"글쓰기 페이지 열기 실패: {e}"}

    # ── 3단계: 제목 입력 ──────────────────────────────────────
    def set_title(self, title: str) -> dict:
        """제목 입력. 반환: {"success": bool, "error": str}"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            title_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "#post-title-inp, input.tit_post, textarea.tit_post, "
                    "[class*='title'] input, [class*='title'] textarea"))
            )
            title_input.clear()
            title_input.send_keys(title)
            time.sleep(0.5)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"제목 입력 실패: {e}"}

    # ── 4단계: HTML 모드 전환 + 본문 입력 ─────────────────────
    def set_html_content(self, html_content: str) -> dict:
        """HTML 모드 전환 후 본문 입력. 반환: {"success": bool, "error": str}"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            # HTML 모드 버튼 클릭
            try:
                html_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,
                        "button.btn_html, [data-mode='html'], button[title='HTML'],"
                        ".btn_switch [class*='html'], .mce-i-code"))
                )
                html_btn.click()
                time.sleep(1)
            except Exception:
                # 이미 HTML 모드이거나 다른 에디터 구조
                pass

            # HTML 입력 영역 찾기
            html_area = None
            selectors = [
                "textarea.html_code",
                "textarea#html-content",
                ".CodeMirror textarea",
                "textarea[class*='html']",
                "#tinymce",
                "div[contenteditable='true']",
            ]
            for sel in selectors:
                try:
                    html_area = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    continue

            if html_area is None:
                # JavaScript로 직접 입력 시도
                self.driver.execute_script("""
                    var editors = document.querySelectorAll('textarea, div[contenteditable="true"]');
                    for (var e of editors) {
                        if (e.offsetHeight > 100) {
                            e.value = arguments[0];
                            e.innerHTML = arguments[0];
                            e.dispatchEvent(new Event('input', {bubbles: true}));
                            break;
                        }
                    }
                """, html_content)
            else:
                html_area.clear()
                # 긴 HTML은 JS로 삽입 (send_keys보다 안정적)
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                    html_area, html_content
                )

            time.sleep(1)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"HTML 본문 입력 실패: {e}"}

    # ── 5단계: 이미지 업로드 ──────────────────────────────────
    def upload_images(self, image_paths: list) -> dict:
        """
        이미지 파일들을 티스토리 에디터에 업로드.
        반환: {"success": bool, "uploaded": int, "error": str}
        """
        from selenium.webdriver.common.by import By

        if not image_paths:
            return {"success": True, "uploaded": 0, "error": ""}

        uploaded = 0
        try:
            for img_path in image_paths:
                if not img_path or not os.path.exists(img_path):
                    continue
                abs_path = os.path.abspath(img_path)

                # 파일 입력 요소 찾기 (숨겨진 input[type=file])
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    file_inputs[0].send_keys(abs_path)
                    time.sleep(2)
                    uploaded += 1
                else:
                    # JS로 file input 생성
                    self.driver.execute_script("""
                        var input = document.createElement('input');
                        input.type = 'file';
                        input.style.display = 'none';
                        document.body.appendChild(input);
                    """)
                    time.sleep(0.5)
                    file_input = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_input:
                        file_input[-1].send_keys(abs_path)
                        time.sleep(2)
                        uploaded += 1

            return {"success": True, "uploaded": uploaded, "error": ""}
        except Exception as e:
            return {"success": False, "uploaded": uploaded, "error": f"이미지 업로드 실패: {e}"}

    # ── 6단계: 태그 입력 ──────────────────────────────────────
    def set_tags(self, tags: str) -> dict:
        """쉼표 구분 태그 입력. 반환: {"success": bool, "error": str}"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        if not tags.strip():
            return {"success": True, "error": ""}

        try:
            tag_input = None
            for sel in ["input.tf_tag", "input#tag-input", "input[placeholder*='태그']",
                        "input[class*='tag']", ".tag_input input"]:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    tag_input = elems[0]
                    break

            if tag_input is None:
                return {"success": False, "error": "태그 입력란을 찾을 수 없습니다."}

            for tag in tags.split(","):
                tag = tag.strip()
                if tag:
                    tag_input.send_keys(tag)
                    tag_input.send_keys(Keys.ENTER)
                    time.sleep(0.3)

            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": f"태그 입력 실패: {e}"}

    # ── 7단계: 카테고리 설정 ──────────────────────────────────
    def set_category(self, category_name: str) -> dict:
        """카테고리 선택. 반환: {"success": bool, "error": str}"""
        from selenium.webdriver.common.by import By

        if not category_name.strip():
            return {"success": True, "error": ""}

        try:
            # 카테고리 선택 드롭다운
            cat_btn = None
            for sel in ["button.btn_category", ".btn_cate", "[class*='category'] button",
                        "select#category", ".post_option select"]:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    cat_btn = elems[0]
                    break

            if cat_btn is None:
                return {"success": True, "error": "카테고리 선택란 미발견 (기본 카테고리 사용)"}

            if cat_btn.tag_name == "select":
                from selenium.webdriver.support.ui import Select
                sel = Select(cat_btn)
                for opt in sel.options:
                    if category_name in opt.text:
                        sel.select_by_visible_text(opt.text)
                        return {"success": True, "error": ""}
            else:
                cat_btn.click()
                time.sleep(1)
                cat_items = self.driver.find_elements(By.CSS_SELECTOR, "li[class*='cate'], .list_cate li")
                for item in cat_items:
                    if category_name in item.text:
                        item.click()
                        time.sleep(0.5)
                        return {"success": True, "error": ""}

            return {"success": True, "error": f"카테고리 '{category_name}' 미발견. 기본값 유지."}
        except Exception as e:
            return {"success": False, "error": f"카테고리 설정 실패: {e}"}

    # ── 8단계: 발행 ───────────────────────────────────────────
    def click_publish(self) -> dict:
        """
        발행 버튼 클릭 → 발행된 URL 반환.
        반환: {"success": bool, "url": str, "error": str}
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            # 발행 버튼 찾기 (다양한 선택자)
            pub_btn = None
            for sel in ["button.btn_publish", "button#publish-layer-btn",
                        "button[class*='save']", "button.btn_submit",
                        "#publish-btn", ".btn_save"]:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    pub_btn = elems[0]
                    break

            if pub_btn is None:
                # 텍스트로 찾기
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if any(kw in btn.text for kw in ["발행", "공개", "저장", "등록"]):
                        pub_btn = btn
                        break

            if pub_btn is None:
                return {"success": False, "url": "", "error": "발행 버튼을 찾을 수 없습니다."}

            pub_btn.click()
            time.sleep(2)

            # 확인 팝업이 있으면 클릭
            try:
                confirm_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,
                        ".btn_ok, button.confirm, button[class*='publish']"))
                )
                confirm_btn.click()
                time.sleep(3)
            except Exception:
                pass

            # 발행된 URL 추출
            time.sleep(2)
            current_url = self.driver.current_url
            if "/manage/" not in current_url and self.blog_url in current_url:
                return {"success": True, "url": current_url, "error": ""}

            # URL을 못 찾으면 관리 페이지에서 최신 글 확인
            self.driver.get(f"{self.blog_url}/manage/posts")
            time.sleep(2)
            try:
                first_post = self.driver.find_element(By.CSS_SELECTOR, ".post_list a, .tit_post a")
                post_url = first_post.get_attribute("href")
                if post_url:
                    return {"success": True, "url": post_url, "error": ""}
            except Exception:
                pass

            _increment_today_count()
            return {"success": True, "url": f"{self.blog_url}", "error": "발행은 됐으나 URL 확인 실패"}

        except Exception as e:
            return {"success": False, "url": "", "error": f"발행 실패: {e}"}

    # ── 전체 자동 발행 (한 번에) ──────────────────────────────
    def publish(self, title: str, html_content: str, tags: str = "",
                category: str = "", image_paths: list = None) -> dict:
        """
        전체 자동 발행 프로세스 실행.
        반환: {"success": bool, "url": str, "error": str, "step": str}
        """
        steps = [
            ("로그인", lambda: self.login()),
            ("글쓰기 열기", lambda: self.open_editor()),
            ("제목 입력", lambda: self.set_title(title)),
            ("본문 입력", lambda: self.set_html_content(html_content)),
            ("이미지 업로드", lambda: self.upload_images(image_paths or [])),
            ("태그 입력", lambda: self.set_tags(tags)),
            ("카테고리 설정", lambda: self.set_category(category)),
            ("발행", lambda: self.click_publish()),
        ]

        last_result = {}
        for step_name, step_func in steps:
            result = step_func()
            if not result.get("success", False):
                self._quit_driver()
                return {
                    "success": False,
                    "url": "",
                    "error": result.get("error", "알 수 없는 오류"),
                    "step": step_name,
                }
            last_result = result

        # 성공 — 쿠키 저장 + 발행 카운트
        _save_cookies(self.driver)
        _increment_today_count()
        self._quit_driver()

        return {
            "success": True,
            "url": last_result.get("url", ""),
            "error": "",
            "step": "완료",
        }

    # ── 로그인 테스트 ─────────────────────────────────────────
    def test_login(self) -> dict:
        """로그인만 테스트. 반환: {"success": bool, "error": str}"""
        result = self.login()
        self._quit_driver()
        return result


# ── 발행 지연 (기존 호환) ──────────────────────────────────────
def delayed_publish(publish_func, delay_mode: str = "random") -> int:
    """발행 지연. 반환: 예상 지연 초"""
    if delay_mode == "immediate":
        publish_func()
        return 0
    delay = random.randint(30 * 60, 120 * 60)

    def run():
        time.sleep(delay)
        publish_func()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return delay


def get_today_publish_count() -> int:
    """오늘 발행 횟수 (외부에서 호출용)"""
    return _get_today_count()
