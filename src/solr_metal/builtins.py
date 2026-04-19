from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from kubernetes import client
from kubernetes.client import ApiException

from solr_metal.artifacts import ArtifactStore
from solr_metal.errors import ErrorCategory, make_error
from solr_metal.kube import KubeClients
from solr_metal.models import Status, TestDefinition, TestResult
from solr_metal.settings import Settings


class BuiltinRunner:
    def __init__(self, clients: KubeClients, settings: Settings, artifacts: ArtifactStore) -> None:
        self.clients = clients
        self.settings = settings
        self.artifacts = artifacts

    def run(self, test: TestDefinition, run_id: str) -> TestResult:
        started_at = utc_now()
        method_name = test.spec.get("builtin", "")
        method = getattr(self, method_name, None)
        if method is None:
            finished_at = utc_now()
            return TestResult(
                id=test.id,
                name=test.name,
                module=test.module,
                kind=test.kind,
                status=Status.ERROR,
                started_at=started_at,
                finished_at=finished_at,
                duration=finished_at - started_at,
                error=make_error(
                    "BUILTIN_UNKNOWN",
                    f"builtin {method_name!r} is not registered",
                    ErrorCategory.RUNNER,
                ).model_dump(mode="json"),
            )

        result = method(test, run_id)
        result.started_at = started_at
        result.finished_at = utc_now()
        result.duration = result.finished_at - started_at
        return result

    def cluster_connected(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            version = self.clients.version.get_code()
        except Exception as exc:
            return error_result(test, "API_DISCOVERY_FAILED", str(exc), ErrorCategory.DEPENDENCY, True)
        return pass_result(test, f"connected to Kubernetes {version.git_version}")

    def nodes_ready(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            nodes = self.clients.core.list_node().items
        except Exception as exc:
            return error_result(test, "LIST_NODES_FAILED", str(exc), ErrorCategory.DEPENDENCY, True)

        not_ready = [node.metadata.name for node in nodes if not is_node_ready(node)]
        if not_ready:
            return fail_result(test, f"{len(not_ready)}/{len(nodes)} nodes not Ready: {', '.join(not_ready)}")
        return pass_result(test, f"{len(nodes)}/{len(nodes)} nodes Ready")

    def namespace_create_delete(self, test: TestDefinition, run_id: str) -> TestResult:
        namespace = safe_name(run_id, "ns")
        body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace,
                labels={"app.kubernetes.io/managed-by": "solr-metal", "sm.run/id": run_id},
            )
        )
        try:
            self.clients.core.create_namespace(body)
            self.clients.core.delete_namespace(namespace)
        except Exception as exc:
            return error_result(
                test,
                "NAMESPACE_LIFECYCLE_FAILED",
                str(exc),
                ErrorCategory.DEPENDENCY,
                True,
            )
        return pass_result(test, "temporary namespace create/delete path succeeded")

    def permissions_smoke(self, test: TestDefinition, run_id: str) -> TestResult:
        checks = [
            ("list namespaces", "list", "namespaces", None),
            ("list nodes", "list", "nodes", None),
            ("create namespaces", "create", "namespaces", None),
            ("create pods in default", "create", "pods", "default"),
        ]
        denied: list[str] = []

        try:
            for label, verb, resource, namespace in checks:
                review = client.V1SelfSubjectAccessReview(
                    spec=client.V1SelfSubjectAccessReviewSpec(
                        resource_attributes=client.V1ResourceAttributes(
                            namespace=namespace,
                            verb=verb,
                            resource=resource,
                        )
                    )
                )
                response = self.clients.auth.create_self_subject_access_review(review)
                if not response.status.allowed:
                    denied.append(label)
        except Exception as exc:
            return error_result(
                test,
                "SELF_SUBJECT_ACCESS_REVIEW_FAILED",
                str(exc),
                ErrorCategory.DEPENDENCY,
                True,
            )

        if denied:
            return fail_result(test, f"missing required permissions: {', '.join(denied)}")
        return pass_result(test, "baseline cluster validation permissions are present")

    def pod_schedule_tiny(self, test: TestDefinition, run_id: str) -> TestResult:
        return self._run_probe_pod(
            test,
            run_id,
            suffix="podcheck",
            image=self.settings.pause_image,
            command=None,
            message_prefix="tiny probe pod",
        )

    def dns_resolve(self, test: TestDefinition, run_id: str) -> TestResult:
        return self._run_probe_pod(
            test,
            run_id,
            suffix="dnscheck",
            image=self.settings.dns_image,
            command=["sh", "-c", "nslookup kubernetes.default.svc.cluster.local || nslookup kubernetes.default.svc"],
            message_prefix="dns resolver pod",
            collect_logs=True,
        )

    def dns_service_present(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            services = self.clients.core.list_namespaced_service("kube-system").items
        except Exception as exc:
            return error_result(
                test,
                "LIST_DNS_SERVICES_FAILED",
                str(exc),
                ErrorCategory.DEPENDENCY,
                True,
            )

        for service in services:
            if is_dns_service(service):
                return pass_result(
                    test, f"found DNS service {service.metadata.namespace}/{service.metadata.name}"
                )
        return fail_result(test, "no kube-dns or coredns service found in kube-system")

    def pvc_bind(self, test: TestDefinition, run_id: str) -> TestResult:
        namespace = safe_name(run_id, "pvc")
        pvc_name = "probe-pvc"
        self._create_namespace(namespace, run_id)
        try:
            body = client.V1PersistentVolumeClaim(
                metadata=client.V1ObjectMeta(
                    name=pvc_name,
                    labels={"app.kubernetes.io/managed-by": "solr-metal", "sm.run/id": run_id},
                ),
                spec=client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteOnce"],
                    resources=client.V1VolumeResourceRequirements(
                        requests={"storage": self.settings.pvc_size}
                    ),
                ),
            )
            self.clients.core.create_namespaced_persistent_volume_claim(namespace, body)
            deadline = time.monotonic() + test.timeout_seconds
            while time.monotonic() < deadline:
                pvc = self.clients.core.read_namespaced_persistent_volume_claim(pvc_name, namespace)
                phase = pvc.status.phase or "Unknown"
                if phase == "Bound":
                    return pass_result(test, f"PVC {namespace}/{pvc_name} bound successfully")
                time.sleep(1)
            return timeout_result(test, "PVC did not reach Bound before timeout")
        except ApiException as exc:
            return error_result(test, "PVC_BIND_FAILED", str(exc), ErrorCategory.DEPENDENCY, True)
        finally:
            self._delete_namespace(namespace)

    def clusteroperators_healthy(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            payload = self.clients.custom.list_cluster_custom_object(
                group="config.openshift.io", version="v1", plural="clusteroperators"
            )
        except ApiException as exc:
            if exc.status in {403, 404}:
                return skip_result(
                    test,
                    "ClusterOperator API unavailable; treating as non-OpenShift or insufficient permissions",
                )
            return error_result(test, "CLUSTEROPERATORS_FAILED", str(exc), ErrorCategory.DEPENDENCY, True)

        items = payload.get("items", [])
        unhealthy = [item.get("metadata", {}).get("name", "unknown") for item in items if not cluster_operator_healthy(item)]
        if unhealthy:
            self.artifacts.write_json(test.id, "clusteroperators.json", payload)
            return fail_result(
                test,
                f"{len(unhealthy)}/{len(items)} ClusterOperators unhealthy: {', '.join(unhealthy)}",
            )
        return pass_result(test, f"{len(items)}/{len(items)} ClusterOperators healthy")

    def ingress_available(self, test: TestDefinition, run_id: str) -> TestResult:
        try:
            payload = self.clients.custom.list_namespaced_custom_object(
                group="operator.openshift.io",
                version="v1",
                namespace="openshift-ingress-operator",
                plural="ingresscontrollers",
            )
        except ApiException as exc:
            if exc.status in {403, 404}:
                return skip_result(
                    test,
                    "IngressController API unavailable; treating as non-OpenShift or insufficient permissions",
                )
            return error_result(test, "INGRESS_AVAILABILITY_FAILED", str(exc), ErrorCategory.DEPENDENCY, True)

        items = payload.get("items", [])
        unhealthy = [item.get("metadata", {}).get("name", "unknown") for item in items if not cluster_operator_healthy(item)]
        if unhealthy:
            self.artifacts.write_json(test.id, "ingresscontrollers.json", payload)
            return fail_result(
                test,
                f"{len(unhealthy)}/{len(items)} IngressControllers unhealthy: {', '.join(unhealthy)}",
            )
        return pass_result(test, f"{len(items)}/{len(items)} IngressControllers healthy")

    def image_pull_sanity(self, test: TestDefinition, run_id: str) -> TestResult:
        return self._run_probe_pod(
            test,
            run_id,
            suffix="imagepull",
            image=self.settings.pause_image,
            command=None,
            message_prefix="image pull probe pod",
        )

    def _run_probe_pod(
        self,
        test: TestDefinition,
        run_id: str,
        suffix: str,
        image: str,
        command: list[str] | None,
        message_prefix: str,
        collect_logs: bool = False,
    ) -> TestResult:
        namespace = safe_name(run_id, suffix)
        pod_name = "probe"
        self._create_namespace(namespace, run_id)

        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels={
                    "app.kubernetes.io/managed-by": "solr-metal",
                    "sm.run/id": run_id,
                    "sm.test/id": test.id,
                },
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[
                    client.V1Container(
                        name="probe",
                        image=image,
                        command=command,
                    )
                ],
            ),
        )
        try:
            self.clients.core.create_namespaced_pod(namespace, pod)
            deadline = time.monotonic() + test.timeout_seconds
            while time.monotonic() < deadline:
                current = self.clients.core.read_namespaced_pod(pod_name, namespace)
                phase = current.status.phase or "Unknown"
                blocked_reason = pod_blocked_reason(current)
                if phase in {"Running", "Succeeded"}:
                    if collect_logs:
                        self._capture_pod_logs(test.id, namespace, pod_name)
                    return pass_result(test, f"{message_prefix} reached {phase} in {namespace}")
                if phase == "Failed":
                    self._capture_pod_state(test.id, current)
                    self._capture_pod_logs(test.id, namespace, pod_name)
                    return fail_result(test, f"{message_prefix} failed in {namespace}")
                if blocked_reason:
                    self._capture_pod_state(test.id, current)
                    self._capture_pod_logs(test.id, namespace, pod_name)
                    return fail_result(test, f"{message_prefix} stalled: {blocked_reason}")
                time.sleep(1)
            current = self.clients.core.read_namespaced_pod(pod_name, namespace)
            self._capture_pod_state(test.id, current)
            self._capture_pod_logs(test.id, namespace, pod_name)
            return timeout_result(test, f"{message_prefix} did not complete before timeout")
        except ApiException as exc:
            return error_result(
                test,
                "PROBE_POD_FAILED",
                str(exc),
                ErrorCategory.DEPENDENCY,
                True,
            )
        finally:
            self._delete_namespace(namespace)

    def _create_namespace(self, namespace: str, run_id: str) -> None:
        body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace,
                labels={"app.kubernetes.io/managed-by": "solr-metal", "sm.run/id": run_id},
            )
        )
        self.clients.core.create_namespace(body)

    def _delete_namespace(self, namespace: str) -> None:
        try:
            self.clients.core.delete_namespace(namespace)
        except Exception:
            return

    def _capture_pod_state(self, test_id: str, pod: client.V1Pod) -> None:
        payload = self.clients.api_client.sanitize_for_serialization(pod)
        self.artifacts.write_json(test_id, "pod.json", payload)

    def _capture_pod_logs(self, test_id: str, namespace: str, pod_name: str) -> None:
        try:
            logs = self.clients.core.read_namespaced_pod_log(pod_name, namespace)
        except Exception:
            return
        self.artifacts.write_text(test_id, "pod.log", logs)


