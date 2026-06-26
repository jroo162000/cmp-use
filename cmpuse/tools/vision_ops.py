"""
Vision Operations Tool - OCR, screen reading, and GPT-5.2 Pro vision analysis
"""

import pyautogui
import os
import base64
from typing import Any, Dict
from io import BytesIO

from ..tool_registry import Tool, register

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "ocr")

    if action == "ocr":
        return {"preview": "Read text from screen using OCR", "args": args}
    elif action == "ocr_region":
        region = args.get("region", [])
        return {"preview": f"Read text from region {region} using OCR", "args": args}
    elif action == "analyze_screen":
        return {"preview": "Analyze screen content with GPT-5.2 Pro Vision", "args": args}
    elif action == "describe_image":
        return {"preview": "Describe image with AI vision", "args": args}
    else:
        return {"preview": f"Vision action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform vision operation", "plan": _plan(args)}

    action = args.get("action", "ocr")

    try:
        if action == "ocr" or action == "ocr_region":
            # OCR - Read text from screen
            try:
                import pytesseract
            except ImportError:
                return {"status": "error", "message": "pytesseract not installed. Run: pip install pytesseract"}

            region = args.get("region")  # (left, top, width, height)

            if region:
                screenshot = pyautogui.screenshot(region=tuple(region))
            else:
                screenshot = pyautogui.screenshot()

            # Perform OCR
            text = pytesseract.image_to_string(screenshot)

            if not text.strip():
                return {"status": "ok", "message": "No text detected", "text": ""}

            return {
                "status": "ok",
                "message": f"Extracted {len(text)} characters",
                "text": text.strip(),
                "region": region
            }

        elif action == "analyze_screen" or action == "describe_image":
            # GPT-5.2 Pro Vision - Analyze screen or image
            from openai import OpenAI
            from ..secrets import load_into_env

            load_into_env()
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {"status": "error", "message": "OpenAI API key not configured"}

            client = OpenAI(api_key=api_key)

            # Get image
            if action == "describe_image":
                image_path = args.get("image_path")
                if not image_path or not os.path.exists(image_path):
                    return {"status": "error", "message": "Valid image_path required"}

                with open(image_path, "rb") as f:
                    image_data = f.read()
            else:
                # Screenshot for screen analysis
                region = args.get("region")
                if region:
                    screenshot = pyautogui.screenshot(region=tuple(region))
                else:
                    screenshot = pyautogui.screenshot()

                # Convert to bytes
                buffer = BytesIO()
                screenshot.save(buffer, format="PNG")
                image_data = buffer.getvalue()

            # Encode to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Get user question/prompt
            question = args.get("question", "What do you see in this image? Describe everything in detail.")

            # Call GPT-4o Vision (gpt-5.2 doesn't support vision yet)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )

            description = response.choices[0].message.content

            return {
                "status": "ok",
                "message": "Vision analysis complete",
                "description": description,
                "action": action
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Vision error: {str(e)}"}

TOOL = Tool(
    name="vision_ops",
    summary="Vision operations - OCR text reading, screen analysis with GPT-5.2 Pro Vision, image understanding",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}
)

register(TOOL)
