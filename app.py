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
    """一般諮詢 - 包含備用回應機制"""
    logger.info("收到 /api/chat 請求")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '請提供 JSON 數據'}), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        # 檢查是否有 DeepSeek API Key
        if not DEEPSEEK_API_KEY:
            logger.error("API Key 未設定")
            return jsonify({'error': '系統配置錯誤：API Key 未設定'}), 500
        
        # ===== 先嘗試用 DeepSeek API =====
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一個碳管理顧問，回答要簡潔專業。"},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.95,
                "stream": False
            }
            
            logger.info("嘗試呼叫 DeepSeek API")
            
            # 設定較短的 timeout，避免卡死
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=10  # 只等 10 秒，不行就用備用
            )
            
            if response.status_code == 200:
                result = response.json()
                reply = result['choices'][0]['message']['content']
                logger.info("DeepSeek API 回應成功")
                return jsonify({'reply': reply})
            else:
                logger.warning(f"DeepSeek API 錯誤: {response.status_code}")
                # 繼續使用備用回應
                
        except requests.exceptions.Timeout:
            logger.warning("DeepSeek API 超時，使用備用回應")
        except requests.exceptions.ConnectionError:
            logger.warning("DeepSeek API 連線錯誤，使用備用回應")
        except Exception as e:
            logger.warning(f"DeepSeek API 錯誤: {str(e)}，使用備用回應")
        
        # ===== 備用回應機制 =====
        logger.info("使用備用回應機制")
        
        # 常見問題的本地回應
        local_responses = {
            '範疇一': '範疇一（直接排放）：包括固定燃燒源（鍋爐）、移動燃燒源（車輛）、製程排放（化學反應）、逸散排放（冷媒洩漏）。',
            '範疇二': '範疇二（能源間接排放）：主要是外購電力、蒸氣、熱能。台灣電力係數 0.495 kg CO₂e/度。',
            '範疇三': '範疇三（其他間接排放）：包含上游運輸、下游運輸、員工通勤、商務旅行、廢棄物處理等。',
            'iso 14064': 'ISO 14064-1:2018 是組織型溫室氣體盤查標準，分為類別1（直接排放）到類別6（其他間接）。',
            'iso 14067': 'ISO 14067:2018 是產品碳足跡計算標準，計算產品從搖籃到大門或搖籃到墳墓的碳排放。',
            '組織邊界': '組織邊界設定有兩種方法：1.營運控制權法（對營運有控制權的設施納入）2.財務控制權法（對財務有控制權的設施納入）',
            '電力係數': '台電2023年電力排放係數：0.495 kg CO₂e/度。來源：環境部。',
            '天然氣': '天然氣排放係數：2.09 kg CO₂e/立方公尺。來源：環境部。',
            '柴油': '柴油排放係數：2.61 kg CO₂e/公升。來源：環境部。',
            '汽油': '汽油排放係數：2.26 kg CO₂e/公升。來源：環境部。',
        }
        
        # 尋找匹配的關鍵字
        reply = None
        for key, value in local_responses.items():
            if key in user_message:
                reply = value
                break
        
        # 如果沒有匹配，給通用回應
        if not reply:
            if '係數' in user_message:
                reply = """常用排放係數：
- 用電：0.495 kg CO₂e/度
- 天然氣：2.09 kg CO₂e/m³
- 柴油：2.61 kg CO₂e/L
- 汽油：2.26 kg CO₂e/L
資料來源：環境部碳足跡資料庫"""
            elif '歡迎' in user_message or '你好' in user_message:
                reply = "您好！我是碳盤查小幫手，請問您想了解什麼？我可以協助您查詢排放係數、計算碳排放、分析行業排放等。"
            else:
                reply = f"""關於「{user_message}」的問題，建議您：
1. 查詢特定排放源的係數（例如：用電係數）
2. 詢問 ISO 標準（例如：ISO 14064）
3. 了解範疇分類（例如：什麼是範疇一？）

目前 AI 服務暫時不穩定，請稍後再試完整查詢。"""
        
        return jsonify({'reply': f"[離線模式] {reply}"})
        
    except Exception as e:
        logger.error(f"聊天錯誤: {traceback.format_exc()}")
        # 即使發生錯誤，也給使用者一個友善的回應
        return jsonify({'reply': '系統暫時忙碌，請稍後再試。您可以嘗試詢問排放係數等基本問題。'}), 200
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
