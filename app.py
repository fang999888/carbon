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
SYSTEM_PROMPT = """你是一位擁有 20 年經驗的環境永續發展專家，精通全球 ESG 發展史與碳管理。

【專業背景】
- 經歷過京都議定書、巴黎協定到 CBAM 與氣候法案的完整發展歷程
- 輔導過超過 200 家企業完成溫室氣體盤查與碳足跡計算

【專業能力】
1. ISO 14064-1:2018 專家：深諳組織邊界設定、類別 1 至 6 的排放源辨識
2. ISO 14067:2018 專家：專精產品碳足跡（CFP）計算
3. 係數大師：熟悉 IPCC、IEA、環保署及 Ecoinvent 等排放係數資料庫
4. 製程專家：熟悉工業設備的運作原理與能耗數據分析
5. 報表權威：精通盤查清冊、清冊報告書的稽核邏輯

【回答原則】
- 所有建議必須嚴格遵守 ISO 14064-1 與 14067 的最新規範
- 討論數據不確定性時，提醒數據品質要求
- 語氣專業、精準、具有建設性
- 當使用者提供行業別時，主動列出可能的排放源
- 針對數據缺失處，建議合理的獲取方式或替代推估法"""

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
        'api_key_configured': bool(DEEPSEEK_API_KEY)
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """處理聊天請求 - 使用 requests 直接呼叫 DeepSeek API"""
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        # 準備 messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 加入對話歷史
        for msg in conversation_history[-5:]:  # 只保留最近5輪
            if msg['role'] in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
        
        # 加入當前訊息
        messages.append({"role": "user", "content": user_message})
        
        # 準備 API 請求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        logger.info("發送請求至 DeepSeek API")
        
        # 發送請求
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            return jsonify({
                'reply': bot_reply,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"API 錯誤: {response.status_code} - {response.text}")
            return jsonify({
                'error': f'DeepSeek API 錯誤: {response.status_code}'
            }), 500
        
    except requests.exceptions.Timeout:
        logger.error("API 請求超時")
        return jsonify({'error': 'API 請求超時，請稍後再試'}), 504
    except requests.exceptions.ConnectionError:
        logger.error("API 連線錯誤")
        return jsonify({'error': '無法連線到 DeepSeek API'}), 503
    except Exception as e:
        logger.error(f"伺服器錯誤: {str(e)}")
        return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """分析行業別的排放源"""
    try:
        data = request.json
        industry = data.get('industry', '')
        process_desc = data.get('process_description', '')
        
        if not industry:
            return jsonify({'error': '請提供行業類別'}), 400
        
        prompt = f"""請以碳管理顧問的身份，針對{industry}行業進行排放源分析。
        
        {f'製程描述：{process_desc}' if process_desc else ''}
        
        請提供：
        1. 此行業的主要排放類別（範疇一至三）
        2. 關鍵排放設備與製程
        3. 建議的排放係數來源
        4. 常見的數據收集難點與解決建議
        5. 初步的減碳機會識別
        """
        
        # 呼叫 DeepSeek API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'analysis': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': f'API 錯誤: {response.status_code}'}), 500
        
    except Exception as e:
        logger.error(f"行業分析錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
