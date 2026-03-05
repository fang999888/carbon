import os
import logging
import traceback
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

logger.info(f"啟動應用程式，API Key 設定狀態: {bool(DEEPSEEK_API_KEY)}")

# 系統提示詞（精簡版）
SYSTEM_PROMPT = """你是一位碳管理顧問，專精於ISO 14064-1和ISO 14067。請用繁體中文回答碳盤查相關問題，提供專業且實用的建議。"""

# ========== 首頁 ==========
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Carbon Expert API 運行中", 200

# ========== 健康檢查 ==========
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'api_key_configured': bool(DEEPSEEK_API_KEY),
        'timestamp': datetime.now().isoformat()
    })

# ========== 一般諮詢 ==========
@app.route('/api/chat', methods=['POST'])
def chat():
    """一般諮詢 - 穩定版本"""
    logger.info("收到 /api/chat 請求")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '請提供 JSON 數據'}), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            logger.error("API Key 未設定")
            return jsonify({'error': '系統配置錯誤'}), 500
        
        # 準備發送给 DeepSeek 的訊息
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000  # 降低 tokens 加快回應
        }
        
        logger.info("發送請求至 DeepSeek API")
        
        # 發送請求 - 使用最簡單的方式
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logger.info(f"DeepSeek 回應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            return jsonify({'reply': reply})
        else:
            logger.error(f"API 錯誤: {response.text[:200]}")
            return jsonify({'error': f'AI 服務錯誤'}), 502
            
    except requests.exceptions.Timeout:
        logger.error("API 超時")
        return jsonify({'error': '請求超時'}), 504
    except Exception as e:
        logger.error(f"錯誤: {traceback.format_exc()}")
        return jsonify({'error': '系統錯誤'}), 500

# ========== 行業排放查詢 ==========
@app.route('/api/industry-emissions', methods=['POST'])
def industry_emissions():
    """行業排放查詢 - 簡化版"""
    logger.info("收到 /api/industry-emissions 請求")
    
    try:
        data = request.get_json()
        industry = data.get('industry', '')
        emission_source = data.get('emission_source', '')
        
        if not industry or not emission_source:
            return jsonify({'error': '請提供行業別和排放源'}), 400
        
        # 本地係數資料庫
        coefficients = {
            '用電': 0.474,
            '天然氣': 2.09,
            '柴油': 2.61,
            '汽油': 2.26
        }
        
        reply = f"【{industry} - {emission_source}】\n"
        
        for key, value in coefficients.items():
            if key in emission_source:
                reply += f"建議係數：{value} kg CO₂e/單位\n"
                reply += "資料來源：環境部\n"
                break
        else:
            reply += "參考係數：\n"
            reply += "- 用電：0.474 kg CO₂e/度\n"
            reply += "- 天然氣：2.09 kg CO₂e/m³\n"
            reply += "- 柴油：2.61 kg CO₂e/L\n"
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        logger.error(f"錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ========== 行業分析 ==========
@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """行業分析 - 簡化版"""
    try:
        data = request.get_json()
        industry = data.get('industry', '')
        
        reply = f"""【{industry} 行業碳排放分析】

主要排放源：
1. 用電 (範疇二) - 係數：0.495 kg CO₂e/度
2. 燃料使用 (範疇一) - 天然氣/柴油
3. 製程排放 (範疇一) - 依製程特性

建議優先盤點用電數據。"""
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== 排放計算 ==========
@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    """排放計算 - 簡化版"""
    try:
        data = request.get_json()
        source = data.get('emission_source', '')
        
        import re
        numbers = re.findall(r'\d+', source)
        
        if numbers and '度' in source:
            value = float(numbers[0])
            emission = value * 0.474 / 1000
            reply = f"用電 {value} 度，碳排放 {emission:.2f} 噸 CO₂e"
        else:
            reply = "請提供數值和單位，例如：5000度"
        
        return jsonify({'calculation': reply})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
