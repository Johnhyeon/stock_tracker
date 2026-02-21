import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from core.timezone import now_kst

router = APIRouter()

UPLOAD_DIR = Path("/home/hyeon/project/my_stock/uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("")
async def upload_image(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다.")

    date_folder = now_kst().strftime("%Y/%m")
    save_dir = UPLOAD_DIR / date_folder
    save_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = save_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(content)

    url = f"/uploads/{date_folder}/{unique_name}"

    return JSONResponse({
        "url": url,
        "filename": file.filename,
        "size": len(content),
    })


@router.delete("/{year}/{month}/{filename}")
async def delete_image(year: str, month: str, filename: str):
    file_path = UPLOAD_DIR / year / month / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    if not str(file_path).startswith(str(UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="잘못된 경로입니다.")

    os.remove(file_path)
    return {"message": "삭제되었습니다."}
