import os
import re
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ========== 排放係數資料庫 ==========
COEFFICIENTS = {
    '用電': {'value': 0.495, 'unit': 'kg CO₂e/度', 'source': '台電2023'},
    '天然氣': {'value': 2.09, 'unit': 'kg CO₂e/m³', 'source': '環境部'},
    '柴油': {'value': 2.61, 'unit': 'kg CO₂e/L', 'source': '環境部'},
    '汽油': {'value': 2.26, 'unit': 'kg CO₂e/L', 'source': '環境部'},
    '燃煤': {'value': 3.96, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
    '液化石油氣': {'value': 1.75, 'unit': 'kg CO₂e/L', 'source': '環境部'},
    '燃料油': {'value': 3.11, 'unit': 'kg CO₂e/L', 'source': '環境部'},
    '冷媒R134a': {'value': 1430, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
    '冷媒R22': {'value': 1810, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
    '冷媒R410a': {'value': 2088, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
    '冷媒R404a': {'value': 3922, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
    '冷媒R407c': {'value': 1774, 'unit': 'kg CO₂e/kg', 'source': 'IPCC'},
}

# ========== 諮詢主題資料庫 ==========
TOPICS = {
    # 📌 類別界定
    '類別界定': '''📌 ISO 14064-1 類別1-6界定：

類別1：直接排放
• 固定燃燒：鍋爐、加熱爐
• 移動燃燒：廠內車輛
• 製程排放：化學反應
• 逸散排放：冷媒洩漏

類別2：進口能源
• 外購電力
• 外購蒸氣
• 外購熱能

類別3：運輸
• 上游原料運輸
• 下游產品運輸
• 員工通勤
• 商務旅行

類別4：組織使用的產品
• 購買的產品
• 資本設備
• 廢棄物處理

類別5：與產品相關
• 產品使用階段
• 產品廢棄階段

類別6：其他間接
• 其他無法歸類的間接排放''',
    
    '範疇一': '✅ 範疇一（直接排放）：\n• 固定燃燒源：鍋爐、加熱爐\n• 移動燃燒源：廠內車輛\n• 製程排放：化學反應\n• 逸散排放：冷媒洩漏',
    '範疇二': '✅ 範疇二（能源間接）：\n• 外購電力（係數：0.495 kg CO₂e/度）\n• 外購蒸氣、熱能',
    '範疇三': '✅ 範疇三（其他間接）：\n• 上游原料運輸\n• 下游產品運輸\n• 員工通勤\n• 商務旅行\n• 廢棄物處理',
    
    # 🔲 邊界設定
    '邊界設定': '''🔲 組織邊界設定方法：

1. 營運控制權法
   • 定義：對營運有控制權的設施納入
   • 優點：容易管理數據
   • 適用：多數企業
   • 判斷：是否有權制定營運政策

2. 財務控制權法
   • 定義：對財務有控制權的設施納入
   • 優點：符合財務報表
   • 適用：集團企業、投資組合
   • 判斷：持股比例 >50%

建議：多數企業採用營運控制權法''',
    
    '營運控制權': '✅ 營運控制權法：對營運有控制權的設施納入邊界',
    '財務控制權': '✅ 財務控制權法：對財務有控制權的設施納入邊界',
    
    # 👣 系統邊界
    '系統邊界': '''👣 產品碳足跡系統邊界：

1. Cradle-to-Gate（搖籃到大門）
   • 範圍：原料開採 → 產品出廠
   • 適用：B2B產品、中間產品
   • 數據需求：原料、製造、廠內運輸

2. Cradle-to-Grave（搖籃到墳墓）
   • 範圍：原料開採 → 廢棄處理
   • 適用：終端消費品
   • 數據需求：原料、製造、配送、使用、廢棄

3. Gate-to-Gate（大門到大門）
   • 範圍：單一製程階段
   • 適用：特定製程分析''',
    
    'cradle-to-gate': '🌱 Cradle-to-Gate：原料開採到產品出廠，適用B2B產品',
    'cradle-to-grave': '🌍 Cradle-to-Grave：原料開採到廢棄處理，適用終端產品',
    
    # 📊 係數選擇
    '係數選擇': '''📊 排放係數資料庫比較：

1. 環保署（台灣）
   • 優點：本地數據，最準確
   • 適用：台灣企業盤查
   • 更新：每年更新

2. IPCC（國際）
   • 優點：國際通用
   • 適用：國家溫室氣體清冊
   • 特色：涵蓋各國預設值

3. DEFRA（英國）
   • 優點：範疇三數據完整
   • 適用：跨國企業、供應鏈
   • 特色：每年更新，免費

4. IEA（國際能源署）
   • 優點：能源數據完整
   • 適用：電力係數比較
   • 特色：各國電力結構

5. Ecoinvent（瑞士）
   • 優點：最詳細，涵蓋全球
   • 適用：學術研究、產品碳足跡
   • 特色：付費資料庫

選擇原則：
• 優先使用本地官方數據
• 次選國際通用數據
• 註明數據來源和不確定性''',
    
    # 🔥 鍋爐排放計算
    '鍋爐': '''🔥 鍋爐排放計算：

1. 排放源識別
   • 天然氣鍋爐
   • 柴油鍋爐
   • 重油鍋爐
   • 燃煤鍋爐

2. 排放係數
   • 天然氣：2.09 kg CO₂e/m³
   • 柴油：2.61 kg CO₂e/L
   • 重油：3.11 kg CO₂e/L
   • 燃煤：3.96 kg CO₂e/kg

3. 計算公式
   排放量(噸) = 燃料用量 × 係數 ÷ 1000

4. 計算範例
   天然氣 10,000 m³
   = 10,000 × 2.09 ÷ 1000
   = 20.9 噸 CO₂e

5. 數據收集
   • 燃料採購記錄
   • 燃料用量計量
   • 燃料發熱量（如有）''',
    
    # 💨 空壓機節能
    '空壓機': '''💨 空壓機系統節能診斷：

1. 效率評估指標
   • 比功率 (kW/m³/min)
   • 洩漏率 (目標 <10%)
   • 壓力設定 (最佳 6-7 kg/cm²)

2. 節能機會
   • 變頻控制：節電 20-35%
   • 管路檢修：減少洩漏
   • 壓力調降：每降1kg，節電7%
   • 熱回收：回收80%以上熱能
   • 多機連鎖：依需求自動啟停

3. 監測重點
   • 運轉時間
   • 加載率 (>70% 較佳)
   • 比功率變化
   • 壓力降

4. 計算節能潛力
   範例：100HP空壓機
   • 改善前：年用電 300,000度
   • 改善後：年用電 210,000度
   • 減碳量：90,000 × 0.495 ÷ 1000 = 44.6噸''',
    
    # ❄️ 冷媒逸散估算
    '冷媒': '''❄️ 冷媒逸散估算方法：

1. 簡化法（推薦）
   排放量(噸) = 年填充量(kg) × GWP ÷ 1000
   
   範例：R134a 填充 100kg
   100 × 1430 ÷ 1000 = 143 噸 CO₂e

2. 系統法
   排放量 = 初始填充量 × 年洩漏率 × GWP
   
   年洩漏率參考：
   • 商業冷凍：15-30%
   • 空調系統：3-5%
   • 工業冷凍：8-15%

3. 常用冷媒GWP值
   • R134a：1430
   • R22：1810
   • R410a：2088
   • R404a：3922
   • R407c：1774
   • R32：675
   • R290(丙烷)：3
   • R744(CO2)：1

4. 數據收集
   • 冷媒採購記錄
   • 填充保養紀錄
   • 設備清冊（型號、填充量）''',
    
    # 🔍 碳足跡熱點
    '碳足跡熱點': '''🔍 產品碳足跡熱點分析步驟：

1. 繪製製程流程圖
   • 列出所有製程步驟
   • 標示物料流、能源流
   • 確認系統邊界

2. 收集活動數據
   • 各階段原料用量
   • 各階段能源用量
   • 運輸距離與方式
   • 廢棄物產生量

3. 計算各階段碳排放
   • 套用排放係數
   • 計算每個階段的碳足跡
   • 建立碳足跡矩陣

4. 找出熱點
   • 計算各階段占比
   • 排序找出前三大
   • 通常80%排放來自20%階段

5. 熱點改善策略
   • 替代低碳原料
   • 提升能源效率
   • 優化運輸模式
   • 廢棄物減量與回收

6. 範例：電子產品
   • 熱點1：晶片製造 (45%)
   • 熱點2：使用階段用電 (30%)
   • 熱點3：原料運輸 (12%)''',
    
    # 📊 數據品質等級
    '數據品質': '''📊 數據品質等級 (DQR) 評估：

1. 技術代表性 (TeR)
   • 高：實際量測數據
   • 中：同類設備平均值
   • 低：文獻參考值

2. 時間代表性 (TiR)
   • 高：當年度數據
   • 中：1-3年內數據
   • 低：3年以上數據

3. 地理代表性 (GR)
   • 高：本地實測數據
   • 中：本國平均值
   • 低：他國數據

4. 數據品質矩陣
   ┌────────────┬──────┬──────┬──────┐
   │  指標      │  高  │  中  │  低  │
   ├────────────┼──────┼──────┼──────┤
   │技術代表性 │ 1    │ 2    │ 3    │
   │時間代表性 │ 1    │ 2    │ 3    │
   │地理代表性 │ 1    │ 2    │ 3    │
   └────────────┴──────┴──────┴──────┘

   整體數據品質 = (TeR + TiR + GR) ÷ 3
   • 1.0-1.5：高品質
   • 1.5-2.5：中等品質
   • 2.5-3.0：低品質

5. 改善數據品質
   • 優先盤點高占比排放源
   • 安裝計量設備
   • 建立數據管理制度
   • 定期校驗儀器''',
    
    # 🌍 CBAM因應
    'CBAM': '''🌍 CBAM（碳邊境調整機制）因應策略：

1. CBAM 適用產品
   • 水泥
   • 鋼鐵
   • 鋁
   • 化肥
   • 電力
   • 氫氣

2. 申報要求
   • 2023-2025：過渡期，僅申報
   • 2026起：購買CBAM憑證
   • 需提供：生產設施實際排放數據

3. 數據準備
   • 建立產品碳足跡計算能力
   • 安裝監測設備
   • 建立數據追溯系統
   • 第三方查證準備

4. 排放計算方法
   • 簡單產品：直接排放 + 能源間接
   • 複雜產品：前驅物排放 + 製程排放
   
   計算公式：
   CBAM排放 = 製程排放 + 燃料燃燒 + 外購電力

5. 減碳策略
   • 提升能源效率
   • 使用低碳燃料
   • 採購綠電
   • 優化製程

6. 時程規劃
   • 立即：建立盤查能力
   • 3個月：完成產品碳足跡
   • 6個月：建立監測系統
   • 1年：取得第三方查證''',
}

# ========== 首頁 ==========
@app.route('/')
def index():
    return render_template('index.html')

# ========== 健康檢查 ==========
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'message': '碳盤查小幫手完整版運行中'})

# ========== 一般諮詢 ==========
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').lower()
        original = data.get('message', '')
        
        # 檢查所有主題
        for key, value in TOPICS.items():
            if key in message or key in original:
                return jsonify({'reply': value})
        
        # 檢查係數查詢
        if '係數' in message:
            reply = '📋 常用排放係數：\n\n'
            for name, info in COEFFICIENTS.items():
                reply += f'• {name}：{info["value"]} {info["unit"]}（{info["source"]}）\n'
            return jsonify({'reply': reply})
        
        # 檢查特定排放源
        for name in COEFFICIENTS:
            if name in message:
                info = COEFFICIENTS[name]
                return jsonify({'reply': f'【{name} 排放係數】\n\n數值：{info["value"]} {info["unit"]}\n來源：{info["source"]}\n\n計算公式：活動數據 × {info["value"]} ÷ 1000 = 噸 CO₂e'})
        
        # 預設回應
        reply = f'''❓ 關於「{original}」

您可以點擊下方主題直接查詢：
📌 類別界定 - 範疇一/二/三分類
🔲 邊界設定 - 營運控制權 vs 財務控制權
👣 系統邊界 - Cradle-to-Gate vs Cradle-to-Grave
📊 係數選擇 - 資料庫比較與適用情境

或查詢特定排放源係數：
• 用電 • 天然氣 • 柴油 • 冷媒R134a'''
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '系統處理中，請稍後再試'})

# ========== 行業排放查詢 ==========
@app.route('/api/industry-emissions', methods=['POST'])
def industry_emissions():
    try:
        data = request.json
        industry = data.get('industry', '')
        process = data.get('process', '')
        source = data.get('emission_source', '')
        
        reply = f'【{industry} {process} {source} 查詢結果】\n\n'
        
        # 搜尋係數
        found = False
        for name, info in COEFFICIENTS.items():
            if name in source:
                reply += f'✅ 排放係數：{info["value"]} {info["unit"]}\n'
                reply += f'📊 資料來源：{info["source"]}\n'
                reply += f'📝 計算公式：活動數據 × {info["value"]} ÷ 1000 = 噸 CO₂e\n\n'
                
                # 加入製程說明
                if '電弧爐' in process:
                    reply += '🏭 電弧爐製程說明：\n• 主要排放源：用電、石墨電極消耗\n• 建議收集：用電度數、電極用量\n'
                elif '鍋爐' in process:
                    reply += '🔥 鍋爐製程說明：\n• 主要排放源：燃料燃燒\n• 建議收集：燃料用量、燃料種類\n'
                
                found = True
                break
        
        if not found:
            reply += '⚠️ 找不到該排放源的係數\n\n參考常用係數：\n'
            for name, info in list(COEFFICIENTS.items())[:6]:
                reply += f'• {name}：{info["value"]} {info["unit"]}\n'
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '查詢失敗，請稍後再試'})

