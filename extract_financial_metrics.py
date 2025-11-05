"""
extract_financial_metrics.py
--------------------------------

This script extracts high-level financial metrics from a Profit and Loss (P&L) PDF report.
It relies on the command‑line utility ``pdftotext`` to convert the PDF into text on
the fly (``pdftotext`` is commonly available on Linux systems). Once the text is
extracted, the script searches for keywords to identify totals for income, cost
of goods sold (COGS), operating expenses, other expenses, and net income. It then
computes a few key metrics such as total expenses and net margin.

Supported keywords:

* ``Total for Income`` or ``Total de ingresos`` – identifies total income
* ``Total for Cost of Goods Sold`` or ``Costo de ventas`` – identifies COGS
* ``Total for Expenses`` or ``Total de gastos`` – identifies operating expenses
* ``Total for Other Expenses`` or ``Otros gastos`` – identifies other expenses
* ``Net Income`` or ``Utilidad neta`` – identifies net income

If only a subset of metrics is found, the script will still compute available
statistics. Numbers with comma separators are handled correctly, and negative
values (prefaced with a minus sign) are supported.

Usage:
    python extract_financial_metrics.py /path/to/report.pdf

This will print a JSON object with the extracted metrics.
"""

import json
import os
import re
import subprocess
import sys
from typing import Dict, Optional


def run_pdftotext(pdf_path: str) -> str:
    """Run pdftotext on the given PDF and return the extracted text.

    If pdftotext is not available or fails, this function raises a RuntimeError.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        # The '-' argument tells pdftotext to write the output to stdout.
        output = subprocess.check_output(["pdftotext", pdf_path, "-"], stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError(
            "'pdftotext' command not found. Please install poppler utils or ensure it's in your PATH."
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running pdftotext: {e.stderr.decode().strip()}")

    return output.decode("utf-8", errors="ignore")


def parse_amount(text: str) -> Optional[float]:
    """Convert a textual number into a float.

    Removes commas, periods used as thousands separators and handles negative numbers.
    Returns None if no valid number is found.
    """
    # Remove currency symbols and whitespace
    text = text.strip()
    # Replace commas used as thousand separators with nothing, and
    # ensure decimal separators are standard.
    # Detect if the number uses comma as decimal separator (e.g., 1.234,56)
    # Detect European format: at least one dot as thousands separator and a comma as decimal
    # Example: '1.234,56' should match, but '846,432.15' (US format) should not.
    if re.match(r"^-?\d{1,3}(?:\.\d{3})+,\d+$", text):
        # European format: '.' thousands, ',' decimal
        clean_text = text.replace(".", "").replace(",", ".")
    else:
        # Assume US format: ',' thousands, '.' decimal
        clean_text = text.replace(",", "")
    # Remove currency symbols
    clean_text = re.sub(r"[\$€¥£]", "", clean_text)
    try:
        return float(clean_text)
    except ValueError:
        return None


def extract_metrics_from_text(text: str) -> Dict[str, float]:
    """Extract financial metrics from the given text and return a dictionary.

    The extraction is tolerant to line breaks between labels and values.
    It scans through the text line by line, looking for known labels (in
    English and Spanish). When a label is found, the function scans forward
    in the subsequent lines until it encounters a token that looks like a
    number and parses it into a float.

    Returns a dictionary containing found metrics and, when possible,
    derived metrics such as total_expenses and margin.
    """
    # First, attempt to extract metrics using regex patterns on a flattened string
    # Replace newlines with spaces to simplify pattern matching across lines
    flat_text = re.sub(r"\s+", " ", text)
    # Patterns keyed by metric name; matches a label followed by optional whitespace and a number.
    # Regex patterns keyed by metric name. We only use regex for income and net_income,
    # because totals for COGS, expenses and other expenses are often not contiguous with
    # their labels and require line-based scanning.
    regex_patterns = {
        "income": r"(?:Total for Income|Total de ingresos)\s*\$?([-]?[0-9][0-9.,]*)",
        "net_income": r"(?:Net Income|Utilidad neta|Ingreso neto)\s*\$?([-]?[0-9][0-9.,]*)",
    }

    metrics: Dict[str, Optional[float]] = {
        "income": None,
        "cogs": None,
        "expenses": None,
        "other_expenses": None,
        "net_income": None,
    }

    # Apply regex extraction
    for key, pattern in regex_patterns.items():
        match = re.search(pattern, flat_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            amount = parse_amount(amount_str)
            if amount is not None:
                metrics[key] = amount

    # For any metric not found via regex, fall back to line‑by‑line scanning
    if None in metrics.values():
        lines = text.splitlines()
        # Mapping of metric keys to possible label keywords (case-insensitive)
        label_map = {
            "income": ["total for income", "total de ingresos"],
            "cogs": ["total for cost of goods sold", "costo de ventas", "total del costo de ventas"],
            "expenses": ["total for expenses", "total de gastos"],
            "other_expenses": ["total for other expenses", "otros gastos"],
            "net_income": ["net income", "utilidad neta", "ingreso neto"],
        }

        def scan_for_number(start_index: int) -> Optional[float]:
            """Scan forward from the given line index and return the largest numeric candidate.

            This function looks ahead up to 10 lines after the label and collects all
            numbers it encounters. It returns the maximum absolute value among them,
            under the assumption that the total is typically the largest magnitude
            number in the group.
            """
            numbers: list[float] = []
            for j in range(start_index, min(len(lines), start_index + 10)):
                candidate = lines[j].strip()
                if not candidate:
                    continue
                # Remove currency symbols
                candidate_clean = re.sub(r"[\$€¥£]", "", candidate)
                # Extract potential numeric tokens separated by whitespace
                tokens = re.split(r"\s+", candidate_clean)
                for tok in tokens:
                    if re.search(r"\d", tok):
                        num = parse_amount(tok)
                        if num is not None:
                            numbers.append(num)
            if not numbers:
                return None
            # Return the value with the largest absolute value (handles negatives)
            return max(numbers, key=abs)

        for i, line in enumerate(lines):
            lower_line = line.strip().lower()
            for key, keywords in label_map.items():
                if metrics[key] is not None:
                    continue
                for kw in keywords:
                    if lower_line.startswith(kw):
                        value = scan_for_number(i + 1)
                        if value is not None:
                            metrics[key] = value
                        break

    # Compute derived metrics
    income = metrics.get("income")
    cogs = metrics.get("cogs") or 0.0
    expenses = metrics.get("expenses") or 0.0
    other_expenses = metrics.get("other_expenses") or 0.0
    net_income = metrics.get("net_income")

    total_expenses = cogs + expenses + other_expenses
    margin = None
    if income and income != 0 and net_income is not None:
        margin = (net_income / income) * 100

    result: Dict[str, float] = {}
    if income is not None:
        result["income"] = income
    if cogs:
        result["cogs"] = cogs
    if expenses:
        result["expenses"] = expenses
    if other_expenses:
        result["other_expenses"] = other_expenses
    if net_income is not None:
        result["net_income"] = net_income
    if total_expenses:
        result["total_expenses"] = total_expenses
    if margin is not None:
        result["margin"] = margin

    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python extract_financial_metrics.py /path/to/report.pdf", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    try:
        text = run_pdftotext(pdf_path)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    metrics = extract_metrics_from_text(text)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()