"""Анализ на изтеглени касови бележки: история на цените, XLSX, графики,
сезонен анализ на плодове и зеленчуци."""

import json
import re
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Callable, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import plotly.graph_objects as go

EUR_PER_BGN = 1.95583
EUR_INTRODUCTION_DATE = datetime(2026, 1, 1)

MONTHS_BG = {
    "януари": "01", "февруари": "02", "март": "03", "април": "04",
    "май": "05", "юни": "06", "юли": "07", "август": "08",
    "септември": "09", "октомври": "10", "ноември": "11", "декември": "12",
}

PRICE_PATTERN = r"^([А-ЯA-Z][А-ЯA-ZА-Яа-я\s\.\,\'\"\-\/\(\)0-9]+?)\s{2,}(\d+[\.,]\d{2})\s*[€BDлв#]*\s*$"
UNIT_PRICE_PATTERN = r"(\d+[\.,]\d+)\s*[xх]\s*(\d+[\.,]\d{2})"

SKIP_KEYWORDS = [
    "ОБЩА", "ОБЩО", "ПЛАТЕНО", "СУМА", "TOTAL", "PAID", "НАЛИЧНОСТ",
    "МЕЖДИННА", "ОТСТЪПКИ", "DISCOUNT", "БАНКОВА", "КАРТА",
    "ВАУЧЕР", "VOUCHER", "СДАЧА", "CHANGE", "РЕСТО", "В БРОЙ",
    "ЗА ПЛАЩАНЕ", "ПЛАЩАНЕ", "FOR PAYMENT", "PAYMENT",
    "Ном:", "Z-отчет", "Каса:", "Касиер:", "АРТИКУЛА", "Копие",
    "ЕЛ. КУПОН", "ЕЛ.КУПОН", "КУПОН",
]
SKIP_LINE_MARKERS = [
    "#Lidl Plus купон", "#Акция", "ОТСТЪПКИ",
    "МЕЖДИННА СУМА", "ОБЩА СУМА", "В БРОЙ",
    "КРЕДИТНА/ДЕБИТНА", "РЕСТО", "-----",
    "Ти спести", "#Ном:", "#Z-отчет:", "#Каса:",
]