# ========== 行業分析 ==========
@app.route('/api/analyze-industry', methods=['POST'])
def analyze_industry():
    try:
        data = request.json
        industry = data.get('industry', '')
        process = data.get('process_description', '')
        
        reply = f'''【{industry} 行業完整分析】
{f'製程：{process}' if process else ''}

🏭 主要排放源分類：

1️⃣ 範疇一（直接排放）
   • 固定燃燒：鍋爐、加熱爐
   • 移動燃燒：廠內車輛
   • 製程排放：化學反應
   • 逸散排放：冷媒洩漏

2️⃣ 範疇二（能源間接）
   • 外購電力：0.495 kg CO₂e/度
   • 外購蒸氣、熱能

3️⃣ 範疇三（其他間接）
   • 上游原料運輸
   • 下游產品運輸
   • 員工通勤
   • 廢棄物處理

📊 排放係數參考：
• 用電：0.495 kg/度
• 天然氣：2.09 kg/m³
• 柴油：2.61 kg/L

🎯 減碳建議：
1. 提高能源效率
2. 採購綠電
3. 製程優化
4. 熱能回收

📋 數據收集重點：
• 用電度數（每月）
• 燃料用量（天然氣/柴油）
• 冷媒填充記錄
• 運輸里程'''
        
        return jsonify({'reply': reply})
        
    except Exception as e:
        return jsonify({'reply': '行業分析暫時無法使用'})

