import pandas as pd
import ast
import unicodedata
import re
from my_logger import get_logger

phone_brands = ["apple", "samsung", "xiaomi", "oppo", "realme", "tecno", "vivo", "infinix", "nokia", "nubia", "nothing phone", "masstel", "sony", "itel"]
phone_rules = {
    "iphone": "apple",
    "iphone (apple)": "apple",
    "redmi": "xiaomi",
    "iqoo": "vivo",
    "moto": "motorola",
    "red": "nubia",
    "zenfone": "asus",
    "xperia": "sony",
    "phillips": "philips",
    "black": lambda parts: "xiaomi" if len(parts) > 1 and parts[1] == "shark" else "black"
}
phone_phrases = ["điện thoại"]

laptop_brands = ["asus", "lenovo", "dell", "hp", "acer", "lg", "huawei", "msi", "gigabyte", "vaio", "masstel", "apple", "microsoft", "itel", "avita"]
laptop_rules = {"macbook": "apple", "mac": "apple", "probook": "hp"}
laptop_phrases = ["laptop"]

tablet_brands = ["apple", "samsung", "xiaomi", "huawei", "lenovo", "nokia", "teclast", "kindle", "boox", "remarkable"]
tablet_rules = {"ipad": "apple"}
tablet_phrases = ["máy tính bảng", "máy đọc sách"]

monitor_brands = ["asus", "samsung", "dell", "lg", "msi", "acer", "xiaomi", "viewsonic", "philips", "aoc", "dahua"]
monitor_rules = {"e-dra": "edra"}
monitor_phrases = ["màn hình cong gaming", "màn hình cong", "màn hình lập trình", "màn hình gaming", "màn hình", "giá treo màn hình", "giá treo màn hình máy tính"]

pc_brands = ["asus", "msi", "singpc"]
pc_rules = {"imac": "apple", "mac": "apple"}
pc_phrases = ["pc"]

cut_patterns = [
    r"\| chính hãng.*",
    r" chính hãng.*",
    r"- nhập khẩu.*",
    r"- chỉ có tại.*",
    r"- đã kích hoạt.*",
    r"- đkh online.*",
    r"- cũ.*",
    r"- kèm.*",
    r" kèm.*",
    r"\(bản không quảng cáo\).*",
]
cut_regex = "|".join(cut_patterns)


def clean_name_column(series):
    series = series.str.lower().str.strip()
    series = series.str.replace(cut_regex, "", regex=True).str.strip()
    return series.str.replace(r'[^\w\s\-/+\.]', '', regex=True)

def clean_display_name_column(series):
    original_series = series.copy()
    lower_series = series.str.lower().str.strip()
    cleaned_series = lower_series.str.replace(cut_regex, "", regex=True).str.strip()

    restored_series = []
    for original, cleaned in zip(original_series, cleaned_series):
        start = original.lower().find(cleaned)
        restored_series.append(original[start:start + len(cleaned)].strip() if start != -1 else cleaned)
    return pd.Series(restored_series, index=series.index)

def parse_dict_string(text):
    try:
        return ast.literal_eval(text)
    except:
        return {}

def parse_list_string(text):
    try:
        return ast.literal_eval(text)
    except:
        return []

def clean_text(text):
    if isinstance(text, str):
        return unicodedata.normalize("NFKC", text).strip().replace("\n", ", ").replace("  ", " ")
    return text

def clean_specs_column(series):
    return series.fillna("").apply(lambda x: {
        clean_text(k): clean_text(v) for k, v in parse_dict_string(x).items()
    } if isinstance(x, str) else {})

def clean_feature_list(lst):
    cleaned = []
    for item in lst:
        if isinstance(item, str):
            # Xoá các thẻ <br>, </br>, <br />, v.v.
            no_br = re.sub(r'<br[^>]*>?', ' ', item, flags=re.IGNORECASE)

            # Normalize và clean khoảng trắng
            normalized = unicodedata.normalize("NFKC", no_br)
            cleaned_item = re.sub(r'\s+', ' ', normalized).strip()
            cleaned.append(cleaned_item)
    return cleaned

def clean_features_column(series):
    return series.fillna("").apply(
        lambda x: clean_feature_list(parse_list_string(x)) if isinstance(x, str) else []
    )

def update_brand(row, valid_brands=None, extra_rules=None, key_phrase_list=None):
    brand = row.get("brand", "unknown")
    name = str(row.get("name", "")).lower()

    if brand != "unknown":
        return brand

    try:
        spec = ast.literal_eval(row.get("specifications", "{}"))
        brand_from_spec = spec.get("Hãng sản xuất", "").strip().lower()
        if brand_from_spec and brand_from_spec not in ["hãng khác", "hang khac", "other", "unknown"]:
            return brand_from_spec
    except:
        pass

    if valid_brands:
        for b in valid_brands:
            if b in name:
                return b

    name_parts = name.split()
    if name_parts and extra_rules:
        first_word = name_parts[0]
        mapped = extra_rules.get(first_word)
        if isinstance(mapped, str):
            return mapped
        elif callable(mapped):
            return mapped(name_parts)
        for word in name_parts:
            mapped = extra_rules.get(word)
            if isinstance(mapped, str):
                return mapped

    if name_parts and key_phrase_list:
        for phrase in key_phrase_list:
            if phrase in name:
                after_phrase = name.split(phrase, 1)[1].strip().split()
                if after_phrase:
                    return "apple" if after_phrase[0] == "ipad" else after_phrase[0]

    return name_parts[0] if name_parts else "unknown"

def clean_product_df(df, brand_list=None, brand_rules=None, key_phrase_list=None):
    # Đảm bảo bạn đang thao tác trên bản sao, không phải slice
    df = df.copy()

    df.loc[:, "display_name"] = clean_display_name_column(df["name"])
    df.loc[:, "name"] = clean_name_column(df["name"])
    df.loc[:, "specifications"] = clean_specs_column(df["specifications"])
    
    if "features" in df.columns:
        df.loc[:, "features"] = clean_features_column(df["features"])

    if brand_list is not None:
        df.loc[:, "brand"] = df["brand"].str.lower().str.strip()
        df.loc[:, "brand"] = df["brand"].apply(lambda x: x if x in brand_list else "unknown")

    if brand_list is not None or brand_rules is not None:
        df.loc[:, "brand"] = df.apply(
            lambda row: update_brand(row, brand_list, brand_rules, key_phrase_list),
            axis=1
        )

    print(df["brand"].unique())
    return df

