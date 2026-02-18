# L2DClaw — Claude Code 开发 Prompt v2

## 项目背景与目标

你正在帮我构建一个名为 **L2DClaw** 的 Live2D 桌宠项目。

- **GitHub 仓库**：https://github.com/YiniRuohong/L2DClaw
- **核心目标**：本地运行的 Live2D 桌宠，感知桌面状态和语音输入，通过云端 OpenClaw（OpenAI 兼容 API）决策后驱动 Live2D 表情动作 + 本地 Qwen3 TTS 语音输出。
- **原则**：尽量少造轮子，优先复用成熟开源项目。
- **平台支持**：Windows 10/11 + macOS 12+，代码中所有平台相关逻辑必须双平台实现。

---

## 架构总览

```
┌──────────────────────────────────────────────────────┐
│                  首次启动向导                          │
│  用户许可协议 → 选择功能 → 下载本地 TTS 模型           │
└──────────────────────┬───────────────────────────────┘
                       │ 完成后进入主程序
                       ▼
┌──────────────────────────────────────────────────────┐
│                  本地 Adapter 层                      │
│                                                      │
│  AdapterBase (抽象基类)                               │
│  ├── ScreenAdapter      # 窗口信息 + 画面内容识别     │
│  ├── VoiceAdapter       # VAD + Whisper ASR          │
│  ├── KeyboardAdapter    # 打字活跃度感知 (可选)        │
│  └── [HardwareAdapter]  # 预留接口，未来接入硬件设备  │
└──────────────────────┬───────────────────────────────┘
                       │ 结构化 context
                       ▼
┌──────────────────────────────────────────────────────┐
│           OpenClaw 云端大脑（OpenAI 兼容）             │
│  输入: {context, user_text}                           │
│  输出: {text, emotion, motion}                        │
└──────────┬───────────────────────────────────────────┘
           │
     ┌─────┴──────────────┐
     ▼                    ▼
┌──────────────┐  ┌───────────────────────┐
│ Live2D 驱动  │  │  本地 Qwen3 TTS 引擎  │
│ (Open-LLM-   │  │  (模型本地运行，      │
│  VTuber 前端)│  │   首次启动时下载)     │
└──────────────┘  └───────────────────────┘
```

---

## 目录结构

```
L2DClaw/
├── README.md
├── conf.yaml                            # 主配置文件
├── .env.example                         # 环境变量模板
├── requirements.txt
├── main.py                              # 启动入口（检测首次运行 → 向导 or 主程序）
│
├── setup/                               # 首次启动向导
│   ├── __init__.py
│   ├── wizard.py                        # 向导主逻辑（CLI 交互式）
│   ├── license.txt                      # 用户许可协议文本
│   └── model_downloader.py              # 下载本地 TTS 模型
│
├── adapter/                             # 感知采集层（可扩展接口设计）
│   ├── __init__.py
│   ├── base.py                          # AdapterBase 抽象基类
│   ├── adapter_manager.py               # 统一管理所有 Adapter
│   ├── screen/
│   │   ├── __init__.py
│   │   ├── screen_adapter.py            # 继承 AdapterBase
│   │   ├── window_watcher.py            # 窗口标题/进程（Win + macOS）
│   │   └── content_recognizer.py        # 画面内容识别（截图 + VLM）
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── voice_adapter.py             # 继承 AdapterBase
│   │   ├── vad.py                       # 语音活动检测
│   │   └── asr.py                       # Whisper 语音识别
│   ├── keyboard/
│   │   ├── __init__.py
│   │   └── keyboard_adapter.py          # 继承 AdapterBase，感知打字活跃度
│   └── hardware/
│       ├── __init__.py
│       └── hardware_adapter_base.py     # 预留硬件设备接口（空实现 + 文档）
│
├── brain/
│   ├── __init__.py
│   ├── openclaw_client.py
│   └── response_parser.py
│
├── live2d_driver/
│   ├── frontend/                        # Fork 自 Open-LLM-VTuber 前端
│   └── driver_server.py
│
├── tts/
│   ├── __init__.py
│   ├── base.py                          # TTSBase 抽象基类（预留扩展）
│   ├── local_qwen3_tts.py               # 本地 Qwen3 TTS（首选）
│   └── dashscope_tts.py                 # DashScope 云端备用（网络不好时降级）
│
└── docs/
    ├── upstream_analysis.md
    ├── adapter_extension_guide.md       # 如何新增自定义 Adapter（硬件接入指南）
    └── architecture.md
```

