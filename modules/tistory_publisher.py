"""티스토리 API 발행"""
import requests
import threading
import random
import time


class TistoryPublisher:
    BASE_URL = "https://www.tistory.com/apis"

    def __init__(self, access_token: str, blog_name: str):
        self.access_token = access_token
        self.blog_name = blog_name

    def _params(self, extra: dict = None) -> dict:
        p = {"access_token": self.access_token, "output": "json"}
        if extra:
            p.update(extra)
        return p

    def upload_image(self, image_path: str) -> str | None:
        """이미지 업로드 → URL 반환"""
        if not image_path:
            return None
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    f"{self.BASE_URL}/post/attach",
                    params=self._params({"blogName": self.blog_name}),
                    files={"uploadedfile": f},
                    timeout=30,
                )
            data = resp.json()
            return data.get("tistory", {}).get("url")
        except Exception as e:
            print(f"이미지 업로드 실패: {e}")
            return None

    def get_categories(self) -> list:
        try:
            resp = requests.get(
                f"{self.BASE_URL}/category/list",
                params=self._params({"blogName": self.blog_name}),
                timeout=10,
            )
            cats = resp.json().get("tistory", {}).get("item", {}).get("categories", [])
            return cats if isinstance(cats, list) else []
        except Exception:
            return []

    def publish(self, title: str, html_content: str, tags: str,
                category_id: str = "", image_path: str = None) -> dict:
        """
        티스토리 포스트 발행
        반환: {"success": bool, "url": str, "post_id": str, "error": str}
        """
        image_url = self.upload_image(image_path) if image_path else None
        if image_url:
            img_tag = f'<img src="{image_url}" alt="{title}" style="max-width:100%;">\n'
            html_content = img_tag + html_content

        params = self._params({
            "blogName": self.blog_name,
            "title": title,
            "content": html_content,
            "visibility": "3",
            "tag": tags,
            "categoryId": category_id,
        })
        try:
            resp = requests.post(f"{self.BASE_URL}/post/write", params=params, timeout=30)
            data = resp.json().get("tistory", {})
            if data.get("status") == "200":
                return {"success": True, "url": data.get("url", ""), "post_id": data.get("postId", ""), "error": ""}
            return {"success": False, "url": "", "post_id": "", "error": str(data)}
        except Exception as e:
            return {"success": False, "url": "", "post_id": "", "error": str(e)}


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
