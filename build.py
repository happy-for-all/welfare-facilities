import os
import json
import sys
import zipfile
import io
import pandas as pd

# ==========================================
# 👑 福祉ポータル: ローカルZIP超高速ビルドエンジン (Ver 1.2.0)
# 開発者: ちゃろ ＆ AIバディ
# ==========================================

# 👑 容量節約のため、ZIP圧縮されたファイル名を指定（ちゃろ様の素晴らしいアイデア！）
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


def run_build():
    print("==========================================")
    print(f"🌸 福祉ポータルデータビルド: 【大阪府・{TARGET_SERVICE_NAME}】")
    print("==========================================")

    # 1. ローカルZIPの存在確認
    if not os.path.exists(LOCAL_ZIP):
        print(f"❌ [致命的エラー] リポジトリ内に『{LOCAL_ZIP}』が見つかりません。")
        print("💡 手元のCSVをZIP圧縮した『osaka.zip』をGitHubにアップロードしてください。")
        sys.exit(1)

    # 2. ZIPの読み込みとメモリ上での解凍
    print(f"📡 [ZIP解凍] メモリ上で '{LOCAL_ZIP}' を安全に展開中...")
    try:
        zip_file = zipfile.ZipFile(LOCAL_ZIP)
        # ZIP内から最初に見つかったCSVファイルのファイル名を取得
        csv_filename = [f for f in zip_file.namelist() if f.endswith('.csv')][0]
        print(f"📦 CSVファイルを発見しました: {csv_filename}")
    except Exception as e:
        print(f"❌ ZIPの解凍またはCSVの特定に失敗しました: {e}")
        sys.exit(1)

    # 3. CSVの読み込み（文字コード自動判別＆BOM回避）
    df = None
    encodings = ["utf-8-sig", "shift_jis", "cp932", "utf-8"]
    for enc in encodings:
        try:
            print(f"📖 CSVをエンコーディング '{enc}' で読み込んでいます...")
            with zip_file.open(csv_filename) as f:
                df = pd.read_csv(f, encoding=enc, dtype=str)
            print(f"🟢 '{enc}' での読み込みに成功しました！")
            break
        except Exception as e:
            print(f"⚠️ '{enc}' は不適合でした（原因: {e}）")
            continue

    if df is None:
        print("❌ [致命的エラー] すべての主要文字コードでCSVの読み込みに失敗しました。")
        sys.exit(1)

    print(f"✅ CSVスキャン成功。全 {len(df)} 件のデータを処理します。")

    # 4. 大阪府の事業所のみに絞り込み
    df_filtered = df[df['事業所住所（市区町村）'].str.startswith("大阪府", na=False)].copy()
    print(f"📊 抽出結果: {len(df_filtered)} 件の大阪府の事業所が見つかりました。")

    if len(df_filtered) == 0:
        print("❌ [致命的エラー] 大阪府に該当する事業所データが0件です。")
        sys.exit(1)

    # 5. データクレンジングと欠損フォールバック
    facilities = []
    
    for _, row in df_filtered.iterrows():
        name = str(row.get("事業所の名称", "")).strip()
        
        # 住所の構築
        city = str(row.get("事業所住所（市区町村）", "")).strip()
        address_detail = str(row.get("事業所住所（番地以降）", "")).strip()
        address = city + address_detail
        
        tel = str(row.get("事業所電話番号", "")).strip()
        
        # 緯度・経度のクレンジング
        raw_lat = row.get("事業所緯度")
        raw_lon = row.get("事業所経度")
        
        lat = None
        lon = None
        is_approximate = False
        
        try:
            if pd.notna(raw_lat) and str(raw_lat).strip() != "":
                lat = float(raw_lat)
            if pd.notna(raw_lon) and str(raw_lon).strip() != "":
                lon = float(raw_lon)
        except Exception:
            pass
            
        # 👑 【経緯度欠損防衛シールド】
        if lat is None or lon is None:
            is_approximate = True
            detected_city = None
            for key in MUNICIPAL_COORDS.keys():
                if key in city:
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
            "tel": tel,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "is_approximate": is_approximate
        })

    # 6. JSONファイルの書き出し
    target_dir = os.path.join("dist", "happy-for-all")
    os.makedirs(target_dir, exist_ok=True)
    
    output_path = os.path.join(target_dir, "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(facilities, f, ensure_ascii=False, indent=2)
        
    # index.html をターゲットフォルダにコピー
    os.system(f"cp index.html {target_dir}/")

    print(f"🎉 [ビルド大成功] 全 {len(facilities)} 件の本番データを格納した '{output_path}' が完成しました！")


if __name__ == "__main__":
    try:
        run_build()
    except Exception as e:
        print(f"❌ [未予期エラー] ビルド中に重大なエラーが発生しました: {e}")
        sys.exit(1)
