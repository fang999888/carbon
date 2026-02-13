import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import openai

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 創建 Flask 應用
app = Flask(__name__)
CORS(app)

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 初始化 OpenAI 客戶端
client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

@app.route('/')
def index():
    """提供前端頁面"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"無法載入模板: {e}")
        return jsonify({
            "message": "Carbon Expert API is running",
            "status": "ok",
            "note": "請確保 templates/index.html 存在"
        })

@app.route('/api/health')
def health():
    """健康檢查"""
    return jsonify({
        'status': 'healthy',
        'api_key_configured': bool(DEEPSEEK_API_KEY)
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """處理聊天請求"""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        # 系統提示詞（簡化版）
        system_prompt = """你是一位擁有20年經驗的環境永續發展專家，精通ISO 14064-1、ISO 14067、排放係數資料庫與工業製程分析。請以專業碳管理顧問的身份回答問題。"""
        
        # 呼叫 DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return jsonify({
            'reply': response.choices[0].message.content,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"API 錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 這行很重要 - 用於本地開發
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

# 這行很重要 - 用於生產環境 (gunicorn 會尋找 app 這個變數)
# 如果您的應用程式實例名稱不是 app，請修改這裡
application = app  # 有些部署平台需要 application 這個名稱
