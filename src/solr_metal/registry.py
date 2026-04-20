from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from solr_metal.models import TestDefinition


def builtin_definitions() -> list[TestDefinition]:
    return [
        TestDefinition(
            id="core.cluster.connected",
            name="Cluster connectivity",
            description="Verifies kubeconfig authentication and API discovery reachability",
            module="core",
            suites=["smoke", "health"],
            kind="builtin",
            timeout="30s",
            severity="critical",
            tags=["api", "auth"],
            spec={"builtin": "cluster_connected"},
        ),
        TestDefinition(
            id="kubernetes.nodes.ready",
            name="Nodes ready",
            description="Ensures every node reports Ready=True",
            module="kubernetes",
            suites=["health"],
            kind="builtin",
            timeout="60s",
            severity="critical",
            tags=["nodes"],
            spec={"builtin": "nodes_ready"},
        ),
        TestDefinition(
            id="kubernetes.namespaces.create_delete",
            name="Namespace create/delete",
            description="Creates and deletes a temporary namespace",
            module="kubernetes",
            suites=["smoke"],
            kind="builtin",
            timeout="90s",
            severity="high",
            tags=["namespace", "cleanup"],
            spec={"builtin": "namespace_create_delete"},
        ),
        TestDefinition(
            id="kubernetes.permissions.smoke",
            name="Baseline permissions",
            description="Checks that the current identity can perform the core read and namespace lifecycle actions needed by smoke checks",
            module="kubernetes",
            suites=["smoke"],
            kind="builtin",
            timeout="45s",
            severity="critical",
            tags=["rbac", "permissions"],
            spec={"builtin": "permissions_smoke"},
        ),
        TestDefinition(
            id="kubernetes.pod.schedule_tiny",
            name="Tiny pod schedules",
            description="Schedules a tiny pause pod in a temporary namespace",
            module="kubernetes",
            suites=["smoke"],
            kind="builtin",
            timeout="120s",
            severity="high",
            tags=["pod", "schedule"],
            spec={"builtin": "pod_schedule_tiny"},
        ),
        TestDefinition(
            id="kubernetes.dns.resolve",
            name="Cluster DNS resolve",
            description="Runs an in-cluster pod that resolves kubernetes.default.svc",
            module="network",
            suites=["smoke"],
            kind="builtin",
            timeout="120s",
            severity="high",
            tags=["dns"],
            spec={"builtin": "dns_resolve"},
        ),
        TestDefinition(
            id="kubernetes.dns.service.present",
            name="DNS service present",
            description="Verifies that a cluster DNS service such as kube-dns or coredns is present in kube-system",
            module="network",
            suites=["smoke", "health"],
            kind="builtin",
            timeout="30s",
            severity="high",
            tags=["dns", "service"],
            spec={"builtin": "dns_service_present"},
        ),
        TestDefinition(
            id="storage.pvc.bind",
            name="PVC binds",
            description="Creates a PVC and waits for Bound phase",
            module="storage",
            suites=["health"],
            kind="builtin",
            timeout="180s",
            severity="high",
            tags=["storage", "pvc"],
            spec={"builtin": "pvc_bind"},
        ),
        TestDefinition(
            id="openshift.clusteroperators.healthy",
            name="ClusterOperators healthy",
            description="Ensures ClusterOperators are Available and not Degraded",
            module="openshift",
            suites=["health"],
            kind="builtin",
            timeout="90s",
            severity="critical",
            tags=["operators", "openshift"],
            spec={"builtin": "clusteroperators_healthy"},
        ),
        TestDefinition(
            id="openshift.ingress.available",
            name="Ingress available",
            description="Checks ingress controller availability on OpenShift",
            module="openshift",
            suites=["health"],
            kind="builtin",
            timeout="90s",
            severity="high",
            tags=["ingress", "openshift"],
            spec={"builtin": "ingress_available"},
        ),
        TestDefinition(
            id="openshift.image_pull.sanity",
            name="Image pull sanity",
            description="Runs a tiny pod using a known image and waits for Ready-like completion",
            module="openshift",
            suites=["smoke"],
            kind="builtin",
            timeout="120s",
            severity="high",
            tags=["image", "openshift"],
            spec={"builtin": "image_pull_sanity"},
        ),
    ]


class Registry:
    def __init__(self) -> None:
        self._tests: dict[str, TestDefinition] = {}

    @classmethod
    def load(cls, definitions_dirs: list[Path] | Path | None = None) -> "Registry":
        registry = cls()
        for item in builtin_definitions():
            registry.add(item)

        for definition in load_packaged_definitions():
            registry.add(definition)

        if definitions_dirs is None:
            sources: list[Path] = []
        elif isinstance(definitions_dirs, Path):
            sources = [definitions_dirs]
        else:
            sources = list(definitions_dirs)

        for definitions_dir in sources:
            if not definitions_dir.exists():
                continue
            for path in sorted(definitions_dir.rglob("*.y*ml")):
                registry.add(load_file(path))
        return registry

    def add(self, definition: TestDefinition) -> None:
        self._tests[definition.id] = definition

    def get(self, test_id: str) -> TestDefinition | None:
        return self._tests.get(test_id)

    def all(self) -> list[TestDefinition]:
        return sorted(self._tests.values(), key=lambda item: item.id)

    def by_suite(self, name: str) -> list[TestDefinition]:
        return sorted(
            [item for item in self._tests.values() if item.matches_suite(name)],
            key=lambda item: item.id,
        )


def load_file(path: Path) -> TestDefinition:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    definition = TestDefinition.model_validate(data)
    definition.source = str(path)
    return definition


def load_packaged_definitions() -> list[TestDefinition]:
    root = resources.files("solr_metal").joinpath("catalog", "definitions")
    out: list[TestDefinition] = []
    for item in _walk(root):
        if item.is_dir() or not item.name.endswith((".yaml", ".yml")):
            continue
        data = yaml.safe_load(item.read_text(encoding="utf-8")) or {}
        definition = TestDefinition.model_validate(data)
        definition.source = f"package:{item.name}"
        out.append(definition)
    return sorted(out, key=lambda definition: definition.id)


def _walk(root):
    for item in root.iterdir():
        if item.is_dir():
            yield from _walk(item)
        else:
            yield item
