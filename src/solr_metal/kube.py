from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


@dataclass
class KubeClients:
    api_client: client.ApiClient
    core: client.CoreV1Api
    auth: client.AuthorizationV1Api
    version: client.VersionApi
    custom: client.CustomObjectsApi


def load_clients() -> KubeClients:
    return load_clients_from(None)


def load_clients_from(kubeconfig: Path | None = None) -> KubeClients:
    if kubeconfig:
        config.load_kube_config(config_file=str(kubeconfig))
    else:
        try:
            config.load_kube_config()
        except ConfigException:
            config.load_incluster_config()

    api_client = client.ApiClient()
    return KubeClients(
        api_client=api_client,
        core=client.CoreV1Api(api_client),
        auth=client.AuthorizationV1Api(api_client),
        version=client.VersionApi(api_client),
        custom=client.CustomObjectsApi(api_client),
    )
