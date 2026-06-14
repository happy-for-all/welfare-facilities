import os
import json

# WAM NETから取得予定のデータのテスト版
test_data = [
    {
        "name": "わおんグループホーム新琴似",
        "address": "北海道札幌市北区新琴似１条３丁目２番７号",
        "tel": "011-299-8585",
        "lat": 43.10414438,
        "lon": 141.32146775
    },
    {
        "name": "コネクト山の手",
        "address": "北海道札幌市西区山の手２条４丁目５番１６号アミティエ山の手２Ｆ",
        "tel": "011-641-5700",
        "lat": 43.06950893,
        "lon": 141.29789134
    }
]

# Cloudflareのサブパスルールに従い、distの中に「happy-for-all」フォルダを作成
target_dir = os.path.join("dist", "happy-for-all")
os.makedirs(target_dir, exist_ok=True)

# データを data.json として保存
with open(os.path.join(target_dir, "data.json"), "w", encoding="utf-8") as f:
    json.dump(test_data, f, ensure_ascii=False, indent=2)

# index.html をターゲットフォルダにコピー
os.system(f"cp index.html {target_dir}/")

print("✅ ビルド完了！dist/happy-for-all フォルダにファイルを用意しました。")
