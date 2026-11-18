import pandas as pd
import json
import glob

def normalize(text):
    if not isinstance(text, str):
        return ""
    return text.replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').strip()

print("1. In hal sakhte database tamiz...")

professors = set()
try:
    df = pd.read_excel('courses.xlsx')
    for col in df.columns:
        if 'استاد' in col or 'مدرس' in col:
            for name in df[col].dropna().unique():
                norm = normalize(str(name))
                if norm and norm != 'نامشخص':
                    professors.add(norm)
            break
except Exception as e:
    print(f"Khata dar excel: {e}")

professors_data = {prof: [] for prof in professors}

json_files = glob.glob("*.json")
for jfile in json_files:
    try:
        with open(jfile, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for msg in data.get('messages', []):
            if msg.get('type') == 'message':
                text = msg.get('text', '')
                if isinstance(text, list):
                    text = "".join([item if isinstance(item, str) else item.get('text', '') for item in text])
                
                if isinstance(text, str) and len(text.strip()) > 5:
                    norm_text = normalize(text)
                    for prof in professors:
                        parts = prof.split()
                        last_name = parts[-1] if len(parts) > 1 else prof
                        
                        if len(last_name) > 2 and last_name in norm_text:
                            clean_t = text.strip().replace('\n', ' ')
                            if clean_t not in professors_data[prof]:
                                professors_data[prof].append(clean_t)
    except Exception as e:
        print(f"Khata dar json: {e}")


with open('structured_professors.txt', 'w', encoding='utf-8') as f:
    for prof, comments in professors_data.items():
        if comments:
            f.write(f"=== شناسنامه استاد: {prof} ===\n")
            f.write(f"تعداد نظرات: {len(comments)}\n")
            for i, c in enumerate(comments[:25], 1): 
                f.write(f"{i}. {c}\n")
            f.write("\n" + "="*40 + "\n\n")

print("[OK] Database ba movafaghiat sakhte shod (structured_professors.txt)!")