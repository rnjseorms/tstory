"""인스타그램 Meta Graph API 발행 — Imgur 이미지 호스팅 + Meta 2단계 발행"""
import requests
import threading
import os


_META_API_BASE = "https://graph.facebook.com/v19.0"
_IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"


def upload_to_imgur(image_path: str, client_id: str) -> str:
    """
    로컬 이미지 → Imgur 업로드 → 공개 URL 반환
    client_id: Imgur API 클라이언트 ID (settings에서 주입)
    """
    if not client_id:
        raise ValueError("Imgur Client ID가 없습니다. 설정 탭 > API 설정에서 입력하세요.")
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일 없음: {image_path}")

    with open(image_path, "rb") as f:
        img_data = f.read()

    resp = requests.post(
        _IMGUR_UPLOAD_URL,
        headers={"Authorization": f"Client-ID {client_id}"},
        data={"image": img_data, "type": "binary"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Imgur 업로드 실패: {result}")
    return result["data"]["link"]  # https://i.imgur.com/xxxxx.jpg


class InstagramPublisher:
    def __init__(self, ig_user_id: str, access_token: str):
        self.ig_user_id = ig_user_id
        self.access_token = access_token

    def _post(self, endpoint: str, params: dict) -> dict:
        params["access_token"] = self.access_token
        resp = requests.post(f"{_META_API_BASE}/{endpoint}", params=params, timeout=30)
        return resp.json()

    def publish(self, image_url: str, caption: str, hashtags: str) -> dict:
        """
        Meta Graph API 2단계 발행
        image_url: 반드시 공개 접근 가능한 URL
        반환: {"success": bool, "media_id": str, "error": str}
        """
        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
        full_caption = full_caption[:2200]  # 인스타 최대 글자수

        # Step 1: 미디어 컨테이너 생성
        try:
            data = self._post(f"{self.ig_user_id}/media", {
                "image_url": image_url,
                "caption": full_caption,
            })
            creation_id = data.get("id")
            if not creation_id:
                err = data.get("error", {}).get("message", str(data))
                return {"success": False, "media_id": "", "error": f"컨테이너 생성 실패: {err}"}
        except Exception as e:
            return {"success": False, "media_id": "", "error": str(e)}

        # Step 2: 발행
        try:
            data2 = self._post(f"{self.ig_user_id}/media_publish", {
                "creation_id": creation_id,
            })
            media_id = data2.get("id", "")
            if media_id:
                return {"success": True, "media_id": media_id, "error": ""}
            err = data2.get("error", {}).get("message", str(data2))
            return {"success": False, "media_id": "", "error": f"발행 실패: {err}"}
        except Exception as e:
            return {"success": False, "media_id": "", "error": str(e)}

    def publish_async(self, image_url: str, caption: str, hashtags: str, callback):
        """비동기 발행. callback(result_dict) 호출"""
        def run():
            result = self.publish(image_url, caption, hashtags)
            callback(result)
        threading.Thread(target=run, daemon=True).start()

    def publish_from_local(self, image_path: str, caption: str, hashtags: str,
                           imgur_client_id: str, callback):
        """로컬 이미지 → Imgur 업로드 → Meta 발행 (비동기)"""
        def run():
            try:
                image_url = upload_to_imgur(image_path, imgur_client_id)
            except Exception as e:
                callback({"success": False, "media_id": "", "error": f"이미지 업로드 실패: {e}"})
                return
            result = self.publish(image_url, caption, hashtags)
            callback(result)
        threading.Thread(target=run, daemon=True).start()
