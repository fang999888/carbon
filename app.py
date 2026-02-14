@app.route('/api/chat', methods=['POST'])
def chat():
    """超級簡化版 - 讓顧問變笨"""
    logger.info("收到 /api/chat 請求")
    
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': '請輸入訊息'}), 400
        
        if not DEEPSEEK_API_KEY:
            return jsonify({'error': 'API Key 未設定'}), 500
        
        # 超級簡化的系統提示詞
        system_prompt = "你是碳盤查專家，請用一兩句話簡單回答。"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.3,  # 調低溫度，讓它更直接
            "max_tokens": 150,   # 大幅減少，不要想太多
            "stream": False
        }
        
        logger.info("發送請求至 DeepSeek API")
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
        return jsonify({'error': '系統錯誤'}), 502
