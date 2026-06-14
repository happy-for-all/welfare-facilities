import os
import re
import io
import zipfile
import json
import requests
import pandas as pd

# ==========================================
# 👑 福祉架け橋OS: 共同生活援助データ本番ビルドエンジン (Ver 1.0.0)
# 開発者: ちゃろ ＆ AIバディ
# ==========================================

# 1. 各種設定と配信パスの定義
OPENDATA_PORTAL_URL = "https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/"
TARGET_SERVICE_NAME = "共同生活援助"
TARGET_PREFECTURE = "大阪府"

# 👑 経緯度欠損（空欄）時のための「市区町村役場の代表座標」マッピング辞書
# 大阪府内の主要な市役所の座標を定義。ここに無い場合は「大阪府庁」をフェイルセーフとして使います。
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


def find_target_zip_url():
    """👑 【自動探知レーダー】オープンデータ公表ページから共同生活援助の最新ZIPのURLを自動検知"""
    print(f"📡 [レーダー起動] WAM NETオープンデータ公表ページをスキャン中...")
    try:
        response = requests.get(OPENDATA_PORTAL_URL, timeout=10)
        if response.status_code != 200:
            print(f"❌ ポータルページの取得に失敗しました。ステータス: {response.status_code}")
            return None
        
        html_content = response.text
        
        # 👑 正規表現で「共同生活援助」の文字に紐づくZIPリンクを自動抽出
        # リンクの形式例: <a href="zip/14_kyoudouseikatsuenjo.zip">共同生活援助</a>
        # WAM NETのリンク構造に柔軟にマッチさせます
        matches = re.findall(r'href="([^"]*?zip[^"]*?)"[^>]*?>[^<]*?' + TARGET_SERVICE_NAME, html_content)
        if not matches:
            # 漢字表記と href の前後関係が逆の場合の予備スキャン
            matches = re.findall(r'<a[^>]*?href="([^"]*?zip[^"]*?)"[^>]*?>' + TARGET_SERVICE_NAME, html_content)
            
        if matches:
            raw_url = matches[0]
            # 相対パスを絶対URLに補完
            if not raw_url.startswith("http"):
                # "zip/xxx.zip" や "/content/.../zip/xxx.zip" などの補完
                if raw_url.startswith("/"):
                    base_domain = "https://www.wam.go.jp"
                    full_url = base_domain + raw_url
                else:
                    full_url = OPENDATA_PORTAL_URL + raw_url
            else:
                full_url = raw_url
                
            print(f"🎯 [探知成功] 共同生活援助のZIPリンクを検出しました: {full_url}")
            return full_url
        else:
            print("⚠️ ページ内に共同生活援助のZIPリンクが見つかりませんでした。")
            return None
    except Exception as e:
        print(f"❌ 自動探知中に例外が発生しました: {e}")
        return None


