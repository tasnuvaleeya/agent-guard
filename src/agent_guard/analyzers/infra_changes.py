"""Path-based detection of infrastructure / CI / deploy-relevant changes."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from agent_guard.analyzers.base import Analyzer, Context
from agent_guard.models import Finding, Severity


@dataclass(frozen=True)
class InfraRule:
    rule_id: str
    severity: Severity
    pattern: re.Pattern[str]
    message: str


_RULES: tuple[InfraRule, ...] = (
    InfraRule("infra.workflow", Severity.HIGH, re.compile(r"^\.github/workflows/.+\.ya?ml$"), "GitHub Actions workflow changed"),
    InfraRule("infra.action-yml", Severity.HIGH, re.compile(r"(^|/)action\.ya?ml$"), "GitHub Action definition changed"),
    InfraRule("infra.dockerfile", Severity.MEDIUM, re.compile(r"(^|/)Dockerfile(\..+)?$"), "Dockerfile changed"),
    InfraRule("infra.terraform", Severity.HIGH, re.compile(r"\.tf$|\.tfvars$"), "Terraform configuration changed"),
    InfraRule("infra.kubernetes", Severity.HIGH, re.compile(r"(^|/)(k8s|kubernetes|manifests|charts)/.+\.(ya?ml|json)$"), "Kubernetes manifest changed"),
    InfraRule("infra.helm", Severity.HIGH, re.compile(r"(^|/)(charts?|helm)/.+\.(ya?ml|tpl)$"), "Helm chart changed"),
    InfraRule("infra.env-file", Severity.CRITICAL, re.compile(r"(^|/)\.env(\..+)?$"), "Environment file changed — verify no secrets committed"),
    InfraRule("infra.lockfile-removed", Severity.MEDIUM, re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock|Cargo\.lock|go\.sum)$"), "Lockfile changed"),
    InfraRule("infra.makefile-deploy", Severity.MEDIUM, re.compile(r"(^|/)Makefile$"), "Makefile changed"),
    InfraRule("infra.ci-config", Severity.MEDIUM, re.compile(r"(^|/)(\.circleci/config\.yml|\.gitlab-ci\.yml|azure-pipelines\.yml|Jenkinsfile)$"), "CI configuration changed"),
)


class InfraChangeDetector(Analyzer):
    id = "infra_changes"
    category = "infra"

    def analyze(self, ctx: Context) -> Iterable[Finding]:
        for change in ctx.changes:
            for rule in _RULES:
                if not rule.pattern.search(change.path):
                    continue
                # Lockfile rule should only fire when the file is removed or substantially shrunk.
                if rule.rule_id == "infra.lockfile-removed" and change.status != "deleted":
                    continue
                yield Finding(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    file=change.path,
                    line=0,
                    message=rule.message,
                    evidence=f"{change.status}: {change.path}",
                    category="infra",
                    metadata={"status": change.status},
                )
                break  # one finding per file is enough
