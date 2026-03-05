import os
import re
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 排放係數資料庫
COEFFICIENTS = {
    '用電': 0.495,
    '天然氣': 2.09,
    '柴油': 2.61,
    '汽油': 2.26,
    '燃煤': 3.96,
    '液化石油氣': 1.75,
    '燃料油': 3.11
}

# 常見問題解答
FAQ = {
    '範疇一': '✅ 範疇一（直接排放）：\n• 固定燃燒源：鍋爐、加熱爐\n• 移動燃燒源：廠內車輛\n• 製程排放：化學反應\n• 逸散排放：冷媒洩漏',
    
    '範疇二': '✅ 範疇二（能源間接）：\n• 外購電力（係數：0.495 kg CO₂e/度）\n• 外購蒸氣、熱能',
    
    '範疇三': '✅ 範疇三（其他間接）：\n• 上游原料運輸\n• 下游產品運輸\n• 員工通勤\n• 商務旅行\n• 廢棄物處理',
    
    '組織邊界': '📌 組織邊界設定方法：\n1. 營運控制權法：對營運有控制權的設施納入\n2. 財務控制權法：對財務有控制權的設施納入\n\n建議：多數企業採用營運控制權法',
    
    '碳足跡熱點': '🔍 產品碳足跡熱點分析步驟：\n1. 繪製製程流程圖\n2. 收集各階段的活動數據\n3. 計算各階段的碳排放\n4. 找出占比最大的階段\n5. 針對熱點進行改善',
    
    '冷媒逸散': '❄️ 冷媒逸散估算方法：\n1. 簡化法：年填充量 × 冷媒GWP值\n2. 系統法：初始填充量 × 年洩漏率\n\n常用冷媒GWP值：\n• R134a：1430\n• R22：1810\n• R410a：2088',
    
    '鍋爐': '🔥 鍋爐排放源：\n1. 燃料燃燒：天然氣/柴油/重油\n2. 排放計算：燃料用量 × 排放係數\n\n天然氣係數：2.09 kg/m³\n柴油係數：2.61 kg/L',
    
    '係數選擇': '📊 排放係數資料庫比較：\n• IPCC：國際通用，適用於國家報告\n• 環保署：台灣本地數據，優先使用\n• DEFRA：英國數據，常用於範疇三\n• Ecoinvent：付費資料庫，最詳細\n\n建議：優先使用環保署係數'
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'message': '碳盤查小幫手運行中'})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        
        # 檢查是否匹配 FAQ
        reply = None
        for key, value in FAQ.items():
            if key in message:
                reply = value
                break
        
        # 如果沒有匹配，檢查是否問係數
        if not reply:
            if '係數' in message or '排放係數' in message:
                reply = '📋 常用排放係數：\n'
                for k, v in COEFFICIENTS.items():
                    reply += f'• {k}：{v} kg CO₂e/單位\n'
                reply += '\n資料來源：環境部碳足跡資料庫'
            else:
                reply = f'❓ 關於「{message}」\n\n您可以詢問：\n• 什麼是範疇一/二/三？\n• 用電排放係數\n• 如何設定組織邊界？\n• 冷媒逸散如何計算？'
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '系統處理中，請稍後再試'})

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
            result = f'用電 {value} 度\n碳排放：{emission:.2f} 噸 CO₂e'
        elif '天然氣' in source or 'm³' in source:
            emission = value * 2.09 / 1000
            result = f'天然氣 {value} m³\n碳排放：{emission:.2f} 噸 CO₂e'
        elif '柴油' in source:
            emission = value * 2.61 / 1000
            result = f'柴油 {value} L\n碳排放：{emission:.2f} 噸 CO₂e'
        else:
            result = f'數值：{value}\n請指定能源類型（用電、天然氣、柴油）'
        
        return jsonify({'calculation': result})
        
    except Exception as e:
        return jsonify({'calculation': '計算失敗，請稍後再試'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
