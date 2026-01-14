"""
Lidl Receipt Downloader
Автоматично изтегля всички касови бележки от Lidl.bg
"""

import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class LidlReceiptDownloader:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.receipts = []
        
    async def login(self, page):
        """Влиза в акаунта"""
        print("Влизане в акаунта...")
        
        try:
            # Отваряне на страницата за вход
            await page.goto('https://accounts.lidl.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fcountry_code%3DBG%26response_type%3Dcode%26client_id%3Dbulgariaretailclient%26scope%3Dopenid%2520profile%2520Lidl.Authentication%2520offline_access%26state%3D7kjyF6Xd4NaMWmVqiNhXmDlKvTzcOa23tPkuFORkF2E%253D%26redirect_uri%3Dhttps%253A%252F%252Fwww.lidl.bg%252Fuser-api%252Fsignin-oidc%26nonce%3DEJIGNwoTYnT5BTScAf8yndJ6_tfF5V-ag26aqBsTg-8%26step%3Dlogin%26language%3Dbg-BG#login', wait_until='networkidle')
            await asyncio.sleep(2)
            
            # Въвеждане на имейл
            await page.fill('input[type="email"], input[name="email"], input[id="email"]', self.email)
            await asyncio.sleep(1)
            
            # Въвеждане на парола
            await page.fill('input[type="password"], input[name="password"], input[id="password"]', self.password)
            await asyncio.sleep(1)
            
            # Натискане на бутона за вход
            await page.click('button[type="submit"], input[type="submit"]')
            await asyncio.sleep(3)
            
            # Проверка дали сме влезли успешно
            await page.wait_for_load_state('networkidle')
            print("Успешно влизане!")
            
        except Exception as e:
            print(f"Грешка при влизане: {e}")
            raise
    
    async def navigate_to_purchase_history(self, page):
        """Отива до страницата с покупки"""
        print("Отваряне на история на покупките...")
        await page.goto('https://www.lidl.bg/mre/purchase-history', wait_until='networkidle')
        await asyncio.sleep(2)
    
    async def extract_receipts_from_page(self, page, page_number):
        """Извлича касовите бележки от текущата страница"""
        print("Извличане на касови бележки...")
        
        try:
            # Изчакване да се заредят покупките
            await asyncio.sleep(3)
            
            # Намиране на всички елементи с покупки (които имат бутони за отваряне)
            purchase_selectors = [
                'a.card[href*="purchase-detail"]',
                'a[data-testid][href*="purchase-detail"]',
                'a.card',
                'a[class*="card"][href*="/mre/purchase-detail"]',
                'button[class*="purchase"], button[class*="receipt"], button[class*="order"]',
                'a[class*="purchase"], a[class*="receipt"], a[class*="order"]'
            ]
            
            purchase_elements = []
            for selector in purchase_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    purchase_elements = elements
                    print(f"Използван селектор: {selector}")
                    break
            
            if not purchase_elements:
                # Опит да намерим всички кликаеми елементи в списъка
                purchase_elements = await page.query_selector_all('button, a[href*="purchase"], a[href*="receipt"]')
            
            print(f"Намерени {len(purchase_elements)} покупки на тази страница")
            
            for i in range(len(purchase_elements)):
                try:
                    print(f"  Обработка на покупка {i + 1}/{len(purchase_elements)}...")
                    
                    # Повторно намиране на елементите (за да избегнем stale elements)
                    await asyncio.sleep(1)
                    # Използваме селектора който работи
                    used_selector = 'a.card[href*="purchase-detail"]'
                    for selector in purchase_selectors:
                        test_elements = await page.query_selector_all(selector)
                        if test_elements:
                            used_selector = selector
                            break
                    current_elements = await page.query_selector_all(used_selector)
                    
                    if i >= len(current_elements):
                        print(f"  Елемент {i + 1} вече не е достъпен, прескачане...")
                        continue
                    
                    element = current_elements[i]
                    
                    # Скролване до елемента
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    
                    # Кликване на покупката
                    await element.click()
                    await asyncio.sleep(2)
                    
                    # Изчакване да се зареди детайлът с бележката
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    await asyncio.sleep(2)
                    
                    # Извличане на текста на касовата бележка
                    # Търсене в различни възможни контейнери
                    receipt_selectors = [
                        'main',
                        '[class*="receipt"]',
                        '[class*="purchase"][class*="detail"]',
                        'article',
                        '.content',
                        'body'
                    ]
                    
                    text_content = None
                    for selector in receipt_selectors:
                        receipt_container = await page.query_selector(selector)
                        if receipt_container:
                            text_content = await receipt_container.inner_text()
                            if text_content and len(text_content.strip()) > 50:
                                break
                    
                    if not text_content:
                        # Ако не намерим контейнер, вземаме цялата страница
                        text_content = await page.inner_text('body')
                    
                    if text_content and text_content.strip():
                        receipt_data = {
                            'page_number': page_number,
                            'index': i + 1,
                            'content': text_content.strip()
                        }
                        self.receipts.append(receipt_data)
                        print(f"    ✓ Извлечена бележка {i + 1} ({len(text_content)} символа)")
                        print(f"    📊 Общо изтеглени бележки: {len(self.receipts)}")
                    else:
                        print(f"    ⚠ Бележка {i + 1} е празна")
                    
                    # Връщане назад към списъка с покупки
                    await page.go_back()
                    await asyncio.sleep(2)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                except PlaywrightTimeout:
                    print(f"  Timeout при обработка на покупка {i + 1}, продължаване...")
                    try:
                        await page.go_back()
                        await asyncio.sleep(2)
                    except:
                        pass
                except Exception as e:
                    print(f"  Грешка при обработка на покупка {i + 1}: {e}")
                    try:
                        await page.go_back()
                        await asyncio.sleep(2)
                    except:
                        pass
                    continue
                    
        except Exception as e:
            print(f"Грешка при извличане на бележки: {e}")
    
    async def has_next_page(self, page):
        """Проверява дали има следваща страница"""
        try:
            # Търсене на бутон за следваща страница
            next_button = await page.query_selector(
                'button:has-text("Следваща"), '
                'a:has-text("Следваща"), '
                'button:has-text("Next"), '
                'a:has-text("Next"), '
                '[aria-label*="next"], '
                '.pagination-next, '
                '.next-page'
            )
            
            if next_button:
                is_disabled = await next_button.get_attribute('disabled')
                is_hidden = await next_button.is_hidden()
                return next_button and not is_disabled and not is_hidden
            
            return False
            
        except Exception:
            return False
    
    async def go_to_next_page(self, page):
        """Отива на следващата страница"""
        try:
            print("Преминаване към следваща страница...")
            
            next_button = await page.query_selector(
                'button:has-text("Следваща"), '
                'a:has-text("Следваща"), '
                'button:has-text("Next"), '
                'a:has-text("Next"), '
                '[aria-label*="next"], '
                '.pagination-next, '
                '.next-page'
            )
            
            if next_button:
                await next_button.click()
                await asyncio.sleep(3)
                await page.wait_for_load_state('networkidle')
                return True
            
            return False
            
        except Exception as e:
            print(f"Грешка при преминаване към следваща страница: {e}")
            return False
    
    async def download_all_receipts(self):
        """Изтегля всички касови бележки"""
        async with async_playwright() as p:
            print("Стартиране на браузър...")
            
            # Стартиране на браузър (headless=False за да видим процеса)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                # Влизане в акаунта
                await self.login(page)
                
                # Отваряне на историята на покупките
                await self.navigate_to_purchase_history(page)
                
                # Обработка на всички страници
                page_number = 1
                while True:
                    print(f"\n{'=' * 60}")
                    print(f"СТРАНИЦА {page_number}")
                    print(f"{'=' * 60}")
                    
                    receipts_before = len(self.receipts)
                    await self.extract_receipts_from_page(page, page_number)
                    receipts_after = len(self.receipts)
                    
                    print(f"\n📋 Изтеглени от тази страница: {receipts_after - receipts_before}")
                    print(f"📊 Общо изтеглени бележки: {receipts_after}")
                    
                    # Проверка за следваща страница
                    if await self.has_next_page(page):
                        if await self.go_to_next_page(page):
                            page_number += 1
                        else:
                            print("\nНе можа да се премине към следваща страница")
                            break
                    else:
                        print("\n✓ Няма повече страници")
                        break
                
                print(f"\n{'=' * 60}")
                print(f"✓ ПРИКЛЮЧЕНО ИЗТЕГЛЯНЕ")
                print(f"{'=' * 60}")
                print(f"📊 Общо извлечени бележки: {len(self.receipts)}")
                print(f"{'=' * 60}")
                
            except Exception as e:
                print(f"Грешка при изтегляне: {e}")
                raise
                
            finally:
                await browser.close()
    
    def save_to_file(self, filename: str = None):
        """Запазва бележките във файл"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'lidl_receipts_{timestamp}.txt'
        
        # Пълен път на файла
        full_path = os.path.abspath(filename)
        
        print(f"\n{'=' * 80}")
        print(f"📝 ЗАПАЗВАНЕ НА БЕЛЕЖКИ")
        print(f"{'=' * 80}")
        print(f"Брой бележки: {len(self.receipts)}")
        print(f"Файл: {filename}")
        print(f"Пълен път: {full_path}")
        print(f"{'=' * 80}")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("КАСОВИ БЕЛЕЖКИ ОТ LIDL.BG\n")
            f.write(f"Дата на изтегляне: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"Общо бележки: {len(self.receipts)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, receipt in enumerate(self.receipts, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"БЕЛЕЖКА #{i}\n")
                f.write(f"Страница: {receipt['page_number']}\n")
                f.write(f"{'=' * 80}\n\n")
                f.write(receipt['content'])
                f.write("\n\n")
        
        file_size = os.path.getsize(full_path) / 1024  # KB
        
        print(f"\n{'=' * 80}")
        print(f"✅ УСПЕШНО ЗАВЪРШЕНО!")
        print(f"{'=' * 80}")
        print(f"📊 Общо бележки: {len(self.receipts)}")
        print(f"📁 Файл: {filename}")
        print(f"📂 Пълен път: {full_path}")
        print(f"💾 Размер: {file_size:.2f} KB")
        print(f"{'=' * 80}")
        
        return full_path


async def main():
    """Главна функция"""
    print("=" * 80)
    print("LIDL RECEIPT DOWNLOADER")
    print("Автоматично изтегляне на касови бележки от Lidl.bg")
    print("=" * 80)
    print()
    
    # Въвеждане на данни за вход
    email = input("Имейл адрес: ").strip()
    password = input("Парола: ").strip()
    
    if not email or not password:
        print("❌ Грешка: Моля въведете имейл и парола!")
        return
    
    print()
    
    # Създаване на downloader
    downloader = LidlReceiptDownloader(email, password)
    
    try:
        # Изтегляне на всички бележки
        await downloader.download_all_receipts()
        
        # Запазване във файл
        if downloader.receipts:
            file_path = downloader.save_to_file()
            print(f"\n🎉 Можете да отворите файла от горния път!")
        else:
            print("\n⚠ Не са намерени касови бележки.")
            print("Възможни причини:")
            print("  - Няма покупки в историята")
            print("  - Структурата на сайта е променена")
            print("  - Проблем с влизането в акаунта")
            
    except Exception as e:
        print(f"\n❌ Грешка: {e}")
        print("\nСъвети:")
        print("1. Уверете се, че имейлът и паролата са правилни")
        print("2. Проверете интернет връзката си")
        print("3. Уверете се, че имате покупки в историята")


if __name__ == "__main__":
    asyncio.run(main())
