import os
import logging
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import requests

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 系統提示詞
SYSTEM_PROMPT = """你是一位擁有 20 年經驗的環境永續發展專家..."""  # 您的完整提示詞

@app.route('/')
def index():
    """提供前端頁面"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"無法載入模板: {e}")
        return "Carbon Expert API 運行中 - 請確保 templates/index.html 存在"

@app.route('/api/health')
def health():
    """健康檢查"""
    return jsonify({
        'status': 'healthy',
        'api_key_configured': bool(DEEPSEEK_API_KEY),
        'api_key_prefix': DEEPSEEK_API_KEY[:10] + '...' if DEEPSEEK_API_KEY else None
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """處理聊天請求"""
    # ... 您的聊天邏輯 ...

@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """分析行業別的排放源"""
    # ... 您的行業分析邏輯 ...

# ===== 這裡開始貼測試程式碼 =====
@app.route('/api/test-deepseek')
def test_deepseek():
    """測試 DeepSeek API 連接"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    # 檢查 API Key 是否存在
    if not api_key:
        return jsonify({
            "error": "API Key 未設定",
            "env_vars": dict(os.environ),
            "has_env_file": os.path.exists('.env')
        }), 500
    
    # 測試 API 連接
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # 簡單的測試請求
        test_payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=test_payload,
            timeout=10
        )
        
        return jsonify({
            "status": "API Key 已設定",
            "key_prefix": api_key[:15] + "..." if api_key else None,
            "api_test_status": response.status_code,
            "api_test_response": response.text[:200] if response.text else None,
            "api_test_ok": response.status_code == 200
        })
        
    except Exception as e:
        return jsonify({
            "status": "API Key 已設定",
            "key_prefix": api_key[:15] + "..." if api_key else None,
            "error": str(e)
        }), 500

@app.route('/api/debug-env')
def debug_env():
    """除錯：查看環境變數（不要用在正式環境！）"""
    # 注意：這個端點會暴露環境變數，僅用於除錯
    safe_env = {}
    for key in os.environ:
        if 'KEY' in key or 'SECRET' in key or 'PASSWORD' in key:
            safe_env[key] = os.environ[key][:10] + '...' if os.environ[key] else None
        else:
            safe_env[key] = os.environ[key]
    
    return jsonify({
        "env_vars": safe_env,
        "has_env_file": os.path.exists('.env'),
        "cwd": os.getcwd(),
        "files": os.listdir('.')
    })
# ===== 測試程式碼結束 =====

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
