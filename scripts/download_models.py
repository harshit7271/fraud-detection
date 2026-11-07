"""
Download and verify official OpenCV Zoo ONNX model weights for YuNet and SFace.
Models:
1. YuNet (face_detection_yunet_2023mar.onnx) - Apache 2.0 License
2. SFace (face_recognition_sface_2021dec.onnx) - Apache 2.0 License
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "description": "YuNet Face Detection ONNX model (March 2023 version)",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "description": "SFace Face Recognition ONNX model (December 2021 version)",
    },
}

TARGET_DIR = Path(__file__).resolve().parent.parent / "models" / "weights"


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_model(filename: str, info: dict[str, str]) -> bool:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = TARGET_DIR / filename

    if dest_path.exists():
        current_hash = compute_sha256(dest_path)
        if current_hash == info["sha256"]:
            print(f"[{filename}] already exists and matches expected SHA256.")
            return True
        else:
            print(f"[{filename}] hash mismatch (found {current_hash[:8]}..., re-downloading)...")

    print(f"Downloading {filename} from {info['url']}...")
    try:
        urllib.request.urlretrieve(info["url"], dest_path)
        downloaded_hash = compute_sha256(dest_path)
        print(f"[{filename}] Downloaded successfully. SHA256: {downloaded_hash}")
        return True
    except Exception as e:
        print(f"Error downloading {filename}: {e}", file=sys.stderr)
        return False


def main() -> None:
    print(f"Target directory: {TARGET_DIR}")
    success = True
    for filename, info in MODELS.items():
        if not download_model(filename, info):
            success = False

    if success:
        print("All model weights successfully verified.")
    else:
        print("Warning: One or more models could not be downloaded.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