---

## Step 0：分析上游项目

Clone Open-LLM-VTuber 到临时目录并分析：

```bash
git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber.git _upstream_reference --depth=1
```

分析以下内容，写入 `docs/upstream_analysis.md`：

1. **LLM 接入方式**：`conf.yaml` 中如何配置 OpenAI-compatible endpoint
2. **WebSocket 协议**：前端 Live2D 通过 WebSocket 接收什么格式的 JSON 指令
3. **TTS 接口抽象**：TTS 模块的基类在哪里，如何新增 provider
4. **屏幕感知实现**：Screen Sense 功能代码位置和触发方式
5. **桌宠模式实现**：透明+置顶+穿透在哪里配置（Electron/Tauri 配置项）

---

## Step 1：首次启动向导

`main.py` 启动时先检测是否首次运行（通过 `~/.l2dclaw/initialized` 标志文件判断）。
若是首次运行，进入向导流程。

### setup/wizard.py — CLI 交互式向导

```
======================================
  欢迎使用 L2DClaw 桌宠 🐾
======================================

【用户许可协议】
（展示 license.txt 内容，分页滚动）

你是否同意以上许可协议？[y/N] > y

【功能配置】
以下是可选功能，请根据需求开启：

[1] 屏幕画面内容识别（截图分析）  默认: 关闭
    ⚠ 截图将发送给 OpenClaw 云端，请确认你接受此隐私风险
    开启? [y/N] > 

[2] 键盘活跃度感知（只统计频率，不记录内容）  默认: 开启
    开启? [Y/n] > 

[3] 麦克风语音识别  默认: 开启
    开启? [Y/n] > 

【TTS 语音合成模型】
L2DClaw 使用本地 Qwen3 TTS 模型进行语音合成（无需联网）。
模型大小约 1.2GB，将下载到 ~/.l2dclaw/models/qwen3-tts/

开始下载？[Y/n] > y

正在下载 Qwen3 TTS 模型...
[████████████████████░░░░] 87% 1.04GB/1.2GB 2.3MB/s

✅ 下载完成！
✅ 初始化完成，L2DClaw 即将启动...
```

**实现要求**：
- 使用 `rich` 库渲染进度条和样式（`rich.progress`、`rich.console`）
- 用户同意许可后才能继续（强制 `y` 确认）
- 截图功能需额外显示隐私提示，且需要二次确认
- 配置结果写入 `~/.l2dclaw/user_prefs.yaml`
- 标志文件 `~/.l2dclaw/initialized` 写入，之后启动跳过向导

### setup/model_downloader.py — 本地 TTS 模型下载

**Qwen3 TTS 本地模型**来自 HuggingFace：`Qwen/Qwen3-TTS`（或 ModelScope 镜像）

```python
class ModelDownloader:
    MODELS = {
        "qwen3-tts": {
            "hf_repo": "Qwen/Qwen3-TTS",
            "modelscope_repo": "Qwen/Qwen3-TTS",   # 国内镜像
            "local_path": "~/.l2dclaw/models/qwen3-tts",
            "required_files": ["model.safetensors", "config.json", "tokenizer.json"]
        }
    }
    
    def download(self, model_name: str, use_modelscope: bool = False):
        """
        优先用 huggingface_hub 下载，国内网络自动切换 ModelScope。
        显示 rich 进度条。
        """
        ...
    
    def verify(self, model_name: str) -> bool:
        """验证模型文件完整性"""
        ...
    
    def is_downloaded(self, model_name: str) -> bool:
        ...
```

