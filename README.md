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
    └── scripts/                    # 站点公开数据抓取脚本
        ├── utils.py                # 公共 HTTP/工具函数
        ├── zxgk_query.py           # 中国执行信息公开网
        ├── spp_news.py             # 最高人民检察院官网
        ├── court_news.py           # 最高人民法院官网
        ├── rmfyalk_search.py       # 人民法院案例库
        └── chinacourt_news.py      # 中国法院网
```

## 脚本说明

`chinese-lawyer/scripts/` 下的脚本用于抓取对应网站的**公开信息**。大部分脚本无需登录；需要登录的站点已实现通过统一认证入口登录，并支持 Session 复用。

### 已开发脚本（无需登录）

| 站点 | 脚本 | 功能 |
|------|------|------|
| [中国执行信息公开网](https://zxgk.court.gov.cn/) | `zxgk_query.py` | 失信被执行人/被执行人/首页公告查询 |
| [最高人民检察院官网](https://www.spp.gov.cn/) | `spp_news.py` | 新闻列表与正文抓取 |
| [中华人民共和国最高人民法院](https://www.court.gov.cn/index.html) | `court_news.py` | 新闻列表与正文抓取 |
| [中国法院网](https://www.chinacourt.cn/index.shtml) | `chinacourt_news.py` | 栏目新闻与正文抓取 |

### 已开发脚本（Token 模式）

| 站点 | 脚本 | 功能 | 说明 |
|------|------|------|------|
| [人民法院案例库](https://rmfyalk.court.gov.cn/) | `rmfyalk_search.py` | 案例检索与详情获取 | 需手动提供 `faxin-cpws-al-token`，通过 `--token` 或环境变量 `RMFYALK_TOKEN` 传入；暂不支持自动登录 |

### 跳过开发（需登录 / 强验证）

| 站点 | 原因 |
|------|------|
| [人民法院在线服务网](https://zxfw.court.gov.cn/zxfw/index.html#/pagesGrxx/pc/login/index) | 入口即登录页，必须账号/实名认证 |
| [中国裁判文书网](https://wenshu.court.gov.cn/) | 检索与下载文书需登录，且存在验证码/反爬验证 |

### 使用方式

1. 安装依赖：

   ```bash
   cd chinese-lawyer/scripts
   pip install -r requirements.txt
   ```

2. 运行示例：

   ```bash
   # 查询失信被执行人
   python zxgk_query.py --name 张三 --type dishonesty

   # 抓取最高检新闻
   python spp_news.py --channel spp/zdgz --limit 10

   # 人民法院案例库检索（Token 模式）
   python rmfyalk_search.py --token <faxin-cpws-al-token> --keyword 诈骗罪 --page 1

   # 人民法院案例库详情
   python rmfyalk_search.py --token <faxin-cpws-al-token> --gid <gid>

   # 仅提取单条案例的注释/要旨信息
   python rmfyalk_search.py --token <faxin-cpws-al-token> --gid <gid> --annotations-only

   # 检索后批量提取注释/要旨信息
   python rmfyalk_search.py --token <faxin-cpws-al-token> --keyword 诈骗罪 --annotations-only --size 5
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
- 脚本仅访问公开数据，遵守各站点 robots 与访问频率限制。
