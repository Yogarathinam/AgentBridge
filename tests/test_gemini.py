import asyncio
import hashlib
import re
from dataclasses import dataclass

class FakeState:
    def __init__(self):
        self.status = {'current_chat_url': None}
        self.messages = []
    def update_status(self, **kwargs):
        self.status.update(kwargs)
    def get_status(self):
        return dict(self.status)
    def add_message(self, role, text):
        self.messages.append((role, text))
    def clear_messages(self):
        self.messages = []

@dataclass
class FakePage:
    responses: list[str]
    idx: int = -1
    url: str = 'https://gemini.google.com/app'
    async def goto(self, target, wait_until='load'):
        self.url = target
    async def evaluate(self, script, args=None):
        self.idx = min(self.idx + 1, len(self.responses) - 1)
        return {'ok': True, 'text': self.responses[self.idx]}

class TestWorker:
    def __init__(self, responses):
        self.state = FakeState()
        self.page = FakePage(responses)
        self._last_response_fingerprint = ''
    def _fingerprint(self, text: str) -> str:
        normalized = re.sub(r'\s+', ' ', (text or '')).strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else ''
    async def _extract_response_once(self) -> str:
        result = await self.page.evaluate('')
        return str(result.get('text') or '').strip() if result.get('ok') else ''
    async def _wait_for_new_response(self, baseline_fp: str) -> str:
        previous = ''
        previous_fp = ''
        stable_hits = 0
        for _ in range(20):
            text = await self._extract_response_once()
            fp = self._fingerprint(text)
            if not text:
                await asyncio.sleep(0)
                continue
            if fp == baseline_fp:
                await asyncio.sleep(0)
                continue
            if fp == previous_fp:
                stable_hits += 1
            else:
                previous = text
                previous_fp = fp
                stable_hits = 0
            if previous and stable_hits >= 1:
                return previous
            await asyncio.sleep(0)
        raise RuntimeError('SCRAPE_FAILED')

async def run_case(name, responses, expected=None, should_fail=False):
    w = TestWorker(responses)
    baseline = w._fingerprint(responses[0] if responses else '')
    try:
        out = await w._wait_for_new_response(baseline)
        ok = (not should_fail) and out == expected
        print(f'{name}:', 'PASS' if ok else f'FAIL got={out!r} expected={expected!r}')
    except Exception as e:
        ok = should_fail
        print(f'{name}:', 'PASS' if ok else f'FAIL {e}')

async def main():
    await run_case('new response after old', ['old answer', 'old answer', 'new answer', 'new answer'], expected='new answer')
    await run_case('same old only', ['old answer', 'old answer', 'old answer'], should_fail=True)
    await run_case('whitespace same ignored', ['Old   Answer', 'old answer', 'old answer'], should_fail=True)
    await run_case('longer response accepted', ['a', 'a', 'b'*1000, 'b'*1000], expected='b'*1000)

asyncio.run(main())