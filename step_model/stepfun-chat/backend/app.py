from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import os
import json
import uuid
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

# 设置静态文件夹路径（指向frontend目录）
static_folder = Path(__file__).parent.parent / 'frontend'
app = Flask(__name__,
            static_folder=str(static_folder),
            static_url_path='')

# 启用CORS（允许跨域请求）
CORS(app)

# 配置从环境变量读取
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SITE_URL = os.getenv("SITE_URL", "https://your-site.com")
APP_NAME = os.getenv("APP_NAME", "StepFun AI Chat")

# 验证必要的环境变量
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY 环境变量未设置！请编辑 .env 文件。")

# 历史记录存储路径
HISTORY_DIR = Path(__file__).parent / 'data'
if not HISTORY_DIR.exists():
    HISTORY_DIR.mkdir(parents=True)

def get_chat_path(chat_id):
    return HISTORY_DIR / f"{chat_id}.json"


@app.route('/')
def index():
    """返回前端主页面"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """提供静态文件（CSS、JS、图片等）"""
    return send_from_directory(app.static_folder, path)


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    代理聊天请求到OpenRouter API
    支持流式响应（SSE）
    """
    try:
        data = request.json

        # 验证请求数据
        if not data or 'messages' not in data:
            return jsonify({"error": "请求格式错误：缺少messages字段"}), 400

        # 构建发送到OpenRouter的请求头
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
            "Content-Type": "application/json"
        }

        # 构建请求体
        web_search = data.get("web_search", False)
        messages = data["messages"]

        payload = {
            "model": data.get("model", "stepfun/step-3.5-flash:free"),
            "messages": messages,
            "stream": data.get("stream", True),
            "max_tokens": data.get("max_tokens", 4000),
            "temperature": data.get("temperature", 0.7),
        }

        # 如果开启了联网搜索，添加 OpenRouter 插件参数
        if web_search:
            # 这里的参数名根据用户提供的线索调整，通常是 plugins
            payload["plugins"] = [{"id": "web"}]
            # 也有些版本支持直接在 payload 根部设置 web_search
            # payload["web_search"] = True 

        # 转发请求到OpenRouter
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=60
        )

        # 检查OpenRouter响应状态
        if response.status_code != 200:
            error_msg = f"OpenRouter API错误: {response.status_code}"
            try:
                error_details = response.json()
                error_msg += f" - {error_details.get('error', {}).get('message', '')}"
            except:
                error_msg += f" - {response.text[:200]}"
            return jsonify({"error": error_msg}), response.status_code

        # 流式响应返回给前端（SSE格式）
        def generate():
            try:
                for line in response.iter_lines():
                    if line:
                        # 直接转发OpenRouter的SSE数据
                        yield f"{line.decode('utf-8')}\n\n"
            except Exception as e:
                app.logger.error(f"流式传输错误: {e}")
                yield f"data: [ERROR] {str(e)}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except requests.exceptions.Timeout:
        return jsonify({"error": "请求超时，请稍后重试"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "无法连接到OpenRouter服务"}), 503
    except Exception as e:
        app.logger.error(f"聊天接口错误: {e}")
        return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500


@app.route('/api/models', methods=['GET'])
def get_models():
    """获取OpenRouter可用模型列表"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }

        response = requests.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"error": f"获取模型列表失败: {response.status_code}"}), response.status_code

        return jsonify(response.json())

    except Exception as e:
        app.logger.error(f"获取模型列表错误: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "StepFun Chat Proxy",
        "version": "1.0.0"
    })


@app.route('/api/usage', methods=['GET'])
def get_usage():
    """获取API使用情况（需要OpenRouter账户有相应权限）"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }

        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"error": "无法获取使用情况"}), response.status_code

        return jsonify(response.json())

    except Exception as e:
        app.logger.error(f"获取使用情况错误: {e}")
        return jsonify({"error": str(e)}), 500


# --- 历史记录接口 ---

@app.route('/api/history', methods=['GET'])
def list_history():
    """获取所有历史对话列表"""
    history = []
    try:
        for file in HISTORY_DIR.glob('*.json'):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                history.append({
                    "id": data.get("id"),
                    "title": data.get("title", "未命名对话"),
                    "updated_at": data.get("updated_at", 0),
                    "model": data.get("model")
                })
        
        # 按更新时间倒序排序
        history.sort(key=lambda x: x['updated_at'], reverse=True)
        return jsonify(history)
    except Exception as e:
        app.logger.error(f"列表拉取历史错误: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<chat_id>', methods=['GET'])
def get_history_detail(chat_id):
    """获取特定对话详情"""
    path = get_chat_path(chat_id)
    if not path.exists():
        return jsonify({"error": "对话不存在"}), 404
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        app.logger.error(f"读取历史错误: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['POST'])
def save_history():
    """保存或更新对话"""
    try:
        data = request.json
        chat_id = data.get('id') or str(uuid.uuid4())
        
        # 提取标题（如果没有标题，用第一条消息内容）
        title = data.get('title')
        if not title and data.get('messages'):
            # 找第一条非system消息
            for msg in data['messages']:
                if msg['role'] == 'user':
                    title = msg['content'][:30] + ( '...' if len(msg['content']) > 30 else '')
                    break
        
        if not title:
            title = "新对话"

        chat_data = {
            "id": chat_id,
            "title": title,
            "messages": data.get('messages', []),
            "model": data.get('model'),
            "updated_at": int(time.time())
        }
        
        with open(get_chat_path(chat_id), 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
            
        return jsonify(chat_data)
    except Exception as e:
        app.logger.error(f"保存历史错误: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<chat_id>', methods=['DELETE'])
def delete_history(chat_id):
    """删除对话"""
    path = get_chat_path(chat_id)
    if path.exists():
        try:
            os.remove(path)
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "对话不存在"}), 404


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "资源不存在"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "方法不允许"}), 405


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


if __name__ == '__main__':
    # 生产环境建议使用以下配置：
    # app.run(host='0.0.0.0', port=5000, debug=False)

    # 开发环境配置
    print("=" * 60)
    print("StepFun AI Chat Backend")
    print("=" * 60)
    print(f"Static folder: {static_folder}")
    print(f"API Address: http://localhost:5000/api/chat")
    print(f"Frontend Address: http://localhost:5000")
    print(f"Health Check: http://localhost:5000/health")
    print("=" * 60)
    print("Please make sure you have configured the API key in backend/.env")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)