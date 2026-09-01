import csv
import io
import os
import re
import openpyxl
import pdfplumber


def clean_price_value(raw_val):
    """Clean various price representations into a float.
    Handles 'Rs. 4,500', '4500/-', '$25.00', 'PKR 12,000.00', etc.
    """
    if raw_val is None:
        return None
    if isinstance(raw_val, (int, float)):
        return float(raw_val) if raw_val >= 0 else None

    text = str(raw_val).strip()
    if not text:
        return None

    # Remove currency symbols, commas, trailing '/-' or '.-'
    text = re.sub(r'(?i)(rs\.?|pkr|\$|eur|usd|/-|\.-)', '', text).strip()
    text = text.replace(',', '')

    # Match numeric portion
    m = re.search(r'(\d+(?:\.\d{1,2})?)', text)
    if m:
        try:
            val = float(m.group(1))
            return val if val >= 0 else None
        except ValueError:
            return None
    return None


def extract_from_pdf(pdf_source):
    """Extract product names and catalogue prices from a PDF file.
    
    Supports:
      1. Grid/Tabular catalogues (detected via pdfplumber extract_tables)
      2. Columnar/Text catalogues (detected line-by-line)
      
    Returns:
      (products_list, csv_text)
    """
    products = []

    with pdfplumber.open(pdf_source) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables() or []
            table_handled = False

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Header detection
                header = [str(c or '').strip().lower() for c in table[0]]
                name_col = -1
                price_col = -1
                stock_col = -1

                for idx, col in enumerate(header):
                    if any(k in col for k in ['product', 'item', 'description', 'title', 'model', 'name']):
                        if name_col == -1:
                            name_col = idx
                    if any(k in col for k in ['price', 'cost', 'rate', 'rs', 'amount', 'pkr', 'wholesale', 'catalog']):
                        if price_col == -1:
                            price_col = idx
                    if any(k in col for k in ['stock', 'qty', 'quantity']):
                        if stock_col == -1:
                            stock_col = idx

                # If no clear headers, inspect first few data rows
                if name_col == -1 or price_col == -1:
                    for sample_row in table[1:4]:
                        for idx, cell in enumerate(sample_row):
                            cell_txt = str(cell or '').strip()
                            if price_col == -1 and clean_price_value(cell_txt) is not None and re.search(r'\d+', cell_txt):
                                price_col = idx
                            elif name_col == -1 and len(cell_txt) > 3 and not re.match(r'^\d+$', cell_txt):
                                name_col = idx

                if name_col != -1 and price_col != -1 and name_col != price_col:
                    table_handled = True
                    for row in table[1:]:
                        if len(row) > max(name_col, price_col):
                            name_val = str(row[name_col] or '').strip()
                            price_val = clean_price_value(row[price_col])
                            stock_val = 20
                            if stock_col != -1 and len(row) > stock_col:
                                try:
                                    stock_val = max(0, int(re.sub(r'\D', '', str(row[stock_col] or '')) or 20))
                                except ValueError:
                                    stock_val = 20

                            # Filter out false headers or empty lines
                            if name_val and len(name_val) >= 2 and price_val is not None and price_val > 0:
                                if name_val.lower() not in ['product name', 'item', 'description', 'total']:
                                    products.append({
                                        'name': name_val,
                                        'catalogue_price': price_val,
                                        'stock': stock_val
                                    })

            # Fallback to line-by-line regex if table extraction didn't yield items on this page
            if not table_handled:
                text = page.extract_text() or ''
                for line in text.splitlines():
                    cleaned = line.strip()
                    if not cleaned or len(cleaned) < 4:
                        continue

                    # Filter out catalogue title headers (e.g. "Product Catalogue 2026", "Price List 2025")
                    header_noise = ['catalogue', 'catalog', 'price list', 'pricelist', 'brochure', 'page ', 'total', 'subtotal', 'date:']
                    if any(w in cleaned.lower() for w in header_noise):
                        continue

                    # Regex looking for Name followed by Price at the end
                    match = re.search(
                        r'^(.*?)(?:Rs\.?|PKR|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:/-)?$',
                        cleaned, re.IGNORECASE
                    )
                    if match:
                        p_name = match.group(1).strip(' \t-:.•*|#')
                        p_price = clean_price_value(match.group(2))
                        if p_name and len(p_name) >= 2 and p_price and p_price > 0:
                            if not any(w in p_name.lower() for w in header_noise):
                                products.append({
                                    'name': p_name,
                                    'catalogue_price': p_price,
                                    'stock': 20
                                })


    # Generate equivalent CSV representation
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product Name', 'Catalogue Price', 'Stock'])
    for p in products:
        writer.writerow([p['name'], f"{p['catalogue_price']:.2f}", p['stock']])
    csv_text = output.getvalue()

    return products, csv_text