def run_build():
    print("==========================================")
    print(f"🌸 福祉ポータルデータビルド: 【{TARGET_PREFECTURE}版・{TARGET_SERVICE_NAME}】")
    print("==========================================")

    # 1. 最新のZIP URLを自動検出
    zip_url = find_target_zip_url()
    
    # 👑 万が一自動検知が失敗した時のための固定の最新版フォールバックURL
    if not zip_url:
        print("🛡️ [フォールバック] 自動探知に失敗したため、固定の最新URLを利用します。")
        zip_url = "https://www.wam.go.jp/content/wamnet/pcpub/top/sfkopendata/zip/14_kyoudouseikatsuenjo.zip"

    # 2. データのダウンロードとインメモリ展開（壁4対策・ディスクを消費しない）
    print(f"📡 [データダウンロード] ZIPファイルをメモリ上にロード中...")
    try:
        res = requests.get(zip_url, timeout=15)
        if res.status_code != 200:
            print(f"❌ ZIPファイルのダウンロードに失敗しました。ステータス: {res.status_code}")
            return
            
        # io.BytesIO を使い、ディスクに一切保存せずメモリ上でZIPを解凍
        zip_in_memory = zipfile.ZipFile(io.BytesIO(res.content))
        
        # ZIPの中から最初に見つかったCSVファイルのファイル名を取得
        csv_filename = [f for f in zip_in_memory.namelist() if f.endswith('.csv')][0]
        print(f"📦 [ZIP展開完了] 内部のCSVファイルを発見しました: {csv_filename}")
        
    except Exception as e:
        print(f"❌ ZIPデータの展開中にエラーが発生しました: {e}")
        return

    # 3. CSVをPandasで読み込み（BOM付きUTF-8を壁2対策のutf-8-sigで自動安全読み込み）
    print(f"📖 [CSV読み込み] BOM文字化けを完全防御して読み込みます...")
    try:
        with zip_in_memory.open(csv_filename) as csv_file:
            df = pd.read_csv(csv_file, encoding='utf-8-sig', dtype=str)
            print(f"✅ CSVデータの読み込みに成功しました。全 {len(df)} 件のデータをスキャンします。")
    except Exception as e:
        print(f"❌ CSVデータの読み込みに失敗しました: {e}")
        return

    # 4. 大阪府の事業所のみに絞り込み
    print(f"🔍 [フィルタリング] 住所情報から『{TARGET_PREFECTURE}』の施設だけを抽出します...")
    # 「事業所住所（市区町村）」が「大阪府」から始まるレコードを抽出
    df_filtered = df[df['事業所住所（市区町村）'].str.startswith(TARGET_PREFECTURE, na=False)].copy()
    print(f"📊 抽出結果: {len(df_filtered)} 件の大阪府の事業所が見つかりました。")

    if len(df_filtered) == 0:
        print("⚠️ 該当する事業所が0件です。処理をスキップします。")
        return

    # 5. データクレンジングと欠損フォールバック（壁3対策）
    facilities = []
    
    for _, row in df_filtered.iterrows():
        name = str(row.get("事業所の名称", "")).strip()
        
        # 住所の構築（市区町村＋番地以降）
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
        
        # 数値に変換できるか検証。空欄や不正値（NaN、空白）の場合はフォールバック
        try:
            if pd.notna(raw_lat) and str(raw_lat).strip() != "":
                lat = float(raw_lat)
            if pd.notna(raw_lon) and str(raw_lon).strip() != "":
                lon = float(raw_lon)
        except Exception:
            pass # 数値変換失敗時はNoneのまま下部の処理へ
            
        # 👑 【壁3：経緯度の欠損防衛シールド】
        if lat is None or lon is None:
            is_approximate = True
            # 市区町村名（例: 「大阪府大阪市西成区」から「大阪市」を抽出）
            # 市役所の代表座標を探します
            detected_city = None
            for key in MUNICIPAL_COORDS.keys():
                if key in city:
                    detected_city = key
                    break
            
            if detected_city:
                lat = MUNICIPAL_COORDS[detected_city]["lat"]
                lon = MUNICIPAL_COORDS[detected_city]["lon"]
                # print(f"🛡️ [経緯度欠損自動補完] {name} の座標を【{detected_city}役所】に代替補正しました。")
            else:
                # 万が一マッピングに無い場合は大阪府庁を注入
                lat = MUNICIPAL_COORDS["フェイルセーフ大阪府庁"]["lat"]
                lon = MUNICIPAL_COORDS["フェイルセーフ大阪府庁"]["lon"]
                # print(f"🛡️ [経緯度欠損最終防衛] {name} の座標を【大阪府庁】に最終補正しました。")

        facilities.append({
            "name": name,
            "address": address,
            "tel": tel,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "is_approximate": is_approximate
        })

    # 6. JSONファイルの書き出し（Wrangler Assets の階層ルールに合わせます）
    target_dir = os.path.join("dist", "happy-for-all")
    os.makedirs(target_dir, exist_ok=True)
    
    output_path = os.path.join(target_dir, "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(facilities, f, ensure_ascii=False, indent=2)
        
    # index.html をターゲットフォルダに確実にコピー（アドオン）
    os.system(f"cp index.html {target_dir}/")

    print(f"🎉 [ビルド大成功] 全 {len(facilities)} 件の本番データを格納した '{output_path}' が完成しました！")


if __name__ == "__main__":
    run_build()
