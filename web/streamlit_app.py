import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st
from pathlib import Path
import os
import tempfile
import json
import logging
import time
from datetime import datetime
import traceback  # 追加

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# セッション状態の初期化
def init_session_state():
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'last_processed' not in st.session_state:
        st.session_state.last_processed = None
    if 'prompt' not in st.session_state:
        st.session_state.prompt = PROMPT_PRESETS["▼ 標準（5行／40字）"]
    if 'preset' not in st.session_state:
        st.session_state.preset = "▼ 標準（5行／40字）"

# Streamlit Cloudの場合は環境変数を直接使用
os.getenv('STREAMLIT_CLOUD')
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

# セッション状態の初期化
init_session_state()

# ログ表示用のエリア
log_container = st.empty()

def update_log(message, level="info"):
    """ログを更新する関数"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    
    if level == "error":
        logger.error(message)
        st.error(log_message)
    elif level == "warning":
        logger.warning(message)
        st.warning(log_message)
    else:
        logger.info(message)
        st.info(log_message)

def reset_session():
    """セッション状態をリセットする関数"""
    st.session_state.processing = False
    st.session_state.last_processed = None

# 環境変数のチェック
if not os.getenv('GOOGLE_API_KEY'):
    st.error("GOOGLE_API_KEYが設定されていません。Streamlit Cloudの環境変数を確認してください。")
    st.stop()

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
    try:
        update_log("処理を開始します...")
        
        with st.spinner("⚙️ 解析中…少し待ってね"):
            # 1) 字幕 JSON 生成
            update_log("動画の字幕を取得中...")
            vid = parse_url(url)
            
            # 字幕取得
            update_log("字幕を処理中...")
            transcript = pipeline_run(url, "caption")
            
            # 字幕データをセッションに保存
            st.session_state["transcript"] = transcript
            
            # 2) 要約生成
            update_log("要約を生成中...")
            summary = summarize(transcript, backend=backend_enum, prompt=prompt)
            
            # 要約をセッションに保存
            st.session_state["summary"] = summary

            # 3) 結果表示
            update_log("処理が完了しました！", "info")
            st.success("✅ 完了！")

            # 要約セクション
            st.subheader("📝 要約")
            
            # コピーボタンと要約テキストを横に並べる
            col_copy, col_text = st.columns([1, 5])
            with col_copy:
                if st.button("📋 コピー", key="copy_summary"):
                    st.write(f'<script>navigator.clipboard.writeText(`{summary}`)</script>', unsafe_allow_html=True)
                    st.success("コピーしました！")
            
            # 要約テキストを表示（モバイル対応）
            st.markdown(summary)

            # 字幕セクション
            st.subheader("📄 字幕 JSON")
            
            # コピーボタンとJSON表示を横に並べる
            col_copy_json, col_json = st.columns([1, 5])
            with col_copy_json:
                if st.button("📋 コピー", key="copy_json"):
                    json_str = json.dumps(transcript, ensure_ascii=False, indent=2)
                    st.write(f'<script>navigator.clipboard.writeText(`{json_str}`)</script>', unsafe_allow_html=True)
                    st.success("コピーしました！")
            
            # JSONを表示（モバイル対応）
            with st.expander("クリックで表示 / コピー", expanded=True):
                st.json(transcript)

            # ダウンロードボタン（モバイル対応）
            st.subheader("💾 ダウンロード")
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "⬇ transcript (.json)",
                    json.dumps(transcript, ensure_ascii=False, indent=2).encode('utf-8'),
                    file_name=f"{vid}.json",
                    mime="application/json"
                )
            with col_dl2:
                st.download_button(
                    "⬇ summary (.md)",
                    summary.encode('utf-8'),
                    file_name=f"{vid}_summary.md",
                    mime="text/markdown"
                )

            # シェアボタン（モバイル対応）
            st.subheader("🔗 シェア")
            share_url = f"https://youtu.be/{vid}"
            st.markdown(f"""
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <a href="https://twitter.com/intent/tweet?url={share_url}&text=YouTube動画の要約" 
                   target="_blank" 
                   style="text-decoration: none; padding: 8px 16px; background-color: #1DA1F2; color: white; border-radius: 4px;">
                    🐦 Twitterでシェア
                </a>
                <a href="https://www.facebook.com/sharer/sharer.php?u={share_url}" 
                   target="_blank"
                   style="text-decoration: none; padding: 8px 16px; background-color: #4267B2; color: white; border-radius: 4px;">
                    👥 Facebookでシェア
                </a>
            </div>
            """, unsafe_allow_html=True)

            # モバイル対応のスタイル
            st.markdown("""
            <style>
            @media (max-width: 768px) {
                .stButton button {
                    width: 100%;
                    margin-bottom: 10px;
                }
                .stDownloadButton button {
                    width: 100%;
                    margin-bottom: 10px;
                }
            }
            </style>
            """, unsafe_allow_html=True)

    except Exception as e:
        error_message = str(e)
        if "字幕の取得に失敗しました" in error_message:
            st.error("""
            ⚠️ 字幕の取得に失敗しました。以下の可能性があります：
            1. この動画には字幕がありません
            2. 字幕が無効になっています
            3. アクセスが制限されています
            
            別の動画を試すか、しばらく時間をおいて再度お試しください。
            """)
        else:
            st.error(f"エラーが発生しました: {error_message}")
        # デバッグ情報を表示
        st.error("デバッグ情報:")
        st.code(traceback.format_exc())

# 処理状態の表示
if st.session_state.processing:
    st.warning("処理中です...")

# 新しい処理を開始するためのリセットボタン
if st.session_state.last_processed is not None:
    if st.button("🔄 新しい処理を開始"):
        reset_session()
        st.experimental_rerun()
