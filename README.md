# GBF 公会成员追踪工具

一个用于采集 Granblue Fantasy（GBF）公会成员列表、保存历史快照、记录成员变化、生成每日报告，并将报告发送到 Discord 的 Python 项目。

## 代码来源声明

**本项目的所有代码均由 GPT 生成。**

项目开发过程中，作者主要负责提出功能需求、提供运行环境与测试反馈、执行代码并验证运行结果。代码的编写、修改及调试建议均由 GPT 提供。

## 功能

- 使用 SRWare Iron 和 Chrome DevTools Protocol（CDP）连接 GBF 网页。
- 分页采集公会成员列表，并在抓取失败时重试。
- 将采集结果保存为带时间戳的 JSON 快照。
- 使用 SQLite 保存成员历史快照。
- 对比快照并记录成员加入、退出及 Rank 变化。
- 生成每日成员变动文本报告。
- 通过 Discord Bot 将报告发送到指定频道。
- 通过统一入口依次运行整个流程，任一步骤失败时停止后续步骤。

## 项目结构

```text
PythonProject/
├── .venv/                    # Python 虚拟环境
├── data/                      # JSON 快照、数据库和报告
├── gbf_browser_profile/       # 浏览器个人资料
├── .gitignore                # Git 忽略规则
├── Open_GBF.py               # 启动或复用 GBF 浏览器
├── Collect_Members.py        # 采集公会成员
├── Database.py               # 更新历史数据库
├── Report_Changes.py         # 生成每日变动报告
├── Send_Discord.py           # 发送 Discord 报告
├── Run_Tracker.py            # 统一运行入口
├── requirements.txt          # Python 依赖
└── README.md                 # 项目说明
```

## 环境要求

- Windows
- Python
- PyCharm 或其他 Python 开发环境
- 已安装 SRWare Iron
- 可以正常登录并访问 GBF 的浏览器会话
- Discord Bot 和目标频道 ID

## 安装与配置

### 1. 获取项目

将项目克隆或下载到本地，然后使用 PyCharm 打开项目目录。

### 2. 配置 Python 环境

如果尚未创建虚拟环境，可在项目目录的 PowerShell 终端执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 4. 检查浏览器配置

打开 `Open_GBF.py`，确认以下设置与本机环境一致：

- SRWare Iron 的可执行文件路径
- 浏览器用户资料目录
- GBF 页面地址
- CDP 调试端口

### 5. 配置 Discord

`Send_Discord.py` 使用以下环境变量：

- `DISCORD_BOT_TOKEN`：Discord Bot Token
- `DISCORD_CHANNEL_ID`：目标频道 ID

可以在 PowerShell 当前终端中临时设置：

```powershell
$env:DISCORD_BOT_TOKEN = "你的 Bot Token"
$env:DISCORD_CHANNEL_ID = "你的频道 ID"
```

随后在同一个终端会话中运行程序。

**安全提醒：** 不要将真实 Bot Token 写入公开代码仓库、README、截图或公开日志。如果 Token 已经泄露，应撤销旧 Token 并重新生成。

## 运行方法

推荐通过统一入口运行完整流程：

```powershell
.\.venv\Scripts\python.exe .\Run_Tracker.py
```

也可以在 PyCharm 中打开 `Run_Tracker.py`，点击运行按钮。

### 执行流程

1. `Collect_Members.py`：连接浏览器、采集公会成员并保存 JSON 快照。
2. `Database.py`：导入快照、更新 SQLite 数据库并识别成员变化。
3. `Report_Changes.py`：生成每日成员变动报告。
4. `Send_Discord.py`：将报告发送到 Discord。

当控制台出现 `GBF 成员追踪流程全部完成！`，且进程退出代码为 `0` 时，表示整条流程正常完成。

## 数据与隐私

以下内容默认仅保存在本地，不应上传到公开仓库：

- `data/`：成员快照、历史数据库及报告。
- `gbf_browser_profile/`：浏览器个人资料，可能包含登录状态。
- `.env`：如果使用该文件保存密钥，应避免提交。

请检查 `.gitignore` 和 Git 暂存区，确保没有意外上传 Token、浏览器资料或私人采集数据。

注意：`.gitignore` 不会自动取消已经被 Git 跟踪的文件。如果敏感文件此前已提交，仅添加忽略规则并不足以将其从 Git 历史中移除。

## 常见问题

### 浏览器无法启动

检查 `Open_GBF.py` 中的浏览器路径是否正确，以及 SRWare Iron 是否已经安装。

### 无法连接浏览器调试接口

检查 CDP 端口配置，确认端口没有被其他进程占用，并检查浏览器是否正常启动。

### 成员人数或变动记录异常

检查采集日志、分页人数和最终保存的 JSON 文件，再与 GBF 页面实际显示进行比较。不要仅凭单次快照就断定成员已经加入或退出。

### Discord 发送失败

检查 Bot Token、频道 ID、Bot 是否已加入服务器，以及是否拥有目标频道的查看和发送消息权限。不要在公开日志中粘贴 Token。

## 开发与更新

修改代码后，建议先运行修改涉及的单个脚本，再运行 `Run_Tracker.py` 验证完整流程。确认成功后再提交 Git。

如果重命名 Python 文件，请同步修改其他脚本中的文件名引用。

## 免责声明

本项目是个人自动化工具，不隶属于 Cygames 或 Granblue Fantasy 官方。使用者应遵守游戏及相关平台的服务条款，并自行承担使用本工具的责任。
