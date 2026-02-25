import sys
import os
import time
import json
import threading
import webbrowser
import pyautogui
import pyperclip
import ctypes
import tkinter as tk
from tkinter import filedialog
from flask import Flask, request, jsonify, render_template_string

# --------------------------
# 环境初始化
# --------------------------
CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# 解决 Windows DPI 缩放
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass


# --------------------------
# RPA 执行引擎
# --------------------------
class RPAFlowEngine:
    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.loop_mode = False
        self.logs = []
        self.CMD_MAP = {
            "左键单击": 1.0, "左键双击": 2.0, "右键单击": 3.0,
            "输入文本": 4.0, "等待(秒)": 5.0, "滚轮滑动": 6.0,
            "系统按键": 7.0, "鼠标悬停": 8.0, "截图保存": 9.0
        }

    def add_log(self, msg):
        t = time.strftime("%H:%M:%S", time.localtime())
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 100: self.logs.pop(0)

    def run(self, graph_data, loop):
        self.is_running = True
        self.should_stop = False
        self.loop_mode = loop
        nodes = {str(n['id']): n for n in graph_data['nodes']}
        links = {str(l[0]): l for l in graph_data['links']}

        try:
            while self.is_running:
                current_node = next((n for n in nodes.values() if n['type'] == "开始"), None)
                if not current_node:
                    self.add_log("错误: 未找到[开始]节点")
                    break

                while current_node and not self.should_stop:
                    node_id = str(current_node['id'])
                    props = current_node.get('properties', {})
                    desc = props.get('desc', '未命名步骤')
                    retry = int(props.get('retry', 1))
                    delay = float(props.get('delay', 0.5))

                    self.add_log(f"执行: {desc}")
                    next_slot = 0

                    if current_node['type'] == "执行动作":
                        act_name = props.get('type')
                        act_val = props.get('value', '')
                        code = self.CMD_MAP.get(act_name, 0)
                        success = False
                        for i in range(retry):
                            if self.should_stop: break
                            success = self.execute_cmd(code, act_val)
                            if success: break
                            time.sleep(0.5)

                    elif current_node['type'] == "分支判断":
                        img_path = props.get('image', '')
                        found = False
                        for _ in range(retry):
                            if self.should_stop: break
                            try:
                                found = pyautogui.locateOnScreen(img_path, confidence=0.8) is not None
                            except:
                                found = False
                            if found: break
                            time.sleep(0.5)
                        next_slot = 0 if found else 1

                    if delay > 0: time.sleep(delay)

                    next_node_id = None
                    for l in links.values():
                        if str(l[1]) == str(node_id) and int(l[2]) == next_slot:
                            next_node_id = l[3];
                            break
                    current_node = nodes.get(str(next_node_id)) if next_node_id else None

                if not self.loop_mode or self.should_stop: break
                self.add_log("--- 循环开始 ---")
                time.sleep(0.1)
        finally:
            self.is_running = False
            self.add_log("任务结束。")

    def execute_cmd(self, code, val):
        try:
            if code in [1.0, 2.0, 3.0, 8.0]:  # 涉及图像查找
                loc = pyautogui.locateCenterOnScreen(val, confidence=0.8)
                if not loc: return False
                if code == 1.0:
                    pyautogui.click(loc)
                elif code == 2.0:
                    pyautogui.doubleClick(loc)
                elif code == 3.0:
                    pyautogui.rightClick(loc)
                elif code == 8.0:
                    pyautogui.moveTo(loc)
            elif code == 4.0:
                pyperclip.copy(str(val));
                pyautogui.hotkey('ctrl', 'v')
            elif code == 7.0:
                pyautogui.press(str(val).lower())
            elif code == 5.0:
                time.sleep(float(val))
            elif code == 6.0:
                pyautogui.scroll(int(val))
            elif code == 9.0:
                pyautogui.screenshot(val)
            return True
        except:
            return False


engine = RPAFlowEngine()
app = Flask(__name__)


# --------------------------
# API 路由
# --------------------------
@app.route('/')
def index(): return render_template_string(HTML_UI)


@app.route('/api/configs')
def list_configs(): return jsonify(sorted([f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]))


@app.route('/api/config/<name>', methods=['GET', 'POST', 'DELETE'])
def config_manager(name):
    path = os.path.join(CONFIG_DIR, name if name.endswith('.json') else name + '.json')
    if request.method == 'GET':
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    elif request.method == 'POST':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(request.json, f, indent=4, ensure_ascii=False)
        return jsonify({"status": "ok"})
    elif request.method == 'DELETE':
        os.remove(path);
        return jsonify({"status": "ok"})


@app.route('/api/run', methods=['POST'])
def run_flow():
    data = request.json
    threading.Thread(target=engine.run, args=(data['graph'], data.get('loop', False))).start()
    return jsonify({"status": "ok"})


