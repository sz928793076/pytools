// 全局变量
let conversationHistory = [
    { "role": "system", "content": "你是阶跃星辰（StepFun）提供的AI聊天助手。你擅长中文、英文等多种语言。" }
];
let isGenerating = false;
let abortController = null;
let currentChatId = null;

// DOM元素
const messagesContainer = document.getElementById('messagesContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const charCount = document.getElementById('charCount');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const modelSelect = document.getElementById('modelSelect');
const maxTokensInput = document.getElementById('maxTokens');
const historyList = document.getElementById('historyList');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 配置 Marked
    const renderer = new marked.Renderer();

    // 自定义代码块渲染，增加复制按钮
    renderer.code = function (code, lang) {
        const highlighted = lang && hljs.getLanguage(lang)
            ? hljs.highlight(code, { language: lang }).value
            : hljs.highlightAuto(code).value;

        // 对代码内容进行转义，以处理引号等特殊字符
        const escapedCode = code.replace(/`/g, '\\`').replace(/\$/g, '\\$');

        return `
            <div style="position: relative;">
                <button class="copy-btn" onclick="copyToClipboard(\`${escapedCode}\`, this)">
                    <i class="fas fa-copy"></i> 复制
                </button>
                <pre><code class="hljs ${lang || ''}">${highlighted}</code></pre>
            </div>
        `;
    };

    marked.setOptions({
        renderer: renderer,
        breaks: true,
        gfm: true
    });

    // 检查API连接状态
    checkHealth();

    // 加载历史记录列表
    loadHistoryList();

    // 输入框事件
    userInput.addEventListener('input', updateCharCount);
    userInput.addEventListener('keydown', handleKeyPress);

    // 设置变更事件
    modelSelect.addEventListener('change', () => {
        showStatus('模型已更改', 'success');
    });

    maxTokensInput.addEventListener('change', () => {
        const value = parseInt(maxTokensInput.value);
        if (value < 100 || value > 4000) {
            maxTokensInput.value = 1000;
            showStatus('Token值必须在100-4000之间', 'warning');
        }
    });
});

// 更新字符计数
function updateCharCount() {
    const count = userInput.value.length;
    charCount.textContent = count;
    sendBtn.disabled = count === 0 || isGenerating;
}

// 处理按键事件
function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// 发送消息
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isGenerating) return;

    // 检查退出命令
    if (['exit', 'quit', '退出', 'q'].includes(message.toLowerCase())) {
        addMessage('user', message);
        showStatus('对话已结束', 'success');
        userInput.value = '';
        updateCharCount();
        return;
    }

    // 1. 先添加用户消息到界面
    addMessage('user', message);
    conversationHistory.push({ "role": "user", "content": message });

    // 清空输入框
    userInput.value = '';
    updateCharCount();

    // 2. 设置生成状态
    isGenerating = true;
    sendBtn.disabled = true;
    showStatus('正在生成回复...', 'normal');

    // 3. 变量用于跟踪助手消息
    let assistantMessageId = null;
    let contentElement = null;
    let fullResponse = '';
    let isFirstChunk = true;

    // 3.5 显示加载动画
    const loadingId = showLoadingIndicator();

    try {
        // 取消之前的请求（如果有）
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: modelSelect.value,
                messages: conversationHistory,
                stream: true,
                max_tokens: parseInt(maxTokensInput.value)
            }),
            signal: abortController.signal
        });

        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        // 4. 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        const content = parsed.choices[0]?.delta?.content || '';

                        if (content) {
                            // 5. 第一次收到内容时，隐藏加载动画并创建助手消息
                            if (isFirstChunk) {
                                hideLoadingIndicator(loadingId);
                                // 创建助手消息（初始为空）
                                assistantMessageId = addMessage('assistant', '');
                                const assistantMessageElement = document.getElementById(assistantMessageId);
                                contentElement = assistantMessageElement.querySelector('.message-content');
                                isFirstChunk = false;
                            }

                            // 6. 追加内容到助手消息
                            fullResponse += content;
                            if (contentElement) {
                                contentElement.innerHTML = formatMessage(fullResponse);
                                scrollToBottom();
                            }
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e);
                    }
                }
            }
        }

        // 7. 如果一直没有收到内容（某些模型可能返回空），显示提示
        if (isFirstChunk) {
            hideLoadingIndicator(loadingId);
            // 此时才创建消息，显示无内容
            assistantMessageId = addMessage('assistant', '<em>（无回复内容）</em>');
        }

        // 8. 将完整回复添加到历史
        conversationHistory.push({ "role": "assistant", "content": fullResponse });

        // 9. 保存当前对话到服务器
        saveCurrentChat();

        showStatus('就绪', 'success');

    } catch (error) {
        console.error('发送消息失败:', error);
        hideLoadingIndicator(loadingId);

        // 如果出错时还没有创建助手消息，则创建一个错误消息
        if (isFirstChunk) {
            addMessage('assistant', `<div class="error-message">请求失败: ${error.message}</div>`);
        } else if (contentElement) {
            // 如果已经创建了消息，则追加错误信息
            contentElement.innerHTML += `<br><div class="error-message">请求失败: ${error.message}</div>`;
        }

        showStatus('请求失败', 'error');
    } finally {
        isGenerating = false;
        sendBtn.disabled = false;
        abortController = null;
    }
}

