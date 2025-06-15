import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st
from pathlib import Path
import os
import tempfile
import json

# Streamlit Cloudの場合は環境変数を直接使用
if os.getenv('STREAMLIT_CLOUD'):
    # Streamlit Cloudの環境変数を使用
    pass
else:
    # ローカル環境の場合は.envファイルを読み込む
    load_dotenv()

# ── 既存ロジック ───────────────────────────────
from main import run as pipeline_run  # run(url, method)
from summarizer import summarize, Backend
from utils.youtube import parse_url

# ── 要約プロンプト・プリセット ───────────────────
PROMPT_PRESETS = {
    "▼ 標準（5行／40字）": """\
あなたは優秀な日本語編集者です。
以下の動画の書き起こしを読み、
・概要や知識のジャンルを簡単にまとめる　例：概要：　ジャンル：
・要点をまとめる
・各行ヘッダーにあたる内容は40文字以内の箇条書き、必要があれば構造化して詳細を記述
で出力してください。できる限り内容を維持すること。
・最後に、原文の内容をできる限り維持して整えただけのトランスクリプトを出力。
""",
    "▼ 超ざっくり 3 行": """\
以下の書き起こしを 3 行以内で要約し、日本語で出力。
各行 30 文字以内。冗長表現は禁止。
""",
    "▼ 英語 5 Bullet": """\
Summarize the transcript below in **exactly five** English bullet points.
Each bullet ≤ 25 words. Keep it concise but informative.
""",
    "▼ タイムライン風": """\
以下書き起こしを時系列に沿って箇条書き。
・見出し行: 〈mm:ss〉 で始める
・200 文字以内で要点
""",
}

# ── Streamlit UI ────────────────────────────────
st.set_page_config(page_title="YT-Summarizer", page_icon="🎬")
st.title("🎬 YouTube 要約くん")

url = st.text_input("YouTube URL", placeholder="https://youtu.be/...")
st.info("※ 字幕付き動画のみ対応しています（音声文字起こしは行いません）")

# ① プリセット選択 → テキストエリア連動
preset_name = st.selectbox("🗂 プリセット選択", list(PROMPT_PRESETS.keys()))
if "prompt" not in st.session_state or st.session_state.get("preset") != preset_name:
    st.session_state["prompt"] = PROMPT_PRESETS[preset_name]
    st.session_state["preset"] = preset_name

# --- テキストエリアは「指示文」だけ編集させる ---
prompt = st.text_area("📝 要約プロンプト (指示文だけ書く)",
                      value=st.session_state["prompt"], height=180)

# ② バックエンド選択を削除し、常にGeminiを使用
backend_enum = Backend.GEMINI

# ③ 実行ボタン
if st.button("▶ 要約する") and url:
    with st.spinner("⚙️ 解析中…少し待ってね"):
        try:
            # 一時ディレクトリの作成
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # 1) 字幕 JSON 生成
                vid = parse_url(url)
                json_path = temp_dir_path / f"{vid}.json"
                md_path = temp_dir_path / f"{vid}_summary.md"
                
                # 字幕取得と保存
                pipeline_run(url, "caption")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(tr, f, ensure_ascii=False, indent=2)

                # 2) 要約生成
                summarize(json_path, md_path, backend=backend_enum, prompt=prompt)

                # 3) 結果表示
                st.success("✅ 完了！")

                st.subheader("📝 要約")
                st.code(md_path.read_text(), language="markdown")

                st.subheader("📄 字幕 JSON")
                with st.expander("クリックで表示 / コピー"):
                    st.code(json_path.read_text(), language="json")

                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button("⬇ transcript (.json)",
                                       json_path.read_bytes(),
                                       file_name=f"{vid}.json")
                with col_dl2:
                    st.download_button("⬇ summary (.md)",
                                       md_path.read_bytes(),
                                       file_name=f"{vid}_summary.md")

        except Exception as e:
            st.error(f"⚠ エラー: {e}")
