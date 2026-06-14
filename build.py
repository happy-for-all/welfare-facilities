import os
import json
import sys
import zipfile
import io
import re
import pandas as pd

# ==========================================
# 👑 福祉ポータル: ローカルZIP超高速ビルドエンジン (Ver 1.3.0)
# 開発者: ちゃろ ＆ AIバディ
# ==========================================

LOCAL_ZIP = "sfkopendata_202603_33.zip"
TARGET_SERVICE_NAME = "共同生活援助"

MUNICIPAL_COORDS = {
    "大阪市": {"lat": 34.6937, "lon": 135.5022},
    "堺市": {"lat": 34.5714, "lon": 135.4807},
    "東大阪市": {"lat": 34.6793, "lon": 135.5999},
    "豊中市": {"lat": 34.7816, "lon": 135.4698},
    "枚方市": {"lat": 34.8162, "lon": 135.6500},
    "吹田市": {"lat": 34.7649, "lon": 135.5140},
    "高槻市": {"lat": 34.8486, "lon": 135.6175},
    "八尾市": {"lat": 34.6293, "lon": 135.6022},
    "寝屋川市": {"lat": 34.7644, "lon": 135.6262},
    "岸和田市": {"lat": 34.4619, "lon": 135.3750},
    "和泉市": {"lat": 34.4883, "lon": 135.4241},
    "守口市": {"lat": 34.7344, "lon": 135.5620},
    "門真市": {"lat": 34.7410, "lon": 135.5911},
    "箕面市": {"lat": 34.8271, "lon": 135.4704},
    "大東市": {"lat": 34.7121, "lon": 135.6224},
    "松原市": {"lat": 34.5772, "lon": 135.5562},
    "富田林市": {"lat": 34.5009, "lon": 135.6019},
    "羽曳野市": {"lat": 34.5583, "lon": 135.6075},
    "河内長野市": {"lat": 34.4536, "lon": 135.5658},
    "池田市": {"lat": 34.8258, "lon": 135.4294},
    "泉佐野市": {"lat": 34.4103, "lon": 135.3262},
    "貝塚市": {"lat": 34.4372, "lon": 135.3589},
    "摂津市": {"lat": 34.7516, "lon": 135.5619},
    "交野市": {"lat": 34.7850, "lon": 135.6811},
    "四條畷市": {"lat": 34.7291, "lon": 135.6413},
    "柏原市": {"lat": 34.5802, "lon": 135.6258},
    "藤井寺市": {"lat": 34.5750, "lon": 135.5969},
    "泉大津市": {"lat": 34.5022, "lon": 135.4058},
    "高石市": {"lat": 34.5219, "lon": 135.4380},
    "大阪狭山市": {"lat": 34.5036, "lon": 135.5519},
    "阪南市": {"lat": 34.3592, "lon": 135.2442},
    "泉南市": {"lat": 34.3725, "lon": 135.2758},
    "フェイルセーフ大阪府庁": {"lat": 34.6862, "lon": 135.5201}
}

# 👑 【アドオン】列名の表記揺れ（全角半角の違い）を吸収して安全に取得する関数
def safe_get(row, possible_keys):
    for key in possible_keys:
        if key in row:
            return str(row[key]).strip()
    return ""

