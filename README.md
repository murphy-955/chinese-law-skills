# Chinese Law Skills

包含以下站点

- [中国执行信息公开网](https://zxgk.court.gov.cn/)
- [最高人民检察院官网](https://www.spp.gov.cn/)
- [中华人民共和国最高人民法院](https://www.court.gov.cn/index.html)
- [人民法院在线服务网](https://zxfw.court.gov.cn/zxfw/index.html#/pagesGrxx/pc/login/index)
- [人民法院案例库](https://rmfyalk.court.gov.cn/)
- [中国裁判文书网](https://wenshu.court.gov.cn/)
- [中国法院网](https://www.chinacourt.cn/index.shtml)

面向中国律师从业者的 Kimi Skill 集合。

## 项目结构

```
chinese-law-skills/
├── README.md                       # 项目说明
└── chinese-lawyer/                 # skill 目录
    ├── SKILL.md                    # skill 元数据与工作流
    └── references/                 # 参考资料
        ├── client-service.md       # 客户沟通与报价
        ├── contracts.md            # 合同实务
        ├── legal-documents.md      # 法律文书模板
        ├── legal-research.md       # 法规与案例检索
        └── litigation.md           # 庭审与证据
```

## 使用方式

将 `chinese-lawyer` 目录复制到 Kimi 的 skills 目录下：

- 用户级：`~/.config/agents/skills/`
- 项目级：`.agents/skills/`

## 设计原则

- 遵循 Kimi Skill 规范：skill 目录内仅保留 `SKILL.md` 及必要的 `references/`、`scripts/`、`assets/` 资源。
- 参考资料按需加载，避免一次塞入过多上下文。
- 内容聚焦中国法律实务，持续迭代补充。
