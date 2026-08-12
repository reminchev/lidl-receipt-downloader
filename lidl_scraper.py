"""Ядро за изтегляне на касови бележки от lidl.bg чрез Playwright.

Работният поток използва ръчно влизане в браузъра (без съхранение на пароли):
приложението отваря браузър, потребителят влиза и се позиционира на
страницата с история на покупките, след което изтеглянето започва автоматично.
"""

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeout

LOGIN_URL = (
    "https://accounts.lidl.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3F"
    "country_code%3DBG%26response_type%3Dcode%26client_id%3Dbulgariaretailclient%26scope%3D"
    "openid%2520profile%2520Lidl.Authentication%2520offline_access%26state%3D7kjyF6Xd4NaMW"
    "mVqiNhXmDlKvTzcOa23tPkuFORkF2E%253D%26redirect_uri%3Dhttps%253A%252F%252Fwww.lidl.bg%252F"
    "user-api%252Fsignin-oidc%26nonce%3DEJIGNwoTYnT5BTScAf8yndJ6_tfF5V-ag26aqBsTg-8%26step%3D"
    "login%26language%3Dbg-BG#login"
)
PURCHASE_HISTORY_URL = "https://www.lidl.bg/mre/purchase-history"

PURCHASE_SELECTORS = [
    'a[href*="/mre/purchase-detail"]',
    'a.card[href*="purchase-detail"]',
    'a[data-testid][class*="card"]',
    'a.card',
    'a[class*="card"][href*="/mre/"]',
]

RECEIPT_SELECTORS = ["main", "body"]

NEXT_PAGE_SELECTOR = (
    'button:has-text("Следваща"), a:has-text("Следваща"), '
    'button:has-text("Next"), a:has-text("Next"), '
    '[aria-label*="next"], .pagination-next, .next-page'
)


async def _first_matching(page, selectors: List[str]):
    """Връща първия списък от елементи, matched от някой от selectors-ите."""
    for selector in selectors:
        elements = await page.query_selector_all(selector)
        if elements:
            return elements, selector
    return [], selectors[0]


