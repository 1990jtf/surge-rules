#!/usr/bin/env bash
set -euo pipefail

output=$1
branch=automation/surge-rules-audit
ref=refs/heads/$branch
owner=${GITHUB_REPOSITORY%%/*}
fingerprint=$(cat "$output/fingerprint")
marker="<!-- surge-rule-audit:$fingerprint -->"
trailer="Surge-Rule-Audit: $fingerprint"
bot_email='41898282+github-actions[bot]@users.noreply.github.com'
title='每周 Surge 规则复核'

requests=$(gh api --method GET --paginate --slurp "repos/$GITHUB_REPOSITORY/pulls" \
  -f state=all -f head="$owner:$branch" -f base="$BASE_BRANCH" -F per_page=100 | jq 'add // []')
number=$(jq -r 'map(select(.state == "open")) | first | .number // empty' <<< "$requests")
if jq -e 'any(.[]; .state == "open" and .draft == false)' <<< "$requests" > /dev/null; then
  echo '现有 PR 已标记为可审阅，本次保留其内容。' >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
if jq -e --arg marker "$marker" --arg number "$number" '
  any(.[]; ($number == "" or (.number | tostring) == $number)
      and ((.body // "") | contains($marker)))
' <<< "$requests" > /dev/null; then
  echo '相同的候选清单已有复核记录。' >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

remote=$(git ls-remote --heads origin "$ref")
read -r remote_sha _ <<< "$remote"
if [[ -n "$remote_sha" ]]; then
  git fetch --no-tags origin "$ref"
  author=$(git show -s --format=%ae "$remote_sha")
  message=$(git show -s --format=%B "$remote_sha")
  if [[ "$author" != "$bot_email" ]] || ! grep -qxE 'Surge-Rule-Audit: [a-f0-9]{64}' <<< "$message"; then
    echo '待审分支包含手动提交，本次保留现有分支供复核。' >> "$GITHUB_STEP_SUMMARY"
    exit 0
  fi
fi

git add -- .github/rule-audit.json audit/latest.md \
  rule/Surge/{Meta,OpenAI,Claude,Google,Microsoft}/*.list
git -c user.name='github-actions[bot]' -c user.email="$bot_email" \
  commit -m "$title" -m "$trailer"
git push --force-with-lease="$ref:$remote_sha" origin "HEAD:$ref"

if [[ -n "$number" ]]; then
  url=$(jq -Rs '{body: .}' < "$output/pull-request.md" |
    gh api --method PATCH "repos/$GITHUB_REPOSITORY/pulls/$number" --input - --jq .html_url)
else
  url=$(gh pr create --repo "$GITHUB_REPOSITORY" --draft --base "$BASE_BRANCH" \
    --head "$branch" --title "$title" --body-file "$output/pull-request.md")
fi
printf '\n[待人工复核的 PR](%s)\n' "$url" >> "$GITHUB_STEP_SUMMARY"