// 显示加载指示器
function showLoadingIndicator() {
    const loadingId = 'loading-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message assistant-message loading-message`;
    messageDiv.id = loadingId;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = '<i class="fas fa-robot"></i>';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    messagesContainer.appendChild(messageDiv);

    scrollToBottom();
    return loadingId;
}

// 隐藏加载指示器
function hideLoadingIndicator(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

// 添加消息到界面
function addMessage(role, content) {
    const messageId = 'msg-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    messageDiv.id = messageId;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = role === 'user' ?
        '<i class="fas fa-user"></i>' :
        '<i class="fas fa-robot"></i>';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = formatMessage(content);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    messagesContainer.appendChild(messageDiv);

    scrollToBottom();
    return messageId;
}

// 格式化消息内容（使用 Marked 处理 Markdown）
function formatMessage(content) {
    if (!content) return '';
    try {
        return marked.parse(content);
    } catch (e) {
        console.error('Markdown 解析失败:', e);
        return content;
    }
}

// 复制内容到剪贴板
async function copyToClipboard(text, btn) {
    try {
        await navigator.clipboard.writeText(text);
        const icon = btn.querySelector('i');
        icon.className = 'fas fa-check';
        setTimeout(() => {
            icon.className = 'fas fa-copy';
        }, 2000);
    } catch (err) {
        console.error('复制失败:', err);
    }
}

// 滚动到底部
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 清空对话
function clearChat() {
    if (isGenerating) {
        if (abortController) {
            abortController.abort();
        }
        isGenerating = false;
    }

    currentChatId = null;
    conversationHistory = [
        { "role": "system", "content": "你是阶跃星辰（StepFun）提供的AI聊天助手。你擅长中文、英文等多种语言。" }
    ];

    // 更新侧边栏选中状态
    updateHistoryActiveStatus();

    messagesContainer.innerHTML = `
        <div class="message assistant-message">
            <div class="avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <p>你好！我是阶跃星辰（StepFun）提供的AI助手。我可以帮助你进行各种对话和推理任务。</p>
                <p class="hint">输入 "exit"、"quit" 或 "退出" 结束对话</p>
            </div>
        </div>
    `;

    showStatus('对话已清空', 'success');
}

// 导出对话
function exportChat() {
    let text = 'StepFun AI 对话记录\n';
    text += '='.repeat(50) + '\n\n';

    conversationHistory.forEach(msg => {
        const role = msg.role === 'user' ? '用户' :
            msg.role === 'assistant' ? '助手' : '系统';
        text += `${role}：\n${msg.content}\n\n`;
    });

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stepfun-chat-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

// 更新状态指示器
function showStatus(text, type = 'normal') {
    statusText.textContent = text;

    statusIndicator.className = 'status-indicator';
    switch (type) {
        case 'success':
            statusIndicator.style.background = 'var(--success-color)';
            break;
        case 'error':
            statusIndicator.style.background = 'var(--error-color)';
            break;
        case 'warning':
            statusIndicator.style.background = 'var(--warning-color)';
            break;
        default:
            statusIndicator.style.background = 'var(--success-color)';
    }
}

// --- 历史记录功能 ---

// 加载历史列表
async function loadHistoryList() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) throw new Error('无法加载历史记录');

        const history = await response.json();
        renderHistoryList(history);
    } catch (error) {
        console.error('加载历史列表失败:', error);
        historyList.innerHTML = '<div class="loading-history">加载失败</div>';
    }
}

