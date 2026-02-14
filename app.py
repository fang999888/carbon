import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. 先建立 Flask 應用 (這是 app 變數)
app = Flask(__name__)
CORS(app)

# 2. DeepSeek API 配置 (可以在建立 app 之後)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 3. 然後才是各種路由 (使用 @app.route)
@app.route('/')
def index():
    """首頁"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/health')
def health():
    """健康檢查"""
    return jsonify({
        'status': 'ok',
        'api_key': 'yes' if DEEPSEEK_API_KEY else 'no'
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """超簡化版聊天"""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'No API Key'}), 500
        
        # 直接呼叫 DeepSeek
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 100
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'reply': result['choices'][0]['message']['content']
            })
        else:
            return jsonify({'error': f'API Error: {response.status_code}'}), 502
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

# 4. 啟動伺服器
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
