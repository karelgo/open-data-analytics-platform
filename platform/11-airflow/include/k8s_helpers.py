"""Small shared pod definitions for the Dutch IT jobs pipeline."""

from kubernetes.client.models import (
    V1ConfigMapVolumeSource,
    V1EnvVar,
    V1EnvVarSource,
    V1ResourceRequirements,
    V1SecretKeySelector,
    V1Volume,
    V1VolumeMount,
)

SMALL_POD_RESOURCES = V1ResourceRequirements(
    requests={"cpu": "100m", "memory": "256Mi"}, limits={"cpu": "500m", "memory": "1Gi"}
)


def ca_volume():
    return V1Volume(
        name="platform-ca",
        config_map=V1ConfigMapVolumeSource(name="platform-ca-bundle"),
    )


def ca_mount():
    return V1VolumeMount(
        name="platform-ca", mount_path="/etc/platform-ca", read_only=True
    )


def om_config_volume():
    return V1Volume(
        name="om-config",
        config_map=V1ConfigMapVolumeSource(name="openmetadata-platform-config"),
    )


def om_config_mount():
    return V1VolumeMount(name="om-config", mount_path="/config", read_only=True)


def secret_env(name, secret, key):
    return V1EnvVar(
        name=name,
        value_from=V1EnvVarSource(
            secret_key_ref=V1SecretKeySelector(name=secret, key=key)
        ),
    )
