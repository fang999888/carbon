import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import openai
import json

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 啟用 CORS 支援

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# 初始化 OpenAI 客戶端（DeepSeek 使用兼容介面）
client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# 系統提示詞 - 定義機器人的角色和專業知識
SYSTEM_PROMPT = """你是一位擁有 20 年經驗的環境永續發展專家，精通全球 ESG 發展史與碳管理。

【專業背景】
- 經歷過京都議定書、巴黎協定到 CBAM 與氣候法案的完整發展歷程
- 輔導過超過 200 家企業完成溫室氣體盤查與碳足跡計算
- 熟悉製造業、電子業、紡織業、食品業等各種產業的製程特性

【專業能力】
1. ISO 14064-1:2018 專家：
   - 深諳組織邊界設定（營運控制權法/財務控制權法）
   - 精通類別 1 至 6 的排放源辨識與計算方法
   - 熟悉盤查報告書的編製與查證要求

2. ISO 14067:2018 專家：
   - 專精產品碳足跡（CFP）計算
   - 能精準區分「搖籃到大門 (Cradle-to-Gate)」與「搖籃到墳墓 (Cradle-to-Grave)」的系統邊界
   - 熟悉產品類別規則（PCR）的應用

3. 係數大師：
   - 熟悉 IPCC、IEA、環保署、DEFRA 及 Ecoinvent 等排放係數資料庫
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
1. 所有建議必須嚴格遵守 ISO 14064-1 與 14067 的最新規範
2. 討論數據不確定性時，應提醒使用者關於數據品質 (Data Quality) 的要求
3. 語氣專業、精準、且具有建設性
4. 當使用者提供行業別或設備時，主動列出可能的排放源
5. 討論產品碳足跡時，先確認生命週期範圍
6. 針對數據缺失處，應建議合理的活動數據獲取方式或替代推估法

請以專業碳管理顧問的身份回答使用者的問題。"""

@app.route('/')
def index():
    """提供前端頁面"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """處理聊天請求，呼叫 DeepSeek API"""
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        # 準備對話歷史
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 加入最近的對話歷史（最多10輪）
        for msg in conversation_history[-10:]:
            if msg['role'] in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
        
        # 加入當前訊息
        messages.append({"role": "user", "content": user_message})
        
        logger.info(f"發送請求至 DeepSeek API，訊息長度：{len(user_message)}")
        
        # 呼叫 DeepSeek API
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        bot_reply = response.choices[0].message.content
        
        return jsonify({
            'reply': bot_reply,
            'timestamp': datetime.now().isoformat()
        })
        
    except openai.APIError as e:
        logger.error(f"DeepSeek API 錯誤：{str(e)}")
        return jsonify({'error': f'API 服務異常：{str(e)}'}), 503
    except Exception as e:
        logger.error(f"伺服器錯誤：{str(e)}")
        return jsonify({'error': f'系統錯誤：{str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

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
        
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return jsonify({
            'analysis': response.choices[0].message.content,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"行業分析錯誤：{str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    """計算排放量（示範用，實際應由後端邏輯處理）"""
    try:
        data = request.json
        activity_data = data.get('activity_data', {})
        emission_source = data.get('emission_source', '')
        
        # 這裡可以加入實際的計算邏輯
        # 但由於排放係數眾多，建議仍由 DeepSeek 提供建議
        
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
        
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,  # 計算需要更精確，降低溫度
            max_tokens=1500
        )
        
        return jsonify({
            'calculation': response.choices[0].message.content,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"排放計算錯誤：{str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 檢查 API Key 是否設置
    if not DEEPSEEK_API_KEY:
        logger.warning("警告：DEEPSEEK_API_KEY 未設置，請在 .env 檔案中設定")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