def extract_from_csv(csv_content):
    """Extract product names and catalogue prices from CSV content."""
    products = []
    # Read text
    if isinstance(csv_content, bytes):
        text = csv_content.decode('utf-8', errors='replace')
    else:
        text = csv_content

    # Detect delimiter
    sample = text[:2048]
    delimiter = ','
    if '\t' in sample and sample.count('\t') > sample.count(','):
        delimiter = '\t'
    elif ';' in sample and sample.count(';') > sample.count(','):
        delimiter = ';'

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return products

    # Find columns
    header = [c.strip().lower() for c in rows[0]]
    name_col = -1
    price_col = -1
    stock_col = -1
    url_col = -1
    brand_col = -1

    for idx, col in enumerate(header):
        if any(k in col for k in ['product', 'item', 'description', 'title', 'model', 'name']):
            if name_col == -1: name_col = idx
        if any(k in col for k in ['price', 'cost', 'rate', 'rs', 'amount', 'wholesale', 'catalog']):
            if price_col == -1: price_col = idx
        if any(k in col for k in ['stock', 'qty', 'quantity']):
            if stock_col == -1: stock_col = idx
        if any(k in col for k in ['url', 'link', 'website', 'page']):
            if url_col == -1: url_col = idx
        if any(k in col for k in ['brand', 'company', 'manufacturer']):
            if brand_col == -1: brand_col = idx

    # If first row wasn't headers, assume col 0 is name and col 1 is price
    start_row = 1
    if name_col == -1 or price_col == -1:
        start_row = 0
        name_col = 0
        price_col = 1 if len(rows[0]) > 1 else -1

    for row in rows[start_row:]:
        if not row:
            continue
        name_val = row[name_col].strip() if name_col < len(row) else ''
        price_val = clean_price_value(row[price_col]) if price_col != -1 and price_col < len(row) else None
        stock_val = 20
        if stock_col != -1 and stock_col < len(row):
            try:
                stock_val = max(0, int(re.sub(r'\D', '', row[stock_col]) or 20))
            except ValueError:
                stock_val = 20

        url_val = row[url_col].strip() if url_col != -1 and url_col < len(row) else ''
        brand_val = row[brand_col].strip() if brand_col != -1 and brand_col < len(row) else ''

        if name_val and len(name_val) >= 2 and price_val is not None:
            products.append({
                'name': name_val,
                'catalogue_price': price_val,
                'stock': stock_val,
                'url': url_val,
                'brand': brand_val
            })

    return products


def extract_from_excel(file_stream_or_path):
    """Extract product names and catalogue prices from Excel (.xlsx / .xls)."""
    products = []
    wb = openpyxl.load_workbook(file_stream_or_path, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return products

    # Find columns
    header = [str(c or '').strip().lower() for c in rows[0]]
    name_col = -1
    price_col = -1
    stock_col = -1
    url_col = -1
    brand_col = -1

    for idx, col in enumerate(header):
        if any(k in col for k in ['product', 'item', 'description', 'title', 'model', 'name']):
            if name_col == -1: name_col = idx
        if any(k in col for k in ['price', 'cost', 'rate', 'rs', 'amount', 'wholesale', 'catalog']):
            if price_col == -1: price_col = idx
        if any(k in col for k in ['stock', 'qty', 'quantity']):
            if stock_col == -1: stock_col = idx
        if any(k in col for k in ['url', 'link', 'website', 'page']):
            if url_col == -1: url_col = idx
        if any(k in col for k in ['brand', 'company', 'manufacturer']):
            if brand_col == -1: brand_col = idx

    start_row = 1
    if name_col == -1 or price_col == -1:
        start_row = 0
        name_col = 0
        price_col = 1 if len(rows[0]) > 1 else -1

    for row in rows[start_row:]:
        if not row:
            continue
        name_val = str(row[name_col] or '').strip() if name_col < len(row) else ''
        price_val = clean_price_value(row[price_col]) if price_col != -1 and price_col < len(row) else None
        stock_val = 20
        if stock_col != -1 and stock_col < len(row):
            try:
                stock_val = max(0, int(re.sub(r'\D', '', str(row[stock_col] or '')) or 20))
            except ValueError:
                stock_val = 20

        url_val = str(row[url_col] or '').strip() if url_col != -1 and url_col < len(row) else ''
        brand_val = str(row[brand_col] or '').strip() if brand_col != -1 and brand_col < len(row) else ''

        if name_val and len(name_val) >= 2 and price_val is not None:
            products.append({
                'name': name_val,
                'catalogue_price': price_val,
                'stock': stock_val,
                'url': url_val,
                'brand': brand_val
            })

    return products


def parse_catalogue_file(file_storage, filename=None, markup=300.0):
    """Main entry point to parse PDF, CSV, or Excel file into a normalized product list.
    
    Rule:
      cost_price = catalogue_price
      sale_price = catalogue_price + markup (default: 300)
    """
    fname = (filename or getattr(file_storage, 'filename', '') or '').lower()
    products = []
    csv_text = None

    try:
        if fname.endswith('.pdf'):
            products, csv_text = extract_from_pdf(file_storage)
        elif fname.endswith('.csv') or fname.endswith('.txt'):
            content = file_storage.read()
            products = extract_from_csv(content)
        elif fname.endswith('.xlsx') or fname.endswith('.xls'):
            products = extract_from_excel(file_storage)
        else:
            # Try PDF first if header bytes match, otherwise CSV
            header_sample = file_storage.read(5) if hasattr(file_storage, 'read') else b''
            if hasattr(file_storage, 'seek'):
                file_storage.seek(0)
            if header_sample.startswith(b'%PDF'):
                products, csv_text = extract_from_pdf(file_storage)
            else:
                content = file_storage.read()
                products = extract_from_csv(content)


        if not products:
            return False, "No valid products with names and prices could be found in the uploaded catalogue.", [], None

        # Apply price calculations
        for p in products:
            p['cost_price'] = round(float(p['catalogue_price']), 2)
            p['sale_price'] = round(float(p['catalogue_price']) + float(markup), 2)
            p['markup'] = float(markup)

        return True, None, products, csv_text

    except Exception as e:
        return False, f"Failed to parse catalogue file: {str(e)}", [], None