// 渲染历史列表
function renderHistoryList(history) {
    if (history.length === 0) {
        historyList.innerHTML = '<div class="loading-history">暂无对话记录</div>';
        return;
    }

    historyList.innerHTML = '';
    history.forEach(item => {
        const div = document.createElement('div');
        div.className = `history-item ${item.id === currentChatId ? 'active' : ''}`;
        div.dataset.id = item.id;
        div.onclick = () => selectChat(item.id);

        div.innerHTML = `
            <div class="history-item-title" title="${item.title}">${item.title}</div>
            <div class="delete-history-btn" onclick="event.stopPropagation(); deleteChat('${item.id}')">
                <i class="fas fa-trash-alt"></i>
            </div>
        `;
        historyList.appendChild(div);
    });
}

// 选择特定对话
async function selectChat(id) {
    if (isGenerating) return;
    if (id === currentChatId) return;

    try {
        showStatus('正在加载对话...', 'normal');
        const response = await fetch(`/api/history/${id}`);
        if (!response.ok) throw new Error('对话加载失败');

        const chatData = await response.json();

        // 更新全局状态
        currentChatId = chatData.id;
        conversationHistory = chatData.messages;
        if (chatData.model) modelSelect.value = chatData.model;

        // 重新渲染消息列表
        renderMessagesFromHistory();

        // 更新侧边栏状态
        updateHistoryActiveStatus();

        showStatus('对话已加载', 'success');
    } catch (error) {
        console.error('加载对话详情失败:', error);
        showStatus('加载对话失败', 'error');
    }
}

// 从历史记录重新渲染所有消息
function renderMessagesFromHistory() {
    messagesContainer.innerHTML = '';

    // 只显示用户和助手的消息
    conversationHistory.forEach(msg => {
        if (msg.role !== 'system') {
            addMessage(msg.role, msg.content);
        }
    });

    if (messagesContainer.innerHTML === '') {
        // 如果没有消息（只有系统提示词），显示欢迎语
        clearChat();
    }
}

// 更新侧边栏选中效果
function updateHistoryActiveStatus() {
    const items = historyList.querySelectorAll('.history-item');
    items.forEach(item => {
        item.classList.toggle('active', item.dataset.id === currentChatId);
    });
}

// 保存当前对话
async function saveCurrentChat() {
    try {
        const response = await fetch('/api/history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: currentChatId,
                messages: conversationHistory,
                model: modelSelect.value
            })
        });

        if (response.ok) {
            const result = await response.json();
            const isNew = !currentChatId;
            currentChatId = result.id;

            // 如果是新对话，重新拉取列表以显示新标题
            if (isNew) {
                loadHistoryList();
            }
        }
    } catch (error) {
        console.error('保存对话失败:', error);
    }
}

// 删除对话
async function deleteChat(id) {
    if (!confirm('确定要删除这条对话记录吗？')) return;

    try {
        const response = await fetch(`/api/history/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            if (id === currentChatId) {
                clearChat();
            }
            loadHistoryList();
            showStatus('已删除', 'success');
        }
    } catch (error) {
        console.error('删除对话失败:', error);
        showStatus('删除失败', 'error');
    }
}

// 检查健康状态
async function checkHealth() {
    try {
        const response = await fetch('/health');
        if (response.ok) {
            showStatus('已连接到服务器', 'success');
        } else {
            showStatus('服务器连接失败', 'error');
        }
    } catch (error) {
        showStatus('无法连接到服务器', 'error');
    }
}