def is_node_ready(node: client.V1Node) -> bool:
    conditions = node.status.conditions or []
    return any(condition.type == "Ready" and condition.status == "True" for condition in conditions)


def cluster_operator_healthy(item: dict[str, Any]) -> bool:
    conditions = item.get("status", {}).get("conditions", [])
    available = any(cond.get("type") == "Available" and cond.get("status") == "True" for cond in conditions)
    degraded = any(cond.get("type") == "Degraded" and cond.get("status") == "True" for cond in conditions)
    return available and not degraded


def is_dns_service(service: client.V1Service) -> bool:
    labels = service.metadata.labels or {}
    return (
        service.metadata.namespace == "kube-system"
        and (
            service.metadata.name in {"kube-dns", "coredns"}
            or labels.get("k8s-app") == "kube-dns"
            or labels.get("app.kubernetes.io/name") == "coredns"
        )
    )


def pod_blocked_reason(pod: client.V1Pod) -> str | None:
    for condition in pod.status.conditions or []:
        if condition.type == "PodScheduled" and condition.status == "False":
            return f"{condition.reason}: {condition.message}"
    for status in pod.status.container_statuses or []:
        state = status.state
        if state and state.waiting:
            return f"{state.waiting.reason}: {state.waiting.message}"
        if state and state.terminated and state.terminated.exit_code != 0:
            return f"{state.terminated.reason}: {state.terminated.message}"
    return None


