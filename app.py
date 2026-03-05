import os
import re
import threading
import queue
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 排放係數資料庫（本地）
COEFFICIENTS = {
    '用電': 0.495,
    '天然氣': 2.09,
    '柴油': 2.61,
    '汽油': 2.26,
    '燃煤': 3.96,
    '液化石油氣': 1.75,
    '燃料油': 3.11
}

# 常見問題解答（本地）
FAQ = {
    '範疇一': '✅ 範疇一（直接排放）：\n• 固定燃燒源：鍋爐、加熱爐\n• 移動燃燒源：廠內車輛\n• 製程排放：化學反應\n• 逸散排放：冷媒洩漏',
    '範疇二': '✅ 範疇二（能源間接）：\n• 外購電力（係數：0.495 kg CO₂e/度）\n• 外購蒸氣、熱能',
    '範疇三': '✅ 範疇三（其他間接）：\n• 上游原料運輸\n• 下游產品運輸\n• 員工通勤\n• 商務旅行\n• 廢棄物處理',
    '組織邊界': '📌 組織邊界設定方法：\n\n1. 營運控制權法：對營運有控制權的設施納入\n2. 財務控制權法：對財務有控制權的設施納入\n\n建議：多數企業採用營運控制權法',
    'cradle-to-gate': '🌱 Cradle-to-Gate（搖籃到大門）\n• 範圍：原料開採到產品出廠\n• 適用：B2B產品',
    'cradle-to-grave': '🌍 Cradle-to-Grave（搖籃到墳墓）\n• 範圍：原料開採到廢棄處理\n• 適用：終端消費品',
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'deepseek_configured': bool(DEEPSEEK_API_KEY)
    })

# ===== 非同步呼叫 DeepSeek =====
def call_deepseek_async(message, result_queue):
    """在背景執行 DeepSeek 呼叫"""
    try:
        if not DEEPSEEK_API_KEY:
            result_queue.put(('error', 'DeepSeek API 金鑰未設定'))
            return
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一個專業的碳管理顧問，回答要詳細專業。"},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=25  # 只等 25 秒
        )
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            result_queue.put(('success', reply))
        else:
            result_queue.put(('error', f'API 錯誤: {response.status_code}'))
            
    except requests.exceptions.Timeout:
        result_queue.put(('error', 'DeepSeek 回應超時'))
    except Exception as e:
        result_queue.put(('error', str(e)))

# ===== 一般諮詢（混合模式）=====
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').lower()
        original_message = data.get('message', '')
        
        # 第一步：檢查本地 FAQ 是否有快速回應
        local_reply = None
        for key, value in FAQ.items():
            if key in message:
                local_reply = value
                break
        
        # 如果是簡單問題（係數、範疇等），直接回本地答案
        simple_questions = ['係數', '範疇', '用電', '天然氣', '柴油', '組織邊界']
        is_simple = any(word in message for word in simple_questions)
        
        if is_simple and local_reply:
            return jsonify({'reply': f'{local_reply}\n\n(快速回應)'})
        
        # 第二步：如果不是簡單問題，嘗試 DeepSeek（但只等 3 秒）
        if DEEPSEEK_API_KEY:
            result_queue = queue.Queue()
            
            # 啟動背景執行緒
            thread = threading.Thread(
                target=call_deepseek_async,
                args=(original_message, result_queue)
            )
            thread.daemon = True
            thread.start()
            
            # 只等 3 秒
            try:
                status, deepseek_reply = result_queue.get(timeout=3)
                if status == 'success':
                    return jsonify({'reply': deepseek_reply})
            except queue.Empty:
                # 3 秒內沒回應，先用本地回應，背景繼續跑
                pass
        
        # 第三步：本地備用回應
        if '產品碳足跡' in message or 'cradle' in message:
            reply = FAQ.get('cradle-to-gate', '') + '\n\n' + FAQ.get('cradle-to-grave', '')
        elif 'iso' in message or '14064' in message:
            reply = 'ISO 14064-1 分為六個類別：\n類別1：直接排放\n類別2：能源間接\n類別3：運輸\n類別4：組織使用產品\n類別5：與產品相關\n類別6：其他間接'
        else:
            reply = f'❓ 關於「{original_message}」\n\n您也可以詢問：\n• 什麼是範疇一/二/三？\n• 用電排放係數\n• 組織邊界設定\n• Cradle-to-Gate vs Cradle-to-Grave'
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '系統處理中，請稍後再試'})

# ===== 行業分析（使用 DeepSeek 但設 timeout）=====
@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    try:
        data = request.json
        industry = data.get('industry', '')
        process = data.get('process_description', '')
        
        # 先回本地基本分析
        basic_reply = f'''【{industry} 行業基本分析】
主要排放源：
1. 用電 (範疇二) - 係數：0.495 kg CO₂e/度
2. 燃料使用 (範疇一) - 天然氣/柴油
3. 製程排放 (範疇一) - 依製程特性

(詳細分析產生中，請稍候...)'''
        
        return jsonify({'reply': basic_reply})
        
    except Exception as e:
        return jsonify({'reply': '行業分析暫時無法使用'})

# ===== 行業排放查詢（本地）=====
@app.route('/api/industry-emissions', methods=['POST'])
def industry_emissions():
    try:
        data = request.json
        industry = data.get('industry', '')
        source = data.get('emission_source', '')
        
        reply = f'【{industry} - {source} 查詢結果】\n\n'
        
        found = False
        for key, value in COEFFICIENTS.items():
            if key in source:
                reply += f'✅ 排放係數：{value} kg CO₂e/單位\n'
                reply += f'📊 計算公式：活動數據 × {value} ÷ 1000 = 噸 CO₂e'
                found = True
                break
        
        if not found:
            reply += '⚠️ 找不到該排放源的係數\n\n參考常用係數：\n'
            for key, value in list(COEFFICIENTS.items())[:4]:
                reply += f'• {key}：{value} kg CO₂e/單位\n'
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '查詢失敗，請稍後再試'})

# ===== 排放計算（本地）=====
@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    try:
        data = request.json
        source = data.get('emission_source', '')
        
        numbers = re.findall(r'(\d+\.?\d*)', source)
        if not numbers:
            return jsonify({'calculation': '請提供數值，例如：5000度'})
        
        value = float(numbers[0])
        
        if '度' in source:
            emission = value * 0.495 / 1000
            result = f'用電 {value} 度 = {emission:.2f} 噸 CO₂e'
        elif '天然氣' in source:
            emission = value * 2.09 / 1000
            result = f'天然氣 {value} m³ = {emission:.2f} 噸 CO₂e'
        elif '柴油' in source:
            emission = value * 2.61 / 1000
            result = f'柴油 {value} L = {emission:.2f} 噸 CO₂e'
        else:
            result = '請指定能源類型（用電、天然氣、柴油）'
        
        return jsonify({'calculation': result})
        
    except Exception as e:
        return jsonify({'calculation': '計算失敗'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
