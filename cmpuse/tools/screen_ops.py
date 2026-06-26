"""
Screen Operations Tool - Take screenshots, capture regions, locate images on screen
"""

import pyautogui
import os
import time
from datetime import datetime
from typing import Any, Dict
from PIL import Image

# OpenCV is heavy; load it lazily on first use rather than at import time.
from .._lazyimport import lazy_module
cv2 = lazy_module("cv2")
_HAS_CV2 = True

from ..tool_registry import Tool, register

# Default screenshot directory
DEFAULT_SCREENSHOT_DIR = os.path.expanduser("~/Pictures/Screenshots")

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "screenshot")
    region = args.get("region")
    file_path = args.get("file_path", "")

    if action == "screenshot":
        if region:
            return {"preview": f"Take screenshot of region {region}", "args": args}
        return {"preview": "Take full screenshot", "args": args}
    elif action == "locate":
        image_path = args.get("image_path", "")
        return {"preview": f"Locate image on screen: {image_path}", "args": args}
    elif action == "screen_size":
        return {"preview": "Get screen size and information", "args": args}
    else:
        return {"preview": f"Screen action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform screen operation", "plan": _plan(args)}

    action = args.get("action", "screenshot")

    try:
        if action == "screenshot":
            # Get screenshot parameters
            region = args.get("region")  # (left, top, width, height)
            file_path = args.get("file_path")

            # Take screenshot
            if region:
                # Validate region format
                if not isinstance(region, (list, tuple)) or len(region) != 4:
                    return {"status": "error", "message": "region must be [left, top, width, height]"}

                screenshot = pyautogui.screenshot(region=tuple(region))
            else:
                screenshot = pyautogui.screenshot()

            # Generate file path if not provided
            if not file_path:
                os.makedirs(DEFAULT_SCREENSHOT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join(DEFAULT_SCREENSHOT_DIR, f"screenshot_{timestamp}.png")

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save screenshot
            screenshot.save(file_path)
            file_size = os.path.getsize(file_path)
            size_kb = round(file_size / 1024, 2)

            return {
                "status": "ok",
                "message": f"Screenshot saved to {file_path}",
                "file_path": file_path,
                "size": f"{size_kb} KB",
                "dimensions": f"{screenshot.width}x{screenshot.height}",
                "region": region
            }

        elif action == "screenshot_region":
            # Shorthand for region screenshot
            left = args.get("left", 0)
            top = args.get("top", 0)
            width = args.get("width")
            height = args.get("height")
            file_path = args.get("file_path")

            if width is None or height is None:
                return {"status": "error", "message": "width and height required for region screenshot"}

            region = (left, top, width, height)
            screenshot = pyautogui.screenshot(region=region)

            if not file_path:
                os.makedirs(DEFAULT_SCREENSHOT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join(DEFAULT_SCREENSHOT_DIR, f"screenshot_region_{timestamp}.png")

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            screenshot.save(file_path)

            return {
                "status": "ok",
                "message": f"Region screenshot saved to {file_path}",
                "file_path": file_path,
                "region": region
            }

        elif action == "locate":
            # Locate an image on the screen
            image_path = args.get("image_path")
            confidence = args.get("confidence", None)
            region = args.get("region")  # optional (left, top, width, height)

            if not image_path or not os.path.exists(image_path):
                return {"status": "error", "message": f"Valid image_path required. File not found: {image_path}"}

            # Try confidence-based locate when OpenCV is available, otherwise
            # fall back to exact pixel matching and a grayscale retry.
            try:
                if _HAS_CV2 and confidence is not None:
                    if region and isinstance(region, (list, tuple)) and len(region) == 4:
                        location = pyautogui.locateOnScreen(image_path, confidence=float(confidence), region=tuple(region))
                    else:
                        location = pyautogui.locateOnScreen(image_path, confidence=float(confidence))
                else:
                    if region and isinstance(region, (list, tuple)) and len(region) == 4:
                        location = pyautogui.locateOnScreen(image_path, region=tuple(region))
                    else:
                        location = pyautogui.locateOnScreen(image_path)
            except Exception:
                # Fallback attempt with grayscale (can tolerate minor color shifts)
                try:
                    if region and isinstance(region, (list, tuple)) and len(region) == 4:
                        location = pyautogui.locateOnScreen(image_path, grayscale=True, region=tuple(region))
                    else:
                        location = pyautogui.locateOnScreen(image_path, grayscale=True)
                except Exception as e2:
                    return {"status": "error", "message": f"Image location error: {str(e2)}"}

            if location:
                center = pyautogui.center(location)
                return {
                    "status": "ok",
                    "message": "Image found on screen",
                    "location": {
                        "left": location.left,
                        "top": location.top,
                        "width": location.width,
                        "height": location.height,
                        "center_x": center.x,
                        "center_y": center.y
                    }
                }
            else:
                return {
                    "status": "ok",
                    "message": "Image not found on screen",
                    "location": None
                }

        elif action == "locate_all":
            # Find all occurrences of an image
            image_path = args.get("image_path")
            confidence = args.get("confidence", None)
            region = args.get("region")

            if not image_path or not os.path.exists(image_path):
                return {"status": "error", "message": f"Valid image_path required"}

            try:
                if _HAS_CV2 and confidence is not None:
                    if region and isinstance(region, (list, tuple)) and len(region) == 4:
                        locations = list(pyautogui.locateAllOnScreen(image_path, confidence=float(confidence), region=tuple(region)))
                    else:
                        locations = list(pyautogui.locateAllOnScreen(image_path, confidence=float(confidence)))
                else:
                    if region and isinstance(region, (list, tuple)) and len(region) == 4:
                        locations = list(pyautogui.locateAllOnScreen(image_path, region=tuple(region)))
                    else:
                        locations = list(pyautogui.locateAllOnScreen(image_path))
            
                if locations:
                    results = []
                    for loc in locations:
                        center = pyautogui.center(loc)
                        results.append({
                            "left": loc.left,
                            "top": loc.top,
                            "width": loc.width,
                            "height": loc.height,
                            "center_x": center.x,
                            "center_y": center.y
                        })

                    return {
                        "status": "ok",
                        "message": f"Found {len(results)} occurrence(s) of image",
                        "count": len(results),
                        "locations": results
                    }
                else:
                    return {
                        "status": "ok",
                        "message": "Image not found on screen",
                        "count": 0,
                        "locations": []
                    }
            except Exception as e:
                return {"status": "error", "message": f"Image location error: {str(e)}"}

        elif action == "screen_size":
            size = pyautogui.size()
            return {
                "status": "ok",
                "message": f"Screen size: {size.width}x{size.height}",
                "width": size.width,
                "height": size.height,
                "total_pixels": size.width * size.height
            }

        elif action == "pixel_color":
            # Get the color of a pixel at specific coordinates
            x = args.get("x")
            y = args.get("y")

            if x is None or y is None:
                return {"status": "error", "message": "x and y coordinates required"}

            try:
                pixel = pyautogui.pixel(x, y)
                hex_color = "#{:02x}{:02x}{:02x}".format(pixel[0], pixel[1], pixel[2])

                return {
                    "status": "ok",
                    "message": f"Pixel color at ({x}, {y}): {hex_color}",
                    "position": {"x": x, "y": y},
                    "rgb": {"r": pixel[0], "g": pixel[1], "b": pixel[2]},
                    "hex": hex_color
                }
            except Exception as e:
                return {"status": "error", "message": f"Pixel color error: {str(e)}"}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Screen operation error: {str(e)}"}

TOOL = Tool(
    name="screen_ops",
    summary="Screen operations - take screenshots, capture regions, locate images, get screen info, pixel colors",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Require confirmation for screen operations
)

register(TOOL)
