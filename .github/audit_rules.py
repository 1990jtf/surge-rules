#!/usr/bin/env python3
"""Compare the five Surge lists with pinned and current upstream snapshots."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CONFIG = Path(".github/rule-audit.json")
REPORT = Path("audit/latest.md")
EXACT = "DOMAIN"
SUFFIX = "DOMAIN-SUFFIX"
SERVICES = {
    "Meta": (("Meta", "Facebook"), "meta"),
    "OpenAI": ((), "openai"),
    "Claude": ((), "anthropic"),
    "Google": (("Google",), "google"),
    "Microsoft": (("Microsoft",), "microsoft"),
}
UPSTREAMS = {
    "rabbit": ("Rabbit-Spec/Surge", "Master"),
    "v2fly": ("v2fly/domain-list-community", "master"),
}
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
DOMAIN = re.compile(rf"{LABEL}(?:\.{LABEL})+")
DOC_DOMAIN = re.compile(rf"(?<![\w.-])(?:\*\.)?{LABEL}(?:\.{LABEL})+(?![\w-]|\.[a-z0-9])")
REF = re.compile(r"[0-9a-f]{40}")
DATA_NAME = re.compile(r"[a-z0-9_-]+")


def fetch(url, limit=4_000_000):
    request = Request(url, headers={"User-Agent": "surge-rule-audit/1.0", "Accept": "text/markdown, text/html, */*"})
    with urlopen(request, timeout=25) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"Response exceeds the size limit: {url}")
    return body


def upstream_tip(repository, branch):
    ref = f"refs/heads/{branch}"
    line = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", f"https://github.com/{repository}.git", ref],
        text=True, timeout=30,
    )
    revision, actual_ref = line.strip().split()
    if actual_ref != ref or not REF.fullmatch(revision):
        raise ValueError(f"Unexpected ref returned by {repository}")
    return revision


def source_link(source, revision, path=""):
    repository, _ = UPSTREAMS[source]
    suffix = f"/blob/{revision}/{path}" if path else f"/commit/{revision}"
    return f"https://github.com/{repository}{suffix}"


def valid_domain(host):
    return len(host) <= 253 and DOMAIN.fullmatch(host) and not host.rsplit(".", 1)[1].isdigit()


def parse_surge(text):
    rules = set()
    for line in text.splitlines():
        fields = [field.strip() for field in line.split("#", 1)[0].split(",")]
        if len(fields) >= 2 and fields[0] in (EXACT, SUFFIX):
            host = fields[1].lower().rstrip(".")
            if valid_domain(host):
                rules.add((fields[0], host))
    return rules


def covers(rules, rule):
    kind, host = rule
    if kind == EXACT and (EXACT, host) in rules:
        return True
    labels = host.split(".")
    return any((SUFFIX, ".".join(labels[i:])) in rules for i in range(len(labels)))


def overlaps(rules, rule):
    kind, host = rule
    return covers(rules, (EXACT, host)) or (
        kind == SUFFIX and any(other.endswith(f".{host}") for _, other in rules)
    )


def read_v2fly(revision):
    repository, _ = UPSTREAMS["v2fly"]
    payload = fetch(f"https://codeload.github.com/{repository}/tar.gz/{revision}", 12_000_000)
    files = {}
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            parts = member.name.split("/", 2)
            if len(parts) == 3 and parts[1] == "data" and DATA_NAME.fullmatch(parts[2]) and member.isfile():
                if member.size > 2_000_000:
                    raise ValueError(f"Unexpectedly large upstream file: {parts[2]}")
                files[parts[2]] = archive.extractfile(member).read().decode("utf-8-sig")

    def expand(root):
        seen = set()
        rules = defaultdict(set)

        def visit(name):
            if name in seen or (root == "microsoft" and name == "github"):
                return
            seen.add(name)
            for line in files[name].splitlines():
                fields = line.split("#", 1)[0].split()
                if not fields:
                    continue
                field = fields[0].lower()
                kind, separator, host = field.partition(":")
                if not separator:
                    kind, host = "domain", field
                if kind == "include":
                    visit(host)
                elif kind in ("domain", "full") and valid_domain(host):
                    rule = (EXACT if kind == "full" else SUFFIX, host)
                    rules[rule].add(source_link("v2fly", revision, f"data/{name}"))

        visit(root)
        if not rules:
            raise ValueError(f"No domain rules found in V2Fly data/{root}")
        return rules

    return {service: expand(root) for service, (_, root) in SERVICES.items()}


def read_rabbit(revision):
    names = sorted({"AIGC", *(name for names, _ in SERVICES.values() for name in names)})
    repository, _ = UPSTREAMS["rabbit"]

    def read(name):
        path = f"Rules/{name}.list"
        url = f"https://raw.githubusercontent.com/{repository}/{revision}/{path}"
        rules = parse_surge(fetch(url).decode("utf-8-sig"))
        if not rules:
            raise ValueError(f"No domain rules found in Rabbit-Spec {path}")
        return name, {rule: source_link("rabbit", revision, path) for rule in rules}

    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(read, names))


def read_snapshot(revisions):
    for name in UPSTREAMS:
        if not REF.fullmatch(revisions[name]):
            raise ValueError(f"Invalid baseline revision for {name}")
    rabbit = read_rabbit(revisions["rabbit"])
    services = read_v2fly(revisions["v2fly"])
    for service, (names, _) in SERVICES.items():
        for name in names:
            for rule, link in rabbit[name].items():
                services[service][rule].add(link)
    return services, rabbit["AIGC"]


class DocumentText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fragments = []
        self.hidden = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden = tag
        if tag == "a" and not self.hidden:
            href = dict(attrs).get("href") or ""
            if href.startswith("https://"):
                self.fragments.append(href)

    def handle_endtag(self, tag):
        if tag == self.hidden:
            self.hidden = None

    def handle_data(self, data):
        if not self.hidden:
            self.fragments.append(data)


def read_document(url):
    try:
        text = fetch(url).decode("utf-8", errors="replace")
    except (OSError, ValueError) as error:
        print(f"Official source unavailable: {url} ({type(error).__name__})")
        return set(), False
    if "<html" in text[:1000].lower() or "<!doctype html" in text[:1000].lower():
        parser = DocumentText()
        parser.feed(text)
        text = " ".join(parser.fragments)
    if url == "https://www.google.com/supported_domains":
        return {f"*{line}" for line in text.lower().split() if line.startswith(".") and valid_domain(line[1:])}, True
    return set(DOC_DOMAIN.findall(text.lower())), True


def audit(current, current_mixed, previous, previous_mixed, local, official, shared):
    candidates = {service: defaultdict(set) for service in SERVICES}
    for service in SERVICES:
        for rule, sources in current[service].items():
            if not covers(previous[service], rule) and not covers(local[service], rule):
                candidates[service][rule].update(sources)

    for rule, link in current_mixed.items():
        if covers(previous_mixed, rule):
            continue
        named = [service for service in SERVICES if covers(current[service], rule)]
        documented = [
            service for service in ("OpenAI", "Claude")
            if any(rule[1] in terms or f"*.{rule[1]}" in terms for terms, _ in official[service].values())
        ]
        owners = named or documented
        if len(owners) == 1 and owners[0] in ("OpenAI", "Claude"):
            service = owners[0]
            if not covers(previous[service], rule) and not covers(local[service], rule):
                candidates[service][rule].add(link)

    candidate_hosts = {
        service: {(EXACT, host) for _, host in gaps} for service, gaps in candidates.items()
    }
    # Evaluate proposed wildcard ranges as well as the exact candidate hostnames.
    for service, hosts in candidate_hosts.items():
        hosts.update(
            (SUFFIX, host) for kind, host in candidates[service]
            if kind == SUFFIX and any(f"*.{host}" in terms for terms, _ in official[service].values())
        )

    result = {}
    for service, gaps in candidates.items():
        items = []
        for (kind, host), sources in sorted(gaps.items(), key=lambda row: (row[0][1], row[0][0])):
            evidence = [url for url, (terms, _) in official[service].items() if host in terms or f"*.{host}" in terms]
            wildcard = any(f"*.{host}" in official[service][url][0] for url in evidence)
            exact = any(host in official[service][url][0] for url in evidence)
            proposal = (SUFFIX if kind == SUFFIX and wildcard else EXACT, host)
            other_services = [
                name for name in SERVICES if name != service and overlaps(local[name], proposal)
            ]
            other_candidates = [
                name for name in SERVICES if name != service and overlaps(candidate_hosts[name], proposal)
            ]
            if other_services:
                status = "已有其他服务匹配，需核对优先级（" + "、".join(other_services) + "）"
                proposal = None
            elif other_candidates:
                status = "多个服务存在重叠候选，需核对归属（" + "、".join(other_candidates) + "）"
                proposal = None
            elif overlaps(shared, proposal):
                status = "共享基础设施，需人工复核"
                proposal = None
            elif not evidence:
                status = "待核实"
                proposal = None
            elif proposal[0] == EXACT and not exact:
                status = "资料仅列出通配符，需核对域名本身"
                proposal = None
            elif covers(local[service], proposal) or (EXACT, host) in local[service]:
                status = "现有主机名已覆盖，后缀范围待复核"
                proposal = None
            else:
                status = "已列入 PR 的规则改动"
            items.append((kind, host, sorted(sources), evidence, proposal, status))
        result[service] = items
    return result


def rule_path(service):
    return Path(f"rule/Surge/{service}/{service}.list")


def update_list(service, additions):
    path = rule_path(service)
    lines = path.read_text().splitlines()
    suffixes = {host for kind, host in additions if kind == SUFFIX}
    additions = sorted(
        (kind, host) for kind, host in additions if kind == SUFFIX or host not in suffixes
    )
    insertion = max(i for i, line in enumerate(lines) if line and not line.startswith("#")) + 1
    heading = "# Officially documented endpoints from the weekly audit"
    new_lines = [] if heading in lines else ["", heading]
    lines[insertion:insertion] = new_lines + [f"{kind},{host}" for kind, host in additions]
    rows = [line for line in lines if line and not line.startswith("#")]
    counts = Counter(line.split(",", 1)[0] for line in rows)
    counts["TOTAL"] = len(rows)
    counts["UPDATED"] = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    for key, count in counts.items():
        header = f"# {key}: "
        for i, line in enumerate(lines):
            if line.startswith(header):
                lines[i] = f"{header}{count}"
                break
        else:
            total = next(i for i, line in enumerate(lines) if line.startswith("# TOTAL: "))
            lines.insert(total, f"{header}{count}")
    path.write_text("\n".join(lines) + "\n")


def format_report(results, revisions, official, limit=None):
    lines = [
        "按服务列出相对于上次复核的新候选。官方依据表示文档明确列出了该主机名或后缀。",
        "",
        " · ".join(
            f"[{repository} `{revisions[name][:10]}`]({source_link(name, revisions[name])})"
            for name, (repository, _) in UPSTREAMS.items()
        ),
    ]
    if limit:
        lines += ["", "完整清单见本 PR 的 `audit/latest.md`。"]
    for service, items in results.items():
        lines += ["", f"## {service}", ""]
        if not items:
            lines.append("本次无新增候选。")
            continue
        lines += ["| 上游规则 | 来源 | 官方依据 | 处理 |", "| --- | --- | --- | --- |"]
        for kind, host, sources, evidence, proposal, status in items[:limit]:
            links = " · ".join(
                f"[{'Rabbit-Spec' if 'Rabbit-Spec/' in url else 'V2Fly'} {url.rsplit('/', 1)[1]}]({url})"
                for url in sources
            )
            docs = " · ".join(f"[文档 {i}]({url})" for i, url in enumerate(evidence, 1)) or "所查页面未找到明确条目"
            change = f"`{','.join(proposal)}`" if proposal else status
            lines.append(f"| `{kind},{host}` | {links} | {docs} | {change} |")
        if limit and len(items) > limit:
            lines += ["", f"另有 {len(items) - limit} 项见完整清单。"]
        unavailable = [url for url, (_, ok) in official[service].items() if not ok]
        if unavailable:
            lines += ["", "本次读取失败的官方资料 · " + " · ".join(
                f"[文档 {i}]({url})" for i, url in enumerate(unavailable, 1)
            )]
    return "\n".join(lines) + "\n"


def main(output):
    config = json.loads(CONFIG.read_text())
    revisions = {name: upstream_tip(*upstream) for name, upstream in UPSTREAMS.items()}
    previous, previous_mixed = read_snapshot(config["baseline"])
    if revisions == config["baseline"]:
        current, current_mixed = previous, previous_mixed
    else:
        current, current_mixed = read_snapshot(revisions)
    local = {service: parse_surge(rule_path(service).read_text()) for service in SERVICES}
    shared = {(SUFFIX, host) for host in config["shared_suffixes"]}
    official = {service: {} for service in SERVICES}

    has_named_gaps = any(
        not covers(previous[service], rule) and not covers(local[service], rule)
        for service in SERVICES for rule in current[service]
    )
    has_mixed_changes = any(not covers(previous_mixed, rule) for rule in current_mixed)
    if has_named_gaps or has_mixed_changes:
        urls = sorted({url for pages in config["official_sources"].values() for url in pages})
        with ThreadPoolExecutor(max_workers=8) as pool:
            documents = dict(zip(urls, pool.map(read_document, urls)))
        official = {
            service: {url: documents[url] for url in urls}
            for service, urls in config["official_sources"].items()
        }

    results = audit(current, current_mixed, previous, previous_mixed, local, official, shared)
    count = sum(map(len, results.values()))
    summary = f"检查了五套规则。发现 {count} 项新增候选。"
    locations = f"Rabbit-Spec: `{revisions['rabbit']}`\n\nV2Fly: `{revisions['v2fly']}`"
    print(summary)
    for name, body in (
        ("GITHUB_OUTPUT", f"has_candidates={'true' if count else 'false'}\n"),
        ("GITHUB_STEP_SUMMARY", f"## Surge 规则复核\n\n{summary}\n\n{locations}\n\n"),
    ):
        if os.environ.get(name):
            with Path(os.environ[name]).open("a") as stream:
                stream.write(body)
    if not count:
        return

    for service, items in results.items():
        additions = {proposal for _, _, _, _, proposal, _ in items if proposal}
        if additions:
            update_list(service, additions)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("# Surge 规则复核\n\n" + format_report(results, revisions, official))
    config["baseline"] = revisions
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")

    fingerprint_data = [
        (service, kind, host, evidence, proposal, status)
        for service, items in results.items() for kind, host, _, evidence, proposal, status in items
    ]
    fingerprint = sha256(json.dumps(fingerprint_data, ensure_ascii=False).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    (output / "fingerprint").write_text(fingerprint + "\n")
    (output / "pull-request.md").write_text(
        f"<!-- surge-rule-audit:{fingerprint} -->\n"
        "请确认域名归属、匹配范围和策略优先级，再决定合并。\n\n"
        + format_report(results, revisions, official, limit=15)
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
