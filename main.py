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

# Configuration
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
API_KEY = os.environ.get("GOOGLE_VISION_API_KEY")

@app.get("/")
async def root():
    return {"status": "online", "message": "AI Food Nutrition API is running"}

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Google Vision API Key not configured on server")

    # 1. Save file locally (optional, but good for debugging)
    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Read file and encode to Base64 for Google Vision
    with open(file_path, "rb") as image_file:
        content = base64.b64encode(image_file.read()).decode("utf-8")

    # 3. Call Google Vision API
    vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    payload = {
        "requests": [
            {
                "image": {"content": content},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 10},
                    {"type": "OBJECT_LOCALIZATION"}
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(vision_url, json=payload, timeout=30.0)
        
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error from Google Vision API")

    result = response.json()
    
    # 4. Extract labels from Google's response
    # The structure is: result['responses'][0]['labelAnnotations']
    responses = result.get("responses", [])
    if not responses:
        return {"status": "success", "labels": [], "message": "No data found"}
    
    labels = responses[0].get("labelAnnotations", [])
    
    # Format labels for our Flutter app
    formatted_labels = [
        {"description": label.get("description"), "score": label.get("score")}
        for label in labels
    ]

    return {
        "status": "success",
        "labels": formatted_labels,
        "message": "Real analysis complete"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
