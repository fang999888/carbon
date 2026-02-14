import os
import logging
import json
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import requests

# 載入環境變數
load_dotenv()

# 設定詳細的日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 建立 Flask 應用
app = Flask(__name__)
CORS(app)

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

logger.info(f"啟動應用程式，API Key 設定狀態: {bool(DEEPSEEK_API_KEY)}")
if DEEPSEEK_API_KEY:
    logger.info(f"API Key 前綴: {DEEPSEEK_API_KEY[:10]}...")

# 詳細版的系統提示詞
SYSTEM_PROMPT = """你是一位擁有20年經驗的環境永續發展專家，精通全球ESG發展史與碳管理。

【專業背景】
- 經歷過京都議定書、巴黎協定到CBAM與氣候法案的完整發展歷程
- 輔導過超過200家企業完成溫室氣體盤查與碳足跡計算
- 熟悉製造業、電子業、紡織業、食品業等各種產業的製程特性

【專業能力】
1. ISO 14064-1:2018 專家：
   - 深諳組織邊界設定（營運控制權法/財務控制權法）
   - 精通類別1至6的排放源辨識與計算方法
   - 熟悉盤查報告書的編製與查證要求

2. ISO 14067:2018 專家：
   - 專精產品碳足跡（CFP）計算
   - 能精準區分「搖籃到大門」與「搖籃到墳墓」的系統邊界
   - 熟悉產品類別規則（PCR）的應用

3. 係數大師：
   - 熟悉IPCC、IEA、環保署、DEFRA及Ecoinvent等排放係數資料庫
   - 能精準指導電力、燃料、原物料及廢棄物的係數套用
   - 了解各國排放係數的差異與轉換方法

4. 製程專家：
   - 熟悉工業設備（鍋爐、空壓機、冰機、製程設備）的運作原理
   - 精通能耗數據分析與節能潛力評估
   - 能從生產流程中找出關鍵排放熱點

5. 報表權威：
   - 精通盤查清冊、清冊報告書的編製邏輯
   - 熟悉各類生產出貨報表的稽核與數據驗證
   - 能協助建立完善的數據管理制度

【回答原則】
- 所有建議必須嚴格遵守ISO 14064-1與14067的最新規範
- 討論數據不確定性時，提醒數據品質(Data Quality)的要求
- 語氣專業、精準、具有建設性
- 當使用者提供行業別時，主動列出可能的排放源
- 討論產品碳足跡時，先確認生命週期範圍
- 針對數據缺失處，建議合理的獲取方式或替代推估法

請以專業碳管理顧問的身份，提供詳細完整的回答。"""

