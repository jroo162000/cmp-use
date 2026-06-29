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
    """Return a live Chrome driver. Prefers undetected-chromedriver with a PERSISTENT
    profile so the automation browser can stay signed in and is far less likely to be
    blocked by Google ('this browser or app may not be secure'). Falls back to plain
    Selenium (also with a persistent profile + automation flags reduced)."""
    global _driver
    _lazy()
    if _driver is not None:
        try:
            _ = _driver.current_url  # probe that it's still alive
            return _driver
        except Exception:
            _driver = None
    profile_dir = os.path.expanduser("~/.cmpuse/ava_chrome_profile")
    try:
        os.makedirs(profile_dir, exist_ok=True)
    except Exception:
        pass
    # 1) undetected-chromedriver (stealth) — keeps Google/site sign-ins working.
    try:
        import undetected_chromedriver as uc
        uopts = uc.ChromeOptions()
        uopts.add_argument("--start-maximized")
        uopts.add_argument("--disable-dev-shm-usage")
        uopts.add_argument("--no-first-run")
        uopts.add_argument("--no-default-browser-check")
        _driver = uc.Chrome(options=uopts, user_data_dir=profile_dir, use_subprocess=True)
        return _driver
    except Exception:
        pass
    # 2) Fallback: plain Selenium-managed Chrome, persistent profile, fewer automation flags.
    opts = _build_options()
    try:
        opts.add_argument(f"--user-data-dir={profile_dir}")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
    except Exception:
        pass
    _driver = webdriver.Chrome(options=opts)
    return _driver

def get_driver_from_session():
    """Back-compat shim — now just returns the persistent Selenium-managed driver."""
    return _get_driver()

def _safe_quit(d):
    try:
        d.quit()
    except Exception:
        pass


# ---- Robust, descriptor-based form helpers (work across arbitrary sites) ----

def _find_input(driver, descriptor):
    """Find a text/select/textarea input by a human descriptor: a CSS selector, an exact
    name/id, or a fuzzy match on label / placeholder / aria-label / name / id."""
    d = (descriptor or "").strip()
    if not d:
        return None
    if d[0] in "#.[":
        try:
            return driver.find_element(By.CSS_SELECTOR, d)
        except Exception:
            pass
    for by, sel in ((By.NAME, d), (By.ID, d), (By.CSS_SELECTOR, f'[name="{d}"]')):
        try:
            return driver.find_element(by, sel)
        except Exception:
            pass
    js = r'''
    const want = (arguments[0]||'').toLowerCase();
    const els = [...document.querySelectorAll('input, textarea, select')].filter(el => {
      const t = (el.type||'').toLowerCase();
      return !['hidden','submit','button','image','file'].includes(t);
    });
    const ctx = (el) => {
      let s = '';
      if (el.id){const l=document.querySelector('label[for="'+CSS.escape(el.id)+'"]'); if(l)s+=' '+l.innerText;}
      const lab = el.closest && el.closest('label'); if(lab)s+=' '+lab.innerText;
      s += ' '+(el.getAttribute('aria-label')||'')+' '+(el.placeholder||'')+' '+(el.name||'')+' '+(el.id||'');
      return s.toLowerCase();
    };
    let best=null;
    for(const el of els){ if(ctx(el).includes(want)){best=el;break;} }
    return best;
    '''
    try:
        return driver.execute_script(js, d)
    except Exception:
        return None


