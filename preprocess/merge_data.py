import pandas as pd
import ast
import re
from my_logger import get_logger

def clean_name_for_extract(name): 
    cut_name_patterns = [
        r"điện thoại",
        r"laptop",
        r"máy tính bảng",
        r"màn hình đồ họa",
        r"màn hình",
        r"máy đọc sách",
        r"màn hình gaming",
        r"màn hình thông minh"
    ]
    # Gộp lại thành một regex duy nhất (match bất kỳ từ nào)
    cut_name_regex = "|".join(cut_name_patterns)
    
    cleaned_name = name.lower().strip()
    cleaned_name = re.sub(cut_name_regex, "", cleaned_name).strip()
    # Xóa khoảng trắng thừa nếu có
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name)
    
    return cleaned_name

def extract_phone_model(name: str, brand: str, category: str) -> str:
    name = name.lower()
    brand = brand.lower()
    
    # Bỏ brand ra khỏi tên
    name = re.sub(rf'\b{re.escape(brand)}\b', '', name)

    # Bỏ dung lượng (RAM/ROM) và từ khóa gây nhiễu
    name = re.sub(r'\b\d+\s?(gb|tb)\b', '', name)
    name = re.sub(r'\b(ram|rom|ssd|hdd|bộ nhớ trong|dung lượng lưu trữ|lưu trữ)\b', '', name)

    # Các từ không liên quan
    noise_words = ['5g', '4g', 'wifi', 'lte', 'dual sim', 'nano', 'android', 'ios', 'windows']
    for word in noise_words:
        name = name.replace(word, '')

    # Làm sạch ký tự đặc biệt
    name = re.sub(r'[^\w\s\+]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()

    # Lấy 3–5 từ đầu tiên làm model (có thể chỉnh nếu cần)
    tokens = name.split()
    model = ' '.join(tokens[:5])
    return model

def extract_phone_model_info(name: str, brand: str, category: str, specs: dict) -> dict:
    print(f"{name}:")
    def parse_gb(value):
        match = re.search(r'(\d+)\s*gb', value.lower())
        return int(match.group(1)) if match else None

    def is_valid_ram(value):
        return value in [1, 2, 3, 4, 6, 8, 12, 16, 18, 24]

    def is_valid_rom(value):
        return value in [8, 16, 32, 64, 128, 256, 512, 1024]

    # Các key phổ biến có thể chứa RAM/ROM
    ram_keys = ['ram', 'dung lượng ram']
    rom_keys = ['rom', 'bộ nhớ trong', 'dung lượng (rom)', 'dung lượng lưu trữ']

    ram = None
    storage = None

    # Ưu tiên lấy từ specs nếu có
    for key in ram_keys:
        for spec_key in specs:
            if key in spec_key.lower():
                ram = parse_gb(specs[spec_key])
                print("Match ram from specs")
                break
        if ram is not None:
            break

    for key in rom_keys:
        for spec_key in specs:
            if key in spec_key.lower():
                storage = parse_gb(specs[spec_key])
                print("Match rom from specs")
                break
        if storage is not None:
            break

    # Nếu không có trong specs thì lấy từ name
    if ram is None or storage is None:
        ram_matches = re.findall(r'(\d+)\s*gb', name.lower())
        if len(ram_matches) == 2:
            ram = ram or int(ram_matches[0])
            storage = storage or int(ram_matches[1])
        elif len(ram_matches) == 1:
            value = int(ram_matches[0])
            if ram is None:
                ram = value
            elif storage is None and value != ram:
                storage = value

    # Kiểm tra hợp lệ
    if ram is not None and not is_valid_ram(ram):
        print(f"RAM không hợp lệ: {ram}GB → loại bỏ")
        ram = None
    if storage is not None and not is_valid_rom(storage):
        print(f"ROM không hợp lệ: {storage}GB → loại bỏ")
        storage = None

    model = extract_phone_model(clean_name_for_extract(name), brand, category)

    print(f" [model: {model}, ram: {ram}, storage: {storage}]")
    return {
        'model': model,
        'ram': ram,
        'storage': storage
    }

import re

BRANDS = ['apple', 'asus', 'hp', 'lenovo', 'acer', 'msi', 'dell', 'masstel', 'gigabyte', 'lg', 'vaio', 'huawei', 'mac', 'laptop', 'samsung']
SERIES = {
    'macbook': ['air', 'pro'],
    'dell': ['xps', 'inspiron', 'latitude', 'alienware'],
    'hp': ['pavilion', 'envy', 'spectre', 'omen'],
    'asus': ['zenbook', 'vivobook', 'tuf', 'rog'],
    'acer': ['aspire', 'nitro', 'swift', 'predator'],
    'msi': ['modern', 'gf', 'gl', 'katana'],
    'lenovo': ['ideapad', 'thinkpad', 'legion', 'yoga'],
    'gigabyte': ['aero', 'aurus'],
    'surface': ['laptop', 'pro', 'book', 'go']
}

def is_valid_laptop_ram(value):
    return value in [2, 4, 6, 8, 12, 16, 20, 24, 32, 64, 128]

def is_valid_laptop_storage(value):
    return value in [128, 256, 512, 1024, 2048, 4096]

def parse_storage(value):
    if isinstance(value, list):
        value = ' '.join(value)
    value = value.lower()
    gb_match = re.search(r'(\d+)\s*gb', value)
    tb_match = re.search(r'(\d+)\s*tb', value)

    if tb_match:
        return int(tb_match.group(1)) * 1024
    elif gb_match:
        return int(gb_match.group(1))
    return None

def detect_storage_type(value):
    if isinstance(value, list):
        value = ' '.join(value)
    value = value.lower()
    if 'ssd' in value:
        return 'SSD'
    elif 'hdd' in value:
        return 'HDD'
    return None

def extract_model(name: str, brand: str, category: str = '') -> str:
    name = name.lower()
    name = name.replace('laptop', '')
    name = name.replace(brand.lower(), '')
    name = re.sub(r'\s+', ' ', name).strip()

    tokens = name.split()
    series_list = SERIES.get(brand.lower(), [])
    model_tokens = []

    for i, token in enumerate(tokens):
        if token in series_list or any(s in token for s in series_list):
            model_tokens = [token]
            for t in tokens[i+1:]:
                # Dừng nếu gặp phần cứng
                if re.match(r'^\d+(gb|tb)$', t) or 'cpu' in t or 'gpu' in t or 'ram' in t:
                    break
                # Bỏ qua các token là năm (2010–2099)
                if re.match(r'^20[1-9][0-9]$', t):
                    continue
                if re.match(r'^[a-z0-9\-/]{1,20}$', t):
                    model_tokens.append(t)
                else:
                    break
            break

    if not model_tokens:
        model_tokens = [t for t in tokens[:4] if not re.match(r'^20[1-9][0-9]$', t)]  # bỏ năm nếu fallback

    return ' '.join(model_tokens).strip()


def extract_model_info(name: str, brand: str, category: str, specs: dict) -> dict:
    print(f"{name}:")

    ram = None
    storage = None
    storage_type = None

    # keys xác định thông tin
    ram_keys = ['ram', 'dung lượng ram', 'bộ nhớ ram']
    rom_keys = ['rom', 'bộ nhớ trong', 'dung lượng lưu trữ', 'ổ cứng', 'storage']

    # tách RAM
    for key in ram_keys:
        for spec_key in specs:
            if key in spec_key.lower():
                ram = parse_storage(specs[spec_key])
                print("Match ram from specs")
                break
        if ram is not None:
            break

    # tách Storage + Type
    for key in rom_keys:
        for spec_key in specs:
            if key in spec_key.lower():
                storage = parse_storage(specs[spec_key])
                storage_type = detect_storage_type(specs[spec_key])
                print("Match storage from specs")
                break
        if storage is not None:
            break

    # fallback tách từ name
    if ram is None or storage is None:
        matches = re.findall(r'(\d+)\s*(gb|tb)', name.lower())
        values = []
        for val, unit in matches:
            val = int(val)
            if unit == 'tb':
                val *= 1024
            values.append(val)
        if len(values) >= 2:
            ram = ram or values[0]
            storage = storage or values[1]
        elif len(values) == 1:
            if ram is None:
                ram = values[0]
            elif storage is None:
                storage = values[0]

    # hợp lệ hóa
    if ram is not None and not is_valid_laptop_ram(ram):
        print(f"RAM không hợp lệ: {ram}GB → loại bỏ")
        ram = None
    if storage is not None and not is_valid_laptop_storage(storage):
        print(f"Storage không hợp lệ: {storage}GB → loại bỏ")
        storage = None

    model = extract_model(clean_name_for_extract(name), brand, category)
    print(f" → [model: {model}, ram: {ram}, storage: {storage}, type: {storage_type}]")

    return {
        'model': model,
        'ram': ram,
        'storage': storage,
        'storage_type': storage_type
    }

def merge_specs(base, other):
    if not isinstance(other, dict):
        return
    for k, v in other.items():
        if k not in base:
            base[k] = v
        elif isinstance(base[k], list):
            if v not in base[k]:
                base[k].append(v)
        elif base[k] != v:
            base[k] = [base[k], v]

def merge_features(base_features, new_features):
    if not isinstance(new_features, list):
        return base_features
    if not isinstance(base_features, list):
        base_features = []
    return list(set(base_features + new_features))

# Hàm hỗ trợ tạo merged record
def create_merged_record(cp_row, fpt_row=None, tgdd_row=None):
    if isinstance(cp_row['specifications'], str):
        cp_specs = ast.literal_eval(cp_row['specifications'])
    else:
        cp_specs = cp_row['specifications']

    merged = {
        'name': cp_row['name'],
        'display_name': cp_row['display_name'],
        'url': {'cellphones': cp_row['url']},
        'category': cp_row.get('category'),
        'brand': cp_row['brand'],        
        'prices': {'cellphones': cp_row['prices']},
        'specifications': cp_specs or {},
        'needs': cp_row.get('needs'),
        'features': cp_row.get('features'),
        'image_links': cp_row['image_links']
    }

    if fpt_row is not None:
        merged['url']['fptshop'] = fpt_row['url']
        merged['prices']['fptshop'] = fpt_row['prices']
        specs = fpt_row.get('specifications')
        if isinstance(specs, str):
            specs = ast.literal_eval(specs)
        merge_specs(merged['specifications'], specs)

        # features = fpt_row.get('features')
        # merged['features'] = merge_features(merged['features'], features)

    if tgdd_row is not None:
        merged['url']['tgdd'] = tgdd_row['url']
        merged['prices']['tgdd'] = tgdd_row['prices']
        specs = tgdd_row.get('specs')
        if isinstance(specs, str):
            specs = ast.literal_eval(specs)
        merge_specs(merged['specifications'], specs)

    return merged

def get_embedding(text, model):
    return model.encode([text])[0]

def merge_product_df(cellphones, fpt, tgdd, category):
    logger = get_logger()
    merged_data = []
    used_fpt_ids = set()
    used_tgdd_ids = set()

    def preprocess(df):
        df = df.copy()
        if (category == "phone"):
            df['info'] = df.apply(
                lambda row: extract_phone_model_info(row['name'], row['brand'], category, row['specifications']),
                axis=1
            )
        else:
            df['info'] = df.apply(
                lambda row: extract_model_info(row['name'], row['brand'], category, row['specifications']),
                axis=1
            )
        return df

    print("-------------------------------------Extract FPT-------------------------------------")
    fpt = preprocess(fpt)
    print("-------------------------------------Extract TGDD-------------------------------------")
    tgdd = preprocess(tgdd)
    print("-------------------------------------Extract CellphoneS-------------------------------------")
    cellphones = preprocess(cellphones)

    for i, cp_row in cellphones.iterrows():
        cp_info = cp_row['info']
        cp_brand = cp_row['brand'].lower()
        cp_name = cp_row['name'].strip().lower()

        fpt_match, tgdd_match = None, None

        # === FPT: Match theo tên hoàn toàn trùng khớp ===
        for idx, row in fpt.iterrows():
            if idx in used_fpt_ids:
                continue
            if row['name'].strip().lower() == cp_name:
                fpt_match = row
                used_fpt_ids.add(idx)
                break

        # Nếu chưa match tên thì dùng model, ram, storage
        if fpt_match is None:
            for idx, row in fpt.iterrows():
                if idx in used_fpt_ids:
                    continue
                row_info = row['info']
                if (
                    row['brand'].lower() == cp_brand and
                    row_info['model'] == cp_info['model'] and
                    row_info['ram'] == cp_info['ram'] and
                    row_info['storage'] == cp_info['storage']
                ):
                    fpt_match = row
                    used_fpt_ids.add(idx)
                    break

        # === TGDD: Match theo tên hoàn toàn trùng khớp ===
        for idx, row in tgdd.iterrows():
            if idx in used_tgdd_ids:
                continue
            if row['name'].strip().lower() == cp_name:
                tgdd_match = row
                used_tgdd_ids.add(idx)
                break

        # Nếu chưa match tên thì dùng model, ram, storage
        if tgdd_match is None:
            for idx, row in tgdd.iterrows():
                if idx in used_tgdd_ids:
                    continue
                row_info = row['info']
                if (
                    row['brand'].lower() == cp_brand and
                    row_info['model'] == cp_info['model'] and
                    row_info['ram'] == cp_info['ram'] and
                    row_info['storage'] == cp_info['storage']
                ):
                    tgdd_match = row
                    used_tgdd_ids.add(idx)
                    break

        logger.info(f"CellphoneS: {cp_row['name']} --- {cp_row['info']}")
        logger.info(f"Matched FPT {fpt_match['name']}  --- {cp_row['info']}" if fpt_match is not None else "Unmatched FPT")
        logger.info(f"Matched TGDD {tgdd_match['name']}  --- {cp_row['info']}" if tgdd_match is not None else "Unmatched TGDD N/A")

        merged_data.append(create_merged_record(cp_row, fpt_match, tgdd_match))

    logger.info(f"\nTổng số sản phẩm đã xử lý: {len(merged_data)}")

    # In sản phẩm FPT không được merge
    unmatched_fpt = fpt[~fpt.index.isin(used_fpt_ids)]
    logger.info(f"\nSản phẩm FPT KHÔNG được merge: {len(unmatched_fpt)}")
    # for _, row in unmatched_fpt.iterrows():
    #     logger.info(f" - {row['name']}")

    # In sản phẩm TGDD không được merge
    unmatched_tgdd = tgdd[~tgdd.index.isin(used_tgdd_ids)]
    logger.info(f"\nSản phẩm TGDD KHÔNG được merge: {len(unmatched_tgdd)}")
    # for _, row in unmatched_tgdd.iterrows():
    #     logger.info(f" - {row['name']}")

    return pd.DataFrame(merged_data)

