from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
import requests
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# 限制 CORS 來源
CORS(app, resources={r"/api/*": {"origins": os.getenv('BASE_URL', 'https://your-domain.com')}})

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

def analyze_single_attempt(text, attempt_num):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": os.getenv('BASE_URL', 'https://your-domain.com'),
            "Content-Type": "application/json"
        }
        
        # 根據嘗試次數調整提示詞，讓模型用不同角度分析
        prompts = [
            # 第一次分析：基本個資檢測
            """你是一個專門用來偵測文章中個人資訊的助手。請分析以下文字，找出所有明顯的個人資訊。

需要偵測的個資類型：姓名(NAME)、電話(PHONE)、地址(ADDRESS)、身分證字號(ID)、電子郵件(EMAIL)、生日(BIRTHDAY)、護照號碼(PASSPORT)、信用卡號(CREDIT_CARD)、銀行帳號(BANK_ACCOUNT)。""",
            
            # 第二次分析：深入檢查隱含的個資
            """你是一個資安專家，專門找出文章中可能被忽略的個人資訊。請仔細分析文字中的每個部分，包括可能被分散或隱藏的個人資訊。

需要偵測的個資類型：姓名(NAME)、電話(PHONE)、地址(ADDRESS)、身分證字號(ID)、電子郵件(EMAIL)、生日(BIRTHDAY)、護照號碼(PASSPORT)、信用卡號(CREDIT_CARD)、銀行帳號(BANK_ACCOUNT)。""",
            
            # 第三次分析：特殊格式和組合檢查
            """你是一個數據分析專家，專門找出文章中特殊格式或組合形式的個人資訊。請特別注意可能被拆分或用特殊格式表示的個資。

需要偵測的個資類型：姓名(NAME)、電話(PHONE)、地址(ADDRESS)、身分證字號(ID)、電子郵件(EMAIL)、生日(BIRTHDAY)、護照號碼(PASSPORT)、信用卡號(CREDIT_CARD)、銀行帳號(BANK_ACCOUNT)。"""
        ]

        prompt = f"""{prompts[attempt_num]}

請嚴格按照以下JSON格式回傳，不要加入任何其他文字：
{{
  "keywords": [
    {{"keyword": "王小明", "type": "NAME"}},
    {{"keyword": "0912345678", "type": "PHONE"}},
    {{"keyword": "台北市中正區重慶南路一段122號", "type": "ADDRESS"}}
  ]
}}

待分析文字：
{text}
"""

        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7 - (attempt_num * 0.2),  # 隨著嘗試次數增加降低隨機性
                "max_tokens": 1000
            }
        )
        
        response_json = response.json()
        if 'choices' not in response_json or len(response_json['choices']) == 0:
            return []
        
        model_output = response_json['choices'][0]['message']['content'].strip()
        
        # 嘗試提取JSON部分
        try:
            start_idx = model_output.find('{')
            end_idx = model_output.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = model_output[start_idx:end_idx]
                result = json.loads(json_str)
                return result.get('keywords', [])
            return []
        except json.JSONDecodeError:
            return []
                
    except Exception as e:
        print(f"Error in analyze_single_attempt {attempt_num + 1}: {str(e)}")
        return []

def analyze_with_openrouter(text):
    try:
        all_keywords = []
        
        # 進行三次分析
        for i in range(3):
            keywords = analyze_single_attempt(text, i)
            all_keywords.extend(keywords)
        
        # 去除重複的結果（基於關鍵字和類型都相同）
        unique_keywords = []
        seen = set()
        for kw in all_keywords:
            key = (kw['keyword'], kw['type'])
            if key not in seen:
                seen.add(key)
                unique_keywords.append(kw)
        
        # 計算所有關鍵字的位置
        spans = calculate_spans(text, unique_keywords)
        
        # 根據位置排序並去除重疊
        spans.sort(key=lambda x: (x['start'], -x['end']))
        filtered_spans = []
        last_end = -1
        for span in spans:
            if span['start'] >= last_end:  # 確保不重疊
                filtered_spans.append(span)
                last_end = span['end']
        
        return {"spans": filtered_spans}
                
    except Exception as e:
        print(f"Error in analyze_with_openrouter: {str(e)}")
        return {"spans": []}

def generate_random_text():
    try:
        if not OPENROUTER_API_KEY:
            print("Error: OPENROUTER_API_KEY not found")
            return {"text": "親愛的人資部門，\n\n我是張小華，想要應徵貴公司的軟體工程師職位。您可以透過我的手機0912345678或是Email test@example.com聯繫我。目前居住在台北市信義區松仁路100號。\n\n期待能收到面試通知。"}

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": os.getenv('BASE_URL', 'https://your-domain.com'),
            "Content-Type": "application/json"
        }
        
        prompt = """請用中文生成一封求職信，內容需包含：
1. 應徵者姓名
2. 聯絡電話
3. 電子郵件
4. 居住地址

直接輸出信件內容，不要加入任何說明或標記。"""

        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 300
            }
        )
        
        if response.status_code != 200:
            print(f"API Error: Status {response.status_code}")
            return {"text": "親愛的人資部門，\n\n我是張小華，想要應徵貴公司的軟體工程師職位。您可以透過我的手機0912345678或是Email test@example.com聯繫我。目前居住在台北市信義區松仁路100號。\n\n期待能收到面試通知。"}
        
        response_json = response.json()
        if 'choices' not in response_json or len(response_json['choices']) == 0:
            print("API Error: No choices in response")
            return {"text": "親愛的人資部門，\n\n我是張小華，想要應徵貴公司的軟體工程師職位。您可以透過我的手機0912345678或是Email test@example.com聯繫我。目前居住在台北市信義區松仁路100號。\n\n期待能收到面試通知。"}
        
        generated_text = response_json['choices'][0]['message']['content'].strip()
        
        if not generated_text or len(generated_text) < 50:
            print("API Error: Generated text too short")
            return {"text": "親愛的人資部門，\n\n我是張小華，想要應徵貴公司的軟體工程師職位。您可以透過我的手機0912345678或是Email test@example.com聯繫我。目前居住在台北市信義區松仁路100號。\n\n期待能收到面試通知。"}
            
        return {"text": generated_text}
                
    except Exception as e:
        print(f"Error in generate_random_text: {str(e)}")
        return {"text": "親愛的人資部門，\n\n我是張小華，想要應徵貴公司的軟體工程師職位。您可以透過我的手機0912345678或是Email test@example.com聯繫我。目前居住在台北市信義區松仁路100號。\n\n期待能收到面試通知。"}

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
    return jsonify({'result': result})

@app.route('/api/generate', methods=['GET'])
def generate_text():
    result = generate_random_text()
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
