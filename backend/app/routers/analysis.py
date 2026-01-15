"""
Analysis retrieval and WebSocket endpoints.
"""

import os
import json
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.models import AnalysisResult
from app.services.music_analyzer import get_analysis_result, analyze_music

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.get("/analysis/{file_id}", response_model=AnalysisResult)
async def get_analysis(file_id: str):
    """
    Get analysis results for a previously uploaded PDF.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)

    if not os.path.exists(upload_path):
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check if analysis is complete
    analysis_file = os.path.join(upload_path, "analysis.json")

    if os.path.exists(analysis_file):
        with open(analysis_file, 'r') as f:
            return json.load(f)

    # If no analysis file exists, generate mock analysis
    result = await get_analysis_result(file_id)
    return result


@router.get("/page/{file_id}/{page_number}")
async def get_page_image(file_id: str, page_number: int):
    """
    Get the rendered image for a specific page.
    """
    upload_path = os.path.join(UPLOAD_DIR, file_id)

    if not os.path.exists(upload_path):
        raise HTTPException(status_code=404, detail="Upload not found")

    image_path = os.path.join(upload_path, f"page_{page_number}.png")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found")

    return FileResponse(image_path, media_type="image/png")


@router.websocket("/ws/analysis/{file_id}")
async def analysis_websocket(websocket: WebSocket, file_id: str):
    """
    WebSocket endpoint for real-time analysis updates.
    """
    await websocket.accept()

    try:
        upload_path = os.path.join(UPLOAD_DIR, file_id)

        if not os.path.exists(upload_path):
            await websocket.send_json({
                "type": "error",
                "message": "Upload not found"
            })
            await websocket.close()
            return

        # Perform analysis with progress updates
        async for progress in analyze_music(file_id):
            if progress["type"] == "progress":
                await websocket.send_json({
                    "type": "progress",
                    "progress": progress["value"]
                })
            elif progress["type"] == "complete":
                await websocket.send_json({
                    "type": "complete",
                    "result": progress["result"]
                })
                break
            elif progress["type"] == "error":
                await websocket.send_json({
                    "type": "error",
                    "message": progress["message"]
                })
                break

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {file_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()