**网络自适应**：先尝试 HuggingFace，若 3 秒内无响应则自动切换 ModelScope（国内用户友好）。

---

## Step 2：Adapter 抽象基类设计

### adapter/base.py — AdapterBase

这是所有 Adapter 的统一接口，未来接入硬件设备时只需继承此类：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional
import asyncio

@dataclass
class AdapterEvent:
    """Adapter 产生的事件，统一格式"""
    adapter_type: str          # "screen" / "voice" / "keyboard" / "hardware_xxx"
    event_type: str            # "window_changed" / "speech" / "typing_burst" / 自定义
    data: dict                 # 事件数据载荷
    timestamp: str             # ISO 格式时间戳
    priority: int = 5          # 1-10，优先级（影响是否打断当前对话）

class AdapterBase(ABC):
    """
    所有感知 Adapter 的抽象基类。
    
    要接入新硬件/数据源时，继承此类并实现以下方法即可：
    
    class MyHardwareAdapter(AdapterBase):
        adapter_type = "hardware_mydevice"
        
        async def initialize(self): ...
        async def start(self): ...
        async def stop(self): ...
        async def get_current_state(self) -> dict: ...
    
    然后在 adapter_manager.py 中注册即可。
    """
    
    adapter_type: str = "base"           # 子类必须覆盖
    enabled: bool = True
    
    def __init__(self, config, event_callback: Callable[[AdapterEvent], None]):
        self.config = config
        self.emit = event_callback       # 向 AdapterManager 发送事件
        self._running = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化资源（加载模型、连接设备等），返回是否成功"""
        ...
    
    @abstractmethod
    async def start(self):
        """启动后台采集循环"""
        ...
    
    @abstractmethod
    async def stop(self):
        """停止并释放资源"""
        ...
    
    @abstractmethod
    async def get_current_state(self) -> dict:
        """获取当前快照状态（供 context_builder 调用）"""
        ...
    
    def is_available(self) -> bool:
        """检测当前平台/环境是否支持此 Adapter（子类可覆盖）"""
        return True
```

### adapter/adapter_manager.py — 统一管理

```python
class AdapterManager:
    """
    统一注册、启动、停止所有 Adapter。
    AdapterBase 子类通过 register() 注入，无需修改此类。
    """
    
    def register(self, adapter: AdapterBase): ...
    async def start_all(self): ...
    async def stop_all(self): ...
    def get_context_snapshot(self) -> dict:
        """从所有 Adapter 收集当前状态，合并成 context dict"""
        ...
```

### adapter/hardware/hardware_adapter_base.py — 硬件预留接口

```python
class HardwareAdapterBase(AdapterBase):
    """
    硬件设备 Adapter 的基类，在 AdapterBase 基础上增加硬件特有接口。
    
    未来可实现的子类示例：
    - SerialHardwareAdapter     # 串口设备（Arduino、传感器）
    - HIDHardwareAdapter        # HID 设备（手柄、特殊输入设备）
    - BluetoothHardwareAdapter  # 蓝牙设备
    - NetworkHardwareAdapter    # 网络设备（IoT 传感器）
    
    接入步骤（写入 docs/adapter_extension_guide.md）：
    1. 继承 HardwareAdapterBase
    2. 实现 initialize/start/stop/get_current_state
    3. 在 conf.yaml 的 adapters.hardware 下添加配置
    4. 在 main.py 中用 adapter_manager.register() 注册实例
    """
    
    adapter_type = "hardware_base"
    
    @abstractmethod
    async def connect(self) -> bool:
        """建立与硬件的连接"""
        ...
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        ...
    
    @property
    @abstractmethod
    def device_info(self) -> dict:
        """返回设备信息 {name, vendor, type, firmware_version}"""
        ...
```

---

## Step 3：ScreenAdapter — 窗口 + 画面内容识别

### adapter/screen/window_watcher.py — 跨平台窗口监控

**Windows 实现**（`pywin32`）：
```python
import win32gui, win32process, psutil

def get_active_window_win() -> dict:
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = psutil.Process(pid).name()
    return {"title": title, "process": process}
```

**macOS 实现**（`AppKit` / `subprocess osascript`）：
```python
import subprocess

def get_active_window_mac() -> dict:
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        set frontWindow to ""
        try
            set frontWindow to name of front window of (first application process whose frontmost is true)
        end try
        return frontApp & "|" & frontWindow
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    parts = result.stdout.strip().split("|")
    return {"process": parts[0], "title": parts[1] if len(parts) > 1 else ""}
```

**统一工厂函数**：
```python
import sys

def get_active_window() -> dict:
    if sys.platform == "win32":
        return get_active_window_win()
    elif sys.platform == "darwin":
        return get_active_window_mac()
    else:
        raise NotImplementedError(f"Platform {sys.platform} not supported")
```

### adapter/screen/content_recognizer.py — 画面内容识别

**仅在用户在向导中开启 `screen_content_recognition: true` 时启用。**

```python
class ContentRecognizer:
    """
    截取屏幕内容，调用 VLM（视觉语言模型）理解画面。
    支持两种模式：
    - 模式A：发送截图给 OpenClaw（需云端 VLM 支持）
    - 模式B：本地 OCR 提取文字（使用 pytesseract 或 easyocr，无隐私风险）
    """
    
    def __init__(self, config):
        self.mode = config.screen_watcher.content_recognition_mode  # "vlm" or "ocr"
        self.capture_region = config.screen_watcher.capture_region  # "fullscreen" or "active_window"
    
    async def capture_and_analyze(self) -> dict:
        screenshot = self._take_screenshot()
        
        if self.mode == "ocr":
            text = self._ocr(screenshot)
            return {"type": "ocr", "content": text[:500]}   # 限制长度
        
        elif self.mode == "vlm":
            # 压缩截图后编码为 base64，附在发给 OpenClaw 的 context 中
            b64 = self._compress_and_encode(screenshot)
            return {"type": "screenshot_b64", "content": b64}
    
    def _take_screenshot(self):
        """跨平台截图：使用 Pillow + mss 库"""
        import mss
        from PIL import Image
        # mss 跨平台，Windows/macOS/Linux 均支持
        ...
    
    def _compress_and_encode(self, img) -> str:
        """压缩到 720p 以内，JPEG 压缩，base64 编码"""
        ...
    
    def _ocr(self, img) -> str:
        """使用 easyocr 本地 OCR，不联网"""
        import easyocr
        ...
```

**conf.yaml 中对应配置**：
```yaml
screen_watcher:
  enabled: true
  interval_seconds: 5
  capture_window_title: true
  capture_active_process: true
  
  # 画面内容识别（向导中配置）
  content_recognition_enabled: false      # 向导写入
  content_recognition_mode: "ocr"         # "ocr"（本地无隐私风险）或 "vlm"（截图上云）
  capture_region: "active_window"         # "fullscreen" 或 "active_window"
  content_recognition_interval: 15        # 内容识别频率（秒），比窗口采样更低
```

---

## Step 4：本地 Qwen3 TTS

### tts/base.py — TTS 抽象基类

```python
class TTSBase(ABC):
    @abstractmethod
    async def speak(self, text: str): ...
    
    @abstractmethod
    def stop(self): ...
    
    @abstractmethod
    def is_ready(self) -> bool: ...
```

### tts/local_qwen3_tts.py — 本地推理

使用下载好的 Qwen3 TTS 模型在本地进行语音合成：

```python
class LocalQwen3TTS(TTSBase):
    """
    使用本地 Qwen3-TTS 模型合成语音，无需联网。
    模型路径来自 ~/.l2dclaw/models/qwen3-tts/
    
    推理后端优先级：
    1. 如果有 NVIDIA GPU → 使用 torch CUDA
    2. 如果是 Apple Silicon → 使用 torch MPS
    3. 其他 → CPU 推理（较慢）
    """
    
    def __init__(self, config):
        self.model_path = Path.home() / ".l2dclaw" / "models" / "qwen3-tts"
        self.device = self._detect_device()
        self.model = None
        self.processor = None
    
    def _detect_device(self) -> str:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():   # Apple Silicon
            return "mps"
        return "cpu"
    
    async def initialize(self):
        """加载模型到内存（在 main.py 启动时调用，非首次合成时才加载）"""
        from transformers import AutoProcessor, AutoModel
        self.processor = AutoProcessor.from_pretrained(str(self.model_path))
        self.model = AutoModel.from_pretrained(str(self.model_path)).to(self.device)
    
    async def speak(self, text: str):
        """合成语音并播放"""
        audio = self._synthesize(text)
        await self._play_audio(audio)
    
    def _synthesize(self, text: str) -> np.ndarray:
        # 调用 Qwen3-TTS 模型推理
        ...
    
    async def _play_audio(self, audio: np.ndarray):
        # 使用 sounddevice 播放，支持提前停止
        import sounddevice as sd
        ...
```

### tts/dashscope_tts.py — 云端降级备用

当本地模型加载失败或用户选择云端时的备用方案，调用 DashScope API。

---

## Step 5：conf.yaml 完整配置

```yaml
# OpenClaw 云端大脑
openclaw:
  base_url: "https://your-openclaw-endpoint/v1"
  api_key: "${OPENCLAW_API_KEY}"
  model: "openclaw-default"
  timeout_seconds: 10
  system_prompt: |
    你是一只名叫 Claw 的可爱桌宠。你能感知用户的桌面状态。
    请根据上下文和用户输入，用简短活泼的语气回应（不超过50字）。
    你的回复必须严格是以下 JSON 格式，不加任何多余文字：
    {"text": "说的话", "emotion": "happy|sad|surprised|neutral|thinking|angry", "motion": "idle|nod|shake|wave|jump"}

# TTS 配置
tts:
  provider: "local_qwen3"         # "local_qwen3"（默认）或 "dashscope"（降级备用）
  voice: "default"
  dashscope_api_key: "${DASHSCOPE_API_KEY}"   # 仅 provider=dashscope 时需要

# 语音识别
asr:
  provider: "faster-whisper"
  model_size: "base"
  language: "zh"
  vad_aggressiveness: 2

# 屏幕感知（具体配置由向导写入 user_prefs.yaml）
screen_watcher:
  enabled: true
  interval_seconds: 5
  capture_window_title: true
  capture_active_process: true
  content_recognition_enabled: false       # 向导配置
  content_recognition_mode: "ocr"
  capture_region: "active_window"
  content_recognition_interval: 15

# 键盘活跃度感知
keyboard_watcher:
  enabled: true
  track_frequency_only: true               # 只统计频率，绝不记录内容

# Adapter 扩展配置（硬件设备在此处添加）
adapters:
  hardware: []                             # 预留，例如：[{type: "serial", port: "COM3"}]

# Live2D
live2d:
  model_path: "live2d_driver/frontend/live2d_models/haru"
  desktop_pet_mode: true
  always_on_top: true
  click_through: true
  window_width: 400
  window_height: 600

# 服务端口
server:
  driver_ws_port: 12393
  adapter_port: 12394
```

---

## Step 6：实现其余核心模块

### brain/openclaw_client.py

```python
from openai import AsyncOpenAI
import json

class OpenClawClient:
    def __init__(self, config):
        self.client = AsyncOpenAI(
            base_url=config.openclaw.base_url,
            api_key=config.openclaw.api_key,
            timeout=config.openclaw.timeout_seconds
        )
        self.model = config.openclaw.model
        self.system_prompt = config.openclaw.system_prompt
    
    async def think(self, context: str, user_text: str) -> dict:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"[桌面状态]\n{context}\n\n[用户说]\n{user_text}"}
        ]
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
```

### adapter/context_builder.py

```python
def build_context(adapter_snapshot: dict) -> str:
    """
    将 AdapterManager.get_context_snapshot() 的结果转成自然语言 context 字符串。
    
    输入示例：
    {
      "screen": {"active_window": "VS Code", "process": "code.exe", "category": "coding",
                 "content": {"type": "ocr", "content": "def main():..."}},
      "keyboard": {"typing_wpm": 45, "active": true},
      "voice": {"last_speech_ago_seconds": 30}
    }
    
    输出示例：
    "[桌面] 用户正在使用 VS Code 编写代码
     [屏幕内容] 代码编辑中，检测到 Python 函数定义
     [输入状态] 正在积极打字（约45词/分钟）
     [时间] 下午3点，周三"
    """
    ...
```

### main.py

```python
import asyncio
import sys
from pathlib import Path
from setup.wizard import SetupWizard
from adapter.adapter_manager import AdapterManager
from adapter.screen.screen_adapter import ScreenAdapter
from adapter.voice.voice_adapter import VoiceAdapter
from adapter.keyboard.keyboard_adapter import KeyboardAdapter
from adapter.context_builder import build_context
from brain.openclaw_client import OpenClawClient
from tts.local_qwen3_tts import LocalQwen3TTS
from tts.dashscope_tts import DashscopeTTS
from live2d_driver.driver_server import Live2DDriverServer
from config import load_config

INIT_FLAG = Path.home() / ".l2dclaw" / "initialized"

async def main():
    # Step 1: 首次启动检测
    if not INIT_FLAG.exists():
        wizard = SetupWizard()
        if not wizard.run():      # 用户拒绝许可或中断
            sys.exit(0)
    
    config = load_config("conf.yaml")
    user_prefs = load_user_prefs()   # ~/.l2dclaw/user_prefs.yaml
    
    # Step 2: 初始化 TTS（本地优先）
    tts = LocalQwen3TTS(config)
    if not await tts.initialize():
        print("⚠ 本地 TTS 加载失败，降级为云端 DashScope TTS")
        tts = DashscopeTTS(config)
    
    # Step 3: 初始化 Adapter
    manager = AdapterManager()
    manager.register(ScreenAdapter(config, user_prefs, manager.on_event))
    manager.register(VoiceAdapter(config, manager.on_event))
    manager.register(KeyboardAdapter(config, manager.on_event))
    # 未来硬件：manager.register(MyHardwareAdapter(config, manager.on_event))
    
    # Step 4: 初始化其他模块
    driver = Live2DDriverServer(config)
    openclaw = OpenClawClient(config)
    
    # Step 5: 事件处理
    async def on_voice_input(text: str):
        context = build_context(manager.get_context_snapshot())
        response = await openclaw.think(context, text)
        await asyncio.gather(
            driver.send_action(response["text"], response["emotion"], response["motion"]),
            tts.speak(response["text"])
        )
    
    manager.set_voice_callback(on_voice_input)
    
    # Step 6: 启动
    await asyncio.gather(
        driver.start(),
        manager.start_all(),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 7：Live2D 前端集成

从 `_upstream_reference` 复制并裁剪前端到 `live2d_driver/frontend/`：

1. 复制 Open-LLM-VTuber 前端（Electron 客户端）
2. 保留：Live2D 渲染、WebSocket 通信、桌宠模式配置
3. 删除：原有 LLM/TTS/ASR 前端代码（由我们 Python 后端负责）
4. 验证 WebSocket 协议格式与 `driver_server.py` 完全匹配

---

## requirements.txt

```
# 核心
openai>=1.0.0
websockets>=12.0
pyyaml>=6.0
python-dotenv>=1.0.0

# 向导 UI
rich>=13.0.0

# TTS 本地推理
torch>=2.0.0
transformers>=4.40.0
sounddevice>=0.4.6
numpy>=1.24.0

# TTS 云端备用
dashscope>=1.14.0

# 语音识别
faster-whisper>=0.10.0
webrtcvad>=2.0.10
pyaudio>=0.2.11

# 屏幕感知
psutil>=5.9.0
mss>=9.0.0                          # 跨平台截图
Pillow>=10.0.0

# OCR（本地画面内容识别）
easyocr>=1.7.0

# Windows 专用（自动按平台安装）
pywin32>=306; sys_platform == "win32"

# 模型下载
huggingface_hub>=0.20.0

# 键盘监控
pynput>=1.7.0                        # 跨平台键盘监听（只统计频率）
```

---

## 完成标准 Checklist

**首次启动向导**
- [ ] 许可协议显示，强制确认 `y` 才继续
- [ ] 截图功能有二次隐私提示
- [ ] Qwen3 TTS 模型自动检测 HF / ModelScope，显示进度条下载
- [ ] 配置写入 `~/.l2dclaw/user_prefs.yaml`，标志文件写入

**Adapter 层**
- [ ] `AdapterBase` 抽象基类完整定义
- [ ] `HardwareAdapterBase` 预留接口文档齐全
- [ ] `ScreenAdapter` 在 Windows 和 macOS 均能正确输出活跃窗口
- [ ] `ContentRecognizer` OCR 模式能从截图提取文字
- [ ] `VoiceAdapter` 能正确触发语音识别回调
- [ ] `AdapterManager` 能统一管理所有 Adapter
- [ ] `docs/adapter_extension_guide.md` 写明如何接入新硬件

**大脑 + TTS**
- [ ] `OpenClawClient` 成功调用并解析 JSON 响应
- [ ] `LocalQwen3TTS` 能加载本地模型并合成语音
- [ ] TTS 降级逻辑正常（本地失败 → 云端）

**测试脚本**
- [ ] `tests/test_screen.py` — 验证窗口采集（Win + macOS）
- [ ] `tests/test_content_ocr.py` — 验证截图 OCR
- [ ] `tests/test_brain.py` — 验证 OpenClaw 调用
- [ ] `tests/test_tts.py` — 验证本地 TTS 合成
- [ ] `tests/test_adapter_manager.py` — 验证 Adapter 注册和事件流

---

## 每阶段 Git 提交节点

```bash
# 阶段一：骨架 + 向导 + 核心模块
git add -A
git commit -m "feat: setup wizard, adapter interface, screen/voice/tts modules"
git push origin main

# 阶段二：Live2D 前端集成
git add -A
git commit -m "feat: integrate Live2D frontend from Open-LLM-VTuber"
git push origin main

# 阶段三：联调 + 内容识别 + 文档
git add -A
git commit -m "feat: full pipeline, content recognition, hardware adapter guide"
git push origin main
```

---

## 注意事项

1. **隐私保护**：截图/VLM 模式需用户在向导中主动开启并确认，OCR 是无隐私风险的默认选项
2. **跨平台**：所有平台相关代码必须同时实现 Windows（`sys.platform == "win32"`）和 macOS（`sys.platform == "darwin"`）分支，不允许只写一个平台
3. **Adapter 扩展性**：`AdapterBase` 的接口设计要稳定，不能频繁改动基类（面向扩展开放，面向修改关闭）
4. **设备检测**：TTS 本地推理自动检测 CUDA / MPS（Apple Silicon）/ CPU，无需用户手动配置
5. **错误处理**：网络调用（OpenClaw、下载）必须有超时和重试；本地模型加载失败有降级路径
6. **日志**：使用 `logging` 模块，不用裸 `print`；向导阶段使用 `rich.console`

完成后请汇报：每个模块的实现状态、跨平台兼容性情况、遇到的问题，以及 Live2D 前端集成的下一步计划。
