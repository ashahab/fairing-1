from fairing.architectures.kubeflow.basic import BasicArchitecture
from fairing.backend.kubeflow import KubeflowBackend
from fairing.notebook_helper import get_notebook_name
import subprocess
import os
import logging
logger = logging.getLogger(__name__)

class CMTraining(BasicArchitecture):
    def __init__(self, ps_count, worker_count, notebook):
        self.ps_count = ps_count
        self.worker_count = worker_count
        self.notebook = notebook

    def add_jobs(self, svc, count, repository, img, name, volumes, volume_mounts):
        img = os.environ['IMAGE_NAME'] or img
        cpu_img = os.environ["CPU_IMAGE_NAME"]
        nb_name = self.notebook or get_notebook_name()
        nb_full_path = os.path.join(os.getcwd(), nb_name)
        cmd = "jupyter nbconvert --to python {} --output /tmp/code".format(nb_full_path).split()
        subprocess.check_call(cmd)
        tfjobs = []
        # append configmap to volume and volumeMounts
        with open('/tmp/code.py', 'rb') as f:
            code = f.read()
        configMap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
               "name": name
            },
            "data": {
                "code.py": code
            }
        }
        svc["configMap"] = configMap
        volume_mounts = volume_mounts or []
        volume_mounts.append({
            "name": "code",
            "mountPath": "/code"
        })
        volumes = volumes or []
        volumes.append({
            "name": 'code',
            "configMap": {
                "name": name
            }
        })
        cmd = "python /code/code.py".split()
        # TODO: This should come from configs
        for ix in range(count):
            tfjobs.append({
                "apiVersion": "kubeflow.org/v1alpha2",
                "kind": "TFJob",
                "metadata": {
                    "name": "{}-{}".format(name, ix)
                },
                "spec": {
                    "tfReplicaSpecs": {
                        "Chief":
                        {
                            "tfReplicaType": "MASTER",
                            "replicas": 1,
                            "template": {
                                "spec": {
                                    "securityContext": {
                                        "runAsUser": 1000,
                                        "fsGroup": 1000
                                    },
                                    "containers": [
                                        {
                                            "name": "tensorflow",
                                            "image": img,
                                            "resources": {
                                                "limits": {
                                                    "nvidia.com/gpu": 1
                                                }
                                            },
                                            "volumeMounts": volume_mounts,
                                            "command": cmd
                                        }
                                    ],
                                    "volumes": volumes
                                }
                            }
                        },
                        "Worker":
                        {
                            "tfReplicaType": "WORKER",
                            "replicas": self.worker_count,
                            "template": {
                                "spec": {
                                    "securityContext": {
                                        "runAsUser": 1000,
                                        "fsGroup": 1000
                                    },
                                    "containers": [
                                        {
                                            "name": "tensorflow",
                                            "image": img,
                                            "resources": {
                                               "limits": {
                                                   "nvidia.com/gpu": 1
                                               }
                                            },
                                            "volumeMounts": volume_mounts,
                                            "command": cmd
                                        }
                                    ],
                                    "volumes": volumes
                                }
                            }
                        },
                        "Evaluator":
                            {
                                "tfReplicaType": "WORKER",
                                "replicas": 1,
                                "template": {
                                    "spec": {
                                        "securityContext": {
                                            "runAsUser": 1000,
                                            "fsGroup": 1000
                                        },
                                        "containers": [
                                            {
                                                "name": "tensorflow",
                                                "image": img,
                                                "resources": {
                                                    "limits": {
                                                        "nvidia.com/gpu": 1
                                                    }
                                                },
                                                "volumeMounts": volume_mounts,
                                                "command": cmd
                                            }
                                        ],
                                        "volumes": volumes
                                    }
                                }
                            },
                        "Ps":
                        {
                            "tfReplicaType": "PS",
                            "replicas": self.ps_count,
                            "template": {
                                "spec": {
                                    "nodeSelector": {
                                        "node-role.kubernetes.io/cpu": "cpu"
                                    },
                                    "securityContext": {
                                        "runAsUser": 1000,
                                        "fsGroup": 1000
                                    },
                                    "containers": [
                                        {
                                            "name": "tensorflow",
                                            "image": cpu_img,
                                            "volumeMounts": volume_mounts,
                                            "command": cmd
                                        }],
                                    "volumes": volumes
                                }
                            }
                        }
                    },
                }
            })

        svc["tfJobs"] = tfjobs
        return svc

    def get_associated_backend(self):
        return KubeflowBackend()
