# Surge 分流规则

每个规则集都可以在 Surge 中通过 `RULE-SET` 单独订阅，并绑定到自己的策略组。规则文件放在 `rule/Surge/<名称>/<名称>.list`。

## 规则集

| 规则集 | 覆盖范围 |
| --- | --- |
| [Meta.list](rule/Surge/Meta/Meta.list) | Muse、Meta AI、Llama、Facebook、Instagram、Messenger、WhatsApp、Threads、Meta Quest 和常用媒体域名 |

## 在 Surge 中添加 Meta 规则集

将以下两行分别加入现有配置的 `[Proxy Group]` 和 `[Rule]` 段。把 `Proxy` 换成配置里已有的代理策略或策略组名称。保存后，在 Surge 的 `Meta` 策略组里选择出站策略。

```ini
[Proxy Group]
Meta = select, Proxy, DIRECT

[Rule]
RULE-SET,https://raw.githubusercontent.com/1990jtf/surge-rules/main/rule/Surge/Meta/Meta.list,Meta
```

Surge 从上到下采用第一条命中的规则。把 Meta 规则放在已有且可能先匹配同一流量的 Facebook、Instagram、WhatsApp 或综合代理规则之前，并放在 `FINAL` 之前。[Surge 规则匹配顺序](https://manual.nssurge.com/rules/overview.html)

也可以将 [Meta.list](rule/Surge/Meta/Meta.list) 放到 Surge 配置文件所在目录，在 `[Rule]` 中写 `RULE-SET,Meta.list,Meta`。[Surge 外部规则集文档](https://manual.nssurge.com/rules/ruleset.html)

## 范围与维护

Meta 规则使用 `DOMAIN-SUFFIX`，每条规则同时匹配域名本身及其子域名，例如 `muse.ai` 和 `security.muse.ai`。仅以 IP 地址发起、且 Surge 无法关联到域名的连接由配置中的后续规则处理。Threads 同时保留 `threads.com` 和 `threads.net`，以覆盖现有和旧链接。

新增域名时，在 [Meta.list](rule/Surge/Meta/Meta.list) 的对应小节添加一行 `DOMAIN-SUFFIX,example.com`，并更新文件头的日期和规则条数。

## 参考

- Muse 入口与官方子域名。[Meta 发布公告](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/)
- Meta AI 与 Llama 入口。[Meta AI 发布公告](https://ai.meta.com/blog/introducing-model-meta-superintelligence-labs) · [Meta 开发者文档](https://dev.meta.ai/help/about-model-api/llama-and-model-api)
- Threads 域名迁移。[Meta 发布公告](https://about.fb.com/news/2025/04/new-features-threads-web-experience/)
- WhatsApp 网络域名与 Quest 的 Oculus 入口。[WhatsApp 帮助中心](https://faq.whatsapp.com/852892549070029/) · [Meta Horizon 开发文档](https://developers.meta.com/vr/documentation/web/web-launch/)
- 规则文件格式参考。[blackmatrix7 的 Surge Facebook 规则](https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Surge/Facebook)
