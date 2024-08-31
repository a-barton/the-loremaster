import os
from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_ec2 as ec2,
)
from constructs import Construct
from .config import ConfigStack
from .networking import NetworkingStack
from .storage import StorageStack

##################
## Parent Stack ##
##################


class ComputeStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        config: ConfigStack,
        networking: NetworkingStack,
        storage: StorageStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.app_name = app_name

        self.ecs = ECS(
            self,
            f"{self.app_name}ECS",
            app_name=self.app_name,
            config=config,
            networking=networking,
            storage=storage,
        )


################
## Constructs ##
################


class ECS(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        config: ConfigStack,
        networking: NetworkingStack,
        storage: StorageStack,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.vpc = networking.vpc_construct.vpc
        self.security_groups = networking.security_groups

        self.cluster = ecs.Cluster(
            self,
            f"{self.app_name}ECSCluster",
            cluster_name=f"{self.app_name}ECSCluster",
            vpc=self.vpc,
            enable_fargate_capacity_providers=True,
        )

        self.task_role = iam.Role(
            self,
            f"{self.app_name}ECSTaskRole",
            role_name=f"{self.app_name}ECSTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        self.task_definition = ecs.FargateTaskDefinition(
            self,
            f"{self.app_name}TaskDefinition",
        )

        self.task_definition.add_container(
            f"{self.app_name}Container",
            # image=ecs.ContainerImage.from_asset(
            #     directory=os.path.join(
            #         os.path.dirname(__file__), "..", ".."
            #     )  # Reference Dockerfile in root of repo
            # ),
            image=ecs.ContainerImage.from_registry("docker.io/python:3.9-slim-buster"),
            container_name=self.app_name,
            memory_limit_mib=512,
            cpu=256,
            essential=True,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=f"{self.app_name}Task",
            ),
            environment={
                key: param.string_value for key, param in config.env_vars.items()
            },
            secrets={
                "POSTGRES_USER": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="username"
                ),
                "POSTGRES_PASSWORD": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="password"
                ),
                "POSTGRES_HOST": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="hostname"
                ),
                "POSTGRES_DBNAME": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="dbname"
                ),
                "POSTGRES_PORT": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="port"
                ),
            },
        )

        for ssm_secure_param in config.secrets.values():
            self.task_definition.default_container.add_secret(
                name=ssm_secure_param.parameter_name,
                secret=ecs.Secret.from_ssm_parameter(ssm_secure_param),
            )

        self.fargate_service = ecs.FargateService(
            self,
            f"{self.app_name}FargateService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=1,
            security_groups=[self.security_groups.ecs_sg],
            vpc_subnets=ec2.SubnetSelection(
                subnets=networking.vpc_construct.vpc.public_subnets
            ),
            assign_public_ip=False,
            enable_execute_command=True,
        )