def _fill_element(driver, el, value):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    if (getattr(el, 'tag_name', '') or '').lower() == 'select':
        try:
            from selenium.webdriver.support.ui import Select
            try:
                Select(el).select_by_visible_text(str(value)); return
            except Exception:
                Select(el).select_by_value(str(value)); return
        except Exception:
            pass
    try:
        el.clear()
    except Exception:
        pass
    try:
        el.send_keys(str(value))
    except Exception:
        driver.execute_script(
            "arguments[0].value=arguments[1];"
            "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el, str(value))


def _find_file_input(driver, descriptor=''):
    try:
        if descriptor:
            el = _find_input(driver, descriptor)
            if el and (el.get_attribute('type') or '').lower() == 'file':
                return el
        return driver.find_element(By.CSS_SELECTOR, 'input[type=file]')
    except Exception:
        return None


def _find_clickable_by_text(driver, label):
    js = r'''
    const want = (arguments[0]||'').toLowerCase().trim();
    const els = [...document.querySelectorAll('button, input[type=submit], input[type=button], a, [role=button]')];
    const txt = (el) => (el.innerText||el.value||el.getAttribute('aria-label')||'').trim().toLowerCase();
    let best = els.find(el => txt(el) === want);
    if(!best) best = els.find(el => txt(el).includes(want));
    return best || null;
    '''
    try:
        return driver.execute_script(js, label)
    except Exception:
        return None


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
                target = str(url).strip()
                from urllib.parse import quote_plus, urlparse
                import re
                if urlparse(target).scheme:
                    nav_url = target
                elif re.match(r"^(localhost|(\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)(:\d+)?(/.*)?$", target):
                    nav_url = "https://" + target
                else:
                    nav_url = "https://www.google.com/search?q=" + quote_plus(target)
                driver.get(nav_url)
                time.sleep(1)
            return {"status": "ok", "message": f"Chrome browser launched to {nav_url if url else url}", "current_url": driver.current_url}

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
            target = str(url).strip()
            from urllib.parse import quote_plus, urlparse
            import re
            if urlparse(target).scheme:
                nav_url = target
            elif re.match(r"^(localhost|(\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)(:\d+)?(/.*)?$", target):
                nav_url = "https://" + target
            else:
                nav_url = "https://www.google.com/search?q=" + quote_plus(target)
            driver.get(nav_url)
            time.sleep(2)
            return {"status": "ok", "message": f"Navigated to {nav_url}", "current_url": driver.current_url}

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
        
        elif action in ("get_fields", "read_page", "inspect_form", "fields"):
            js = r'''
            const out = {fields: [], buttons: [], url: location.href, title: document.title};
            const labelFor = (el) => {
              let t = '';
              if (el.id) { const l = document.querySelector('label[for="'+CSS.escape(el.id)+'"]'); if (l) t = l.innerText; }
              if (!t && el.closest) { const l = el.closest('label'); if (l) t = l.innerText; }
              return (t || el.getAttribute('aria-label') || el.placeholder || el.name || el.id || '').trim().slice(0,80);
            };
            document.querySelectorAll('input, textarea, select').forEach(el => {
              const type = (el.type || el.tagName).toLowerCase();
              if (['hidden','submit','button','image'].includes(type)) return;
              const r = el.getBoundingClientRect();
              if (r.width === 0 && r.height === 0) return;
              out.fields.push({label: labelFor(el), name: el.name||'', id: el.id||'', type, placeholder: el.placeholder||'', value: (type==='password'?'':(el.value||'')).slice(0,40), required: !!el.required});
            });
            document.querySelectorAll('button, input[type=submit], a[role=button], [role=button]').forEach(el => {
              const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
              if (t) out.buttons.push(t.slice(0,50));
            });
            return JSON.stringify(out);
            '''
            import json as _json
            data = driver.execute_script(js)
            parsed = _json.loads(data) if isinstance(data, str) else (data or {})
            buttons = list(dict.fromkeys(parsed.get('buttons', [])))[:25]
            fields = parsed.get('fields', [])[:60]
            return {"status": "ok", "url": parsed.get('url'), "title": parsed.get('title'),
                    "fields": fields, "buttons": buttons,
                    "message": f"{len(fields)} field(s) and {len(buttons)} button(s) on the page"}

        elif action in ("fill_field", "fill", "set_field"):
            field = args.get("field") or args.get("label") or args.get("name") or args.get("selector") or ""
            value = args.get("value", args.get("text", ""))
            if not field:
                return {"status": "error", "message": "field (label/name/placeholder) required"}
            el = _find_input(driver, field)
            if not el:
                return {"status": "error", "message": f"Couldn't find a field matching '{field}'"}
            _fill_element(driver, el, value)
            time.sleep(0.4)
            return {"status": "ok", "message": f"Filled '{field}'"}

        elif action in ("upload_file", "attach_file", "upload", "attach"):
            file_path = args.get("file_path") or args.get("path") or args.get("file") or ""
            field = args.get("field") or args.get("label") or args.get("selector") or ""
            if not file_path or not os.path.isfile(file_path):
                return {"status": "error", "message": f"file_path required and must exist: {file_path}"}
            el = _find_file_input(driver, field)
            if not el:
                return {"status": "error", "message": "No file-upload field found on this page"}
            try:
                driver.execute_script("arguments[0].scrollIntoView();", el)
            except Exception:
                pass
            el.send_keys(os.path.abspath(file_path))
            time.sleep(1)
            return {"status": "ok", "message": f"Uploaded {os.path.basename(file_path)}"}

        elif action in ("click_text", "click_button", "press"):
            label = args.get("text") or args.get("label") or args.get("button") or ""
            if not label:
                return {"status": "error", "message": "text/label of the button or link to click is required"}
            el = _find_clickable_by_text(driver, label)
            if not el:
                return {"status": "error", "message": f"Couldn't find a button/link labeled '{label}'"}
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.4)
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            time.sleep(2)
            return {"status": "ok", "message": f"Clicked '{label}'", "current_url": driver.current_url}

        elif action in ("fill_form", "fill_and_submit"):
            fields = args.get("fields") or {}
            if isinstance(fields, str):
                try:
                    import json as _json
                    fields = _json.loads(fields)
                except Exception:
                    fields = {}
            file_path = args.get("file_path") or args.get("file") or ""
            file_field = args.get("file_field") or ""
            do_submit = bool(args.get("submit", False))
            submit_text = args.get("submit_text") or "submit"
            filled, missed = [], []
            for k, v in (fields or {}).items():
                el = _find_input(driver, k)
                if el:
                    _fill_element(driver, el, v); filled.append(k)
                else:
                    missed.append(k)
                time.sleep(0.2)
            uploaded = None
            if file_path and os.path.isfile(file_path):
                fel = _find_file_input(driver, file_field)
                if fel:
                    try:
                        fel.send_keys(os.path.abspath(file_path)); uploaded = os.path.basename(file_path)
                    except Exception:
                        pass
            submitted = False
            if do_submit:
                bel = _find_clickable_by_text(driver, submit_text)
                if bel:
                    try:
                        bel.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", bel)
                    time.sleep(2); submitted = True
            msg = f"Filled {len(filled)} field(s)"
            if missed:
                msg += f"; couldn't find {len(missed)} ({', '.join(missed[:5])})"
            if uploaded:
                msg += f"; uploaded {uploaded}"
            if submitted:
                msg += "; submitted"
            return {"status": "ok", "filled": filled, "missed": missed, "uploaded": uploaded,
                    "submitted": submitted, "current_url": driver.current_url, "message": msg}

        elif action in ("wait_for", "wait_until", "wait"):
            target = args.get("selector") or args.get("text") or args.get("for") or ""
            secs = int(args.get("timeout", 15) or 15)
            if not target:
                time.sleep(min(secs, 5))
                return {"status": "ok", "message": f"Waited {min(secs, 5)}s"}
            deadline = time.time() + secs
            found = False
            while time.time() < deadline:
                try:
                    if target.strip()[0] in "#.[":
                        els = driver.find_elements(By.CSS_SELECTOR, target)
                        if els and any(e.is_displayed() for e in els):
                            found = True
                            break
                    else:
                        body = driver.find_element(By.TAG_NAME, "body").text or ""
                        if target.lower() in body.lower():
                            found = True
                            break
                except Exception:
                    pass
                time.sleep(0.5)
            return {"status": "ok" if found else "timeout",
                    "message": (f"'{target}' appeared" if found else f"'{target}' didn't appear within {secs}s")}

        elif action in ("get_text", "read_text", "page_text"):
            try:
                txt = driver.find_element(By.TAG_NAME, "body").text or ""
            except Exception:
                txt = ""
            return {"status": "ok", "url": driver.current_url, "title": driver.title,
                    "text": txt[:4000], "message": f"Read {len(txt)} characters from the page"}

        elif action in ("current", "where", "current_url", "current_tab"):
            return {"status": "ok", "current_url": driver.current_url, "title": driver.title,
                    "message": f"Currently on \"{driver.title}\" — {driver.current_url}"}

        elif action in ("list_tabs", "tabs", "get_tabs"):
            handles = driver.window_handles
            cur = driver.current_window_handle
            tabs = []
            for i, h in enumerate(handles):
                try:
                    driver.switch_to.window(h)
                    tabs.append({"index": i, "title": driver.title, "url": driver.current_url,
                                 "active": (h == cur)})
                except Exception:
                    tabs.append({"index": i, "title": "(unavailable)", "url": "", "active": (h == cur)})
            try:
                driver.switch_to.window(cur)  # restore the originally-active tab
            except Exception:
                pass
            listing = "; ".join(f"[{t['index']}] {t['title']}" + (" *" if t['active'] else "") for t in tabs)
            return {"status": "ok", "tabs": tabs, "count": len(tabs),
                    "message": f"{len(tabs)} tab(s) open: {listing}"}

        elif action in ("switch_tab", "select_tab", "goto_tab", "tab"):
            handles = driver.window_handles
            idx = args.get("index", args.get("tab"))
            match = str(args.get("title") or args.get("url") or args.get("text") or "").strip().lower()
            target = None
            if idx is not None and str(idx).strip() != "":
                try:
                    i = int(idx)
                    if -len(handles) <= i < len(handles):
                        target = handles[i]
                except Exception:
                    target = None
            if target is None and match:
                cur = driver.current_window_handle
                for h in handles:
                    try:
                        driver.switch_to.window(h)
                        if match in (driver.title or "").lower() or match in (driver.current_url or "").lower():
                            target = h
                            break
                    except Exception:
                        pass
                if target is None:
                    try:
                        driver.switch_to.window(cur)
                    except Exception:
                        pass
            if target is None:
                return {"status": "error",
                        "message": "No matching tab — pass index (0-based) or a title/url substring. Use list_tabs to see them."}
            driver.switch_to.window(target)
            return {"status": "ok", "current_url": driver.current_url, "title": driver.title,
                    "message": f"Switched to \"{driver.title}\""}

        elif action in ("new_tab", "open_tab"):
            before = set(driver.window_handles)
            try:
                driver.switch_to.new_window('tab')
            except Exception:
                driver.execute_script("window.open('about:blank','_blank');")
                new = [h for h in driver.window_handles if h not in before]
                if new:
                    driver.switch_to.window(new[-1])
            if url:
                target = str(url).strip()
                from urllib.parse import quote_plus, urlparse
                import re
                if urlparse(target).scheme:
                    nav_url = target
                elif re.match(r"^(localhost|(\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)(:\d+)?(/.*)?$", target):
                    nav_url = "https://" + target
                else:
                    nav_url = "https://www.google.com/search?q=" + quote_plus(target)
                driver.get(nav_url)
                time.sleep(1)
            return {"status": "ok", "current_url": driver.current_url, "title": driver.title,
                    "count": len(driver.window_handles),
                    "message": f"Opened a new tab ({len(driver.window_handles)} now open)"}

        elif action in ("close_tab",):
            if len(driver.window_handles) <= 1:
                return {"status": "error",
                        "message": "Only one tab is open — use action=close to end the whole browser session instead."}
            driver.close()
            driver.switch_to.window(driver.window_handles[-1])
            return {"status": "ok", "current_url": driver.current_url, "title": driver.title,
                    "count": len(driver.window_handles),
                    "message": f"Closed the tab; now on \"{driver.title}\""}

        elif action in ("check_access", "detect_blockers", "check_captcha", "is_blocked"):
            # HONEST detection only. AVA never solves CAPTCHAs — she reports them so the user can.
            js = r'''
            const out = {captcha:false, captcha_kind:'', login_wall:false, signals:[]};
            const ifr = [...document.querySelectorAll('iframe')].map(f => (f.getAttribute('src')||'').toLowerCase());
            const html = (document.documentElement.innerHTML || '').toLowerCase();
            if (ifr.some(s => s.includes('recaptcha'))) { out.captcha=true; out.captcha_kind='reCAPTCHA'; }
            else if (ifr.some(s => s.includes('hcaptcha'))) { out.captcha=true; out.captcha_kind='hCaptcha'; }
            else if (document.querySelector('.cf-turnstile, iframe[src*="challenges.cloudflare.com"], #challenge-form, #cf-challenge-running, iframe[src*="turnstile"]')) { out.captcha=true; out.captcha_kind='Cloudflare'; }
            else if (/i'?m not a robot|verify (you are|that you are) (a )?human|are you a robot|complete the captcha|press *(and|&) *hold|unusual traffic/.test(html)) { out.captcha=true; out.captcha_kind='challenge'; }
            const pw = document.querySelector('input[type=password]');
            const head = (document.body ? document.body.innerText : '').toLowerCase().slice(0, 4000);
            if (pw) { out.login_wall=true; out.signals.push('password field'); }
            else if (/\b(sign in|log in|login|sign-in)\b/.test(head)) { out.signals.push('sign-in text'); }
            out.title = document.title; out.url = location.href;
            return JSON.stringify(out);
            '''
            import json as _json
            data = driver.execute_script(js)
            parsed = _json.loads(data) if isinstance(data, str) else (data or {})
            msgs = []
            if parsed.get('captcha'):
                msgs.append(f"a {parsed.get('captcha_kind') or 'CAPTCHA'} challenge is on the page — I can't solve CAPTCHAs, so you'll need to complete it")
            if parsed.get('login_wall'):
                msgs.append("a sign-in / password wall is present — you'll need to log in")
            if not msgs:
                msgs.append("no CAPTCHA or login wall detected — the page looks accessible")
            return {"status": "ok", "captcha": bool(parsed.get('captcha')),
                    "captcha_kind": parsed.get('captcha_kind', ''),
                    "login_wall": bool(parsed.get('login_wall')),
                    "current_url": parsed.get('url'), "title": parsed.get('title'),
                    "message": "; ".join(msgs)}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Browser automation error: {str(e)}"}