# ========== 排放計算 ==========
@app.route('/api/calculate-emission', methods=['POST'])
def calculate_emission():
    try:
        data = request.json
        source = data.get('emission_source', '')
        
        # 提取數字
        numbers = re.findall(r'(\d+\.?\d*)', source)
        if not numbers:
            return jsonify({'calculation': '請提供數值，例如：5000度、100m³天然氣'})
        
        value = float(numbers[0])
        
        # 判斷類型並計算
        if '度' in source or 'kWh' in source:
            emission = value * 0.495 / 1000
            result = f'⚡ 用電 {value} 度\n\n排放量：{emission:.2f} 噸 CO₂e\n\n計算式：{value} × 0.495 ÷ 1000 = {emission:.2f}'
        
        elif '天然氣' in source or 'm³' in source:
            emission = value * 2.09 / 1000
            result = f'🔥 天然氣 {value} m³\n\n排放量：{emission:.2f} 噸 CO₂e\n\n計算式：{value} × 2.09 ÷ 1000 = {emission:.2f}'
        
        elif '柴油' in source:
            emission = value * 2.61 / 1000
            result = f'⛽ 柴油 {value} L\n\n排放量：{emission:.2f} 噸 CO₂e\n\n計算式：{value} × 2.61 ÷ 1000 = {emission:.2f}'
        
        elif '汽油' in source:
            emission = value * 2.26 / 1000
            result = f'⛽ 汽油 {value} L\n\n排放量：{emission:.2f} 噸 CO₂e\n\n計算式：{value} × 2.26 ÷ 1000 = {emission:.2f}'
        
        elif 'R134a' in source or '冷媒' in source:
            emission = value * 1430 / 1000
            result = f'❄️ 冷媒 R134a {value} kg\n\n排放量：{emission:.2f} 噸 CO₂e\n\n計算式：{value} × 1430 ÷ 1000 = {emission:.2f}'
        
        else:
            result = f'數值：{value}\n請指定能源類型，例如：\n• 5000度\n• 100m³天然氣\n• 200L柴油\n• 50kg冷媒R134a'
        
        return jsonify({'calculation': result})
        
    except Exception as e:
        return jsonify({'calculation': '計算失敗，請稍後再試'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
