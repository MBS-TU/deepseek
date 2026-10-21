# 肥鱼桌宠

一个 Windows 桌宠小项目：蓝发蓝瞳、穿深蓝白女仆装、有鱼鳍耳朵的「肥鱼」坐在书桌前陪用户用电脑，会跟着鼠标和键盘活动。左键短按冒 `deep` 气泡，长按拖拽，右键打开菜单，隐藏后变成悬浮的 `deep`，点一下回来。右键「Harness 对话」可打开独立的 DeepSeek 对话窗。

## 已实现

- **角色**：使用 `design/feiyu.png` 作为唯一原画，去白底后生成 18 帧透明动画；桌宠窗口为 100×100。
- **鼠标/键盘活动感知**：只统计“有活动”，不保存按键内容；鼠标移动时左手会在鼠标垫上滑动，键盘敲击时右手会抬起再敲下；待机和拖拽时整张桌子不动，键盘和鼠标垫始终固定，只有独立的手部图层运动。
- **左键拖拽**：按住并移动即可拖走桌宠。
- **左键短按**：升起 `deep` 气泡。
- **五次短按**：1.5 秒内累计五次短按，照样弹出 `deep` 气泡（无音效）。
- **右键菜单**：Harness 对话、管理后台、隐藏、关闭。
- **隐藏/唤醒**：隐藏后显示 78×42 的 `deep` 悬浮标签，点击恢复桌宠。
- **无音效**：音频资源和播放代码已移除。
- **浅蓝/天蓝主题**：Harness 对话、气泡、管理后台与 API 设置均为浅蓝/天蓝配色。
- **DeepSeek V4.1 Flash**：模型名 `deepseek-flash`，通过官方 OpenAI 兼容接口流式对话。
- **首次 API 配置**：右键「Harness 对话」且没有 Key 时，先弹出 API 配置窗口；「连接并保存」会真实测试接口，成功后才保存并打开对话。
- **独立 Harness 对话框**：不嵌在桌宠里；支持流式输出、Markdown、停止、新对话、修改 API 设置、后台入口。
- **本地管理后台**：右键桌宠选「管理后台」，或在 Harness 里点「后台」。
  - 人设：直接编辑 system prompt，保存后下一轮对话生效。
  - 后台：查看 API/模型/接口/输入活动、本次运行事件日志，修改 API 设置。
  - 思考过程：实时查看 DeepSeek 返回的 `reasoning_content`，可以复制或清空记录。
- **配置存储**：
  - 源码运行：项目根目录 `config.json`
  - 打包运行：`%APPDATA%\FeiyuDeep\config.json`
  - 首次启动会尝试从旧版 `%APPDATA%\Laozhou325\config.json` 迁移本地配置，并保留已有的 API Key/人设。
  - API Key 和自定义人设为本地明文保存，不会上传到除 DeepSeek API 之外的地方。

## 隐私

- `config.json` 已加入 `.gitignore`，API Key 和人设设置都不会进入 Git 仓库。
- `.idea/`、`release/`、`build/`、`dist/` 和压缩包也不会提交（仅保留源码与运行素材）。
- 管理后台不会显示 API Key 原文。
- 思考过程只保存在当前进程内存中，不写入 config、日志文件或仓库。
- 如果 API Key 曾出现在任何公开位置，请立即到 DeepSeek 平台撤销并重新生成。

## 目录

```
main.py                 启动入口
pet_window.py           桌宠窗口、拖拽、点击计数、悬浮 deep、右键菜单
animation.py            帧动画与状态过渡
input_listener.py       全局鼠标/键盘活动监听（不收集内容）
bubble.py               deep 气泡
harness_dialog.py       独立 DeepSeek 对话窗（浅蓝主题）
api_client.py           DeepSeek 流式请求、思考流、连接验证
api_settings.py         首次 API 配置/修改窗口
admin_dialog.py         本地管理后台：人设、运行状态/日志、思考过程
runtime_state.py        本次运行的后台事件与内存思考记录
config_util.py          配置存取与旧配置迁移
paths.py                源码/打包资源路径
theme.py                浅蓝/天蓝配色与字体
assets/                 动画帧与图标（无音频）
design/                 feiyu.png、素材预览
tools/build_assets.py   从 feiyu.png 重建动画帧和图标
```

## 源码运行

```bat
venv\Scripts\python.exe main.py
```

或直接在 PyCharm 里运行 `main.py`。

## 打包

```bat
build_exe.bat
```

PyInstaller 产物是 `dist\FeiyuPet.exe`。单文件、动画已内嵌；
首次启动会慢一点。整理好的发布包在 `release\肥鱼桌宠\`
（内含 `肥鱼桌宠.exe`、使用说明和预览图）。

## 素材重建

需要 Pillow、numpy、scipy、OpenCV（在 venv 中安装 `requirements-dev.txt`）：

```bat
venv\Scripts\python.exe tools\build_assets.py
```

这会读取 `design/feiyu.png`，重建 `assets/idle|mouse|key|drag` 与 `assets/icon.*`，不会修改 `design` 里的原图。键盘和鼠标垫保持静止，动画只移动裁切出来的手部图层。

## 说明

- 全局键鼠监听使用 `pynput`，只感知活动，不抓取键值。
- 桌宠窗口使用 Qt 透明无边框置顶窗口；Harness 对话窗是普通独立窗口。
- 如果 API 报 401，请在 Harness 的「设置」里重新填写 Key；如果报模型错误，确认模型名为 `deepseek-flash`。
