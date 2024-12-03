from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
import requests
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)
load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

def calculate_spans(text, keywords):
    spans = []
    for item in keywords:
        keyword = item['keyword']
        keyword_type = item['type']
        start = text.find(keyword)
        while start != -1:
            end = start + len(keyword)
            spans.append({"start": start, "end": end, "type": keyword_type})
            # 繼續尋找下一個出現的位置
            start = text.find(keyword, end)
    return spans

def analyze_with_openrouter(text):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:5000",  # 你的網站網址
            "Content-Type": "application/json"
        }
        
        # 修改 Prompt，讓模型只輸出關鍵字和類別
        prompt = f"""你是一個專門用來偵測文章中個人資訊的助手。請分析以下文字，並列出所有可能的個人資訊以及其對應的類型。

需要偵測的個資類型：姓名(NAME)、電話(PHONE)、地址(ADDRESS)、身分證字號(ID)、電子郵件(EMAIL)、生日(BIRTHDAY)、護照號碼(PASSPORT)、信用卡號(CREDIT_CARD)、銀行帳號(BANK_ACCOUNT)。

請直接回傳 JSON 格式，範例如下：
{{
  "keywords": [
    {{"keyword": "王小明", "type": "NAME"}},
    {{"keyword": "0912345678", "type": "PHONE"}},
    {{"keyword": "台北市中正區重慶南路一段122號", "type": "ADDRESS"}}
  ]
}}

待分析文字：
{text}

請按照範例格式直接回傳 JSON，不要加入其他說明。
"""

        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json={
                "model": "meta-llama/llama-3.1-70b-instruct:free",  # 可換成其他模型
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        
        response_json = response.json()
        if 'choices' not in response_json or len(response_json['choices']) == 0:
            return {"error": "模型沒有返回結果。"}
        
        model_output = response_json['choices'][0]['message']['content'].strip()
        
        # 解析模型輸出的 JSON
        try:
            result = json.loads(model_output)
            keywords = result.get('keywords', [])
            if not keywords:
                return {"spans": []}
            
            # 計算每個關鍵字的起始和結束位置
            spans = calculate_spans(text, keywords)
            return {"spans": spans}
        except json.JSONDecodeError:
            return {"error": "無法解析模型返回的 JSON 格式。"}
                
    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/detect', methods=['POST'])
def detect_personal_info():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': '請提供文字內容'}), 400

    result = analyze_with_openrouter(text)
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
        
    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
