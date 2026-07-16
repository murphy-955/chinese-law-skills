# Chinese Law Skills

面向中国律师从业者的 Kimi Skill 集合。

## 项目结构

```
chinese-law-skills/
├── README.md                       # 项目说明
└── chinese-lawyer/                 # skill 目录
    ├── SKILL.md                    # skill 元数据与工作流
    ├── references/                 # 参考资料
    │   ├── client-service.md       # 客户沟通与报价
    │   ├── contracts.md            # 合同实务
    │   ├── legal-documents.md      # 法律文书模板
    │   ├── legal-research.md       # 法规与案例检索
    │   └── litigation.md           # 庭审与证据
    └── scripts/                    # 脚本
        ├── utils.py                # 公共 HTTP/工具函数
        ├── rmfyalk_search.py       # 人民法院案例库检索与详情获取
        └── requirements.txt        # Python 依赖
```

## 脚本说明

`chinese-lawyer/scripts/rmfyalk_search.py` 用于调用人民法院案例库（rmfyalk.court.gov.cn）的公开接口，支持案例检索、详情获取以及注释/要旨信息提取。

### 登录方式

由于人民法院案例库的检索/详情接口需要登录态，脚本提供两种获取 Token 的方式：

1. **浏览器自动化登录（推荐）**：使用 Playwright 打开真实浏览器，用户可自行选择账号密码、支付宝、短信等方式完成登录；登录成功后脚本自动从 Cookie 中提取 `faxin-cpws-al-token` 并缓存。
2. **手动传入 Token**：用户从浏览器开发者工具中复制 `faxin-cpws-al-token`，通过 `--token` 或环境变量 `RMFYALK_TOKEN` 传入。

Token 有效期约为 4 小时，脚本会自动解析 JWT 的 `exp` 字段，在过期前提示重新登录。

### 使用方式

1. 安装依赖：

   ```bash
   cd chinese-lawyer/scripts
   pip install -r requirements.txt
   playwright install chromium
   ```

2. 运行示例：

   ```bash
   # 首次：打开浏览器登录（支持账号密码/支付宝/短信），登录成功后自动保存 Token
   python rmfyalk_search.py --login-browser --keyword 诈骗罪

   # 后续：复用已保存的 Token（4 小时内有效）
   python rmfyalk_search.py --keyword 诈骗罪

   # 使用已有 Token
   python rmfyalk_search.py --token <faxin-cpws-al-token> --keyword 诈骗罪

   # 获取案例详情
   python rmfyalk_search.py --gid <gid>

   # 仅提取注释/要旨信息
   python rmfyalk_search.py --gid <gid> --annotations-only

   # 检索后批量提取注释/要旨信息
   python rmfyalk_search.py --keyword 诈骗罪 --annotations-only --size 5
   ```

3. 结果默认保存到 `scripts/output/` 目录下的 JSON 文件。

## 使用方式（Skill）

将 `chinese-lawyer` 目录复制到 Kimi 的 skills 目录下：

- 用户级：`~/.config/agents/skills/`
- 项目级：`.agents/skills/`

## 设计原则

- 遵循 Kimi Skill 规范：skill 目录内仅保留 `SKILL.md` 及必要的 `references/`、`scripts/`、`assets/` 资源。
- 参考资料按需加载，避免一次塞入过多上下文。
- 内容聚焦中国法律实务，持续迭代补充。
- 脚本仅访问人民法院案例库公开接口，遵守网站访问频率限制。
