# Surge 分流规则

每个规则集都可以在 Surge 中通过 `RULE-SET` 单独订阅，并绑定到自己的策略组。规则文件放在 `rule/Surge/<名称>/<名称>.list`。

## 规则集

| 规则集 | 覆盖范围 |
| --- | --- |
| [Meta.list](rule/Surge/Meta/Meta.list) | Muse、Meta AI、Llama、Facebook、Instagram、Messenger、WhatsApp、Threads、Meta Quest 和常用媒体域名 |
| [OpenAI.list](rule/Surge/OpenAI/OpenAI.list) | ChatGPT、Codex、OpenAI API、登录、实时连接和附件 |

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

## 在 Surge 中添加 OpenAI 规则集

将以下规则加入 `[Rule]`，放在可能先匹配附件或静态资源的综合规则集之前。策略名称使用配置中已有的 `OpenAI` 策略组或其他代理策略。

```ini
RULE-SET,https://raw.githubusercontent.com/1990jtf/surge-rules/main/rule/Surge/OpenAI/OpenAI.list,OpenAI
```

`chatgpt.com` 同时覆盖 ChatGPT 的 `ws.chatgpt.com` 和 Codex 的流式连接。Stripe、WorkOS 等共享域名，以及 ChatGPT Voice 使用的动态 IP，交由配置中的其他规则匹配。[OpenAI 网络要求](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)

## 规则维护

Meta 规则使用 `DOMAIN-SUFFIX`，每条规则同时匹配域名本身及其子域名，例如 `muse.ai` 和 `security.muse.ai`。仅以 IP 地址发起、且 Surge 无法关联到域名的连接由配置中的后续规则处理。Threads 同时保留 `threads.com` 和 `threads.net`，以覆盖现有和旧链接。

新增域名时，在对应规则文件中使用 `DOMAIN` 匹配单个主机名，或使用 `DOMAIN-SUFFIX` 匹配域名及其子域名，并更新文件头的日期和规则条数。

## 参考

- Muse 入口与官方子域名。[Meta 发布公告](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/)
- Meta AI 与 Llama 入口。[Meta AI 发布公告](https://ai.meta.com/blog/introducing-model-meta-superintelligence-labs) · [Meta 开发者文档](https://dev.meta.ai/help/about-model-api/llama-and-model-api)
- Threads 域名迁移。[Meta 发布公告](https://about.fb.com/news/2025/04/new-features-threads-web-experience/)
- WhatsApp 网络域名与 Quest 的 Oculus 入口。[WhatsApp 帮助中心](https://faq.whatsapp.com/852892549070029/) · [Meta Horizon 开发文档](https://developers.meta.com/vr/documentation/web/web-launch/)
- Codex 的生产后端及登录入口。[Codex 源代码](https://github.com/openai/codex/blob/main/codex-rs/login/src/auth/workload_identity.rs) · [Codex 登录实现](https://github.com/openai/codex/blob/main/codex-rs/login/src/server.rs)
- OpenAI 专用 CDN 和 Azure 端点参考。[blackmatrix7 的 Surge OpenAI 规则](https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Surge/OpenAI)
- 规则文件格式参考。[blackmatrix7 的 Surge Facebook 规则](https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Surge/Facebook)