def run_build():
    print("==========================================")
    print(f"🌸 福祉ポータルデータビルド: 【大阪府・{TARGET_SERVICE_NAME}】")
    print("==========================================")

    if not os.path.exists(LOCAL_ZIP):
        print(f"❌ [致命的エラー] リポジトリ内に『{LOCAL_ZIP}』が見つかりません。")
        sys.exit(1)

    print(f"📡 [ZIP解凍] メモリ上で '{LOCAL_ZIP}' を安全に展開中...")
    try:
        zip_file = zipfile.ZipFile(LOCAL_ZIP)
        csv_filename = [f for f in zip_file.namelist() if f.endswith('.csv')][0]
    except Exception as e:
        print(f"❌ ZIPの解凍またはCSVの特定に失敗しました: {e}")
        sys.exit(1)

    df = None
    encodings = ["utf-8-sig", "shift_jis", "cp932", "utf-8"]
    for enc in encodings:
        try:
            with zip_file.open(csv_filename) as f:
                df = pd.read_csv(f, encoding=enc, dtype=str)
            print(f"🟢 '{enc}' での読み込みに成功しました！")
            break
        except Exception:
            continue

    if df is None:
        print("❌ [致命的エラー] すべての主要文字コードでCSVの読み込みに失敗しました。")
        sys.exit(1)

    # 👑 【外部AI提案のデバッグ機能】GitHub Actionsのログで実際の列名を確認できます
    print("【列名チェック（実際のCSVヘッダー）】")
    print(list(df.columns))

    # 「事業所住所」の表記揺れに対応する列名リストを用意
    col_address_city = [col for col in df.columns if "住所" in col and "市区町村" in col]
    if not col_address_city:
        print("❌ [致命的エラー] 住所（市区町村）を示す列が見つかりません。列名チェックのログを確認してください。")
        sys.exit(1)

    target_col = col_address_city[0]
    df_filtered = df[df[target_col].str.startswith("大阪府", na=False)].copy()
    print(f"📊 抽出結果: {len(df_filtered)} 件の大阪府の事業所が見つかりました。")

    facilities = []
    
    for _, row in df_filtered.iterrows():
        # 表記揺れを吸収してデータを取得
        name = safe_get(row, ["事業所の名称", "事業所名称"])
        city = safe_get(row, ["事業所住所（市区町村）", "事業所住所(市区町村)", target_col])
        address_detail = safe_get(row, ["事業所住所（番地以降）", "事業所住所(番地以降)"])
        address = city + address_detail
        
        raw_tel = safe_get(row, ["事業所電話番号", "事業所連絡先", "電話番号"])
        
        # 👑 【アドオン】電話番号クレンジング（発信できないバグ対策）
        # 全角数字を半角に直し、数字とハイフン以外（不要な空白など）を削除
        tel_clean = re.sub(r'[^0-9\-]', '', raw_tel.translate(str.maketrans('０１２３４５６７８９', '0123456789')))

        raw_lat = safe_get(row, ["事業所緯度", "緯度"])
        raw_lon = safe_get(row, ["事業所経度", "経度"])
        
        lat, lon = None, None
        is_approximate = False
        
        try:
            if raw_lat: lat = float(raw_lat)
            if raw_lon: lon = float(raw_lon)
        except Exception:
            pass
            
        if lat is None or lon is None:
            is_approximate = True
            detected_city = None
            # 👑 【アドオン】市区町村の誤判定防止（前方一致等の厳密判定）
            for key in MUNICIPAL_COORDS.keys():
                # "大阪府東大阪市..." の中から "東大阪市" などを正確に探す
                if key in city and (city.index(key) == 3 or city.index(key) == 0):
                    detected_city = key
                    break
            
            if detected_city:
                lat = MUNICIPAL_COORDS[detected_city]["lat"]
                lon = MUNICIPAL_COORDS[detected_city]["lon"]
            else:
                lat = MUNICIPAL_COORDS["フェイルセーフ大阪府庁"]["lat"]
                lon = MUNICIPAL_COORDS["フェイルセーフ大阪府庁"]["lon"]

        facilities.append({
            "name": name,
            "address": address,
            "tel": raw_tel,        # 画面表示用（そのまま）
            "tel_clean": tel_clean, # 👑 リンク（発信）用
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "is_approximate": is_approximate
        })

    target_dir = os.path.join("dist", "happy-for-all")
    os.makedirs(target_dir, exist_ok=True)
    
    output_path = os.path.join(target_dir, "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(facilities, f, ensure_ascii=False, indent=2)
        
    os.system(f"cp index.html {target_dir}/")
    print(f"🎉 [ビルド大成功] '{output_path}' が完成しました！")

if __name__ == "__main__":
    try:
        run_build()
    except Exception as e:
        print(f"❌ [未予期エラー] ビルド中に重大なエラーが発生しました: {e}")
        sys.exit(1)
