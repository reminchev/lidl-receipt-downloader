"""
Lidl Receipt Downloader - GUI Version
Автоматично изтегля всички касови бележки от Lidl.bg с филтриране по дата
"""

import asyncio
import os
import threading
import time
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from tkcalendar import DateEntry
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class LidlReceiptDownloader:
    def __init__(self, output_dir: str, start_date=None, end_date=None, log_callback=None, progress_callback=None):
        self.output_dir = output_dir
        self.start_date = start_date
        self.end_date = end_date
        self.receipts = []
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.is_cancelled = False
        self.ready_to_start = False
        self.total_pages_estimated = 100  # Оценка - 10 бележки на страница
        self.current_page_processed = 0
        self.start_time = None
        
    def log(self, message):
        """Логване на съобщение"""
        if self.log_callback:
            self.log_callback(message)
        print(message)
    
    def parse_receipt_date(self, text_content):
        """Извлича датата от касовата бележка"""
        try:
            # Търсим дата във формат DD.MM.YYYY HH:MM:SS
            date_pattern = r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2})'
            match = re.search(date_pattern, text_content)
            if match:
                date_str = match.group(1)
                # Конвертираме във формат YYYY-MM-DD за сравнение
                parts = date_str.split('.')
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        except (AttributeError, IndexError, ValueError):
            pass
        return None
    
    def is_date_in_range(self, receipt_date_str):
        """Проверява дали датата е в избрания период"""
        if not self.start_date and not self.end_date:
            return True
        
        if not receipt_date_str:
            return True  # Ако не можем да извлечем дата, включваме бележката
        
        try:
            if self.start_date and receipt_date_str < self.start_date:
                return False
            if self.end_date and receipt_date_str > self.end_date:
                return False
            return True
        except:
            return True
    
    async def wait_for_user_ready(self, page):
        """Изчаква потребителя да се позиционира на страницата с касови бележки"""
        self.log("📌 ИНСТРУКЦИИ:")
        self.log("=" * 60)
        self.log("1. Влезте в акаунта си в отворения браузър")
        self.log("2. Отидете на страницата с касови бележки")
        self.log("   (https://www.lidl.bg/mre/purchase-history)")
        self.log("3. Натиснете 'Започни изтегляне' когато сте готови")
        self.log("=" * 60)
        
        try:
            await page.goto('https://accounts.lidl.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fcountry_code%3DBG%26response_type%3Dcode%26client_id%3Dbulgariaretailclient%26scope%3Dopenid%2520profile%2520Lidl.Authentication%2520offline_access%26state%3D7kjyF6Xd4NaMWmVqiNhXmDlKvTzcOa23tPkuFORkF2E%253D%26redirect_uri%3Dhttps%253A%252F%252Fwww.lidl.bg%252Fuser-api%252Fsignin-oidc%26nonce%3DEJIGNwoTYnT5BTScAf8yndJ6_tfF5V-ag26aqBsTg-8%26step%3Dlogin%26language%3Dbg-BG#login', wait_until='networkidle')
            
            self.log("\n⏳ Изчакване на потребителя...")
            self.log("   Моля, влезте и отидете на страницата с касови бележки\n")
            
            # Изчакваме сигнал за продължаване
            while not self.ready_to_start and not self.is_cancelled:
                await asyncio.sleep(0.5)
            
            if self.is_cancelled:
                return
            
            self.log("✓ Стартиране на изтегляне на бележки...")
            self.start_time = time.time()
            await asyncio.sleep(1)
            
        except Exception as e:
            self.log(f"❌ Грешка: {e}")
            raise
    
    async def navigate_to_purchase_history(self, page, page_num=1):
        """Отива до страницата с покупки"""
        url = f'https://www.lidl.bg/mre/purchase-history?client_id=BulgariaRetailClient&country_code=bg&language=bg-BG&page={page_num}'
        self.log(f"Отваряне на история на покупките (страница {page_num})...")
        await page.goto(url, wait_until='networkidle')
        await asyncio.sleep(2)
    
    async def extract_receipts_from_page(self, page, page_number):
        """Извлича касовите бележки от текущата страница"""
        self.log("Извличане на касови бележки...")
        
        try:
            await asyncio.sleep(3)
            
            purchase_selectors = [
                'a[href*="/mre/purchase-detail"]',
                'a.card[href*="purchase-detail"]',
                'a[data-testid][class*="card"]',
                'a.card',
                'a[class*="card"][href*="/mre/"]'
            ]
            
            purchase_elements = []
            for selector in purchase_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    purchase_elements = elements
                    self.log(f"Използван селектор: {selector}")
                    break
            
            if not purchase_elements:
                purchase_elements = await page.query_selector_all('button, a[href*="purchase"], a[href*="receipt"]')
            
            self.log(f"Намерени {len(purchase_elements)} покупки на тази страница")
            
            # Предполагаме 10 бележки на страница, коригираме оценката
            if len(purchase_elements) > 0:
                self.total_pages_estimated = max(self.total_pages_estimated, page_number + 10)
            
            for i in range(len(purchase_elements)):
                if self.is_cancelled:
                    self.log("⚠ Процесът е прекъснат от потребителя")
                    return
                
                try:
                    self.log(f"  Обработка на покупка {i + 1}/{len(purchase_elements)}...")
                    
                    await asyncio.sleep(1)
                    used_selector = 'a.card[href*="purchase-detail"]'
                    for selector in purchase_selectors:
                        test_elements = await page.query_selector_all(selector)
                        if test_elements:
                            used_selector = selector
                            break
                    current_elements = await page.query_selector_all(used_selector)
                    
                    if i >= len(current_elements):
                        self.log(f"  Елемент {i + 1} вече не е достъпен, прескачане...")
                        continue
                    
                    element = current_elements[i]
                    
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    
                    await element.click()
                    await asyncio.sleep(2)
                    
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    await asyncio.sleep(2)
                    
                    # Изчакване за зареждане на бележката
                    await asyncio.sleep(1)
                    
                    receipt_selectors = [
                        'main',
                        'body'
                    ]
                    
                    text_content = None
                    for selector in receipt_selectors:
                        receipt_container = await page.query_selector(selector)
                        if receipt_container:
                            text_content = await receipt_container.inner_text()
                            if text_content and len(text_content.strip()) > 100:
                                break
                    
                    if not text_content:
                        text_content = await page.inner_text('body')
                    
                    # Почистване на ненужен текст от navigation и footer
                    if text_content:
                        # Извличаме само основното съдържание на бележката
                        lines = text_content.split('\n')
                        # Премахваме първите редове ако са navigation
                        cleaned_lines = []
                        start_found = False
                        for line in lines:
                            # Търсим начало на бележката (обикновено със БУЛСТАТ или адрес на магазин)
                            if 'БУЛСТАТ' in line or 'УНП' in line or 'Лидл' in line or not start_found:
                                start_found = True
                            if start_found:
                                cleaned_lines.append(line)
                        text_content = '\n'.join(cleaned_lines).strip()
                    
                    if text_content and text_content.strip():
                        # Проверка на датата
                        receipt_date = self.parse_receipt_date(text_content)
                        
                        if self.is_date_in_range(receipt_date):
                            receipt_data = {
                                'page_number': page_number,
                                'index': i + 1,
                                'date': receipt_date,
                                'content': text_content.strip()
                            }
                            self.receipts.append(receipt_data)
                            date_info = f" ({receipt_date})" if receipt_date else ""
                            self.log(f"    ✓ Извлечена бележка {i + 1}{date_info} ({len(text_content)} символа)")
                            self.log(f"    📊 Общо изтеглени бележки: {len(self.receipts)}")
                        else:
                            date_info = f" ({receipt_date})" if receipt_date else ""
                            self.log(f"    ⊗ Пропусната бележка {i + 1}{date_info} - извън период")
                    else:
                        self.log(f"    ⚠ Бележка {i + 1} е празна")
                    
                    await page.go_back()
                    await asyncio.sleep(2)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                except PlaywrightTimeout:
                    self.log(f"  Timeout при обработка на покупка {i + 1}, продължаване...")
                    try:
                        await page.go_back()
                        await asyncio.sleep(2)
                    except:
                        pass
                except Exception as e:
                    self.log(f"  Грешка при обработка на покупка {i + 1}: {e}")
                    try:
                        await page.go_back()
                        await asyncio.sleep(2)
                    except:
                        pass
                    continue
                    
        except Exception as e:
            self.log(f"Грешка при извличане на бележки: {e}")
    
    async def has_more_receipts(self, page):
        """Проверява дали има още бележки (покупки) на страницата"""
        try:
            # Проверка за покупки на страницата
            purchase_links = await page.query_selector_all('a[href*="/mre/purchase-detail"]')
            return len(purchase_links) > 0
        except Exception:
            return False
    
    async def check_current_page_number(self, page):
        """Извлича текущия номер на страницата от URL"""
        try:
            current_url = page.url
            if 'page=' in current_url:
                page_param = current_url.split('page=')[1].split('&')[0]
                return int(page_param)
            return 1
        except:
            return 1
    
    async def download_all_receipts(self):
        """Изтегля всички касови бележки"""
        async with async_playwright() as p:
            self.log("Стартиране на браузър...")
            
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                await self.wait_for_user_ready(page)
                
                # Получаваме текущия URL за да определим началната страница
                current_url = page.url
                page_number = await self.check_current_page_number(page)
                
                while not self.is_cancelled:
                    self.log(f"\n{'=' * 60}")
                    self.log(f"СТРАНИЦА {page_number}")
                    self.log(f"{'=' * 60}")
                    
                    # Отваряне на страницата с покупки
                    await self.navigate_to_purchase_history(page, page_number)
                    
                    # Проверка дали има покупки на страницата
                    if not await self.has_more_receipts(page):
                        self.log(f"\n✓ Няма повече покупки на страница {page_number}")
                        break
                    
                    receipts_before = len(self.receipts)
                    await self.extract_receipts_from_page(page, page_number)
                    receipts_after = len(self.receipts)
                    
                    self.current_page_processed = page_number
                    if self.progress_callback:
                        progress_percent = min(100, (page_number / self.total_pages_estimated) * 100)
                        elapsed_time = time.time() - self.start_time if self.start_time else 0
                        self.progress_callback(progress_percent, page_number, self.total_pages_estimated, elapsed_time)
                    
                    if self.is_cancelled:
                        self.log("\n⚠ Процесът е прекъснат")
                        break
                    
                    self.log(f"\n📋 Изтеглени от тази страница: {receipts_after - receipts_before}")
                    self.log(f"📊 Общо изтеглени бележки: {receipts_after}")
                    
                    # Преминаваме към следващата страница
                    page_number += 1
                
                if not self.is_cancelled:
                    self.log(f"\n{'=' * 60}")
                    self.log(f"✓ ПРИКЛЮЧЕНО ИЗТЕГЛЯНЕ")
                    self.log(f"{'=' * 60}")
                    self.log(f"📊 Общо извлечени бележки: {len(self.receipts)}")
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    self.log(f"⏱ Общо време: {self.format_time(elapsed_time)}")
                    self.log(f"{'=' * 60}")
                
            except Exception as e:
                self.log(f"❌ Грешка при изтегляне: {e}")
                raise
                
            finally:
                await browser.close()
    
    def format_time(self, seconds):
        """Форматира времето в часове:минути:секунди"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}ч {minutes}м {secs}с"
        elif minutes > 0:
            return f"{minutes}м {secs}с"
        else:
            return f"{secs}с"
    
    def save_to_file(self):
        """Запазва бележките във файл"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'lidl_receipts_{timestamp}.txt'
        filepath = os.path.join(self.output_dir, filename)
        
        full_path = os.path.abspath(filepath)
        
        self.log(f"\n{'=' * 80}")
        self.log(f"📝 ЗАПАЗВАНЕ НА БЕЛЕЖКИ")
        self.log(f"{'=' * 80}")
        self.log(f"Брой бележки: {len(self.receipts)}")
        self.log(f"Файл: {filename}")
        self.log(f"Директория: {self.output_dir}")
        self.log(f"Пълен път: {full_path}")
        self.log(f"{'=' * 80}")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("КАСОВИ БЕЛЕЖКИ ОТ LIDL.BG\n")
            f.write(f"Дата на изтегляне: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"Общо бележки: {len(self.receipts)}\n")
            if self.start_date or self.end_date:
                f.write(f"Период: ")
                if self.start_date:
                    f.write(f"от {self.start_date} ")
                if self.end_date:
                    f.write(f"до {self.end_date}")
                f.write("\n")
            f.write("=" * 80 + "\n\n")
            
            for i, receipt in enumerate(self.receipts, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"БЕЛЕЖКА #{i}\n")
                f.write(f"Страница: {receipt['page_number']}\n")
                if receipt.get('date'):
                    f.write(f"Дата: {receipt['date']}\n")
                f.write(f"{'=' * 80}\n\n")
                f.write(receipt['content'])
                f.write("\n\n")
        
        file_size = os.path.getsize(full_path) / 1024  # KB
        
        self.log(f"\n{'=' * 80}")
        self.log(f"✅ УСПЕШНО ЗАВЪРШЕНО!")
        self.log(f"{'=' * 80}")
        self.log(f"📊 Общо бележки: {len(self.receipts)}")
        self.log(f"📁 Файл: {filename}")
        self.log(f"📂 Пълен път: {full_path}")
        self.log(f"💾 Размер: {file_size:.2f} KB")
        self.log(f"{'=' * 60}")
        
        return full_path


class LidlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lidl Receipt Downloader")
        self.root.geometry("800x850")
        self.root.resizable(True, True)
        
        self.downloader = None
        self.download_thread = None
        self.output_dir = str(Path.home() / "Documents")
        self.analysis_file = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Създава интерфейса"""
        # Заглавие
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        title_label = ttk.Label(
            title_frame, 
            text="Lidl Receipt Downloader", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=5)
        
        subtitle_label = ttk.Label(
            title_frame, 
            text="Автоматично изтегляне на касови бележки от Lidl.bg",
            font=("Arial", 10)
        )
        subtitle_label.grid(row=1, column=0, pady=2)
        
        # Рамка за период
        period_frame = ttk.LabelFrame(self.root, text="Период на бележките (опционално)", padding="10")
        period_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        ttk.Label(period_frame, text="От дата:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.start_date_entry = DateEntry(
            period_frame,
            width=18,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            state='normal'
        )
        self.start_date_entry.grid(row=0, column=1, sticky=(tk.W), pady=5, padx=5)
        
        # Бутон за изчистване на начална дата
        self.clear_start_btn = ttk.Button(
            period_frame,
            text="✖",
            width=3,
            command=self.clear_start_date
        )
        self.clear_start_btn.grid(row=0, column=2, pady=5, padx=2)
        
        ttk.Label(period_frame, text="До дата:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.end_date_entry = DateEntry(
            period_frame,
            width=18,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            state='normal'
        )
        self.end_date_entry.grid(row=1, column=1, sticky=(tk.W), pady=5, padx=5)
        
        # Бутон за изчистване на крайна дата
        self.clear_end_btn = ttk.Button(
            period_frame,
            text="✖",
            width=3,
            command=self.clear_end_date
        )
        self.clear_end_btn.grid(row=1, column=2, pady=5, padx=2)
        
        # Checkbox за използване на период
        self.use_period_var = tk.BooleanVar(value=False)
        self.use_period_check = ttk.Checkbutton(
            period_frame,
            text="✓ Филтрирай по период",
            variable=self.use_period_var
        )
        self.use_period_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)
        
        period_frame.columnconfigure(3, weight=1)
        
        # Рамка за директория
        dir_frame = ttk.LabelFrame(self.root, text="Директория за съхранение", padding="10")
        dir_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.dir_label = ttk.Label(dir_frame, text=self.output_dir, foreground="blue")
        self.dir_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.dir_button = ttk.Button(
            dir_frame, 
            text="📁 Избери директория", 
            command=self.choose_directory
        )
        self.dir_button.grid(row=0, column=1, padx=5)
        
        dir_frame.columnconfigure(0, weight=1)
        
        # Рамка за файл за анализ
        analysis_frame = ttk.LabelFrame(self.root, text="Файл за анализ на цени", padding="10")
        analysis_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.analysis_file_label = ttk.Label(
            analysis_frame, 
            text="Няма избран файл", 
            foreground="gray"
        )
        self.analysis_file_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.analysis_file_button = ttk.Button(
            analysis_frame, 
            text="📄 Избери файл за анализ", 
            command=self.choose_analysis_file
        )
        self.analysis_file_button.grid(row=0, column=1, padx=5)
        
        analysis_frame.columnconfigure(0, weight=1)
        
        # Рамка за контроли
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.start_button = ttk.Button(
            control_frame, 
            text="▶ Старт", 
            command=self.start_download,
            style="Accent.TButton"
        )
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(
            control_frame, 
            text="⏸ Прекъсване", 
            command=self.stop_download,
            state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=5)
        
        self.continue_button = ttk.Button(
            control_frame, 
            text="✓ Започни изтегляне", 
            command=self.continue_after_ready,
            state=tk.DISABLED,
            style="Accent.TButton"
        )
        self.continue_button.grid(row=0, column=2, padx=5)
        
        # Бутон за анализ
        self.analyze_button = ttk.Button(
            control_frame, 
            text="📊 Анализ → XLSX", 
            command=self.analyze_receipts,
            style="Accent.TButton"
        )
        self.analyze_button.grid(row=0, column=3, padx=5)
        
        # Статус лейбъл
        self.status_label = ttk.Label(
            control_frame, 
            text="Готов за стартиране",
            foreground="green",
            font=("Arial", 10, "bold")
        )
        self.status_label.grid(row=0, column=4, padx=15)
        
        # Таймер лейбъл
        self.timer_label = ttk.Label(
            control_frame, 
            text="⏱ Време: 0с",
            foreground="blue",
            font=("Arial", 10)
        )
        self.timer_label.grid(row=0, column=5, padx=5)
        
        # Рамка за прогрес барове
        progress_frame = ttk.LabelFrame(self.root, text="Прогрес", padding="10")
        progress_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # Първи прогрес бар - страници
        ttk.Label(progress_frame, text="Прогрес по страници:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.page_progress = ttk.Progressbar(
            progress_frame, 
            mode='determinate',
            length=400
        )
        self.page_progress.grid(row=0, column=1, padx=10, pady=2, sticky=(tk.W, tk.E))
        
        self.page_progress_label = ttk.Label(
            progress_frame, 
            text="0%",
            font=("Arial", 9)
        )
        self.page_progress_label.grid(row=0, column=2, pady=2)
        
        # Втори прогрес бар - бележки
        ttk.Label(progress_frame, text="Изтеглени бележки:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.receipt_label = ttk.Label(
            progress_frame, 
            text="0 бележки",
            font=("Arial", 9, "bold"),
            foreground="darkgreen"
        )
        self.receipt_label.grid(row=1, column=1, sticky=tk.W, padx=10, pady=2)
        
        progress_frame.columnconfigure(1, weight=1)
        
        # Рамка за логове
        log_frame = ttk.LabelFrame(self.root, text="Прогрес и логове", padding="10")
        log_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=20, 
            width=80,
            font=("Consolas", 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Конфигурация на grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(6, weight=1)
        
        # Стилове
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=("Arial", 10, "bold"))
        except:
            pass
    
    def clear_start_date(self):
        """Изчиства началната дата"""
        self.use_period_var.set(False)
        self.log_message("✓ Изчистена начална дата")
    
    def clear_end_date(self):
        """Изчиства крайната дата"""
        self.use_period_var.set(False)
        self.log_message("✓ Изчистена крайна дата")
    
    def choose_directory(self):
        """Избира директория за съхранение"""
        directory = filedialog.askdirectory(
            title="Избери директория за съхранение на бележките",
            initialdir=self.output_dir
        )
        if directory:
            self.output_dir = directory
            self.dir_label.config(text=directory)
            self.log_message(f"✓ Избрана директория: {directory}")
    
    def choose_analysis_file(self):
        """Избира файл за анализ"""
        file_path = filedialog.askopenfilename(
            title="Избери файл с касови бележки за анализ",
            initialdir=self.output_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.analysis_file = file_path
            # Показваме само името на файла, не целия път (за да се побере в интерфейса)
            file_name = os.path.basename(file_path)
            self.analysis_file_label.config(text=file_name, foreground="blue")
            self.log_message(f"✓ Избран файл за анализ: {file_name}")
    
    def log_message(self, message):
        """Добавя съобщение в лог текста"""
        def _log():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, _log)
        else:
            _log()
    
    def update_status(self, message, color="black"):
        """Обновява статус лейбъла"""
        def _update():
            self.status_label.config(text=message, foreground=color)
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, _update)
        else:
            _update()
    
    def update_progress(self, percent, page_num, total_pages, elapsed_time):
        """Обновява прогрес баровете и таймъра"""
        def _update():
            self.page_progress['value'] = percent
            self.page_progress_label.config(text=f"{int(percent)}% (стр. {page_num}/{total_pages})")
            
            receipt_count = len(self.downloader.receipts) if self.downloader else 0
            self.receipt_label.config(text=f"{receipt_count} бележки")
            
            # Обновяване на таймера
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)
            if hours > 0:
                time_str = f"{hours}ч {minutes}м {seconds}с"
            elif minutes > 0:
                time_str = f"{minutes}м {seconds}с"
            else:
                time_str = f"{seconds}с"
            self.timer_label.config(text=f"⏱ Време: {time_str}")
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, _update)
        else:
            _update()
    
    def start_download(self):
        """Стартира изтеглянето"""
        if not os.path.exists(self.output_dir):
            messagebox.showerror("Грешка", "Избраната директория не съществува!")
            return
        
        # Получаване на датите от DateEntry виджетите
        start_date = None
        end_date = None
        
        if self.use_period_var.get():
            try:
                start_date = self.start_date_entry.get_date().strftime('%Y-%m-%d')
            except:
                start_date = None
            
            try:
                end_date = self.end_date_entry.get_date().strftime('%Y-%m-%d')
            except:
                end_date = None
            
            if start_date and end_date and start_date > end_date:
                messagebox.showerror("Грешка", "Началната дата не може да е след крайната!")
                return
        
        # Деактивиране на контроли
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.start_date_entry.config(state=tk.DISABLED)
        self.end_date_entry.config(state=tk.DISABLED)
        self.dir_button.config(state=tk.DISABLED)
        self.continue_button.config(state=tk.NORMAL)
        
        # Изчистване на логовете
        self.log_text.delete(1.0, tk.END)
        
        # Нулиране на прогрес баровете
        self.page_progress['value'] = 0
        self.page_progress_label.config(text="0%")
        self.receipt_label.config(text="0 бележки")
        self.timer_label.config(text="⏱ Време: 0с")
        
        self.update_status("⏳ Изчакване за влизане...", "orange")
        
        # Създаване на downloader
        self.downloader = LidlReceiptDownloader(
            self.output_dir,
            start_date=start_date,
            end_date=end_date,
            log_callback=self.log_message,
            progress_callback=self.update_progress
        )
        
        # Стартиране в отделна нишка
        self.download_thread = threading.Thread(target=self.run_download, daemon=True)
        self.download_thread.start()
    
    def run_download(self):
        """Изпълнява изтеглянето в отделна нишка"""
        try:
            # Създаване на нов event loop за тази нишка
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Изпълнение на изтеглянето
            loop.run_until_complete(self.downloader.download_all_receipts())
            
            # Запазване на файла
            if self.downloader.receipts and not self.downloader.is_cancelled:
                file_path = self.downloader.save_to_file()
                self.root.after(0, lambda: messagebox.showinfo(
                    "Успех", 
                    f"Успешно изтеглени {len(self.downloader.receipts)} бележки!\n\n"
                    f"Файл: {file_path}"
                ))
                self.update_status("✓ Завършено успешно", "green")
            elif self.downloader.is_cancelled:
                self.update_status("⚠ Прекъснато", "orange")
                if self.downloader.receipts:
                    file_path = self.downloader.save_to_file()
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Прекъснато", 
                        f"Процесът беше прекъснат.\n"
                        f"Запазени {len(self.downloader.receipts)} бележки.\n\n"
                        f"Файл: {file_path}"
                    ))
            else:
                self.update_status("⚠ Няма намерени бележки", "orange")
                self.root.after(0, lambda: messagebox.showwarning(
                    "Внимание", 
                    "Не са намерени касови бележки.\n\n"
                    "Възможни причини:\n"
                    "- Няма покупки в историята\n"
                    "- Проблем с влизането в акаунта\n"
                    "- Структурата на сайта е променена\n"
                    "- Всички бележки са извън избрания период"
                ))
                
        except Exception as e:
            self.log_message(f"\n❌ Грешка: {e}")
            self.update_status("❌ Грешка", "red")
            self.root.after(0, lambda: messagebox.showerror(
                "Грешка", 
                f"Възникна грешка при изтеглянето:\n\n{str(e)}"
            ))
        finally:
            # Активиране на контроли
            self.root.after(0, self.reset_ui)
    
    def continue_after_ready(self):
        """Продължава след като потребителя е готов"""
        if self.downloader:
            self.downloader.ready_to_start = True
            self.continue_button.config(state=tk.DISABLED)
            self.update_status("📥 Изтегляне...", "blue")
            self.log_message("\n✓ Стартиране на изтегляне на бележки...")
    
    def stop_download(self):
        """Прекъсва изтеглянето"""
        if self.downloader:
            self.downloader.is_cancelled = True
            self.log_message("\n⚠ Изпращане на сигнал за прекъсване...")
            self.stop_button.config(state=tk.DISABLED)
    
    def reset_ui(self):
        """Връща UI в начално състояние"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.continue_button.config(state=tk.DISABLED)
        self.start_date_entry.config(state=tk.NORMAL)
        self.end_date_entry.config(state=tk.NORMAL)
        self.dir_button.config(state=tk.NORMAL)
    
    def analyze_receipts(self):
        """Анализира касовите бележки и създава XLSX файл с история на цените"""
        # Проверка дали е избран файл
        if not self.analysis_file:
            # Ако няма избран файл, отваряме диалог
            file_path = filedialog.askopenfilename(
                title="Избери файл с касови бележки за анализ",
                initialdir=self.output_dir,
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
            
            self.analysis_file = file_path
            file_name = os.path.basename(file_path)
            self.analysis_file_label.config(text=file_name, foreground="blue")
        else:
            file_path = self.analysis_file
        
        # Проверка дали файлът съществува
        if not os.path.exists(file_path):
            messagebox.showerror(
                "Грешка", 
                f"Файлът не съществува:\n{file_path}\n\nМоля изберете друг файл."
            )
            self.analysis_file = None
            self.analysis_file_label.config(text="Няма избран файл", foreground="gray")
            return
        
        self.log_message(f"\n📊 Стартиране на анализ на файл: {os.path.basename(file_path)}")
        self.update_status("📊 Анализ...", "blue")
        
        try:
            # Парсване на файла
            products_data = self.parse_receipts_file(file_path)
            
            if not products_data:
                messagebox.showwarning("Внимание", "Не са намерени артикули за анализ!")
                self.update_status("⚠ Няма данни", "orange")
                return
            
            # Филтриране на продукти, които се срещат повече от веднъж
            filtered_products = {
                product: dates_prices 
                for product, dates_prices in products_data.items() 
                if len(dates_prices) > 1
            }
            
            if not filtered_products:
                messagebox.showwarning(
                    "Внимание", 
                    "Не са намерени артикули, които се срещат повече от веднъж!"
                )
                self.update_status("⚠ Няма данни", "orange")
                return
            
            self.log_message(f"✓ Намерени {len(filtered_products)} артикула с повече от 1 покупка")
            self.log_message(f"  (Общо {len(products_data)} уникални артикула)")
            
            # Генериране на XLSX файл
            output_file = self.generate_xlsx(filtered_products, file_path)
            
            self.log_message(f"\n✓ XLSX файлът е създаден успешно!")
            self.log_message(f"  Файл: {output_file}")
            self.update_status("✓ Анализ завършен", "green")
            
            messagebox.showinfo(
                "Успех", 
                f"Анализът завърши успешно!\n\n"
                f"Артикули с повече от 1 покупка: {len(filtered_products)}\n"
                f"Общо уникални артикули: {len(products_data)}\n\n"
                f"Файл: {os.path.basename(output_file)}"
            )
            
        except Exception as e:
            self.log_message(f"\n❌ Грешка при анализ: {e}")
            self.update_status("❌ Грешка при анализ", "red")
            messagebox.showerror("Грешка", f"Грешка при анализ:\n\n{str(e)}")
    
    def parse_receipts_file(self, file_path):
        """Парсва файла с бележки и извлича продукти с дати и цени"""
        products_data = defaultdict(dict)  # {product_name: {date: price}}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Разделяне на бележки
            receipts = content.split('БЕЛЕЖКА #')
            
            self.log_message(f"✓ Намерени {len(receipts)-1} бележки за парсинг...")
            
            for receipt_idx, receipt in enumerate(receipts[1:], 1):  # Прескачаме първия празен елемент
                # Извличане на дата - търсим различни формати
                date_match = None
                receipt_date_str = None
                
                # Формат 1: DD.MM.YYYY HH:MM:SS в края (например "13.01.2026 13:03:32")
                date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\s+\d{2}:\d{2}:\d{2}', receipt)
                if date_match:
                    day, month, year = date_match.groups()
                    receipt_date_str = f"{year}-{month}-{day}"
                
                # Формат 2: YYYY.MM.DD HH:MM (например "2025.12.26 17:24")
                if not receipt_date_str:
                    date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}', receipt)
                    if date_match:
                        year, month, day = date_match.groups()
                        receipt_date_str = f"{year}-{month}-{day}"
                
                # Формат 3: В заглавието "DD.месец" (например "13.януари")
                if not receipt_date_str:
                    months_bg = {
                        'януари': '01', 'февруари': '02', 'март': '03', 'април': '04',
                        'май': '05', 'юни': '06', 'юли': '07', 'август': '08',
                        'септември': '09', 'октомври': '10', 'ноември': '11', 'декември': '12'
                    }
                    for month_name, month_num in months_bg.items():
                        if month_name in receipt.lower():
                            day_match = re.search(r'(\d{1,2})\.' + month_name, receipt.lower())
                            if day_match:
                                day = day_match.group(1).zfill(2)
                                # Определяме годината - ако месецът е декември и сме в януари, значи е миналата година
                                year = '2025' if month_name == 'декември' else '2026'
                                receipt_date_str = f"{year}-{month_num}-{day}"
                                break
                
                if not receipt_date_str:
                    self.log_message(f"  ⚠ Пропусната бележка #{receipt_idx} - не може да се извлече дата")
                    continue
                
                try:
                    receipt_date = datetime.strptime(receipt_date_str, '%Y-%m-%d')
                except ValueError:
                    self.log_message(f"  ⚠ Пропусната бележка #{receipt_idx} - невалиден формат на дата: {receipt_date_str}")
                    continue
                
                # Определяне на конверсионен фактор и валута
                # Проверяваме дали е BGN, лв или Евро
                is_bgn = 'BGN' in receipt or '# лв' in receipt or 'лв  #' in receipt
                is_eur = 'Евро' in receipt or '# Евро #' in receipt or 'EUR' in receipt
                
                # Ако е преди 01.01.2026, трябва да конвертираме от BGN към EUR
                if receipt_date < datetime(2026, 1, 1):
                    # Стари бележки - винаги са в BGN, трябва да конвертираме
                    conversion_rate = 1.95583
                else:
                    # Нови бележки - ако са в BGN, конвертираме, ако са в EUR, оставяме
                    conversion_rate = 1.95583 if is_bgn else 1.0
                
                # Извличане на артикули и цени
                lines = receipt.split('\n')
                products_found = 0
                
                # Обработка на редовете - запазваме индекса за обработка на килограмови продукти
                for i, line in enumerate(lines):
                    # Прескачаме редове с маркери за купони и отстъпки
                    if any(marker in line for marker in ['#Lidl Plus купон', '#Акция', 'ОТСТЪПКИ', 
                                                          'МЕЖДИННА СУМА', 'ОБЩА СУМА', 'В БРОЙ',
                                                          'КРЕДИТНА/ДЕБИТНА', 'РЕСТО', '-----',
                                                          'Ти спести', '#Ном:', '#Z-отчет:', '#Каса:']):
                        continue
                    
                    # Шаблони за различни формати цени
                    # Формат 1: "ПРОДУКТ    ЦЕНА B" или "ПРОДУКТ    ЦЕНА лв"
                    price_pattern1 = r'^([А-ЯA-Z][А-ЯA-ZА-Яа-я\s\.\,\'\"\-\/\(\)0-9]+?)\s{2,}(\d+[\.,]\d{2})\s*[BDлв]*\s*$'
                    match = re.match(price_pattern1, line.strip())
                    
                    if match:
                        product_name = match.group(1).strip()
                        price_str = match.group(2).replace(',', '.')
                        
                        try:
                            price = float(price_str)
                        except ValueError:
                            continue
                        
                        # Прескачаме очевидни не-продукти
                        skip_keywords = ['ОБЩА', 'ОБЩО', 'ПЛАТЕНО', 'СУМА', 'TOTAL', 'PAID', 'НАЛИЧНОСТ', 
                                       'МЕЖДИННА', 'ОТСТЪПКИ', 'DISCOUNT', 'БАНКОВА', 'КАРТА',
                                       'ВАУЧЕР', 'VOUCHER', 'СДАЧА', 'CHANGE', 'РЕСТО', 'В БРОЙ',
                                       'Ном:', 'Z-отчет', 'Каса:', 'Касиер:', 'АРТИКУЛА', 'Копие']
                        
                        if any(keyword in product_name.upper() for keyword in skip_keywords):
                            continue
                        
                        # Прескачаме твърде къси имена
                        if len(product_name) < 3:
                            continue
                        
                        # Прескачаме редове с количество (напр. "2,000 x 3,37")
                        if 'x' in product_name.lower() or 'х' in product_name.lower():
                            continue
                        
                        # Проверка дали е килограмов продукт
                        product_upper = product_name.upper()
                        is_kg_product = any(indicator in product_upper for indicator in 
                                          ['НА КГ', 'НА КГ.', '/КГ', ' КГ', 'НА KG', 'НА KG.', '/KG', ' KG']) or \
                                       product_upper.endswith('КГ') or product_upper.endswith('KG')
                        
                        final_price = price
                        
                        # Ако е килограмов продукт, търсим цената за кг в предишния ред
                        if is_kg_product and i > 0:
                            prev_line = lines[i-1].strip()
                            # Формат: "количество x цена_за_кг" (напр. "1,012 x 1,99" или "0,890 x 2,55")
                            kg_pattern = r'(\d+[\.,]\d+)\s*[xх]\s*(\d+[\.,]\d{2})'
                            kg_match = re.search(kg_pattern, prev_line)
                            
                            if kg_match:
                                # Използваме цената за кг вместо крайната цена
                                price_per_kg_str = kg_match.group(2).replace(',', '.')
                                try:
                                    price_per_kg = float(price_per_kg_str)
                                    # Конвертиране на цена ако е нужно
                                    final_price = price_per_kg / conversion_rate
                                except ValueError:
                                    # Ако не може да се парсне, използваме оригиналната цена
                                    final_price = price / conversion_rate
                            else:
                                # Ако не намерим шаблона, използваме оригиналната цена
                                final_price = price / conversion_rate
                        else:
                            # Конвертиране на цена ако е нужно (за не-килограмови продукти)
                            final_price = price / conversion_rate
                        
                        # Съхраняване на данните
                        products_data[product_name][receipt_date_str] = final_price
                        products_found += 1
                
                if products_found > 0:
                    self.log_message(f"  ✓ Бележка #{receipt_idx} ({receipt_date_str}): {products_found} артикула")
            
            self.log_message(f"\n✓ Общо обработени: {len(products_data)} уникални артикула")
            return products_data
            
        except Exception as e:
            raise Exception(f"Грешка при четене на файла: {e}")
    
    def generate_xlsx(self, products_data, source_file):
        """Генерира XLSX файл с анализ на цените"""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror(
                "Грешка", 
                "Библиотеката 'openpyxl' не е инсталирана!\n\n"
                "Моля инсталирайте я с командата:\n"
                "pip install openpyxl"
            )
            raise ImportError("openpyxl is not installed")
        
        # Създаване на работна книга
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Price History"
        
        # Събиране на всички уникални дати и сортиране
        all_dates = set()
        for dates_prices in products_data.values():
            all_dates.update(dates_prices.keys())
        
        sorted_dates = sorted(all_dates)
        
        # Създаване на хедър
        ws['A1'] = "Артикул"
        ws['A1'].font = Font(bold=True, size=12)
        ws['A1'].fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        ws['A1'].font = Font(bold=True, size=12, color="FFFFFF")
        ws['A1'].alignment = Alignment(horizontal='left', vertical='center')
        
        # Добавяне на дати като колони
        for idx, date in enumerate(sorted_dates, start=2):
            col_letter = get_column_letter(idx)
            ws[f'{col_letter}1'] = date
            ws[f'{col_letter}1'].font = Font(bold=True, size=11, color="FFFFFF")
            ws[f'{col_letter}1'].fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            ws[f'{col_letter}1'].alignment = Alignment(horizontal='center', vertical='center')
        
        # Добавяне на данни за продуктите
        row_idx = 2
        for product_name in sorted(products_data.keys()):
            ws[f'A{row_idx}'] = product_name
            ws[f'A{row_idx}'].alignment = Alignment(horizontal='left', vertical='center')
            
            dates_prices = products_data[product_name]
            
            for col_idx, date in enumerate(sorted_dates, start=2):
                col_letter = get_column_letter(col_idx)
                
                if date in dates_prices:
                    price = dates_prices[date]
                    cell = ws[f'{col_letter}{row_idx}']
                    cell.value = price
                    cell.number_format = '[$€-407] #,##0.00'  # EUR формат
                    cell.alignment = Alignment(horizontal='right', vertical='center')
            
            row_idx += 1
        
        # Настройка на ширина на колоните
        ws.column_dimensions['A'].width = 50
        for col_idx in range(2, len(sorted_dates) + 2):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 15
        
        # Добавяне на бордъри
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for row in ws.iter_rows(min_row=1, max_row=row_idx-1, min_col=1, max_col=len(sorted_dates)+1):
            for cell in row:
                cell.border = thin_border
        
        # Замръзване на първия ред и първата колона
        ws.freeze_panes = 'B2'
        
        # Генериране на име на файла
        base_name = os.path.splitext(source_file)[0]
        output_file = f"{base_name}_price_analysis.xlsx"
        
        # Запазване на файла
        wb.save(output_file)
        
        return output_file


def main():
    root = tk.Tk()
    app = LidlGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