def safe_name(run_id: str, suffix: str) -> str:
    normalized = run_id.lower().replace(":", "-").replace(".", "-")
    return f"sm-{normalized}-{suffix}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def pass_result(test: TestDefinition, message: str) -> TestResult:
    now = utc_now()
    return TestResult(
        id=test.id,
        name=test.name,
        module=test.module,
        kind=test.kind,
        status=Status.PASS,
        started_at=now,
        finished_at=now,
        duration=timedelta(),
        message=message,
    )


def fail_result(test: TestDefinition, message: str) -> TestResult:
    now = utc_now()
    return TestResult(
        id=test.id,
        name=test.name,
        module=test.module,
        kind=test.kind,
        status=Status.FAIL,
        started_at=now,
        finished_at=now,
        duration=timedelta(),
        message=message,
    )


def skip_result(test: TestDefinition, message: str) -> TestResult:
    now = utc_now()
    return TestResult(
        id=test.id,
        name=test.name,
        module=test.module,
        kind=test.kind,
        status=Status.SKIP,
        started_at=now,
        finished_at=now,
        duration=timedelta(),
        message=message,
    )


def timeout_result(test: TestDefinition, message: str) -> TestResult:
    now = utc_now()
    return TestResult(
        id=test.id,
        name=test.name,
        module=test.module,
        kind=test.kind,
        status=Status.TIMEOUT,
        started_at=now,
        finished_at=now,
        duration=timedelta(),
        error=make_error("TEST_TIMEOUT", message, ErrorCategory.TIMEOUT, True).model_dump(mode="json"),
    )


def error_result(
    test: TestDefinition,
    code: str,
    message: str,
    category: ErrorCategory,
    retryable: bool = False,
) -> TestResult:
    now = utc_now()
    return TestResult(
        id=test.id,
        name=test.name,
        module=test.module,
        kind=test.kind,
        status=Status.ERROR,
        started_at=now,
        finished_at=now,
        duration=timedelta(),
        error=make_error(code, message, category, retryable).model_dump(mode="json"),
    )