# Списък с плодове и зеленчуци (ключови думи, срещани в касови бележки от LIDL.bg)
FRUITS_VEGETABLES_KEYWORDS = [
    "ЯБЪЛК", "БАНАН", "ПОРТОКАЛ", "МАНДАРИН", "ЛИМОН", "ГРЕЙПФРУТ", "ГРОЗДЕ",
    "ЯГОД", "МАЛИН", "КАПИН", "КАЙСИИ", "КАЙСИЯ", "ПРАСКОВИ", "ПРАСКОВА",
    "СЛИВ", "ЧЕРЕШ", "ВИШНИ", "ВИШНА", "ПЪПЕШ", "ДИНЯ", "КРУШ", "НЕКТАРИН",
    "СМОКИН", "НАР", "БОРОВИНК", "АРОНИЯ", "КАСИС", "КЛЕМЕНТИН", "САТСУМА",
    "МАНДАРИНК", "ПОРТОКАЛОВ", "ЛИМОНОВ",
    "АВОКАДО", "МАНГО", "АНАНАС", "ПАПАЯ", "МАРАКУЯ", "КИВИ", "ЛИЧИ", "РАМБУТАН",
    "ЛОНГАН", "ДУРИАН", "ДЖАКФРУТ", "КАРАМБОЛА", "ЗВЕЗДНА", "ПИТАЯ", "ДРАКОН",
    "ГУАВА", "ТАМАРИНД", "ПОМЕЛО", "ЮЗУ", "КУМКВАТ", "ФЕЙХОА",
    "ЧЕРИМОЯ", "САПОД", "МАМЕЙ", "АCЕРОЛА", "АЦЕРОЛА", "НОНИ", "ДЕРЕН",
    "ХУРМА", "ФИНИК", "СМОКИНЯ", "ИНЖИР", "ТАМАРИЛЬ", "ФИЗАЛИС", "ГОДЖИ",
    "ОБЛЕПИХ", "ШИПК", "ДЮЛЯ", "МУШМУЛ", "ДЖАНК", "ДЖАНКА",
    "КАНИСТЕЛ", "ДЖАБУТИКАБА", "НАНГКА", "САЛАК", "СНЕЙК ФРУТ",
    "БАБАКО", "БИРИМБИ", "КАРИССА", "ЛУКУМА", "НАШПИР",
    "ЦИТРОН", "БЕРГАМОТ", "КАФИР", "ПОМПЕЛМ", "БУДДХАС ХЕНД", "ХЕНД",
    "ПЕПИНО", "КУПУАСУ", "АСАИ", "АСАЙ", "МОНСТЕРА",
    "ЯГОДОПЛОДЕН", "ЦАРИГРАДСКО", "ЦАРИГРАДСК", "АГРУС",
    "АРБУТУС", "МИРТ", "МИРТА", "МОМИНА СЪЛЗА", "РОСИЦА", "КЛЮКВА", "КЛЮКВ",
    "БРУСНИЦ", "БРУСНИКА", "МОРОШК", "МОРОШКА", "ГОЛДЕН БЕРИ", "ГОЛДЪНБЕРИ",
    "ДОМАТ", "КРАСТАВИЦ", "ЧУШК", "КАРТОФ", "МОРКОВ", "ЛУКА", "ЛУК", "ЧЕСЪН",
    "ЗЕЛЕ", "БРОКОЛ", "КАРФИОЛ", "СПАНАК", "ТИКВА", "ПАТЛАДЖАН", "ТИКВИЧК",
    "МАРУЛЯ", "РЕПИЧК", "ЦЕЛИНА", "МАГДАНОЗ", "ПРАЗ", "АСПЕРЖИ", "АРТИШОК",
    "ЦВЕКЛО", "РЯПА", "КОПЪР", "РУКОЛА", "АЙСБЕРГ", "ЕНДИВИЯ", "ЦИКОРИЯ",
    "ЦАРЕВИЦ", "ГРАХ", "БОБ", "ЛЕЩА", "ПИПЕР", "ЧИЛИ", "ХАБАНЕРО", "ЯЛАДЖА",
    "ТИКВЕН", "ЗЕЛЕН", "ЗЕЛЕНЧУК", "САЛАТ", "МАШ", "НАХУТ", "СОЯ", "ЕДАМАМЕ",
    "СЛАДКА ЦАРЕВИЦ", "БРОКОЛИ", "КЕЙЛ", "МАНГОЛД", "МАНГОЛ",
    "ОКРА", "БАМЯ", "ГОРЧИЦА", "ГОРЧИЧН", "ПАКЧОЙ", "ПАК ЧОЙ", "БОКТАЙ",
    "КИТАЙСКО ЗЕЛЕ", "НАПА", "МИЗУН", "ТАТСОЙ", "КОМАЦУН", "ШИСО",
    "ДАЙКОН", "ЯПОНСК", "РЕДИС", "ХИКАМА", "ТАРО", "ЕДОК", "ЯМ", "БАТАТ",
    "СЛАДЪК КАРТОФ", "МАНИОКА", "КАСАВ", "ЯМС", "ТОПИНАМБУР", "ЕРУСАЛИМСК",
    "ПАЩЪРНАК", "СКОРЦОНЕРА", "ЗЕЛЕНА РЕПИЧК", "ВАСАБИ", "КОЛРАБИ",
    "ФЕНЕЛ", "КОПРИНЕН", "ОРИЗОВА КАША", "БАМБУКОВ", "БАМБУК ИЗДЪНИ",
    "ЛОТОС", "ЛОТУСОВ", "ВОДНА КЕСТЕН", "СИНАПТИЧН", "СИНАП",
    "КАРАМБОЛ", "ВИТЛОФ", "ЦИКОРИЙ", "РАКОВИН", "МОРКОВИ",
    "ЗЕМНА ЯБЪЛК", "ЧЕРНА РЕПА", "АЛТАЙСК", "АЛФАЛФ", "ЛЮЦЕРН",
    "КРЕСОН", "МИКРО", "МИКРОГРИЙН", "НИКНИК", "КЪЛНОВ", "КЪЛНОВЕ",
    "БЕЙБИ СПАНАК", "БЕЙБИ РУКОЛ", "БЕЙБИ МОРКОВ", "ЧЕРРИ ДОМАТ",
    "ЧЕРИ ДОМАТ", "КОКТЕЙЛЕН ДОМАТ", "СЛИВОВ ДОМАТ",
    "ГЪБИ", "ГЪБА", "ШАМПИНИОН", "СТРИДОВА", "ШИЙТАКЕ", "ПОРТОБЕЛО",
    "МАНАТАРК", "МАНАТАРКА", "ПАЧИ", "ЛИСИЧК", "ЛИСИЧКА", "ТРЮФЕЛ",
    "МАЦУТАКЕ", "ЕРИНГИЙ", "ЕНОКИ", "КРАЛСК", "КРАЛСКА ГЪБА",
    "ДЖИНДЖИФИЛ", "КУРКУМА", "ТУРМЕРИК", "БОСИЛЕК", "МЕНТА", "РИГАН",
    "МАЩЕРКА", "РОЗМАРИН", "ЛАВАНДУЛА", "ЧУБРИЦА", "ЕСТРАГОН", "ХРЯН",
    "ДЖОДЖЕН", "КОРИАНДЪР", "КОРИАНДЪ", "ЛИМОНОВА ТРЕВА", "ПАНДАН",
    "ГАЛАНГАЛ", "ЗЕЛЕН ЛИМОН", "КИНЗА", "КИНЗОВ", "МАТОЧИН",
    "ЛАЙМ", "ЛАЙМОВ", "ЦИТРУСОВ", "ЦИТРУС",
    "ПЛОД", "ПЛОДОВ", "ПЛОДОВ СОК", "ПРЕСНИ", "СВЕЖИ", "БИО ПЛОД",
    "БИО ЗЕЛЕНЧУК", "ОРГАНИЧ", "ФЕРМЕРСК", "СЕЗОНН",
]

