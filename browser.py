import base64
from dataclasses import dataclass

from playwright.sync_api import Browser as PlaywrightBrowser, Page, sync_playwright


@dataclass
class BrowserState:
    screenshot_b64: str
    url: str


class Browser:
    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._playwright = None
        self._browser: PlaywrightBrowser | None = None
        self._page: Page | None = None
        self._headless = headless

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    def start(self, start_url: str = "https://www.google.com") -> BrowserState:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._page = self._browser.new_page(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        self._page.goto(start_url)
        return self.get_state()

    def get_state(self) -> BrowserState:
        screenshot_bytes = self.page.screenshot()
        return BrowserState(
            screenshot_b64=base64.b64encode(screenshot_bytes).decode("utf-8"),
            url=self.page.url,
        )

    def click(self, x: int, y: int) -> None:
        px_x = int(x * self.viewport_width / 1000)
        px_y = int(y * self.viewport_height / 1000)
        self.page.mouse.click(px_x, px_y)

    def scroll(self, x: int, y: int, direction: str) -> None:
        px_x = int(x * self.viewport_width / 1000)
        px_y = int(y * self.viewport_height / 1000)
        self.page.mouse.move(px_x, px_y)
        delta = -300 if direction == "up" else 300
        self.page.mouse.wheel(0, delta)

    def type_text(self, content: str) -> None:
        self.page.keyboard.type(content)

    def press_key(self, key: str) -> None:
        self.page.keyboard.press(key)

    def wait(self, ms: int = 1000) -> None:
        self.page.wait_for_timeout(ms)

    def close(self) -> None:
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __enter__(self) -> "Browser":
        return self

    def __exit__(self, *_args) -> None:
        self.close()
