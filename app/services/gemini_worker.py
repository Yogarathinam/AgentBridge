from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright

from app.config import GEMINI_URL, GOOGLE_LOGIN_URL, HEADLESS, PROFILE_DIR, REQUEST_TIMEOUT_SEC, SCRAPE_POLL_INTERVAL, SCRAPE_STABLE_POLLS


class GeminiWorker:
    def __init__(self, state):
        self.state = state
        self.playwright = None
        self.context = None
        self.page = None
        self.started = False
        self.browser_closed = False
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self.context:
            return
        if self.browser_closed:
            print('[gemini] browser was closed; restarting worker')
            self.browser_closed = False
        print('[gemini] starting browser worker')
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
        self.started = True
        self.state.update_status(browser_ready=True, last_info='Chromium worker started.')
        await self._safe_initial_state()

    async def start_login_browser(self) -> None:
        if self.context:
            await self.stop()
        print('[gemini] starting login browser')
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
        self.started = True
        self.state.update_status(browser_ready=True, last_info='Login browser opened.')
        await self.page.goto(GOOGLE_LOGIN_URL, wait_until='load')
        self.state.update_status(
            first_run=True,
            logged_in=False,
            last_info='Please sign in in the browser window.',
        )

    def _mark_closed(self):
        print('[gemini] browser context closed')
        self.browser_closed = True
        self.context = None
        self.page = None
        self.started = False
        self.state.update_status(browser_ready=False, logged_in=False, last_error='Browser closed.')

    async def _safe_initial_state(self) -> None:
        try:
            if not self.page:
                return

            saved_url = self.state.get_status().get('current_chat_url')
            if saved_url:
                print(f'[gemini] verifying saved session at {saved_url}')
                self.state.update_status(last_info='Verifying saved session...')
                await self.page.goto(saved_url, wait_until='load')
                
                logged_in = False
                for _ in range(10):
                    if await self._detect_logged_in():
                        logged_in = True
                        break
                    await asyncio.sleep(0.5)
                
                if logged_in:
                    print('[gemini] session valid, stayed on chat')
                    self.state.update_status(
                        logged_in=True, 
                        first_run=False, 
                        last_info='Logged in and session restored.'
                    )
                    return
                else:
                    print('[gemini] session invalid or redirected, prompting login')
            
            await self.open_login()
            logged_in = await self._detect_logged_in()
            self.state.update_status(
                logged_in=logged_in,
                first_run=not logged_in,
                last_info='Probing session validity in background...' if not logged_in else 'Logged in.'
            )
        except Exception as exc:
            print(f'[gemini] initial state check failed: {exc}')

    async def ensure_started(self) -> bool:
        if self.browser_closed:
            self.state.update_status(browser_ready=False, logged_in=False, last_error='Browser was closed. Click Open Login to reopen.')
            return False
        if not self.context:
            return False
        return True

    async def stop(self) -> None:
        print('[gemini] stopping browser worker')
        try:
            if self.context:
                await self.context.close()
        finally:
            self.context = None
            self.page = None
            self.started = False
            self.browser_closed = False
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            self.state.update_status(browser_ready=False, logged_in=False)

    async def open_login(self) -> None:
        print('[gemini] open login')
        await self.start_login_browser()

    async def open_gemini(self) -> None:
        if not await self.ensure_started():
            await self.start()
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        print('[gemini] open gemini')
        await self._open_preferred_chat()
        await self.check_login()

    async def new_chat(self) -> None:
        if not await self.ensure_started():
            await self.start()
        if not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        print('[gemini] new chat')
        await self.page.goto(GEMINI_URL, wait_until='load')
        self.state.update_status(current_chat_url=None, last_info='Opened fresh Gemini app page for a new chat.')
        self.state.clear_messages()

    async def check_login(self) -> bool:
        if self.browser_closed:
            self.state.update_status(browser_ready=False, logged_in=False, last_error='Browser closed. Click Open Login to reopen.')
            print('[gemini] check_login: browser closed')
            return False
        if not self.context or not self.page:
            self.state.update_status(last_info='Browser not started yet. Click Open Login.', logged_in=False)
            print('[gemini] check_login without browser -> False')
            return False
        try:
            logged_in = await self._detect_logged_in()
            print(f'[gemini] login check logged_in={logged_in} url={self.page.url}')
            self.state.update_status(logged_in=logged_in, first_run=not logged_in, last_info=('Logged in.' if logged_in else 'Not logged in.'))
            return logged_in
        except Exception as exc:
            self.state.update_status(last_error=str(exc), last_info='')
            print(f'[gemini] check_login failed: {exc}')
            return False

    async def _detect_logged_in(self) -> bool:
        if not self.page:
            return False
        try:
            url = self.page.url.lower()
            if 'myaccount.google.com/?utm_source=sign_in_no_continue&pli=1' in url:
                return True
            if 'accounts.google.com' in url:
                return False
            if 'gemini.google.com' not in url and 'myaccount.google.com' not in url:
                return False
            body = await self.page.locator('body').inner_text(timeout=2000)
            text = ' '.join(body.lower().split())
            bad_markers = [
                'sign in', 'sign in to google', 'create account', 'choose an account',
                'couldn’t sign you in', 'couldnt sign you in', 'this browser or app may not be secure',
                'try using a different browser', 'not logged in', 'finish signing in', 'something went wrong'
            ]
            good_markers = [
                'new chat', 'gemini', 'ask gemini', 'prompt', 'message', 'chat', 'help me',
                'you said', 'conversation', 'draft', 'generate', 'myaccount.google.com/?utm_source=sign_in_no_continue&pli=1'
            ]
            if any(m in text for m in bad_markers):
                return False
            if any(m in text for m in good_markers):
                return True
            return 'myaccount.google.com/?utm_source=sign_in_no_continue&pli=1' in url or ('accounts.google.com' not in url and ('gemini.google.com' in url or 'myaccount.google.com' in url))
        except Exception:
            url = self.page.url.lower()
            return 'myaccount.google.com/?utm_source=sign_in_no_continue&pli=1' in url or ('accounts.google.com' not in url and ('gemini.google.com' in url or 'myaccount.google.com' in url))

    async def ask(self, prompt: str) -> dict:
        if not self.context or not self.page:
            raise RuntimeError('BROWSER_NOT_READY')
        if self.browser_closed:
            raise RuntimeError('BROWSER_CLOSED')
        if not await self.check_login():
            raise RuntimeError('LOGIN_REQUIRED')
        await self._open_preferred_chat()
        self.state.add_message('user', prompt)
        print(f'[gemini] ask prompt={prompt[:120]!r}')
        await self._type_prompt(prompt)
        await self._submit_prompt()
        text = await self._wait_for_response()
        await self._capture_chat_url_if_any()
        self.state.add_message('assistant', text)
        print(f'[gemini] got response chars={len(text)}')
        return {'text': text, 'chat_url': self.state.get_status().get('current_chat_url')}

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

    async def _wait_for_response(self) -> str:
        deadline = asyncio.get_event_loop().time() + REQUEST_TIMEOUT_SEC
        previous = ''
        stable_hits = 0
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(SCRAPE_POLL_INTERVAL)
            text = await self._extract_response_once()
            if text and text == previous:
                stable_hits += 1
            elif text:
                previous = text
                stable_hits = 0
            if previous and stable_hits >= SCRAPE_STABLE_POLLS:
                return previous
        raise RuntimeError('SCRAPE_FAILED')

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