@app.route('/')
def index():
    """提供前端頁面"""
    try:
        logger.info("渲染首頁")
        return render_template('index.html')
    except Exception as e:
        logger.error(f"無法載入模板: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Carbon Expert API 運行中 - 但無法載入模板: {str(e)}", 500

@app.route('/api/health')
def health():
    """健康檢查"""
    return jsonify({
        'status': 'healthy',
        'api_key_configured': bool(DEEPSEEK_API_KEY),
        'api_key_prefix': DEEPSEEK_API_KEY[:10] + '...' if DEEPSEEK_API_KEY else None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """詳細版聊天 - 包含完整的系統提示詞"""
    logger.info("收到 /api/chat 請求")
    
    try:
        # 取得請求資料
        data = request.json
        logger.info(f"請求資料: {data}")
        
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            logger.warning("請求中沒有訊息")
            return jsonify({'error': '請輸入訊息'}), 400
        
        # 檢查 API Key
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API Key 未設定")
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        # 準備 messages，包含詳細的系統提示詞
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 加入對話歷史（最多5筆）
        for msg in conversation_history[-5:]:
            if msg.get('role') in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
        
        # 加入當前訊息
        messages.append({"role": "user", "content": user_message})
        
        logger.info(f"準備發送請求到 DeepSeek，messages 數量: {len(messages)}")
        
        # 準備 API 請求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500,  # 增加到1500，讓回答更詳細
            "top_p": 0.95,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        # 發送請求到 DeepSeek
        logger.info("發送請求至 DeepSeek API")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=45  # 增加超時到45秒
        )
        
        logger.info(f"DeepSeek API 回應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info("成功取得 DeepSeek 回應")
            
            bot_reply = result['choices'][0]['message']['content']
            
            return jsonify({
                'reply': bot_reply,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"DeepSeek API 錯誤: {response.status_code} - {response.text}")
            return jsonify({
                'error': f'DeepSeek API 錯誤: {response.status_code}',
                'detail': response.text[:200]
            }), 502
            
    except requests.exceptions.Timeout:
        logger.error("API 請求超時")
        return jsonify({'error': '請求超時，請稍後再試'}), 504
    except requests.exceptions.ConnectionError as e:
        logger.error(f"API 連線錯誤: {str(e)}")
        return jsonify({'error': '無法連線到 DeepSeek API'}), 503
    except Exception as e:
        logger.error(f"伺服器錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """分析行業別的排放源"""
    logger.info("收到 /api/analyze-industry 請求")
    
    try:
        data = request.json
        logger.info(f"行業分析請求資料: {data}")
        
        industry = data.get('industry', '')
        process_desc = data.get('process_description', '')
        
        if not industry:
            return jsonify({'error': '請提供行業類別'}), 400
        
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API Key 未設定")
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        prompt = f"""請以碳管理顧問的身份，針對{industry}行業進行排放源分析。
        
        {f'製程描述：{process_desc}' if process_desc else ''}
        
        請提供：
        1. 此行業的主要排放類別（範疇一至三）
        2. 關鍵排放設備與製程
        3. 建議的排放係數來源
        4. 常見的數據收集難點與解決建議
        5. 初步的減碳機會識別
        """
        
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
            "max_tokens": 1500,
            "top_p": 0.95
        }
        
        logger.info("發送行業分析請求至 DeepSeek")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'analysis': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"DeepSeek API 錯誤: {response.status_code} - {response.text}")
            return jsonify({'error': f'API 錯誤: {response.status_code}'}), 502
        
    except Exception as e:
        logger.error(f"行業分析錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    """計算排放量"""
    logger.info("收到 /api/calculate-emission 請求")
    
    try:
        data = request.json
        logger.info(f"排放計算請求資料: {data}")
        
        activity_data = data.get('activity_data', {})
        emission_source = data.get('emission_source', '')
        
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API Key 未設定")
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        prompt = f"""請協助計算下列活動數據的溫室氣體排放量：
        
        排放源：{emission_source}
        活動數據：{json.dumps(activity_data, ensure_ascii=False)}
        
        請提供：
        1. 適用的排放係數與來源
        2. 計算公式與過程
        3. 計算結果（以 kg CO2e 表示）
        4. 數據品質等級評估
        5. 注意事項與不確定性說明
        """
        
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
            "temperature": 0.5,
            "max_tokens": 1500,
            "top_p": 0.95
        }
        
        logger.info("發送排放計算請求至 DeepSeek")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'calculation': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"DeepSeek API 錯誤: {response.status_code} - {response.text}")
            return jsonify({'error': f'API 錯誤: {response.status_code}'}), 502
        
    except Exception as e:
        logger.error(f"排放計算錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-deepseek')
def test_deepseek():
    """測試 DeepSeek API 連接"""
    logger.info("收到 /api/test-deepseek 請求")
    
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        
        if not api_key:
            return jsonify({
                "error": "API Key 未設定",
                "env_vars": list(os.environ.keys()),
                "has_env_file": os.path.exists('.env')
            }), 500
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        test_payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 10
        }
        
        logger.info("發送測試請求至 DeepSeek")
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
        logger.error(f"測試 DeepSeek 時發生錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "測試失敗",
            "error": str(e)
        }), 500

@app.route('/api/debug-env')
def debug_env():
    """除錯：查看環境變數（僅用於除錯）"""
    safe_env = {}
    for key in os.environ:
        if 'KEY' in key or 'SECRET' in key or 'PASSWORD' in key:
            if os.environ[key]:
                safe_env[key] = os.environ[key][:10] + '...'
            else:
                safe_env[key] = None
        else:
            safe_env[key] = os.environ[key]
    
    return jsonify({
        "env_vars": safe_env,
        "has_env_file": os.path.exists('.env'),
        "cwd": os.getcwd(),
        "files": os.listdir('.')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"啟動伺服器在 port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
