from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
import datetime
import json
import time
import random
from playwright.async_api import async_playwright

from app.config import (
    GEMINI_URL, GOOGLE_LOGIN_URL, PROFILE_DIR, REQUEST_TIMEOUT_SEC, 
    SCRAPE_POLL_INTERVAL, SCRAPE_STABLE_POLLS, ENABLE_CLOUD, APP_VERSION, API_BASE_URL
)
from app.state import AppState

MAX_MESSAGES = 50

class GeminiWorker:
    def __init__(self, state):
        self.state = state
        self.playwright = None
        self.context = None
        self.page = None
        self.browser_closed = True
        self._intentional_close = False
        self.mode = 'stopped'
        self._last_response_fingerprint = ''
        
        # Priority 1: Queue requests instead of rejecting them
        self._request_lock = asyncio.Lock()
        
        # Priority 11: Hard Recovery Tracking
        self.chat_failure_count = 0
        
        self.messages_in_current_chat = 0
        self.telemetry = {
            "successful_requests": 0,
            "timeouts": 0,
            "page_reloads": 0,
            "new_chats": 0,
            "browser_restarts": 0
        }
        self._watchdog_task = None
        
        # Concurrency & Restart Management
        self.is_processing = False
        self.requests_since_restart = 0
        self._start_time = datetime.datetime.now()
        
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.diag_dir = PROFILE_DIR / "diagnostics"
        self.diag_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        print('[gemini] start() called.')
        if self.context:
            return
        self.mode = 'headless_checking'
        print('[gemini] mode=headless_checking.')
        print('[gemini] launching headless persistent context.')
        
        await self._close_context_only()
        
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
        browser = self.playwright.chromium
        self.context = await browser.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            channel='chrome',
            args=['--disable-blink-features=AutomationControlled'],
            ignore_default_args=['--enable-automation'],
            viewport={'width': 1440, 'height': 920},
        )
        self.context.on('close', lambda: self._mark_closed())
        pages = self.context.pages
        self.page = pages[0] if pages else await self.context.new_page()
        self.browser_closed = False
        self._intentional_close = False
        print('[gemini] headless page ready.')
        self.state.update_status(browser_ready=True, last_info='Chromium worker started.', cloud_enabled=bool(ENABLE_CLOUD))
        
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())

        await self.check_google_login_headless()

    async def _watchdog_loop(self):
        while not self.browser_closed:
            await asyncio.sleep(30)
            if self.is_processing:
                continue
                
            if self.mode in ('headless_ready', 'gemini_ready'):
                try:
                    is_healthy = await self._check_health_quietly()
                    if not is_healthy:
                        print("[watchdog] Unhealthy state detected. Recovering silently.")
                        await self._refresh_page()
                except Exception as e:
                    print(f"[watchdog] Error checking health: {e}")

    async def _check_health_quietly(self) -> bool:
        if not self.page:
            return False
        try:
            return await self.page.evaluate("""
                () => document.readyState === 'complete' && navigator.onLine
            """)
        except Exception:
            return False

    async def get_google_email(self):
        if not self.page:
            return None
        try:
            await self.page.goto('https://myaccount.google.com/', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            text = await self.page.locator('body').inner_text(timeout=5000)
            m = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text or '')
            return m.group(0) if m else None
        except Exception:
            return None

    async def check_google_login_headless(self) -> bool:
        if not self.page:
            return False
        print('[gemini] headless auth probe started')
        probe_url = 'https://myaccount.google.com/'
        print(f'[gemini] probe url={probe_url}')
        try:
            await self.page.goto(probe_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
        except Exception:
            pass
        final_url = self.page.url
        print(f'[gemini] probe final url={final_url}')
        logged_in = 'myaccount.google.com' in final_url and 'accounts.google.com' not in final_url
        print(f'[gemini] probe result logged_in={logged_in}')
        if logged_in:
            self.mode = 'headless_ready'
            email = await self.get_google_email()
            self.state.update_status(logged_in=True, first_run=False, last_info='Logged in and session restored.', user_email=email)
            if ENABLE_CLOUD and email:
                self.state.update_status(cloud_enabled=True)
        else:
            self.mode = 'auth_required'
            self.state.update_status(logged_in=False, first_run=True, last_info='Login required.')
        return logged_in

    async def check_gemini_readiness(self) -> bool:
        if not self.page:
            return False
        try:
            return bool(await self.page.evaluate("""
                () => {
                    const selectors = ['textarea', '[contenteditable="true"]', '[role="textbox"]', 'div[contenteditable="true"]'];
                    for (const sel of selectors) {
                        const els = Array.from(document.querySelectorAll(sel));
                        if (els.some(el => el && el.offsetParent !== null)) return true;
                    }
                    return false;
                }
            """))
        except Exception:
            return False

    async def check_login(self) -> bool:
        return await self.check_google_login_headless()

    async def open_login(self) -> None:
        print('[gemini] open_login() called.')
        print('[gemini] auth probe before opening visible browser.')
        if self.mode == 'stopped' or not self.context:
            await self.start()
        else:
            await self.check_google_login_headless()
            
        if self.mode == 'headless_ready':
            return
            
        print('[gemini] opening visible login')
        self.mode = 'visible_login'
        
        # Completely terminate engine to release SingletonLock
        await self._close_context_only()
        
        print('[gemini] launching visible persistent context.')
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
        browser = self.playwright.chromium
        self.context = await browser.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel='chrome',
            args=['--disable-blink-features=AutomationControlled'],
            ignore_default_args=['--enable-automation'],
            viewport={'width': 1440, 'height': 920},
        )
        self.context.on('close', lambda: self._mark_closed())
        pages = self.context.pages
        self.page = pages[0] if pages else await self.context.new_page()
        self.browser_closed = False
        self._intentional_close = False
        self.state.update_status(browser_ready=True, last_info='Please sign in in the browser window.')
        print('[gemini] login page opened.')
        
        try:
            await self.page.goto(GOOGLE_LOGIN_URL, wait_until='load')
        except Exception:
            pass
            
        # Dynamic polling loop: Detects login success and auto-closes!
        while self.context and not self.browser_closed and self.mode == 'visible_login':
            try:
                if self.page and not self.page.is_closed():
                    url = self.page.url
                    if 'myaccount.google.com' in url and 'accounts.google.com' not in url:
                        print('[gemini] Login success detected automatically! Closing browser.')
                        break
            except Exception:
                pass
            await asyncio.sleep(1)
            
        if self.mode == 'stopped':
            return
            
        print('[gemini] visible login closed')
        print('[gemini] forcing graceful teardown to permanently save cookies...')
        
        # Critically important to flush cookies to disk
        await self._close_context_only()
        
        print('[gemini] restarting headless auth after visible close')
        await self.start()
        gemini_ready = self.mode == 'headless_ready'
        print(f'[gemini] gemini ready={gemini_ready}')

    async def _close_context_only(self):
        """Tears down everything including the Playwright engine to force cookie writing and lock releasing."""
        print('[gemini] closing context intentionally to release profile locks')
        self._intentional_close = True
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
            
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
            
        self.context = None
        self.page = None
        self.playwright = None
        self.browser_closed = True
        
        # Give OS time to write cookies to sqlite DB and remove SingletonLock
        await asyncio.sleep(1.5)

    def _mark_closed(self):
        print('[gemini] context close event fired.')
        print(f'[gemini] intentional_close={self._intentional_close}.')
        print(f'[gemini] mode at close={self.mode}.')
        recovery_needed = not self._intentional_close and self.mode in ('headless_checking', 'headless_ready', 'gemini_ready')
        print(f'[gemini] recovery needed={recovery_needed}.')
        self.browser_closed = True
        self.context = None
        self.page = None
        if self._intentional_close:
            self._intentional_close = False
            return
        if self.mode != 'visible_login' and self.mode != 'stopped':
            self.state.update_status(browser_ready=False, last_error='Browser closed unexpectedly.')

    async def stop(self) -> None:
        print('[gemini] stop() called.')
        print('[gemini] close all resources intentionally.')
        self.mode = 'stopped'
        self._intentional_close = True
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.context = None
        self.page = None
        self.playwright = None
        self.browser_closed = True
        self.state.update_status(browser_ready=False, logged_in=False)
        print('[gemini] worker stopped.')

    async def open_gemini(self) -> None:
        if self.mode == 'stopped' or not self.context:
            await self.start()
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        print('[gemini] open gemini')
        await self._open_preferred_chat()
        await self.check_google_login_headless()

    async def new_chat(self) -> None:
        if self.mode == 'stopped' or not self.context:
            await self.start()
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        print('[gemini] new chat')
        self.telemetry['new_chats'] += 1
        self.messages_in_current_chat = 0
        await self.page.goto(GEMINI_URL, wait_until='load')
        self.state.update_status(current_chat_url=None, last_info='Opened fresh Gemini app page for a new chat.')
        self.state.clear_messages()
        self._last_response_fingerprint = ''

    async def _ensure_page_healthy(self, request_id: str) -> None:
        if not self.page:
            raise RuntimeError("PAGE_MISSING")
        healthy = await self.page.evaluate("""
            () => {
                return document.readyState === 'complete' && 
                       navigator.onLine && 
                       window.location.href.includes('gemini');
            }
        """)
        if not healthy:
            print(f"[{request_id}] Page unhealthy! Triggering reload.")
            self.telemetry['page_reloads'] += 1
            await self._refresh_page()
            await asyncio.sleep(2)

    async def _get_ui_state(self) -> dict:
        if not self.page:
            return {'isGenerating': False, 'messageCount': 0, 'latestLen': 0, 'inputTextLen': 0, 'hasStopButton': False, 'textboxText': '', 'hasGeminiError': False}
        script = """
        () => {
            const stopSelectors = ['button[aria-label*="Stop"]', 'button[mattooltip*="Stop"]', 'button[aria-label*="Pause"]', '.generating-indicator'];
            let hasStopButton = false;
            for (const sel of stopSelectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) { hasStopButton = true; break; }
            }

            const msgs = Array.from(document.querySelectorAll('message-content, model-response, [data-message-author-role="assistant"]')).filter(el => el.offsetParent !== null);
            let latestLen = 0;
            if (msgs.length > 0) {
                latestLen = (msgs[msgs.length - 1].innerText || '').trim().length;
            }

            const inputSelectors = ['textarea', '[contenteditable="true"]', '[role="textbox"]'];
            let inputTextLen = 0;
            let textboxText = "";
            for (const sel of inputSelectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) {
                    textboxText = (el.value || el.textContent || '').trim();
                    inputTextLen = textboxText.length;
                    break;
                }
            }

            const bodyText = document.body.innerText || "";
            const errorTexts = ["Something went wrong", "Unable to generate", "Try again", "An error occurred"];
            const hasGeminiError = errorTexts.some(err => bodyText.includes(err));

            return {
                isGenerating: hasStopButton,
                hasStopButton: hasStopButton,
                messageCount: msgs.length,
                latestLen: latestLen,
                inputTextLen: inputTextLen,
                textboxText: textboxText,
                hasResponseContent: latestLen > 0,
                pageTextLength: bodyText.length,
                hasGeminiError: hasGeminiError
            };
        }
        """
        try:
            return await self.page.evaluate(script)
        except Exception:
            return {'isGenerating': False, 'messageCount': 0, 'latestLen': 0, 'inputTextLen': 0, 'hasStopButton': False, 'textboxText': '', 'hasGeminiError': False}

    async def debug_dump_ui(self, request_id: str):
        if not self.page:
            return
        try:
            data = await self.page.evaluate("""
            () => {
                return {
                    url: location.href,
                    buttons: Array.from(document.querySelectorAll("button"))
                        .filter(b => b.offsetParent !== null)
                        .map(b => ({
                            text: (b.innerText || "").trim(),
                            aria: b.getAttribute("aria-label"),
                            title: b.getAttribute("title")
                        })),
                    bodyPreview: document.body.innerText.slice(0, 1000)
                };
            }
            """)
            print(f"[{request_id}] UI DUMP")
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[{request_id}] dump failed: {e}")

    async def _capture_snapshot(self, request_id: str):
        if not self.page:
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = self.diag_dir / f"failure_{timestamp}_{request_id}"
            await self.page.screenshot(path=f"{base_name}.png")
            with open(f"{base_name}.html", "w", encoding="utf-8") as f:
                f.write(await self.page.content())
            print(f"[{request_id}] Snapshot saved: {base_name}.png")
        except Exception as e:
            print(f"[{request_id}] Snapshot capture failed: {e}")

    async def ask(self, prompt: str) -> dict:
        async with self._request_lock:
            return await self._ask_impl(prompt)

    async def _ask_impl(self, prompt: str) -> dict:
        request_id = uuid.uuid4().hex[:8]
        print(f"[{request_id}] ask start")
        
        if self.mode == 'stopped' or not self.context or not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
            
        if self.mode not in ('headless_ready', 'gemini_ready'):
            if not await self.check_google_login_headless():
                raise RuntimeError('LOGIN_REQUIRED')
                
        uptime_seconds = (datetime.datetime.now() - self._start_time).total_seconds()
        if self.requests_since_restart >= 100 or uptime_seconds > (6 * 3600):
            print(f"[{request_id}] Auto-restarting browser context (requests: {self.requests_since_restart}, uptime: {uptime_seconds/3600:.2f}h)")
            self.telemetry['browser_restarts'] += 1
            await self.stop()
            await self.start()
            self.requests_since_restart = 0
            self._start_time = datetime.datetime.now()

        if self.messages_in_current_chat >= MAX_MESSAGES:
            print(f"[{request_id}] MAX_MESSAGES exceeded. Rotating chat automatically.")
            await self.new_chat()

        self.state.add_message('user', prompt)
        
        self.is_processing = True
        try:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                print(f"[{request_id}] --- Attempt {attempt}/{max_attempts} ---")
                try:
                    await self._ensure_page_healthy(request_id)
                    print(f"[{request_id}] open chat")
                    await self._open_preferred_chat()
                    
                    is_ready = await self.check_gemini_readiness()
                    if is_ready:
                        self.mode = 'gemini_ready'
                    
                    baseline_state = await self._get_ui_state()
                    print(f"[{request_id}] baseline captured: msgs={baseline_state['messageCount']} len={baseline_state['latestLen']}")
                    
                    print(f"[{request_id}] prompt typed")
                    await self._type_prompt(prompt)
                    
                    state = await self._get_ui_state()
                    if not state['textboxText'].strip():
                        print(f"[{request_id}] Type verification missed. Retrying type...")
                        await self._type_prompt(prompt)
                        state = await self._get_ui_state()
                        if not state['textboxText'].strip():
                            raise RuntimeError("PROMPT_NOT_TYPED")
                    
                    print(f"[{request_id}] prompt submitted")
                    await self._submit_prompt()
                    
                    await asyncio.sleep(1)
                    post_submit_state = await self._get_ui_state()
                    if post_submit_state['inputTextLen'] > 0 and not post_submit_state['hasStopButton'] and post_submit_state['messageCount'] == baseline_state['messageCount']:
                        print(f"[{request_id}] Submit missed! Pressing enter again...")
                        await self._submit_prompt()
                        await asyncio.sleep(1.5)
                        post_submit_state2 = await self._get_ui_state()
                        if post_submit_state2['inputTextLen'] > 0 and not post_submit_state2['hasStopButton'] and post_submit_state2['messageCount'] == baseline_state['messageCount']:
                            raise RuntimeError("PROMPT_NOT_SUBMITTED")
                    
                    print(f"[{request_id}] waiting response")
                    text = await self._wait_for_new_response(request_id, baseline_state['messageCount'], baseline_state['latestLen'])
                    
                    print(f"[{request_id}] FINAL_EXTRACTED = {repr(text)}")
                    
                    if len(text) < 3:
                        raise RuntimeError("RESPONSE_TOO_SHORT")
                        
                    await self._capture_chat_url_if_any(request_id)
                    self.state.add_message('assistant', text)
                    self.messages_in_current_chat += 1
                    self.requests_since_restart += 1
                    self.telemetry['successful_requests'] += 1
                    self.chat_failure_count = 0 
                    
                    print(f"[{request_id}] completed")
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    return {'text': text, 'chat_url': self.state.get_status().get('current_chat_url')}
                    
                except Exception as e:
                    err_msg = str(e)
                    print(f"[{request_id}] ❌ Error on attempt {attempt}: {err_msg}")
                    
                    fail_state = await self._get_ui_state()
                    print(f"[{request_id}] UI State on Failure -> msgs={fail_state['messageCount']} gen={fail_state['isGenerating']} len={fail_state['latestLen']} err={fail_state['hasGeminiError']}")
                    
                    await self._capture_snapshot(request_id)
                    self.chat_failure_count += 1
                    
                    if self.chat_failure_count >= 3:
                        print(f"[{request_id}] Chat failure count >= 3. Hard recovery.")
                        await self.new_chat()
                        self.chat_failure_count = 0
                        continue
                    
                    if attempt == 1:
                        await self.debug_dump_ui(request_id)
                    
                    if "PROMPT_NOT_TYPED" in err_msg:
                        print(f"[{request_id}] Recovery Action: Retyping (skipping reload)")
                        continue
                    elif "PROMPT_NOT_SUBMITTED" in err_msg:
                        print(f"[{request_id}] Recovery Action: Pressing enter again")
                        await self._submit_prompt()
                        continue
                    elif "GENERATION_NEVER_STARTED" in err_msg:
                        print(f"[{request_id}] Recovery Action: Click stop, wait 2s, resubmit")
                        try:
                            await self.page.evaluate("() => { const b = document.querySelector('button[aria-label*=\"Stop\"], button[mattooltip*=\"Stop\"], button[aria-label*=\"Pause\"]'); if(b) b.click(); }")
                        except: pass
                        await asyncio.sleep(2)
                        continue
                    elif "PROMPT_NOT_ACCEPTED" in err_msg or "GEMINI_ERROR" in err_msg:
                        print(f"[{request_id}] Recovery Action: Reloading and resending")
                        self.telemetry['page_reloads'] += 1
                        await self._refresh_page()
                    elif "GENERATION_STALLED" in err_msg:
                        print(f"[{request_id}] Recovery Action: Try stop button, reload, resend")
                        try:
                            await self.page.evaluate("() => { const b = document.querySelector('button[aria-label*=\"Stop\"], button[mattooltip*=\"Stop\"], button[aria-label*=\"Pause\"]'); if(b) b.click(); }")
                        except: pass
                        await asyncio.sleep(1)
                        self.telemetry['page_reloads'] += 1
                        await self._refresh_page()
                    elif "SCRAPE_TIMEOUT" in err_msg:
                        print(f"[{request_id}] Recovery Action: Forcing New Chat")
                        await self.new_chat()
                    else:
                        if attempt >= 4:
                            print(f"[{request_id}] Recovery Action: Restarting Browser Context")
                            self.telemetry['browser_restarts'] += 1
                            await self.stop()
                            await self.start()
                        else:
                            self.telemetry['page_reloads'] += 1
                            await self._refresh_page()

            self.telemetry['timeouts'] += 1
            raise RuntimeError('TIMEOUT')
        finally:
            self.is_processing = False

    async def _refresh_page(self) -> None:
        if not self.page:
            return
        try:
            await self.page.reload(wait_until='load')
        except Exception:
            try:
                await self.page.goto(self.page.url, wait_until='load')
            except Exception:
                pass

    async def _open_preferred_chat(self) -> None:
        current_chat = self.state.get_status().get('current_chat_url')
        target = current_chat or GEMINI_URL
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        if self.page.url != target:
            print(f'[gemini] navigating target={target}')
            await self.page.goto(target, wait_until='load')

    async def _capture_chat_url_if_any(self, request_id: str) -> None:
        if not self.page:
            return
        url = self.page.url
        if 'gemini.google.com' in url and '/app' in url and url != GEMINI_URL:
            self.state.update_status(current_chat_url=url, last_info='Active Gemini chat saved.')
            print(f'[{request_id}] chat url={url}')

    async def _wait_for_new_response(self, request_id: str, baseline_msg_count: int, baseline_latest_len: int) -> str:
        submit_time = time.monotonic()
        last_progress = time.monotonic()
        last_len = baseline_latest_len
        response_started = False
        
        deadline = time.monotonic() + REQUEST_TIMEOUT_SEC
        
        while time.monotonic() < deadline:
            await asyncio.sleep(SCRAPE_POLL_INTERVAL)
            state = await self._get_ui_state()
            
            print(f"[{request_id}] base_msgs={baseline_msg_count} base_len={baseline_latest_len} current_msgs={state['messageCount']} len={state['latestLen']} generating={state['isGenerating']} err={state['hasGeminiError']}")

            if state['hasGeminiError']:
                raise RuntimeError("GEMINI_ERROR")

            if state["messageCount"] > baseline_msg_count or state["latestLen"] > baseline_latest_len:
                response_started = True

            if time.monotonic() - submit_time > 8 and not response_started and not state['hasStopButton']:
                raise RuntimeError("PROMPT_NOT_ACCEPTED")
                
            if state['latestLen'] != last_len:
                last_len = state['latestLen']
                last_progress = time.monotonic()
            
            if not response_started and state["hasStopButton"] and time.monotonic() - submit_time > 45:
                raise RuntimeError("GENERATION_NEVER_STARTED")
                
            if response_started and state['hasStopButton'] and time.monotonic() - last_progress > 20:
                raise RuntimeError("GENERATION_STALLED")

            count_increased = state['messageCount'] > baseline_msg_count
            length_increased_significantly = (state['messageCount'] == baseline_msg_count) and (state['latestLen'] > baseline_latest_len + 15)

            if (count_increased or length_increased_significantly) and not state['isGenerating'] and state['latestLen'] > 0:
                print(f"[{request_id}] response found! Extracting final text...")
                text = await self._extract_response_once()
                if text and len(text) > 0:
                    return text
                    
        raise RuntimeError('SCRAPE_TIMEOUT')

    async def _type_prompt(self, prompt: str) -> None:
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
            
        selectors = [
            'rich-textarea textarea',
            'textarea[aria-label]',
            'textarea',
            '[contenteditable="true"]',
            '[role="textbox"]',
            'div[contenteditable="true"]'
        ]
        
        target_locator = None
        for sel in selectors:
            elements = await self.page.locator(sel).all()
            for el in elements:
                try:
                    if await el.is_visible() and await el.is_editable():
                        target_locator = el
                        break
                except Exception:
                    pass
            if target_locator:
                break
                
        if not target_locator:
            raise RuntimeError('TYPE_FAILED: No input box found')

        try:
            await target_locator.focus()
            await target_locator.click()
            await target_locator.fill(prompt)
        except Exception as e:
            raise RuntimeError(f'TYPE_FAILED: {str(e)}')

    async def _submit_prompt(self) -> None:
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        script = """
        () => {
            const buttonSelectors = ['button[aria-label*="Send"]','button[aria-label*="send"]','button[data-testid*="send"]','button[mattooltip*="Send"]','button[mattooltip*="send"]','button'];
            for (const sel of buttonSelectors) {
                for (const btn of Array.from(document.querySelectorAll(sel))) {
                    const txt = (btn.innerText || '').toLowerCase().trim();
                    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const title = (btn.getAttribute('title') || '').toLowerCase();
                    const disabled = btn.disabled || btn.getAttribute('aria-disabled') === 'true';
                    const looksLikeSend = aria.includes('send') || title.includes('send') || txt === 'send' || txt.includes('send message') || txt.includes('submit');
                    if (!disabled && (sel !== 'button' || looksLikeSend)) {
                        btn.focus(); btn.click(); return { ok: true };
                    }
                }
            }
            const active = document.activeElement;
            if (active) {
                active.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
                active.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
                return { ok: true };
            }
            return { ok: false, error: 'SUBMIT_FAILED: No send button or active element found' };
        }
        """
        result = await self.page.evaluate(script)
        if not result.get('ok'):
            raise RuntimeError(result.get('error') or 'SUBMIT_FAILED')

    async def _extract_response_once(self) -> str:
        if not self.page:
            return ''

        script = """
        () => {
            const responses = [];

            document.querySelectorAll('message-content').forEach((node, index) => {
                const txt = (node.innerText || '').trim();

                if (txt) {
                    responses.push({
                        index,
                        text: txt
                    });
                }
            });

            return {
                ok: true,
                responses
            };
        }
        """

        result = await self.page.evaluate(script)

        print("\n===== RESPONSES =====")
        print(json.dumps(result, indent=2))
        print("=====================\n")

        responses = result.get("responses", [])

        if not responses:
            return ""

        return responses[-1]["text"].strip()