# Surge 分流规则

每个规则集都可以在 Surge 中通过 `RULE-SET` 单独订阅，并绑定到自己的策略组。规则文件放在 `rule/Surge/<名称>/<名称>.list`。

## 规则集

| 规则集 | 覆盖范围 |
| --- | --- |
| [Meta.list](rule/Surge/Meta/Meta.list) | Muse、Meta AI、Llama、Facebook、Instagram、Messenger、WhatsApp、Threads、Meta Quest 和常用媒体域名 |
| [OpenAI.list](rule/Surge/OpenAI/OpenAI.list) | ChatGPT、Codex、OpenAI API、登录、实时连接和附件 |
| [Claude.list](rule/Surge/Claude/Claude.list) | Claude 网页端、桌面端、Claude Code、Anthropic API、登录和更新 |
| [Google.list](rule/Surge/Google/Google.list) | Google 搜索、Workspace、YouTube、Play、Google Cloud、Firebase、Gemini、AI Studio 和 Gemini CLI |

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

## 在 Surge 中添加 Claude 规则集

在现有配置的 `[Rule]` 段加入以下一行，并使用已有的 `Claude` 策略组。

```ini
RULE-SET,https://raw.githubusercontent.com/1990jtf/surge-rules/main/rule/Surge/Claude/Claude.list,Claude
```

规则覆盖 Claude 的网页与 API、OAuth 和 SSO、桌面与原生 CLI 更新、Artifacts、浏览器桥接及 MCP Apps 内容。GitHub、npm、Google Cloud Storage 等共享服务由配置中的其他规则匹配。[Claude Desktop 网络要求](https://code.claude.com/docs/en/desktop#network-access-requirements) · [Claude Code 网络要求](https://code.claude.com/docs/en/network-config#network-access-requirements)

## 在 Surge 中添加 Google 规则集

将以下规则加入 `[Rule]`，并使用已有的 `Google` 策略组。Google 和 YouTube 同用一个策略组时，可以用这一行替换两个旧订阅。

```ini
RULE-SET,https://raw.githubusercontent.com/1990jtf/surge-rules/main/rule/Surge/Google/Google.list,Google
```

规则覆盖 Gemini 网页端、AI Studio 及其 `ai.studio` 发布地址，以及 Gemini CLI 的 Google 登录、Code Assist、Gemini API 和 Vertex AI 端点。Gemini CLI 的 GitHub 和 npm 下载由配置中的对应规则处理。[AI Studio 文档](https://ai.google.dev/gemini-api/docs/ai-studio-quickstart) · [Gemini CLI 认证文档](https://geminicli.com/docs/get-started/authentication/) · [Code Assist 客户端代码](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/code_assist/server.ts)

Google Cloud 和 Firebase 的平台域名（如 `run.app`、`web.app`）包含客户部署的应用。规则集按域名匹配，并保留少量带 `no-resolve` 的 Google IP 段，以覆盖直接连接这些 IP 的请求。[Google Cloud 域名文档](https://docs.cloud.google.com/vpc/docs/access-apis-external-ip) · [Firebase 项目域名](https://firebase.google.com/docs/projects/learn-more)

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
- Google 和 YouTube 的域名基于 V2Fly 的 MIT 许可数据，来源版本和许可文本随规则文件保留。搜索地区域名和保留的 IP 段使用 Google 公布的数据。[V2Fly Google 数据](https://github.com/v2fly/domain-list-community/tree/93d681debd7abdf1c08c3b3891ca1d7da657ea23/data) · [Google 搜索地区域名](https://www.google.com/supported_domains) · [Google IP 段](https://www.gstatic.com/ipranges/goog.json)
- 规则文件格式参考。[blackmatrix7 的 Surge Facebook 规则](https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Surge/Facebook)
