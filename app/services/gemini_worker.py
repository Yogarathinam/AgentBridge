from __future__ import annotations

import asyncio
import hashlib
import re
from playwright.async_api import async_playwright

from app.config import GEMINI_URL, GOOGLE_LOGIN_URL, PROFILE_DIR, REQUEST_TIMEOUT_SEC, SCRAPE_POLL_INTERVAL, SCRAPE_STABLE_POLLS, ENABLE_CLOUD, APP_VERSION, API_BASE_URL
from app.state import AppState


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
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

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
        await self.check_google_login_headless()

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
        while self.context and not self.browser_closed and self.mode == 'visible_login':
            await asyncio.sleep(1)
        if self.mode == 'stopped':
            return
        print('[gemini] visible login closed')
        print('[gemini] rechecking headless auth after visible close')
        await self.start()
        gemini_ready = self.mode == 'headless_ready'
        print(f'[gemini] gemini ready={gemini_ready}')

    async def _close_context_only(self):
        print('[gemini] closing headless context intentionally')
        self._intentional_close = True
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        self.context = None
        self.page = None
        self.browser_closed = True

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
        await self.page.goto(GEMINI_URL, wait_until='load')
        self.state.update_status(current_chat_url=None, last_info='Opened fresh Gemini app page for a new chat.')
        self.state.clear_messages()
        self._last_response_fingerprint = ''

    async def ask(self, prompt: str) -> dict:
        if self.mode == 'stopped' or not self.context or not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        if self.mode not in ('headless_ready', 'gemini_ready'):
            if not await self.check_google_login_headless():
                raise RuntimeError('LOGIN_REQUIRED')
        await self._open_preferred_chat()
        is_ready = await self.check_gemini_readiness()
        if is_ready:
            self.mode = 'gemini_ready'
        baseline = await self._get_latest_response_text()
        self._last_response_fingerprint = self._fingerprint(baseline)
        self.state.add_message('user', prompt)
        print(f"[gemini] ask prompt={prompt[:120]!r}")
        await self._type_prompt(prompt)
        await self._submit_prompt()
        try:
            text = await self._wait_for_new_response(self._last_response_fingerprint)
        except RuntimeError:
            await self._refresh_page()
            raise RuntimeError('TIMEOUT')
        await self._capture_chat_url_if_any()
        self.state.add_message('assistant', text)
        self._last_response_fingerprint = self._fingerprint(text)
        print(f'[gemini] got response chars={len(text)}')
        return {'text': text, 'chat_url': self.state.get_status().get('current_chat_url')}

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

    async def _capture_chat_url_if_any(self) -> None:
        if not self.page:
            return
        url = self.page.url
        if 'gemini.google.com' in url and '/app' in url and url != GEMINI_URL:
            self.state.update_status(current_chat_url=url, last_info='Active Gemini chat saved.')
            print(f'[gemini] saved chat url={url}')

    def _fingerprint(self, text: str) -> str:
        normalized = re.sub(r'\s+', ' ', (text or '')).strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else ''

    async def _get_latest_response_text(self) -> str:
        if not self.page:
            return ''
        return await self._extract_response_once()

    async def _wait_for_new_response(self, baseline_fp: str) -> str:
        deadline = asyncio.get_event_loop().time() + REQUEST_TIMEOUT_SEC
        previous = ''
        previous_fp = ''
        stable_hits = 0
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(SCRAPE_POLL_INTERVAL)
            text = await self._extract_response_once()
            fp = self._fingerprint(text)
            if not text:
                continue
            if fp == baseline_fp:
                continue
            if fp == previous_fp:
                stable_hits += 1
            else:
                previous = text
                previous_fp = fp
                stable_hits = 0
            if previous and stable_hits >= SCRAPE_STABLE_POLLS:
                return previous
        raise RuntimeError('SCRAPE_FAILED')

    async def _type_prompt(self, prompt: str) -> None:
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        script = """
        ([promptText]) => {
            const selectors = ['textarea','[contenteditable="true"]','[role="textbox"]','div[contenteditable="true"]','rich-textarea textarea','textarea[aria-label]'];
            let box = null;
            for (const sel of selectors) {
                for (const el of Array.from(document.querySelectorAll(sel))) {
                    if (el && el.offsetParent !== null && !el.disabled) { box = el; break; }
                }
                if (box) break;
            }
            if (!box) return { ok: false, error: 'No input box found' };
            box.focus();
            box.click();
            const tag = (box.tagName || '').toLowerCase();
            if (tag === 'textarea' || 'value' in box) {
                box.value = '';
                box.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                box.value = promptText;
                box.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                box.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
            } else {
                box.textContent = '';
                box.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, data: '', inputType: 'deleteContentBackward' }));
                box.textContent = promptText;
                box.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, data: promptText, inputType: 'insertText' }));
                box.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
            }
            return { ok: true, typed: true, tag };
        }
        """
        result = await self.page.evaluate(script, [prompt])
        if not result.get('ok'):
            raise RuntimeError(result.get('error') or 'TYPE_FAILED')

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
            return { ok: false, error: 'No send button or active element found' };
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
            const noiseExact = new Set(['Sign in','Gemini','About Gemini','Opens in a new window','Gemini App','Subscriptions','For Business','Conversation with Gemini','You said','Gemini said','Tools','Fast','Gemini is AI and can make mistakes.','Show more']);
            function cleanText(text) {
                return (text || '').split('\\n').map(x => x.trim()).filter(x => x && !noiseExact.has(x)).join('\\n').trim();
            }
            function visible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }
            const selectors = ['message-content','model-response','.message-content','.model-response','[data-message-author-role="assistant"]','[data-testid*="response"]','[role="main"] [data-message-author-role]','.markdown'];
            let candidates = [];
            for (const sel of selectors) {
                for (const node of Array.from(document.querySelectorAll(sel))) {
                    if (!visible(node)) continue;
                    const txt = cleanText(node.innerText || '');
                    if (txt && txt.length > 5) candidates.push({ text: txt, top: node.getBoundingClientRect().top });
                }
            }
            if (!candidates.length) return { ok: true, text: '' };
            candidates = candidates.filter((item, index, arr) => arr.findIndex(x => x.text === item.text) === index);
            candidates.sort((a, b) => b.top - a.top);
            return { ok: true, text: candidates[0].text };
        }
        """
        result = await self.page.evaluate(script)
        if not result.get('ok'):
            return ''
        return str(result.get('text') or '').strip()