# Продукти, чиито имена съдържат ключова дума за плод/зеленчук, но НЕ са такива
FV_EXCLUDE_KEYWORDS = [
    "ЛУКАНК", "НАРЯЗАН", "ЯМБОЛСК", "ЯМБОЛЕН",
    "ЯХНИЯ", "ЗЕЛЕНЧУКОВА ЯХН", "БОБОТИ",
    "МАНГОЛД", "СОКОЛ", "БАЛКАНКА", "БОБИНА",
    "СЛОЕНА", "СЛИВЕНСК", "ЗЕЛЕНОСАН", "ГРАХАМ",
]

# Летен сезон - месеци с по-ниски цени за свежи плодове/зеленчуци
SUMMER_MONTHS = {6, 7, 8, 9}
SUMMER_MONTHS_NAMES = "Юни, Юли, Август, Септември"
OFF_SEASON_MONTHS_NAMES = "Януари – Май, Октомври – Декември"


class ReceiptAnalyzer:
    def __init__(self, log: Optional[Callable[[str], None]] = None):
        self.log = log or (lambda message: print(message))
        # Единица за всеки продукт: '€/кг', '€/100г' или '€' (цена за пакет)
        self.products_units = {}

    def parse_files(self, file_paths) -> dict:
        """Парсва множество файлове и обединява продуктите в {product: {date: price}}."""
        products_data = defaultdict(dict)
        total_receipts = 0

        for file_idx, file_path in enumerate(file_paths, 1):
            self.log(f"\nФайл {file_idx}/{len(file_paths)}: {Path(file_path).name}")
            try:
                file_products = self.parse_file(file_path)
                for product_name, dates_prices in file_products.items():
                    for date_str, price in dates_prices.items():
                        if date_str in products_data[product_name]:
                            existing = products_data[product_name][date_str]
                            products_data[product_name][date_str] = (existing + price) / 2
                        else:
                            products_data[product_name][date_str] = price

                content = Path(file_path).read_text(encoding="utf-8")
                total_receipts += content.count("БЕЛЕЖКА #")
            except Exception as e:
                self.log(f"  Грешка при четене на файл: {e}")
                continue

        self.log(f"\nОбработени {total_receipts} бележки от {len(file_paths)} файла")
        self.log(f"Намерени {len(products_data)} уникални артикула")
        return products_data

    def parse_file(self, file_path) -> dict:
        """Парсва един файл с бележки и връща {product: {date: price}}."""
        products_data = defaultdict(dict)
        content = Path(file_path).read_text(encoding="utf-8")
        receipts = content.split("БЕЛЕЖКА #")

        self.log(f"  Намерени {len(receipts) - 1} бележки за парсинг...")

        for receipt_idx, receipt in enumerate(receipts[1:], 1):
            receipt_date_str = self._parse_receipt_date(receipt)
            if receipt_date_str is None:
                self.log(f"  Пропусната бележка #{receipt_idx} - не може да се извлече дата")
                continue

            try:
                receipt_date = datetime.strptime(receipt_date_str, "%Y-%m-%d")
            except ValueError:
                self.log(f"  Пропусната бележка #{receipt_idx} - невалидна дата")
                continue

            is_bgn = "BGN" in receipt or "# лв" in receipt or "лв  #" in receipt
            is_eur = "Евро" in receipt or "# Евро #" in receipt or "EUR" in receipt

            if receipt_date < EUR_INTRODUCTION_DATE:
                conversion_rate = EUR_PER_BGN
            else:
                conversion_rate = EUR_PER_BGN if is_bgn else 1.0

            products_found = 0
            lines = receipt.split("\n")

            for i, line in enumerate(lines):
                if any(marker in line for marker in SKIP_LINE_MARKERS):
                    continue

                match = re.match(PRICE_PATTERN, line.strip())
                if not match:
                    continue

                product_name = match.group(1).strip()
                price_str = match.group(2).replace(",", ".")

                try:
                    price = float(price_str)
                except ValueError:
                    continue

                if any(keyword in product_name.upper() for keyword in SKIP_KEYWORDS):
                    continue
                if len(product_name) < 3:
                    continue
                if "x" in product_name.lower() or "х" in product_name.lower():
                    continue

                final_price = price / conversion_rate

                if i > 0:
                    unit_match = re.search(UNIT_PRICE_PATTERN, lines[i - 1].strip())
                    if unit_match:
                        unit_price = float(unit_match.group(2).replace(",", "."))
                        final_price = unit_price / conversion_rate
                        self.products_units[product_name] = "€/кг"
                    else:
                        weight_kg, unit_label = self.extract_weight_from_name(product_name)
                        if weight_kg and weight_kg > 0:
                            if unit_label == "€/100г":
                                final_price = final_price / (weight_kg * 10)
                            else:
                                final_price = final_price / weight_kg
                            self.products_units[product_name] = unit_label
                        else:
                            self.products_units.setdefault(product_name, "€")

                products_data[product_name][receipt_date_str] = final_price
                products_found += 1

            if products_found > 0:
                self.log(f"    Бележка #{receipt_idx} ({receipt_date_str}): {products_found} артикула")

        self.log(f"  От този файл: {len(products_data)} уникални артикула")
        return products_data

    def _parse_receipt_date(self, receipt: str) -> Optional[str]:
        """Извлича датата на бележката в ISO формат от различни източници."""
        header = re.search(r"Дата:\s*(\d{4})-(\d{2})-(\d{2})", receipt)
        if header:
            year, month, day = header.groups()
            return f"{year}-{month}-{day}"

        dotted = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s+\d{2}:\d{2}:\d{2}", receipt)
        if dotted:
            day, month, year = dotted.groups()
            return f"{year}-{month}-{day}"

        dotted_year_first = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}", receipt)
        if dotted_year_first:
            year, month, day = dotted_year_first.groups()
            return f"{year}-{month}-{day}"

        for month_name, month_num in MONTHS_BG.items():
            match = re.search(r"(\d{1,2})\." + month_name, receipt.lower())
            if match:
                day = match.group(1).zfill(2)
                today = date.today()
                year = today.year
                if date(year, int(month_num), int(day)) > today:
                    year -= 1
                return f"{year}-{month_num}-{day}"
        return None

    def extract_weight_from_name(self, product_name: str):
        """Извлича теглото от името на продукта. Връща (weight_kg, unit_label) или (None, None)."""
        upper = product_name.upper()
        weight_kg = None

        for pat in [r"(\d+[\.,]?\d*)\s*КГ(?!\w)", r"(\d+[\.,]?\d*)\s*KG(?![A-Z])"]:
            match = re.search(pat, upper)
            if match:
                try:
                    value = float(match.group(1).replace(",", "."))
                    if 0.05 <= value <= 25:
                        weight_kg = value
                        break
                except ValueError:
                    pass

        if weight_kg is None:
            for pat in [r"(\d+[\.,]?\d*)\s*Л(?!\w)", r"(\d+[\.,]?\d*)\s*L(?![A-Z])"]:
                match = re.search(pat, upper)
                if match:
                    try:
                        value = float(match.group(1).replace(",", "."))
                        if 0.05 <= value <= 10:
                            weight_kg = value
                            break
                    except ValueError:
                        pass

        if weight_kg is None:
            for pat in [r"(\d{2,4})\s*ГР?(?!\w)", r"(\d{2,4})\s*GR?(?![A-Z])"]:
                match = re.search(pat, upper)
                if match:
                    try:
                        value = float(match.group(1))
                        if 10 <= value <= 9999:
                            weight_kg = value / 1000.0
                            break
                    except ValueError:
                        pass

        if weight_kg is None:
            return None, None

        unit_label = "€/100г" if weight_kg < 0.5 else "€/кг"
        return weight_kg, unit_label

    def is_fruit_or_vegetable(self, product_name: str) -> bool:
        """Проверява дали продуктът е плод или зеленчук."""
        upper_name = product_name.upper()
        if any(excl in upper_name for excl in FV_EXCLUDE_KEYWORDS):
            return False
        return any(keyword in upper_name for keyword in FRUITS_VEGETABLES_KEYWORDS)

    def generate_xlsx(self, products_data: dict, source_file: str) -> str:
        """Генерира XLSX файл с история на цените и връща пътя до него."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Price History"

        all_dates = set()
        for dates_prices in products_data.values():
            all_dates.update(dates_prices.keys())
        sorted_dates = sorted(all_dates)

        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, size=12, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        ws["A1"] = "Артикул"
        ws["B1"] = "Единица"
        for cell in (ws["A1"], ws["B1"]):
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center")
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
        ws["B1"].alignment = Alignment(horizontal="center", vertical="center")

        for idx, date_str in enumerate(sorted_dates, start=3):
            col_letter = get_column_letter(idx)
            formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            ws[f"{col_letter}1"] = formatted
            ws[f"{col_letter}1"].font = header_font
            ws[f"{col_letter}1"].fill = header_fill
            ws[f"{col_letter}1"].alignment = Alignment(horizontal="center", vertical="center")

        row_idx = 2
        for product_name in sorted(products_data.keys()):
            ws[f"A{row_idx}"] = product_name
            ws[f"B{row_idx}"] = self.products_units.get(product_name, "€")
            for cell in (ws[f"A{row_idx}"], ws[f"B{row_idx}"]):
                cell.alignment = Alignment(vertical="center")
            ws[f"B{row_idx}"].alignment = Alignment(horizontal="center", vertical="center")

            for col_idx, date_str in enumerate(sorted_dates, start=3):
                if date_str in products_data[product_name]:
                    col_letter = get_column_letter(col_idx)
                    cell = ws[f"{col_letter}{row_idx}"]
                    cell.value = products_data[product_name][date_str]
                    cell.number_format = "[$€-407] #,##0.00"
                    cell.alignment = Alignment(horizontal="right", vertical="center")

            for col_idx in range(1, len(sorted_dates) + 3):
                ws.cell(row=row_idx, column=col_idx).border = thin_border
            row_idx += 1

        ws.column_dimensions["A"].width = 50
        ws.column_dimensions["B"].width = 12
        for col_idx in range(3, len(sorted_dates) + 3):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15

        for cell in ws[1]:
            cell.border = thin_border

        ws.freeze_panes = "C2"

        output_file = Path(source_file).with_name(Path(source_file).stem + "_price_analysis.xlsx")
        wb.save(output_file)
        self.log(f"\nXLSX файлът е създаден успешно: {output_file}")
        return str(output_file)

    def generate_chart(self, xlsx_file: str) -> Optional[str]:
        """Генерира интерактивна HTML и статична PNG графика от XLSX файла."""
        from openpyxl import load_workbook

        wb = load_workbook(xlsx_file)
        ws = wb.active

        dates = []
        for col in range(3, ws.max_column + 1):
            date_str = ws.cell(row=1, column=col).value
            if date_str:
                try:
                    dates.append(datetime.strptime(date_str, "%d.%m.%Y"))
                except (ValueError, TypeError):
                    continue

        if not dates:
            self.log("Не са намерени дати в XLSX файла")
            return None

        products = []
        for row_idx in range(2, ws.max_row + 1):
            product_name = ws.cell(row=row_idx, column=1).value
            if not product_name:
                continue
            prices, valid_dates = [], []
            for col_idx, date in enumerate(dates, start=3):
                value = ws.cell(row=row_idx, column=col_idx).value
                if value is not None:
                    prices.append(float(value))
                    valid_dates.append(date)
            if len(prices) > 5:
                products.append(
                    {
                        "name": product_name,
                        "unit": ws.cell(row=row_idx, column=2).value or "€",
                        "dates": valid_dates,
                        "prices": prices,
                    }
                )

        if not products:
            self.log("Няма продукти с повече от 5 ценови записа")
            return None

        self.log(f"Намерени {len(products)} продукта с повече от 5 цени")

        fig = go.Figure()

        for product in products:
            unit = product["unit"] or self.products_units.get(product["name"], "€")
            fig.add_trace(
                go.Scatter(
                    x=product["dates"],
                    y=product["prices"],
                    mode="lines+markers",
                    name=product["name"],
                    hovertemplate=(
                        f"<b>%{{fullData.name}}</b><br>"
                        f"Дата: %{{x|%d.%m.%Y}}<br>"
                        f"Цена: %{{y:.2f}} {unit}<br>"
                        "<extra></extra>"
                    ),
                    line=dict(width=2),
                    marker=dict(size=6),
                )
            )

        fig.update_layout(
            title={
                "text": (
                    f"Промяна на цените на продуктите във времето<br>"
                    f"<sub>Продукти с повече от 5 записа: {len(products)}</sub>"
                ),
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 20},
            },
            xaxis=dict(title=dict(text="Дата", font=dict(size=14)), tickformat="%d.%m.%Y", gridcolor="lightgray"),
            yaxis=dict(title=dict(text="Цена (€/кг · €/100г · €/пакет)", font=dict(size=14)), gridcolor="lightgray"),
            hovermode="closest",
            template="plotly_white",
            height=800,
            showlegend=True,
            legend=dict(
                orientation="v", yanchor="top", y=1, xanchor="left", x=1.02,
                bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="lightgray", borderwidth=1,
            ),
            margin=dict(l=60, r=300, t=100, b=60),
        )
        fig.update_xaxes(rangeslider_visible=True)

        base_name = Path(xlsx_file).with_name(Path(xlsx_file).stem)
        html_file = f"{base_name}_interactive_chart.html"

        html_content = _build_chart_html(fig, products, self.products_units)
        Path(html_file).write_text(html_content, encoding="utf-8")
        self.log(f"Интерактивна графика запазена: {html_file}")

        try:
            self._save_static_png(products, base_name)
            self.log(f"Статична PNG графика запазена: {base_name}_chart.png")
        except Exception as e:
            self.log(f"Статичната PNG графика не можа да се генерира: {e}")

        return str(html_file)

    def _save_static_png(self, products: list, base_name: str) -> None:
        """Запазва статична PNG версия на графиката."""
        try:
            plt.style.use("seaborn-v0_8-darkgrid")
        except OSError:
            pass

        fig_height = max(8, min(20, 8 + len(products) * 0.3))
        fig_static, ax = plt.subplots(figsize=(16, fig_height))

        for product in products:
            short_name = product["name"][:35] + "..." if len(product["name"]) > 35 else product["name"]
            ax.plot(product["dates"], product["prices"], marker="o", linewidth=2, markersize=5, label=short_name, alpha=0.8)

        ax.set_xlabel("Дата", fontsize=12, weight="bold")
        ax.set_ylabel("Цена (€)", fontsize=12, weight="bold")
        ax.set_title(
            f"Промяна на цените на продуктите във времето (продукти с повече от 5 записа: {len(products)})",
            fontsize=14, weight="bold", pad=20,
        )
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha="right")

        if len(products) <= 15:
            ax.legend(loc="best", fontsize=8, framealpha=0.9)
        else:
            ncols = min(3, (len(products) + 9) // 10)
            ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=7, framealpha=0.9, ncol=ncols)

        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        fig_static.savefig(f"{base_name}_chart.png", dpi=200, bbox_inches="tight")
        plt.close(fig_static)

    def generate_seasonal_html(self, fv_data: dict, output_file: str) -> None:
        """Генерира HTML отчет със сезонно сравнение на цените на плодове/зеленчуци."""
        seasonal_stats = []

        for product_name, dates_prices in sorted(fv_data.items()):
            summer, off_season = [], []
            for date_str, price in dates_prices.items():
                try:
                    month = int(date_str[5:7])
                except (ValueError, IndexError):
                    continue
                (summer if month in SUMMER_MONTHS else off_season).append((date_str, price))

            if not summer and not off_season:
                continue

            avg_summer = sum(p for _, p in summer) / len(summer) if summer else None
            avg_off = sum(p for _, p in off_season) / len(off_season) if off_season else None
            diff_pct = ((avg_summer - avg_off) / avg_off) * 100 if avg_summer is not None and avg_off else None

            seasonal_stats.append(
                {
                    "name": product_name,
                    "summer_prices": sorted(summer),
                    "off_season_prices": sorted(off_season),
                    "avg_summer": avg_summer,
                    "avg_off": avg_off,
                    "diff_pct": diff_pct,
                    "all_prices": sorted(list(dates_prices.items())),
                }
            )

        seasonal_stats.sort(
            key=lambda x: (0 if x["diff_pct"] is not None else 1, -abs(x["diff_pct"]) if x["diff_pct"] is not None else 0)
        )

        traces = []
        for item in seasonal_stats:
            if len(item["all_prices"]) < 2:
                continue
            if item["diff_pct"] is not None:
                color = "#e74c3c" if item["diff_pct"] > 5 else ("#27ae60" if item["diff_pct"] < -5 else "#3498db")
            else:
                color = "#95a5a6"
            traces.append(
                {
                    "x": [d for d, _ in item["all_prices"]],
                    "y": [round(p, 4) for _, p in item["all_prices"]],
                    "mode": "lines+markers",
                    "name": item["name"],
                    "line": {"width": 2, "color": color},
                    "marker": {"size": 6},
                    "hovertemplate": f'<b>{item["name"]}</b><br>Дата: %{{x}}<br>Цена: %{{y:.2f}} €<extra></extra>',
                }
            )

        shapes_js = [
            {
                "type": "rect", "xref": "x", "yref": "paper",
                "x0": f"{yr}-06-01", "x1": f"{yr}-10-01",
                "y0": 0, "y1": 1,
                "fillcolor": "rgba(255,200,0,0.10)",
                "line": {"width": 0}, "layer": "below",
            }
            for yr in range(2024, 2028)
        ]

        traces_json = json.dumps(traces, ensure_ascii=False)
        shapes_json = json.dumps(shapes_js, ensure_ascii=False)

        def fmt_price(p):
            return f"{p:.2f} €" if p is not None else "–"

        def fmt_diff(d):
            if d is None:
                return "–", "#888"
            color = "#e74c3c" if d > 5 else ("#27ae60" if d < -5 else "#888")
            arrow = "↑" if d > 0 else "↓"
            return f"{arrow} {d:+.1f}%", color

        def price_details(prices):
            return ", ".join(
                f'<span title="{d}">{round(p, 2):.2f}</span>' for d, p in prices
            ) or "–"

        table_rows = ""
        for idx, item in enumerate(seasonal_stats, 1):
            diff_text, diff_color = fmt_diff(item["diff_pct"])
            row_bg = "#f8f9fa" if idx % 2 == 0 else "white"
            table_rows += f'''
            <tr style="background:{row_bg}">
              <td style="padding:8px;border:1px solid #ddd;text-align:center">{idx}</td>
              <td style="padding:8px;border:1px solid #ddd">{item["name"]}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center">{len(item["summer_prices"])}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:right">{fmt_price(item["avg_summer"])}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center">{len(item["off_season_prices"])}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:right">{fmt_price(item["avg_off"])}</td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center;font-weight:bold;color:{diff_color}">{diff_text}</td>
              <td style="padding:8px;border:1px solid #ddd;font-size:11px;color:#555">{price_details(item["summer_prices"])}</td>
              <td style="padding:8px;border:1px solid #ddd;font-size:11px;color:#555">{price_details(item["off_season_prices"])}</td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html lang="bg">
<head>
  <meta charset="utf-8">
  <title>Lidl – Сезонен анализ на плодове и зеленчуци</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
    h1 {{ color: #2c7a2c; }}
    h2 {{ color: #333; margin-top: 30px; }}
    .legend-box {{ display: inline-block; width: 14px; height: 14px;
                   border-radius: 3px; margin-right: 6px; vertical-align: middle; }}
    .info-banner {{ background: #fff3cd; border-left: 5px solid #ffc107;
                    padding: 12px 16px; margin-bottom: 20px; border-radius: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; font-size: 13px; }}
    thead tr {{ background: #2c7a2c; color: white; }}
    th {{ padding: 10px; border: 1px solid #999; }}
    .controls {{ margin-bottom: 16px; }}
    input[type=text] {{ padding: 7px; width: 260px; border: 1px solid #ccc;
                        border-radius: 4px; font-size: 14px; }}
    button {{ padding: 7px 18px; margin: 4px; border: none; border-radius: 4px;
              cursor: pointer; font-size: 13px; }}
    .btn-green {{ background: #2c7a2c; color: white; }}
    .btn-gray  {{ background: #6c757d; color: white; }}
  </style>
</head>
<body>
  <h1>🌿 Lidl – Сезонен анализ на плодове и зеленчуци</h1>

  <div class="info-banner">
    <strong>Легенда:</strong>
    <span class="legend-box" style="background:#ffc107;opacity:0.5"></span> Летен сезон ({SUMMER_MONTHS_NAMES}) |&nbsp;
    <span style="color:#e74c3c;font-weight:bold">↑ Скъпи лятото</span> (разлика &gt;5%) |&nbsp;
    <span style="color:#27ae60;font-weight:bold">↓ По-евтини лятото</span> (разлика &lt;–5%) |&nbsp;
    <span style="color:#888">≈ Без съществена разлика</span><br>
    <small>Цените са в EUR. Средната лятна цена се сравнява с извън-сезонната (жълтите ленти = юни – септември).</small>
  </div>

  <h2>📈 Ценова история</h2>
  <div class="controls">
    <input type="text" id="searchInput" placeholder="Търси продукт...">
    <button class="btn-green" onclick="filterTraces()">Филтрирай</button>
    <button class="btn-gray" onclick="showAllTraces()">Всички</button>
    <button class="btn-gray" onclick="hideAllTraces()">Скрий всички</button>
  </div>
  <div id="chart"></div>

  <h2>📊 Сравнителна таблица по сезон</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Продукт</th>
        <th>Брой цени<br>(лято)</th>
        <th>Ср. цена лято<br>({SUMMER_MONTHS_NAMES})</th>
        <th>Брой цени<br>(извън сезон)</th>
        <th>Ср. цена извън сезон<br>({OFF_SEASON_MONTHS_NAMES})</th>
        <th>Разлика</th>
        <th>Цени лято (€)</th>
        <th>Цени извън сезон (€)</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>

  <p style="margin-top:20px;color:#666;font-size:12px">
    Генерирано от Lidl Receipt Downloader • {datetime.now().strftime("%d.%m.%Y %H:%M")}
  </p>

  <script>
    var traces = {traces_json};
    var shapes = {shapes_json};
    var layout = {{
      title: 'Цени на плодове и зеленчуци (жълто = летен сезон)',
      xaxis: {{ title: 'Дата', tickformat: '%d.%m.%Y', rangeslider: {{visible: true}} }},
      yaxis: {{ title: 'Цена (€/кг)' }},
      shapes: shapes,
      hovermode: 'closest',
      template: 'plotly_white',
      height: 600,
      legend: {{ orientation: 'v', x: 1.02, y: 1 }},
      margin: {{l:60, r:260, t:80, b:60}}
    }};
    Plotly.newPlot('chart', traces, layout, {{responsive: true}});

    function filterTraces() {{
      var q = document.getElementById('searchInput').value.toLowerCase();
      if (!q) {{ showAllTraces(); return; }}
      var vis = traces.map(t => t.name.toLowerCase().includes(q));
      Plotly.restyle('chart', {{visible: vis}});
    }}
    function showAllTraces() {{
      Plotly.restyle('chart', {{visible: traces.map(() => true)}});
      document.getElementById('searchInput').value = '';
    }}
    function hideAllTraces() {{
      Plotly.restyle('chart', {{visible: traces.map(() => 'legendonly')}});
    }}
    document.getElementById('searchInput').addEventListener('keypress', function(e) {{
      if (e.key === 'Enter') filterTraces();
    }});
  </script>
</body>
</html>'''

        Path(output_file).write_text(html, encoding="utf-8")
        self.log(f"Сезонен отчет запазен: {output_file}")


def _build_chart_html(fig, products: list, products_units: dict) -> str:
    """Изгражда HTML-а на интерактивната графика с филтър и топ-10 таблици."""
    changes = []
    for product in products:
        prices = product["prices"]
        if len(prices) < 2 or prices[0] <= 0:
            continue
        min_i, max_i = prices.index(min(prices)), prices.index(max(prices))
        changes.append(
            {
                "name": product["name"],
                "unit": product.get("unit") or products_units.get(product["name"], "€"),
                "change_percent": ((prices[-1] - prices[0]) / prices[0]) * 100,
                "min_price": min(prices),
                "max_price": max(prices),
                "min_price_date": product["dates"][min_i].strftime("%d.%m.%Y"),
                "max_price_date": product["dates"][max_i].strftime("%d.%m.%Y"),
            }
        )

    changes.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
    top_up = changes[:10]
    top_down = sorted([c for c in changes if c["change_percent"] < 0], key=lambda x: x["change_percent"])[:10]

    def table_block(items, title, header_color):
        rows = ""
        for idx, item in enumerate(items, 1):
            row_bg = "#f8f9fa" if idx % 2 == 0 else "white"
            color = "#dc3545" if item["change_percent"] > 0 else "#28a745"
            arrow = "↑" if item["change_percent"] > 0 else "↓"
            rows += f'''
            <tr style="background-color: {row_bg};">
                <td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{idx}</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{item["name"]} <small style="color:#888">({item["unit"]})</small></td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold; color: {color};">{arrow} {item["change_percent"]:+.2f}%</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{item["min_price"]:.2f}<br><small style="color: #666;">({item["min_price_date"]})</small></td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{item["max_price"]:.2f}<br><small style="color: #666;">({item["max_price_date"]})</small></td>
            </tr>'''
        return f'''
            <div class="table-container" style="margin-top: 30px; padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #333; margin-bottom: 20px;">{title}</h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background-color: {header_color}; color: white;">
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">#</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Продукт</th>
                            <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Промяна (%)</th>
                            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Мин. цена (€)</th>
                            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Макс. цена (€)</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>'''

    top_up_html = table_block(top_up, "📊 Топ 10 продукти с най-голяма ценова промяна", "#007bff")
    top_down_html = table_block(top_down, "📉 Топ 10 продукти с най-голямо понижение на цените", "#28a745") if top_down else ""

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Lidl - Интерактивна графика на цените</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 100%;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .controls {{ margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
        .control-group {{ margin-bottom: 15px; }}
        label {{ font-weight: bold; margin-right: 10px; display: inline-block; width: 150px; }}
        input[type="text"] {{ padding: 8px; width: 300px; border: 1px solid #ddd; border-radius: 4px; }}
        button {{ padding: 8px 20px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }}
        .btn-primary {{ background-color: #007bff; color: white; }}
        .btn-primary:hover {{ background-color: #0056b3; }}
        .btn-secondary {{ background-color: #6c757d; color: white; }}
        .btn-secondary:hover {{ background-color: #545b62; }}
        .btn-success {{ background-color: #28a745; color: white; }}
        .btn-success:hover {{ background-color: #218838; }}
        .info {{ margin-top: 10px; padding: 10px; background-color: #d1ecf1; border-left: 4px solid #0c5460; color: #0c5460; }}
        #chart {{ margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛒 Lidl - Интерактивна графика на цените</h1>

        <div class="controls">
            <div class="control-group">
                <label>🔍 Търси продукт:</label>
                <input type="text" id="searchInput" placeholder="Въведете име на продукт...">
                <button class="btn-primary" onclick="filterProducts()">Филтрирай</button>
            </div>

            <div class="control-group">
                <button class="btn-success" onclick="showAll()">Покажи всички</button>
                <button class="btn-secondary" onclick="hideAll()">Скрий всички</button>
                <button class="btn-secondary" onclick="resetView()">Възстанови изглед</button>
            </div>

            <div class="info">
                <strong>💡 Съвети:</strong>
                <ul style="margin: 5px 0;">
                    <li>Кликнете на продукт в легендата за да го покажете/скриете</li>
                    <li>Използвайте мишката за приближаване (scroll) и местене (drag)</li>
                    <li>Използвайте филтъра за търсене на конкретни продукти</li>
                    <li>Двоен клик на легендата изолира един продукт</li>
                </ul>
            </div>
        </div>

        <div id="chart"></div>

        {top_up_html}

        {top_down_html}
    </div>

    <script>
        var plotData = {fig.to_json()};
        var layout = plotData.layout;
        var data = plotData.data;
        var config = {{
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToAdd: ['drawopenpath', 'eraseshape'],
            toImageButtonOptions: {{
                format: 'png',
                filename: 'lidl_prices_chart',
                height: 1080,
                width: 1920,
                scale: 2
            }}
        }};

        var originalVisibility = data.map(trace => trace.visible);
        Plotly.newPlot('chart', data, layout, config);

        function filterProducts() {{
            var searchText = document.getElementById('searchInput').value.toLowerCase();
            if (!searchText) {{ showAll(); return; }}
            Plotly.restyle('chart', {{
                visible: data.map(function(trace) {{
                    return trace.name.toLowerCase().includes(searchText);
                }})
            }});
        }}

        function showAll() {{
            Plotly.restyle('chart', {{visible: data.map(() => true)}});
            document.getElementById('searchInput').value = '';
        }}

        function hideAll() {{
            Plotly.restyle('chart', {{visible: data.map(() => 'legendonly')}});
        }}

        function resetView() {{
            Plotly.relayout('chart', {{
                'xaxis.autorange': true,
                'yaxis.autorange': true
            }});
        }}

        document.getElementById('searchInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{ filterProducts(); }}
        }});
    </script>
</body>
</html>'''