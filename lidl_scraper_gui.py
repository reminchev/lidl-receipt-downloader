"""Lidl Receipt Downloader - GUI.

Интерфейс за изтегляне на касови бележки от lidl.bg и анализ на цените.
Влизането е ръчно (в отворения от Playwright браузър) — пароли не се съхраняват.
"""

import asyncio
import os
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from tkcalendar import DateEntry

from config import load_config, save_config
from lidl_scraper import LidlReceiptDownloader
from receipt_analysis import ReceiptAnalyzer


class LidlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lidl Receipt Downloader")
        self.root.geometry("820x880")

        self.downloader = None
        self.download_thread = None
        self.current_page = 0
        self.use_period_var = tk.BooleanVar(value=False)

        self.config = load_config()
        self.output_dir = self.config["output_dir"]
        self.analysis_files = list(self.config.get("analysis_files", []))
        self.db_path = self.config.get(
            "db_path",
            str(Path(__file__).resolve().parent / "lidl_local_prices.db"),
        )

        self.setup_ui()
        self.load_saved_analysis_file()
        self.root.after(500, self._poll_progress)

    # ── UI ────────────────────────────────────────────────────────────────────
    def setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(7, weight=1)

        ttk.Label(self.root, text="Lidl Receipt Downloader", font=("Arial", 16, "bold")).grid(
            row=0, column=0, pady=(10, 0)
        )
        ttk.Label(self.root, text="Автоматично изтегляне на касови бележки от Lidl.bg", font=("Arial", 10)).grid(
            row=1, column=0
        )

        self._build_period_frame()
        self._build_dir_frame()
        self._build_download_frame()
        self._build_analysis_frame()
        self._build_status_frame()
        self._build_log_frame()

    def _build_period_frame(self):
        frame = ttk.LabelFrame(self.root, text="СТЪПКА 1: Период на бележките (опционално)", padding="10")
        frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=5)

        def date_entry():
            return DateEntry(frame, width=18, date_pattern="yyyy-mm-dd")

        ttk.Label(frame, text="От дата:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.start_date_entry = date_entry()
        self.start_date_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(frame, text="До дата:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.end_date_entry = date_entry()
        self.end_date_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Checkbutton(
            frame, text="Филтрирай по период", variable=self.use_period_var
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)

    def _build_dir_frame(self):
        frame = ttk.LabelFrame(self.root, text="СТЪПКА 2: Директория за съхранение", padding="10")
        frame.grid(row=3, column=0, sticky=tk.EW, padx=10, pady=5)
        frame.columnconfigure(0, weight=1)

        self.dir_label = ttk.Label(frame, text=self.output_dir, foreground="blue")
        self.dir_label.grid(row=0, column=0, sticky=tk.W, pady=5)

        ttk.Button(frame, text="Избери директория", command=self.choose_directory).grid(
            row=0, column=1, padx=5
        )

    def _build_download_frame(self):
        frame = ttk.LabelFrame(self.root, text="СТЪПКА 3: Изтегляне на бележки", padding="10")
        frame.grid(row=4, column=0, sticky=tk.EW, padx=10, pady=5)

        ttk.Label(
            frame,
            text="Натиснете 'Старт', влезте в акаунта си в отворения браузър, "
                 "след това натиснете 'Започни изтегляне'.",
            font=("Arial", 9),
            foreground="darkblue",
        ).grid(row=0, column=0, columnspan=3, pady=(0, 8), sticky=tk.W)

        self.start_button = ttk.Button(frame, text="1. Старт", command=self.start_download, width=18)
        self.start_button.grid(row=1, column=0, padx=5, pady=5)

        self.continue_button = ttk.Button(
            frame, text="2. Започни изтегляне", command=self.continue_after_ready,
            state=tk.DISABLED, width=20,
        )
        self.continue_button.grid(row=1, column=1, padx=5, pady=5)

        self.stop_button = ttk.Button(frame, text="Спиране", command=self.stop_download, state=tk.DISABLED, width=14)
        self.stop_button.grid(row=1, column=2, padx=5, pady=5)

    def _build_analysis_frame(self):
        frame = ttk.LabelFrame(self.root, text="СТЪПКА 4: Анализ на цени (опционално)", padding="10")
        frame.grid(row=5, column=0, sticky=tk.EW, padx=10, pady=5)
        frame.columnconfigure(0, weight=1)

        self.analysis_file_label = ttk.Label(frame, text="Няма избрани файлове", foreground="gray")
        self.analysis_file_label.grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)

        ttk.Button(frame, text="Избери файлове", command=self.choose_analysis_files).grid(
            row=0, column=1, padx=5
        )
        ttk.Button(frame, text="Избери папка", command=self.choose_analysis_folder).grid(
            row=0, column=2, padx=5
        )

        ttk.Button(
            frame, text="Анализ → XLSX + сезонен отчет",
            command=self.analyze_receipts,
        ).grid(row=1, column=0, columnspan=3, pady=8)

        ttk.Button(
            frame, text="Локална база данни → HTML",
            command=self.generate_local_db_report,
        ).grid(row=2, column=0, columnspan=3, pady=(0, 8))

    def _build_status_frame(self):
        frame = ttk.Frame(self.root, padding="10")
        frame.grid(row=6, column=0, sticky=tk.EW, padx=10)

        self.status_label = ttk.Label(frame, text="Готов за стартиране", foreground="green", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=0, padx=5)

        self.receipt_label = ttk.Label(frame, text="0 бележки", foreground="darkgreen", font=("Arial", 10, "bold"))
        self.receipt_label.grid(row=0, column=1, padx=15)

        self.timer_label = ttk.Label(frame, text="Време: 0с", foreground="blue", font=("Arial", 10))
        self.timer_label.grid(row=0, column=2, padx=15)

        self.page_progress = ttk.Progressbar(frame, mode="determinate", length=260)
        self.page_progress.grid(row=0, column=3, padx=15)

        self.page_progress_label = ttk.Label(frame, text="")
        self.page_progress_label.grid(row=0, column=4)

    def _build_log_frame(self):
        frame = ttk.LabelFrame(self.root, text="Детайлни логове", padding="10")
        frame.grid(row=7, column=0, sticky=tk.NSEW, padx=10, pady=5)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(frame, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)

    # ── Конфигурация ──────────────────────────────────────────────────────────
    def _persist_config(self):
        self.config["output_dir"] = self.output_dir
        if self.analysis_files:
            self.config["analysis_files"] = self.analysis_files
        save_config(self.config)

    def load_saved_analysis_file(self):
        existing = [f for f in self.analysis_files if os.path.exists(f)]
        self.analysis_files = existing
        if existing:
            self.analysis_file_label.config(text=f"Избрани {len(existing)} файла", foreground="blue")

    # ── Действия в UI ─────────────────────────────────────────────────────────
    def choose_directory(self):
        directory = filedialog.askdirectory(title="Избери директория за съхранение", initialdir=self.output_dir)
        if directory:
            self.output_dir = directory
            self.dir_label.config(text=directory)
            self.log_message(f"Избрана директория: {directory}")
            self._persist_config()

    def choose_analysis_files(self):
        paths = filedialog.askopenfilenames(
            title="Избери файлове с касови бележки",
            initialdir=self.output_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if paths:
            self.analysis_files = list(paths)
            self._set_analysis_files_ui(len(paths))
            self._persist_config()

    def choose_analysis_folder(self):
        folder = filedialog.askdirectory(title="Избери папка с касови бележки", initialdir=self.output_dir)
        if not folder:
            return
        txt_files = [str(p) for p in Path(folder).glob("*.txt")]
        if txt_files:
            self.analysis_files = txt_files
            self._set_analysis_files_ui(len(txt_files))
            self.log_message(f"Намерени {len(txt_files)} txt файла в папката")
            self._persist_config()
        else:
            messagebox.showwarning("Внимание", "Няма намерени txt файлове в избраната папка!")

    def _set_analysis_files_ui(self, count):
        self.analysis_file_label.config(text=f"Избрани {count} файла", foreground="blue")
        self.log_message(f"Избрани {count} файла за анализ")

    # ── Логване и статус (thread-safe) ────────────────────────────────────────
    def log_message(self, message):
        match = re.search(r"СТРАНИЦА (\d+)", message)
        if match:
            self.current_page = int(match.group(1))

        def _log():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)

        if threading.current_thread() != threading.main_thread():
            self.root.after(0, _log)
        else:
            _log()

    def update_status(self, message, color="black"):
        def _update():
            self.status_label.config(text=message, foreground=color)

        if threading.current_thread() != threading.main_thread():
            self.root.after(0, _update)
        else:
            _update()

    def _poll_progress(self):
        """Периодично обновява брояча на бележки, таймера и прогреса по страници."""
        if self.downloader and self.downloader.start_time:
            count = len(self.downloader.receipts)
            elapsed = int(time.time() - self.downloader.start_time)
            minutes, seconds = divmod(elapsed, 60)
            hours, minutes = divmod(minutes, 60)
            time_str = f"{hours}ч {minutes}м {seconds}с" if hours else f"{minutes}м {seconds}с"
            self.receipt_label.config(text=f"{count} бележки")
            self.timer_label.config(text=f"Време: {time_str}")
            if self.current_page:
                percent = min(100, (self.current_page / 100) * 100)
                self.page_progress["value"] = percent
                self.page_progress_label.config(text=f"стр. {self.current_page}")
        self.root.after(500, self._poll_progress)

    # ── Изтегляне ─────────────────────────────────────────────────────────────
    def start_download(self):
        if not os.path.exists(self.output_dir):
            messagebox.showerror("Грешка", "Избраната директория не съществува!")
            return

        start_date = end_date = None
        if self.use_period_var.get():
            try:
                start_date = self.start_date_entry.get_date().strftime("%Y-%m-%d")
                end_date = self.end_date_entry.get_date().strftime("%Y-%m-%d")
            except Exception:
                messagebox.showerror("Грешка", "Невалидни дати в периода!")
                return
            if start_date > end_date:
                messagebox.showerror("Грешка", "Началната дата не може да е след крайната!")
                return

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.continue_button.config(state=tk.NORMAL)
        self.start_date_entry.config(state=tk.DISABLED)
        self.end_date_entry.config(state=tk.DISABLED)

        self.log_text.delete(1.0, tk.END)
        self.current_page = 0
        self.receipt_label.config(text="0 бележки")
        self.timer_label.config(text="Време: 0с")
        self.page_progress["value"] = 0
        self.update_status("Изчакване за влизане...", "orange")

        self.downloader = LidlReceiptDownloader(
            self.output_dir, start_date=start_date, end_date=end_date, log=self.log_message
        )
        self.download_thread = threading.Thread(target=self.run_download, daemon=True)
        self.download_thread.start()

    def run_download(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.downloader.download_all_receipts())

            if self.downloader.receipts and not self.downloader.is_cancelled:
                file_path = self.downloader.save_to_file()
                self.update_status("Завършено успешно", "green")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Успех",
                        f"Успешно изтеглени {len(self.downloader.receipts)} бележки!\n\nФайл: {file_path}",
                    ),
                )
            elif self.downloader.is_cancelled:
                self.update_status("Прекъснато", "orange")
                if self.downloader.receipts:
                    file_path = self.downloader.save_to_file()
                    self.root.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Прекъснато",
                            f"Процесът беше прекъснат.\nЗапазени {len(self.downloader.receipts)} бележки.\n\nФайл: {file_path}",
                        ),
                    )
            else:
                self.update_status("Няма намерени бележки", "orange")
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Внимание",
                        "Не са намерени касови бележки.\n\nВъзможни причини:\n"
                        "- Няма покупки в историята\n- Проблем с влизането в акаунта\n"
                        "- Структурата на сайта е променена\n- Всички бележки са извън избрания период",
                    ),
                )
        except Exception as e:
            self.log_message(f"Грешка при изтегляне: {e}")
            self.update_status("Грешка", "red")
            self.root.after(0, lambda: messagebox.showerror("Грешка", f"Възникна грешка при изтеглянето:\n\n{e}"))
        finally:
            self.root.after(0, self.reset_ui)

    def continue_after_ready(self):
        if self.downloader:
            self.downloader.ready_to_start = True
            self.continue_button.config(state=tk.DISABLED)
            self.update_status("Изтегляне...", "blue")
            self.log_message("Стартиране на изтегляне на бележки...")

    def stop_download(self):
        if self.downloader:
            self.downloader.is_cancelled = True
            self.stop_button.config(state=tk.DISABLED)
            self.log_message("Изпращане на сигнал за прекъсване...")

    def reset_ui(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.continue_button.config(state=tk.DISABLED)
        self.start_date_entry.config(state=tk.NORMAL)
        self.end_date_entry.config(state=tk.NORMAL)

    # ── Анализ ────────────────────────────────────────────────────────────────
    def generate_local_db_report(self):
        try:
            analyzer = ReceiptAnalyzer(log=self.log_message, db_path=self.db_path)
            report_path = f"{Path(self.output_dir).resolve() / 'local_price_history.html'}"
            analyzer.generate_local_db_report(str(report_path))
            self.log_message(f"Локална база данни → HTML: {report_path}")
            messagebox.showinfo("Успех", f"Локалният отчет е създаден:\n\n{report_path}")
        except Exception as e:
            self.log_message(f"Грешка при създаване на локален отчет: {e}")
            messagebox.showerror("Грешка", f"Неуспешно създаване на локален отчет:\n\n{e}")

    def analyze_receipts(self):
        if not self.analysis_files:
            self.choose_analysis_files()
            if not self.analysis_files:
                return

        existing = [f for f in self.analysis_files if os.path.exists(f)]
        if not existing:
            messagebox.showerror("Грешка", "Избраните файлове не съществуват! Моля изберете други файлове.")
            self.analysis_files = []
            self.analysis_file_label.config(text="Няма избрани файлове", foreground="gray")
            return

        self.analysis_files = existing
        analyzer = ReceiptAnalyzer(log=self.log_message, db_path=self.db_path)

        self.log_message(f"Стартиране на анализ на {len(self.analysis_files)} файла:")
        for file_path in self.analysis_files:
            self.log_message(f"  - {os.path.basename(file_path)}")
        self.update_status("Анализ...", "blue")

        try:
            products_data = analyzer.parse_files(self.analysis_files)
            if not products_data:
                messagebox.showwarning("Внимание", "Не са намерени артикули за анализ!")
                self.update_status("Няма данни", "orange")
                return

            filtered = {
                product: dates_prices
                for product, dates_prices in products_data.items()
                if len(dates_prices) > 1
            }
            if not filtered:
                messagebox.showwarning("Внимание", "Не са намерени артикули, които се срещат повече от веднъж!")
                self.update_status("Няма данни", "orange")
                return

            self.log_message(f"Намерени {len(filtered)} артикула с повече от 1 покупка "
                             f"(общо {len(products_data)} уникални)")

            base_file = self.analysis_files[0]
            output_file = analyzer.generate_xlsx(filtered, base_file)
            chart_file = analyzer.generate_chart(output_file)
            
            base_output_dir = Path(self.output_dir).resolve()
            self.log_message("")
            self.log_message("📁 ФАЙЛОВЕ:")
            if output_file:
                self.log_message(f"  XLSX: {base_output_dir / Path(output_file).name}")
            if chart_file:
                self.log_message(f"  Графика: {base_output_dir / Path(chart_file).name}")

            fv_data = {
                name: dates_prices
                for name, dates_prices in products_data.items()
                if analyzer.is_fruit_or_vegetable(name)
            }
            seasonal_file = None
            if fv_data:
                self.log_message(f"Генериране на сезонен анализ за {len(fv_data)} плода/зеленчука...")
                seasonal_file = str(base_output_dir / f"{Path(base_file).stem}_seasonal_analysis.html")
                analyzer.generate_seasonal_html(fv_data, seasonal_file)
                self.log_message(f"  Сезонен анализ: {seasonal_file}")
            else:
                self.log_message("Не са намерени плодове/зеленчуци за сезонен анализ")

            years_rows = analyzer.compare_years(products_data)
            years_file = None
            if years_rows:
                self.log_message(f"Генериране на сравнение 2025/2026 за {len(years_rows)} съпоставими артикула...")
                years_file = str(base_output_dir / f"{Path(base_file).stem}_years_comparison.html")
                analyzer.generate_years_html(years_rows, years_file)
                self.log_message(f"  📊 Годишен отчет (2025/2026): {years_file}")
            else:
                self.log_message("Няма артикули с данни и за 2025, и за 2026")

            # Генериране на лендинг страница
            self.log_message("Генериране на лендинг страница...")
            index_file = str(base_output_dir / f"{Path(base_file).stem}_index.html")
            files_info = {
                "xlsx": output_file,
                "chart": chart_file,
                "seasonal": seasonal_file,
                "years": years_file,
            }
            analyzer.generate_index_html(index_file, files_info)
            self.log_message(f"  🏠 Начална страница: {index_file}")

            self.update_status("Анализ завършен", "green")
            messagebox.showinfo(
                "Успех",
                f"Анализът завърши успешно!\n\n"
                f"Артикули с повече от 1 покупка: {len(filtered)}\n"
                f"Общо уникални артикули: {len(products_data)}\n"
                f"Плодове/зеленчуци за сезонен анализ: {len(fv_data)}\n"
                f"Съпоставими артикули 2025/2026: {len(years_rows)}\n\n"
                f"XLSX: {os.path.basename(output_file)}\n"
                f"Графика: {os.path.basename(chart_file) if chart_file else 'N/A'}\n"
                f"Сезонен отчет: {os.path.basename(seasonal_file) if seasonal_file else 'N/A'}\n"
                f"Сравнение 2025/2026: {os.path.basename(years_file) if years_file else 'N/A'}\n"
                f"Лендинг страница: {os.path.basename(index_file)}",
            )
        except Exception as e:
            self.log_message(f"Грешка при анализ: {e}")
            self.update_status("Грешка при анализ", "red")
            messagebox.showerror("Грешка", f"Грешка при анализ:\n\n{e}")


def main():
    root = tk.Tk()
    LidlGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()