"""Ядро за изтегляне на касови бележки от lidl.bg чрез Playwright.

Работният поток използва ръчно влизане в браузъра (без съхранение на пароли):
приложението отваря браузър, потребителят влиза и се позиционира на
страницата с история на покупките, след което изтеглянето започва автоматично.

За скорост:
- тежките ресурси (изображения, медия, шрифтове) не се зареждат;
- бележките от една страница се отварят паралелно в няколко раздела;
- вместо `networkidle` и дълги паузи се чака бързо `domcontentloaded`.
"""

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import urljoin

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

# Брой паралелни раздела при изтегляне на бележки от една страница
MAX_CONCURRENT_TABS = 5
PAGE_LOAD_TIMEOUT = 30000


async def _first_matching(page, selectors: List[str]):
    """Връща първия списък от елементи, matched от някой от selectors-ите."""
    for selector in selectors:
        elements = await page.query_selector_all(selector)
        if elements:
            return elements, selector
    return [], selectors[0]


async def _skip_heavy_resources(route) -> None:
    """Не зарежда изображения, медия и шрифтове (нямат значение за текста)."""
    if route.request.resource_type in ("image", "media", "font"):
        await route.abort()
    else:
        await route.continue_()


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

        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        self.log("Очакване на потребителя...")

        while not self.ready_to_start and not self.is_cancelled:
            await asyncio.sleep(0.2)

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
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        await self._wait_purchase_links(page)

    async def _wait_purchase_links(self, page, timeout: int = 15000) -> None:
        """Чака покупките да се появят на страницата (има скрол-зареждане)."""
        try:
            await page.wait_for_selector(PURCHASE_SELECTORS[0], state="attached", timeout=timeout)
        except PlaywrightTimeout:
            pass
        await asyncio.sleep(0.3)

    async def has_more_receipts(self, page) -> bool:
        """Проверява дали на страницата има покупки."""
        try:
            links, _ = await _first_matching(page, PURCHASE_SELECTORS)
            return bool(links)
        except Exception:
            return False

    async def _purchase_urls(self, page) -> List[str]:
        """Събира уникалните URL адреси на бележките от текущата страница."""
        links, _ = await _first_matching(page, PURCHASE_SELECTORS)
        if not links:
            links = await page.query_selector_all('a[href*="purchase"], a[href*="receipt"]')

        urls, seen = [], set()
        for element in links:
            href = await element.get_attribute("href")
            if not href:
                continue
            full = urljoin(page.url, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    async def _extract_receipt_text(self, page) -> Optional[str]:
        """Връща текста на отворената бележка от някой от известните контейнери."""
        for selector in RECEIPT_SELECTORS:
            container = await page.query_selector(selector)
            if container:
                text = await container.inner_text()
                if text and len(text.strip()) > 100:
                    return text.strip()
        return None

    async def _store_receipt(self, text_content: str, page_number: int, index: int, total: int) -> int:
        """Проверява датата, добавa бележката в списъка и връща 1 при успех."""
        receipt_date = self.parse_receipt_date(text_content)
        if not self.is_date_in_range(receipt_date):
            date_info = f" ({receipt_date})" if receipt_date else ""
            self.log(f"    Пропусната бележка {index}{date_info} - извън период")
            return 0

        self.receipts.append(
            {
                "page_number": page_number,
                "index": index,
                "date": receipt_date,
                "content": text_content,
            }
        )
        date_info = f" ({receipt_date})" if receipt_date else ""
        self.log(f"    Извлечена бележка {index}/{total}{date_info}")
        self.log(f"    Общо изтеглени бележки: {len(self.receipts)}")
        return 1

    async def _open_and_extract(self, context, url: str, page_number: int, index: int, total: int) -> int:
        """Отваря бележката в отделен раздел и я извлича."""
        if self.is_cancelled:
            return 0
        tab = await context.new_page()
        try:
            await tab.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            try:
                await tab.wait_for_selector("main", state="attached", timeout=5000)
            except PlaywrightTimeout:
                pass
            await asyncio.sleep(0.4)

            text_content = await self._extract_receipt_text(tab)
            if not text_content:
                self.log(f"    Бележка {index}/{total} е празна")
                return 0
            return await self._store_receipt(text_content, page_number, index, total)
        except Exception as e:
            self.log(f"  Грешка при изтегляне на бележка {index}: {e}")
            return 0
        finally:
            await tab.close()

    async def _download_batches(self, context, urls: List[str], page_number: int, total: int) -> int:
        """Отваря бележките паралелно на групи и връща броя на изтеглените."""
        extracted = 0
        for start in range(0, len(urls), MAX_CONCURRENT_TABS):
            if self.is_cancelled:
                self.log("Процесът е прекъснат от потребителя")
                break
            batch = urls[start:start + MAX_CONCURRENT_TABS]
            self.log(f"  Партида {(start // MAX_CONCURRENT_TABS) + 1}: {len(batch)} бележки паралелно...")
            results = await asyncio.gather(
                *(self._open_and_extract(context, url, page_number, idx, total)
                  for idx, url in enumerate(batch, start=start + 1))
            )
            extracted += sum(results)
        return extracted

    async def _extract_sequentially(self, page, page_number: int) -> int:
        """Резервен вариант: последователно кликване, ако няма href за бележката."""
        purchase_elements, _ = await _first_matching(page, PURCHASE_SELECTORS)
        total = len(purchase_elements)
        self.log(f"Няма директни линкове, последователно извличане на {total} покупки...")
        extracted = 0

        for i in range(total):
            if self.is_cancelled:
                break
            try:
                elements, _ = await _first_matching(page, PURCHASE_SELECTORS)
                if i >= len(elements):
                    continue
                element = elements[i]
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.2)
                await element.click()
                await asyncio.sleep(1)

                text_content = await self._extract_receipt_text(page)
                if text_content:
                    extracted += await self._store_receipt(text_content, page_number, i + 1, total)

                await page.go_back()
                await asyncio.sleep(0.5)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception as e:
                self.log(f"  Грешка при обработка на покупка {i + 1}: {e}")
                try:
                    await page.go_back()
                except Exception:
                    pass

        return extracted

    async def extract_receipts_from_page(self, page, page_number: int) -> int:
        """Извлича бележките от текущата страница и връща броя на изтеглените."""
        self.log("Извличане на касови бележки...")
        await self._wait_purchase_links(page)

        urls = await self._purchase_urls(page)
        if not urls:
            return await self._extract_sequentially(page, page_number)

        total = len(urls)
        self.log(f"Намерени {total} покупки на тази страница (паралелно изтегляне)")
        return await self._download_batches(page.context, urls, page_number, total)

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
            await context.route("**/*", _skip_heavy_resources)
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