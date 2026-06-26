"""
Browser Automation Tool - Visible Chrome browser with navigation and input capabilities
"""

import os
import subprocess
import time
import uuid
import json
from typing import Any, Dict

# selenium + webdriver_manager are heavy; import them lazily on first tool run
# (via _lazy(), invoked from the run wrapper below) instead of at module import.
webdriver = By = Keys = WebDriverWait = EC = ChromeOptions = ChromeService = ChromeDriverManager = None

def _lazy():
    global webdriver, By, Keys, WebDriverWait, EC, ChromeOptions, ChromeService, ChromeDriverManager
    if webdriver is not None:
        return
    from selenium import webdriver as _wd
    from selenium.webdriver.common.by import By as _By
    from selenium.webdriver.common.keys import Keys as _Keys
    from selenium.webdriver.support.ui import WebDriverWait as _WDW
    from selenium.webdriver.support import expected_conditions as _EC
    from selenium.webdriver.chrome.options import Options as _CO
    from selenium.webdriver.chrome.service import Service as _CS
    from webdriver_manager.chrome import ChromeDriverManager as _CDM
    webdriver, By, Keys, WebDriverWait, EC, ChromeOptions, ChromeService, ChromeDriverManager = (
        _wd, _By, _Keys, _WDW, _EC, _CO, _CS, _CDM)

from ..tool_registry import Tool, register

SESSION_FILE = os.path.expanduser("~/.cmpuse/browser_session.json")

_driver = None  # persistent Selenium-managed Chrome driver

def _build_options():
    _lazy()
    opts = ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-popup-blocking")
    return opts

def _get_driver():
    """Return a live, Selenium-managed Chrome driver (creating one if needed).
    Selenium Manager (selenium 4.6+) resolves the chromedriver automatically — this
    replaces the old webdriver_manager download (which hung) and the fragile
    remote-debugging attach/session-file dance."""
    global _driver
    _lazy()
    if _driver is not None:
        try:
            _ = _driver.current_url  # probe that it's still alive
            return _driver
        except Exception:
            _driver = None
    _driver = webdriver.Chrome(options=_build_options())
    return _driver

def get_driver_from_session():
    """Back-compat shim — now just returns the persistent Selenium-managed driver."""
    return _get_driver()

def _safe_quit(d):
    try:
        d.quit()
    except Exception:
        pass

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "launch")
    url = args.get("url", "https://www.google.com")
    selector = args.get("selector", "")
    text = args.get("text", "")

    if action == "launch":
        return {"preview": f"Launch visible Chrome browser to: {url}", "args": args}
    elif action == "navigate":
        return {"preview": f"Navigate to: {url}", "args": args}
    elif action == "click":
        return {"preview": f"Click element: {selector}", "args": args}
    elif action == "type":
        return {"preview": f"Type '{text}' into: {selector}", "args": args}
    elif action == "close":
        return {"preview": "Close the browser and end the session", "args": args}
    else:
        return {"preview": f"Browser action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform browser automation", "plan": _plan(args)}

    action = args.get("action", "launch")
    url = args.get("url", "https://www.google.com")
    selector = args.get("selector", "")
    text = args.get("text", "")
    timeout = args.get("timeout", 10)

    try:
        if action == "launch":
            driver = _get_driver()
            if url:
                driver.get(url)
                time.sleep(1)
            return {"status": "ok", "message": f"Chrome browser launched to {url}", "current_url": driver.current_url}

        elif action == "close":
            global _driver
            d = _driver
            _driver = None
            if d is None:
                return {"status": "ok", "message": "No active browser session to close."}
            # quit() can block if chromedriver is unresponsive; do it fire-and-forget.
            import threading as _th
            _th.Thread(target=lambda: _safe_quit(d), daemon=True).start()
            return {"status": "ok", "message": "Browser session closed."}

        # For all other actions, get the driver from the session
        driver = get_driver_from_session()

        if action == "navigate":
            if not url:
                return {"status": "error", "message": "URL required for navigation"}
            driver.get(url)
            time.sleep(2)
            return {"status": "ok", "message": f"Navigated to {url}", "current_url": driver.current_url}

        elif action == "click":
            if not selector:
                return {"status": "error", "message": "Selector required for clicking"}
            wait = WebDriverWait(driver, timeout)
            try:
                element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                driver.execute_script("arguments[0].scrollIntoView();", element)
                time.sleep(1)
                element.click()
                time.sleep(2)
                return {"status": "ok", "message": f"Clicked element: {selector}"}
            except Exception as e:
                # Try JavaScript click as fallback
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(2)
                    return {"status": "ok", "message": f"Clicked element with JavaScript: {selector}"}
                except Exception as js_error:
                    return {"status": "error", "message": f"Failed to click {selector}: {str(e)}"}

        elif action == "type":
            if not selector or not text:
                return {"status": "error", "message": "Selector and text required for typing"}
            wait = WebDriverWait(driver, timeout)
            try:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                driver.execute_script("arguments[0].scrollIntoView();", element)
                time.sleep(1)
                element.clear()
                element.send_keys(text)
                time.sleep(1)
                return {"status": "ok", "message": f"Typed '{text}' into {selector}"}
            except Exception as e:
                # Try JavaScript input as fallback
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    driver.execute_script("arguments[0].focus();", element)
                    driver.execute_script("arguments[0].value = arguments[1];", element, text)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
                    time.sleep(1)
                    return {"status": "ok", "message": f"Typed '{text}' into {selector} using JavaScript"}
                except Exception as js_error:
                    return {"status": "error", "message": f"Failed to type into {selector}: {str(e)}"}
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Browser automation error: {str(e)}"}

TOOL = Tool(
    name="browser_automation",
    summary="Complete visible browser automation - launch, navigate, click, type, search, and interact with web pages",
    plan=_plan,
    run=lambda args, dry_run: (_lazy(), _run(args, dry_run))[1],
    permissions={"confirm": False}
)

register(TOOL)
