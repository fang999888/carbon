import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 簡單的回應
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '')
    
    if '範疇一' in msg:
        reply = '範疇一：直接排放，包括鍋爐、車輛、冷媒等'
    elif '範疇二' in msg:
        reply = '範疇二：能源間接排放，主要是用電，係數0.495 kg/度'
    elif '係數' in msg:
        reply = '用電:0.495, 天然氣:2.09, 柴油:2.61'
    else:
        reply = f'您說: {msg}'
    
    return jsonify({'reply': reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
