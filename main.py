from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import base64
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
API_KEY = os.environ.get("GOOGLE_VISION_API_KEY")

@app.get("/")
async def root():
    return {"status": "online", "message": "Vision API is active"}

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key missing on Render")

    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with open(file_path, "rb") as image_file:
        content = base64.b64encode(image_file.read()).decode("utf-8")

    vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    payload = {
        "requests": [{
            "image": {"content": content},
            "features": [
                {"type": "LABEL_DETECTION", "maxResults": 15},
                {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                {"type": "TEXT_DETECTION", "maxResults": 5}
            ]
        }]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(vision_url, json=payload, timeout=30.0)
    
    if response.status_code != 200:
        return {"status": "error", "message": f"Google Error: {response.status_code}"}

    result = response.json()
    res = result.get("responses", [{}])[0]
    
    # Collect all findings
    findings = []
    
    # 1. Labels
    for label in res.get("labelAnnotations", []):
        findings.append({"name": label.get("description"), "score": label.get("score"), "type": "label"})
    
    # 2. Objects (often more specific)
    for obj in res.get("localizedObjectAnnotations", []):
        findings.append({"name": obj.get("name"), "score": obj.get("score"), "type": "object"})

    # Sort by confidence score
    findings.sort(key=lambda x: x['score'] or 0, reverse=True)

    return {
        "status": "success",
        "labels": findings, # Flutter app expects 'labels'
        "raw_text": res.get("fullTextAnnotation", {}).get("text", "")
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