TOOL = Tool(
    name="browser_automation",
    summary=("Drive a real (stealth, signed-in) Chrome to complete tasks on ANY website — forms, "
             "applications, portals. WORKFLOW to fill something out: (1) action=navigate url=<page>. "
             "(2) action=get_fields — returns the page's fields (label/name/type) and buttons, so you "
             "target real fields and never guess. (3) action=fill_form with fields={\"<label or name>\":\"<value>\", ...} "
             "(matched fuzzily by label/placeholder/name); add file_path=<full path> to upload an attachment "
             "(e.g. a resume), and submit=true + submit_text=<button label> to submit. Or step by step: "
             "fill_field (field,value), upload_file (file_path), click_text (text). If the file is in Gmail, "
             "download it first with comm_ops download_attachment, then pass its path here. For pages that load "
             "dynamically use wait_for (selector or text); use get_text to READ the page's instructions/errors. "
             "TABS: list_tabs (see all open tabs with index/title/url), switch_tab (index=N or title/url substring), "
             "new_tab (optional url), close_tab. current — confirm which page/URL you're actually on. "
             "check_access — detect a CAPTCHA or login wall BEFORE acting (it reports them honestly; AVA never "
             "solves CAPTCHAs, she tells the user to). Also: navigate, click (CSS), type (CSS), close (ends session)."),
    plan=_plan,
    run=lambda args, dry_run: (_lazy(), _run(args, dry_run))[1],
    permissions={"confirm": False}
)

register(TOOL)
