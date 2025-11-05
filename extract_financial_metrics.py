import sys
import json
import re
from pathlib import Path
from typing import Dict, Any

# This script reads a PDF or CSV path from argv[1] and prints a JSON with metrics.
# It uses pure-Python pypdf to avoid system dependencies like 'pdftotext'.

def extract_text_from_pdf(pdf_path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            # Some pages may fail to extract cleanly; continue best-effort
            continue
    return "\n".join(texts)

def parse_metrics_from_text(text: str) -> Dict[str, Any]:
    # Normalize
    t = text.replace(",", "")
    # Simple regex helpers for US-style statements (P&L)
    def find_amount(label_variants):
        for lbl in label_variants:
            # look for the label followed by optional punctuation and any non-digit chars, then a signed/decimal number
            m = re.search(rf"{lbl}\s*[:\-]?\s*\$?(-?\d+(\.\d+)?)", t, flags=re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except Exception:
                    pass
        return None

    revenue = find_amount([r"total revenue", r"revenue", r"sales", r"total income"])
    cogs = find_amount([r"cost of goods sold", r"cogs", r"cost of sales"])
    gross_profit = find_amount([r"gross profit"])
    total_exp = find_amount([r"total expenses", r"expenses total", r"operating expenses"])
    net_income = find_amount([r"net income", r"net profit", r"profit \(loss\)", r"net earnings"])

    # Compute missing pieces if possible
    if gross_profit is None and revenue is not None and cogs is not None:
        gross_profit = revenue - cogs
    if net_income is None and revenue is not None and total_exp is not None and cogs is not None:
        net_income = revenue - cogs - total_exp

    result = {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "total_expenses": total_exp,
        "net_income": net_income,
    }
    return result

def extract_from_csv(csv_path: Path) -> Dict[str, Any]:
    import csv
    total_revenue = 0.0
    cogs = 0.0
    expenses = 0.0
    net = None
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)
    flat = " ".join(",".join(r) for r in rows).lower().replace(",", "")
    # Heuristics for CSV exports
    def num_after(keyword):
        m = re.search(rf"{re.escape(keyword)}\s*\$?(-?\d+(\.\d+)?)", flat)
        if m:
            return float(m.group(1))
        return None
    total_revenue = num_after("total revenue") or num_after("revenue") or num_after("sales") or 0.0
    cogs = num_after("cost of goods sold") or num_after("cogs") or 0.0
    expenses = num_after("total expenses") or 0.0
    net = num_after("net income") or (total_revenue - cogs - expenses if any([total_revenue, cogs, expenses]) else None)
    return {
        "revenue": total_revenue,
        "cogs": cogs,
        "gross_profit": (total_revenue - cogs) if total_revenue and cogs is not None else None,
        "total_expenses": expenses,
        "net_income": net,
    }

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path provided"}))
        return
    path = Path(sys.argv[1])
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        return

    try:
        if path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(path)
            data = parse_metrics_from_text(text)
        elif path.suffix.lower() == ".csv":
            data = extract_from_csv(path)
        else:
            print(json.dumps({"error": "Unsupported file type"}))
            return

        # Basic sanity post-processing
        # Round floats to 2 decimals
        for k, v in list(data.items()):
            if isinstance(v, float):
                data[k] = round(v, 2)
        print(json.dumps({"ok": True, "metrics": data}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