@app.route('/api/stop', methods=['POST'])
def stop_flow(): engine.should_stop = True; return jsonify({"status": "ok"})


@app.route('/api/logs')
def get_logs(): return jsonify(engine.logs)


# 核心功能：调用 Python 原生对话框选择文件/目录
@app.route('/api/browse')
def browse():
    mode = request.args.get('mode', 'file')
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # 确保对话框在最前面
    if mode == 'dir':
        res = filedialog.askdirectory()
    else:
        res = filedialog.askopenfilename(filetypes=[("图像/所有文件", "*.png;*.jpg;*.jpeg;*.bmp;*.*")])
    root.destroy()
    return jsonify({"path": res})


# --------------------------
# 前端 UI
# --------------------------
HTML_UI = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>可视化 RPA 编辑器</title>
    <link rel="stylesheet" type="text/css" href="https://tamats.com/projects/litegraph/css/litegraph.css">
    <script type="text/javascript" src="https://tamats.com/projects/litegraph/build/litegraph.js"></script>
    <style>
        body { margin: 0; background: #1a1a1a; color: #eee; font-family: "Microsoft YaHei", sans-serif; display: flex; height: 100vh; overflow: hidden; }
        #sidebar { width: 240px; background: #252525; border-right: 1px solid #333; display: flex; flex-direction: column; padding: 10px; }
        .config-item { padding: 8px; margin: 4px 0; background: #333; cursor: pointer; border-radius: 4px; display: flex; justify-content: space-between; font-size: 13px; }
        .config-item.active { border-left: 4px solid #3498db; background: #3d3d3d; }
        #main { flex: 1; display: flex; flex-direction: column; }
        #toolbar { height: 50px; background: #2d2d2d; display: flex; align-items: center; padding: 0 15px; gap: 10px; border-bottom: 1px solid #3d3d3d; }
        #log-panel { height: 120px; background: #111; border-top: 2px solid #333; padding: 10px; overflow-y: auto; font-family: Consolas; font-size: 12px; color: #2ecc71; }
        button { background: #444; color: white; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 12px;}
        button:hover { background: #555; }
        input { background: #333; border: 1px solid #555; color: white; padding: 5px; border-radius: 3px; }
        .btn-green { background: #27ae60 !important; }
        .btn-red { background: #c0392b !important; }
        .btn-blue { background: #2980b9 !important; }
    </style>
</head>
<body>

<div id="sidebar">
    <h3 style="font-size:14px; margin:5px 0;">📂 本地配置库</h3>
    <div id="config-list" style="flex:1; overflow-y:auto;"></div>
    <div style="margin-top:10px; display:flex; flex-direction:column; gap:5px;">
        <input type="text" id="new-name" placeholder="输入配置名称">
        <button class="btn-blue" onclick="saveConfig()">💾 保存当前可视化配置</button>
        <button style="background:#8e44ad" onclick="importOldConfig()">📥 导入旧版线性配置</button>
    </div>
</div>

<div id="main">
    <div id="toolbar">
        <button class="btn-green" onclick="runFlow(false)">▶ 执行一次</button>
        <button class="btn-green" onclick="runFlow(true)">🔁 循环执行</button>
        <button class="btn-red" onclick="stopFlow()">⏹ 停止运行</button>
        <span id="status-text" style="margin-left:20px; font-size:12px; color:#888;">右键画布添加节点</span>
    </div>
    <div style="flex:1; position:relative;">
        <canvas id="main-canvas" style="width:100%; height:100%;"></canvas>
    </div>
    <div id="log-panel">日志就绪...</div>
</div>

<script>
    // --- 彻底汉化右键菜单 ---
    LGraphCanvas.prototype.getCanvasMenuOptions = function() {
        return [
            { content: "添加节点", has_submenu: true, callback: this.processContextMenu.bind(this) },
            { content: "添加分组", callback: () => this.graph.addGroup() },
            { content: "清除画布", callback: () => { if(confirm("确定清空？")) this.graph.clear(); } }
        ];
    };

    LiteGraph.clearRegisteredTypes();

    // 通用的文件浏览函数
    function browsePath(node, mode, propertyKey, widgetIndex) {
        fetch('/api/browse?mode=' + mode)
            .then(res => res.json())
            .then(data => {
                if(data.path) {
                    node.properties[propertyKey] = data.path;
                    if(node.widgets[widgetIndex]) node.widgets[widgetIndex].value = data.path;
                }
            });
    }

    // --- 注册节点 ---
    function StartNode() { this.addOutput("流程起点", "path"); this.size = [120, 40]; }
    StartNode.title = "开始";
    LiteGraph.registerNodeType("开始", StartNode);

    function ActionNode() {
        this.addInput("入", "path");
        this.addOutput("出", "path");
        this.properties = { desc: "新动作", type: "左键单击", value: "", retry: 1, delay: 0.5 };
        this.addWidget("text", "步骤说明", "新动作", (v)=>this.properties.desc=v);
        this.addWidget("combo", "指令类型", "左键单击", (v)=>this.properties.type=v, { values: ["左键单击", "左键双击", "右键单击", "输入文本", "等待(秒)", "滚轮滑动", "系统按键", "鼠标悬停", "截图保存"] });
        this.addWidget("text", "内容/参数/路径", "", (v)=>this.properties.value=v);

        // 核心：添加【选择文件】按钮
        this.addWidget("button", "📁 选择文件/保存路径", "", () => {
            let mode = (this.properties.type === "截图保存") ? "dir" : "file";
            browsePath(this, mode, "value", 2);
        });

        this.addWidget("number", "重试次数", 1, (v)=>this.properties.retry=v, {precision:0});
        this.addWidget("number", "间隔(秒)", 0.5, (v)=>this.properties.delay=v);
        this.size = [280, 190];
    }
    ActionNode.title = "执行动作";
    LiteGraph.registerNodeType("执行动作", ActionNode);

    function ConditionNode() {
        this.addInput("入", "path");
        this.addOutput("成功(找到)", "path");
        this.addOutput("失败(没找到)", "path");
        this.properties = { desc: "找图分支", image: "", retry: 1, delay: 0.5 };
        this.addWidget("text", "步骤说明", "找图分支", (v)=>this.properties.desc=v);
        this.addWidget("text", "图片路径", "", (v)=>this.properties.image=v);

        // 核心：添加【选择图片】按钮
        this.addWidget("button", "📁 选择参考图片", "", () => {
            browsePath(this, "file", "image", 1);
        });

        this.addWidget("number", "检测重试", 1, (v)=>this.properties.retry=v);
        this.size = [280, 160];
    }
    ConditionNode.title = "分支判断";
    LiteGraph.registerNodeType("分支判断", ConditionNode);

    var graph = new LGraph();
    var canvas = new LGraphCanvas("#main-canvas", graph);

    // --- 逻辑函数 ---
    function loadList() {
        fetch('/api/configs').then(res=>res.json()).then(data=>{
            const list = document.getElementById('config-list');
            list.innerHTML = "";
            data.forEach(name=>{
                const item = document.createElement('div');
                item.className = 'config-item';
                item.innerHTML = `<span>${name}</span><span style="color:#e74c3c" onclick="delConfig('${name}',event)">×</span>`;
                item.onclick = ()=> {
                    fetch('/api/config/'+name).then(res=>res.json()).then(g=>{
                        graph.configure(g);
                        document.getElementById('new-name').value = name.replace('.json','');
                    });
                };
                list.appendChild(item);
            });
        });
    }

    function saveConfig() {
        let name = document.getElementById('new-name').value;
        if(!name) return alert("请输入配置名");
        fetch('/api/config/'+name, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(graph.serialize()) }).then(()=>loadList());
    }

    function delConfig(name,e) {
        e.stopPropagation();
        if(confirm("确定删除？")) fetch('/api/config/'+name, {method:'DELETE'}).then(()=>loadList());
    }

    function importOldConfig() {
        const input = document.createElement('input');
        input.type = 'file';
        input.onchange = e => {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = event => {
                const oldList = JSON.parse(event.target.result);
                graph.clear();
                let prevNode = LiteGraph.createNode("开始");
                prevNode.pos = [50, 200];
                graph.add(prevNode);
                const REV_MAP = {1.0:"左键单击", 2.0:"左键双击", 3.0:"右键单击", 4.0:"输入文本", 5.0:"等待(秒)", 6.0:"滚轮滑动", 7.0:"系统按键", 8.0:"鼠标悬停", 9.0:"截图保存"};
                oldList.forEach((item, index) => {
                    let node = LiteGraph.createNode("执行动作");
                    node.pos = [300 + index * 320, 150];
                    node.properties = { desc: item.desc, type: REV_MAP[item.type] || "左键单击", value: item.value, retry: item.retry, delay: item.delay };
                    node.widgets[0].value = node.properties.desc;
                    node.widgets[1].value = node.properties.type;
                    node.widgets[2].value = node.properties.value;
                    node.widgets[4].value = node.properties.retry;
                    node.widgets[5].value = node.properties.delay;
                    graph.add(node);
                    prevNode.connect(0, node, 0);
                    prevNode = node;
                });
            };
            reader.readAsText(file);
        };
        input.click();
    }

    function runFlow(loop) {
        fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({graph:graph.serialize(), loop:loop}) });
    }
    function stopFlow() { fetch('/api/stop', {method:'POST'}); }

    setInterval(() => {
        fetch('/api/logs').then(res=>res.json()).then(logs=>{
            const panel = document.getElementById('log-panel');
            panel.innerHTML = logs.join('<br>');
            panel.scrollTop = panel.scrollHeight;
        });
    }, 1000);

    loadList();
    window.onresize = () => canvas.resize();
    canvas.resize();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host='127.0.0.1', port=5000, debug=False)