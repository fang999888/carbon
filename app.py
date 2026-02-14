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

@app.route('/api/test-deepseek')
def test_deepseek():
    """測試 DeepSeek API 連接"""
    logger.info("收到 /api/test-deepseek 請求")
    
    try:
        if not DEEPSEEK_API_KEY:
            return jsonify({"error": "API Key 未設定"}), 500
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        test_payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=test_payload,
            timeout=10
        )
        
        return jsonify({
            "status": "API Key 已設定",
            "api_test_ok": response.status_code == 200,
            "api_test_status": response.status_code
        })
        
    except Exception as e:
        return jsonify({"status": "測試失敗", "error": str(e)}), 500

@app.route('/api/debug-env')
def debug_env():
    """除錯：查看環境變數"""
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
        "files": os.listdir('.')
    })

# ========== 一般諮詢功能 ==========
@app.route('/api/chat', methods=['POST'])
def chat():
    """一般諮詢 - 回答各種碳盤查問題"""
    logger.info("收到 /api/chat 請求")
    
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'API Key 未設定'}), 500
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        for msg in conversation_history[-5:]:
            if msg.get('role') in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
        
        messages.append({"role": "user", "content": user_message})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.95
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'reply': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': f'API錯誤: {response.status_code}'}), 502
            
    except Exception as e:
        logger.error(f"錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ========== 行業排放源查詢功能 ==========
@app.route('/api/industry-emissions', methods=['POST'])
def industry_emissions():
    """行業別排放源查詢 - 讓使用者輸入行業別和排放源，BOT確認範疇和係數"""
    logger.info("收到 /api/industry-emissions 請求")
    
    try:
        data = request.json
        industry = data.get('industry', '')
        emission_source = data.get('emission_source', '')
        
        logger.info(f"行業排放查詢: {industry} - {emission_source}")
        
        if not industry or not emission_source:
            return jsonify({'error': '請提供行業別和排放源'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'API Key 未設定'}), 500
        
        # 專門用於行業排放查詢的提示詞
        query_prompt = f"""請針對以下資訊提供碳盤查專業建議，要非常具體實用：

行業別：{industry}
排放源：{emission_source}

請按照以下格式回答：

【範疇分類】
- 範疇：______ (請說明是範疇一/二/三，以及原因)

【類別歸屬 (ISO 14064-1)】
- 類別：______ (類別1-6)
- 歸屬原因：______

【適用排放係數】
- 建議係數值：______ (請給出具體數值，例如: 0.495 kg CO2e/度)
- 係數來源：______ (IPCC/環保署/IEA/DEFRA/Ecoinvent/其他)
- 單位：______

【計算公式】
- 公式：______
- 活動數據需求：______
- 計算範例：______

【實務建議】
- 常見問題：______
- 注意事項：______

請確保回答非常具體實用，包含實際的係數數值。"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一位實用型碳管理顧問，專注於提供具體的排放係數和計算方式。回答要包含實際的數值，不要只是籠統的說明。"},
                {"role": "user", "content": query_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
            "top_p": 0.95
        }
        
        logger.info("發送行業排放查詢請求至 DeepSeek")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            reply_content = result['choices'][0]['message']['content']
            logger.info("成功取得行業排放查詢回應")
            
            return jsonify({
                'reply': reply_content,
                'industry': industry,
                'emission_source': emission_source,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"DeepSeek API 錯誤: {response.status_code}")
            return jsonify({'error': f'查詢失敗: {response.status_code}'}), 502
            
    except requests.exceptions.Timeout:
        logger.error("API 請求超時")
        return jsonify({'error': '請求超時，請稍後再試'}), 504
    except Exception as e:
        logger.error(f"行業排放查詢錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ========== 行業分析功能 (模式2) ==========
@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    """🏭 行業分析 - 針對特定行業進行完整排放分析"""
    logger.info("收到 /api/analyze-industry 請求")
    
    try:
        data = request.json
        industry = data.get('industry', '')
        process_desc = data.get('process_description', '')
        
        if not industry:
            return jsonify({'error': '請提供行業類別'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        prompt = f"""請以碳管理顧問的身份，針對「{industry}」行業進行完整的排放源分析。
        
        {f'製程描述：{process_desc}' if process_desc else '請根據一般行業特性分析'}
        
        請提供以下詳細分析：

【1. 行業概述】
- 主要製程流程
- 常見設備與設施

【2. 排放源分類 (範疇一/二/三)】
- 範疇一排放源：______ (列出所有可能的直接排放源)
- 範疇二排放源：______ (電力、蒸氣、熱能等)
- 範疇三排放源：______ (上下游運輸、廢棄物、商務旅行等)

【3. 關鍵排放設備與係數】
- 設備/製程 | 排放源 | 建議係數 | 係數來源
(用表格列出至少5個關鍵排放點)

【4. 數據收集建議】
- 需要收集哪些活動數據
- 數據來源與收集方式
- 常見困難與解決方案

【5. 減碳機會識別】
- 短期可行措施
- 中長期規劃
- 預期減碳效果

【6. 行業特定注意事項】
- 法規要求
- 國際趨勢
- 標竿企業做法

請提供專業、具體、有實用價值的分析。"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一位專業的碳管理顧問，擅長進行行業別排放分析。請提供結構化、詳細的分析報告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.95
        }
        
        logger.info(f"發送行業分析請求: {industry}")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'reply': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': f'API 錯誤: {response.status_code}'}), 502
        
    except Exception as e:
        logger.error(f"行業分析錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ========== 排放計算功能 (模式3) ==========
@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    """🧮 排放計算 - 協助使用者計算具體的碳排放量"""
    logger.info("收到 /api/calculate-emission 請求")
    
    try:
        data = request.json
        emission_source = data.get('emission_source', '')
        activity_data = data.get('activity_data', {})
        
        # 如果 activity_data 是空的，但 emission_source 有值，嘗試解析
        if not activity_data and emission_source:
            # 嘗試從文字中解析數值
            import re
            numbers = re.findall(r'\d+\.?\d*', emission_source)
            units = re.findall(r'(度|kWh|立方公尺|公升|L|kg|噸|公里|km)', emission_source)
            
            activity_data = {
                'description': emission_source,
                'detected_numbers': numbers,
                'detected_units': units
            }
        
        if not emission_source:
            return jsonify({'error': '請提供排放源和活動數據'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'DeepSeek API Key 未設定'}), 500
        
        prompt = f"""請協助計算下列活動數據的溫室氣體排放量：

排放源描述：{emission_source}
活動數據：{json.dumps(activity_data, ensure_ascii=False, indent=2)}

請按照以下格式提供計算結果：

【排放源識別】
- 排放源類型：______
- 範疇歸屬：______
- 類別歸屬：______

【適用排放係數】
- 係數值：______
- 係數來源：______
- 資料年份：______
- 參考文獻：______

【計算過程】
- 計算公式：______
- 代入數值：______
- 計算結果：______ kg CO2e

【數據品質評估】
- 活動數據等級：______ (高/中/低)
- 係數數據等級：______ (高/中/低)
- 整體不確定性：______

【減量建議】
- 如何降低此排放源
- 替代方案或改善措施

如果活動數據不足，請說明需要收集哪些數據，並提供估算方法。"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一位碳排放計算專家，擅長根據活動數據計算排放量。請提供精確的計算過程和結果。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # 計算需要精確，降低溫度
            "max_tokens": 1500,
            "top_p": 0.95
        }
        
        logger.info(f"發送排放計算請求: {emission_source[:50]}...")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'reply': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': f'API 錯誤: {response.status_code}'}), 502
        
    except Exception as e:
        logger.error(f"排放計算錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"啟動伺服器在 port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