class LidlReceiptDownloader:
    def __init__(
        self,
        output_dir: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.start_date = start_date
        self.end_date = end_date
        self.receipts: List[dict] = []
        self.log = log or (lambda message: print(message))
        self.is_cancelled = False
        self.ready_to_start = False
        self.start_time: Optional[float] = None

    def parse_receipt_date(self, text_content: str) -> Optional[str]:
        """Извлича датата (ISO YYYY-MM-DD) от съдържанието на бележката."""
        match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s+\d{2}:\d{2}:\d{2}", text_content)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return None

    def is_date_in_range(self, receipt_date: Optional[str]) -> bool:
        """Проверява дали датата е в избрания период (ISO низовете се сравняват лексикографски)."""
        if receipt_date is None or (self.start_date is None and self.end_date is None):
            return True
        if self.start_date and receipt_date < self.start_date:
            return False
        if self.end_date and receipt_date > self.end_date:
            return False
        return True

    async def wait_for_user_ready(self, page) -> None:
        """Отваря страницата за вход и изчаква потребителя да е готов (ръчно влизане)."""
        self.log("== ИНСТРУКЦИИ ==")
        self.log("1. Влезте в акаунта си в отворения браузър")
        self.log(f"2. Отидете на страницата с касови бележки: {PURCHASE_HISTORY_URL}")
        self.log("3. Натиснете 'Започни изтегляне' в приложението, когато сте готови")
        self.log("== ==")

        await page.goto(LOGIN_URL, wait_until="networkidle")
        self.log("Очакване на потребителя...")

        while not self.ready_to_start and not self.is_cancelled:
            await asyncio.sleep(0.3)

        if not self.is_cancelled:
            self.start_time = time.time()
            self.log("Стартиране на изтегляне на бележки...")

    async def navigate_to_page(self, page, page_num: int) -> None:
        """Отива на страницата с история на покупките (page_num)."""
        url = (
            f"{PURCHASE_HISTORY_URL}?client_id=BulgariaRetailClient"
            f"&country_code=bg&language=bg-BG&page={page_num}"
        )
        self.log(f"Отваряне на история на покупките (страница {page_num})...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)

    async def has_more_receipts(self, page) -> bool:
        """Проверява дали на страницата има покупки."""
        try:
            links, _ = await _first_matching(page, PURCHASE_SELECTORS)
            return bool(links)
        except Exception:
            return False

    async def _extract_receipt_text(self, page) -> Optional[str]:
        """Връща текста на отворената бележка от някой от известните контейнери."""
        for selector in RECEIPT_SELECTORS:
            container = await page.query_selector(selector)
            if container:
                text = await container.inner_text()
                if text and len(text.strip()) > 100:
                    return text.strip()
        return None

    async def extract_receipts_from_page(self, page, page_number: int) -> int:
        """Извлича бележките от текущата страница и връща броя на изтеглените."""
        self.log("Извличане на касови бележки...")
        await asyncio.sleep(3)

        purchase_elements, selector = await _first_matching(page, PURCHASE_SELECTORS)
        if not purchase_elements:
            purchase_elements = await page.query_selector_all(
                'button, a[href*="purchase"], a[href*="receipt"]'
            )

        self.log(f"Намерени {len(purchase_elements)} покупки на тази страница")
        extracted = 0

        for i in range(len(purchase_elements)):
            if self.is_cancelled:
                self.log("Процесът е прекъснат от потребителя")
                break

            try:
                self.log(f"  Обработка на покупка {i + 1}/{len(purchase_elements)}...")
                await asyncio.sleep(1)

                elements, _ = await _first_matching(page, PURCHASE_SELECTORS)
                if i >= len(elements):
                    self.log("  Елементът вече не е достъпен, прескачане...")
                    continue

                element = elements[i]
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await element.click()
                await asyncio.sleep(2)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)

                text_content = await self._extract_receipt_text(page)

                if text_content:
                    receipt_date = self.parse_receipt_date(text_content)
                    if self.is_date_in_range(receipt_date):
                        self.receipts.append(
                            {
                                "page_number": page_number,
                                "index": i + 1,
                                "date": receipt_date,
                                "content": text_content,
                            }
                        )
                        extracted += 1
                        date_info = f" ({receipt_date})" if receipt_date else ""
                        self.log(f"    Извлечена бележка {i + 1}{date_info}")
                        self.log(f"    Общо изтеглени бележки: {len(self.receipts)}")
                    else:
                        date_info = f" ({receipt_date})" if receipt_date else ""
                        self.log(f"    Пропусната бележка {i + 1}{date_info} - извън период")
                else:
                    self.log(f"    Бележка {i + 1} е празна")

                await page.go_back()
                await asyncio.sleep(2)
                await page.wait_for_load_state("networkidle", timeout=10000)

            except PlaywrightTimeout:
                self.log(f"  Timeout при обработка на покупка {i + 1}, продължаване...")
                try:
                    await page.go_back()
                    await asyncio.sleep(2)
                except Exception:
                    pass
            except Exception as e:
                self.log(f"  Грешка при обработка на покупка {i + 1}: {e}")
                try:
                    await page.go_back()
                    await asyncio.sleep(2)
                except Exception:
                    pass

        return extracted

    async def check_current_page_number(self, page) -> int:
        """Извлича текущия номер на страницата от URL."""
        match = re.search(r"[?&]page=(\d+)", page.url)
        return int(match.group(1)) if match else 1

    async def download_all_receipts(self) -> None:
        """Стартира браузър, изчаква ръчно влизане и изтегля всички бележки."""
        from playwright.async_api import async_playwright

        self.log("Стартиране на браузър...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
            )
            page = await context.new_page()

            try:
                await self.wait_for_user_ready(page)
                page_number = await self.check_current_page_number(page)

                while not self.is_cancelled:
                    self.log(f"\n{'=' * 60}")
                    self.log(f"СТРАНИЦА {page_number}")
                    self.log(f"{'=' * 60}")

                    await self.navigate_to_page(page, page_number)

                    if not await self.has_more_receipts(page):
                        self.log(f"\nНяма повече покупки на страница {page_number}")
                        break

                    extracted = await self.extract_receipts_from_page(page, page_number)
                    self.log(f"\nИзтеглени от тази страница: {extracted}")
                    self.log(f"Общо изтеглени бележки: {len(self.receipts)}")

                    if self.is_cancelled:
                        break
                    page_number += 1

                if not self.is_cancelled:
                    self.log(f"\n{'=' * 60}")
                    self.log(f"ПРИКЛЮЧЕНО ИЗТЕГЛЯНЕ")
                    self.log(f"{'=' * 60}")
                    self.log(f"Общо извлечени бележки: {len(self.receipts)}")

            except Exception as e:
                self.log(f"Грешка при изтегляне: {e}")
                raise
            finally:
                await browser.close()

    def save_to_file(self) -> str:
        """Запазва бележките във файл и връща пълния му път."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lidl_receipts_{timestamp}.txt"
        filepath = self.output_dir / filename

        self.output_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            "=" * 80,
            "КАСОВИ БЕЛЕЖКИ ОТ LIDL.BG",
            f"Дата на изтегляне: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            f"Общо бележки: {len(self.receipts)}",
        ]
        if self.start_date or self.end_date:
            period = "от " + self.start_date if self.start_date else ""
            if self.end_date:
                period += (" до " if self.start_date else "до ") + self.end_date
            lines.append(f"Период: {period}")
        lines.append("=" * 80)
        lines.append("")

        for i, receipt in enumerate(self.receipts, 1):
            lines += [
                "=" * 80,
                f"БЕЛЕЖКА #{i}",
                f"Страница: {receipt['page_number']}",
            ]
            if receipt.get("date"):
                lines.append(f"Дата: {receipt['date']}")
            lines += ["=" * 80, ""]
            lines.append(receipt["content"])
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")

        size_kb = filepath.stat().st_size / 1024
        self.log(f"\nУспешно запазени {len(self.receipts)} бележки във файл:")
        self.log(f"  {filepath} ({size_kb:.2f} KB)")
        return str(filepath)