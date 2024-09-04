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
            cpu=1024,
            memory_limit_mib=2048,
            ephemeral_storage_gib=30,
        )

        self.task_definition.add_container(
            f"{self.app_name}Container",
            # image=ecs.ContainerImage.from_asset("/home/mantid/the-loremaster/"),
            image=ecs.ContainerImage.from_registry(
                "docker.io/mantidau/the-loremaster:latest"
            ),
            container_name=self.app_name,
            memory_limit_mib=2048,
            cpu=1024,
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
                    secret=storage.rds_creds_secret, field="host"
                ),
                "POSTGRES_DBNAME": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="dbname"
                ),
                "POSTGRES_PORT": ecs.Secret.from_secrets_manager(
                    secret=storage.rds_creds_secret, field="port"
                ),
            },
        )

        for secret_name, ssm_secure_param in config.secrets.items():
            self.task_definition.default_container.add_secret(
                name=secret_name,
                secret=ecs.Secret.from_ssm_parameter(ssm_secure_param),
            )

        self.task_definition.default_container.add_to_execution_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[storage.rds_creds_secret.secret_arn],
            )
        )

        self.fargate_service = ecs.FargateService(
            self,
            f"{self.app_name}FargateService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT",
                    weight=1,
                )
            ],
            desired_count=1,
            security_groups=[self.security_groups.ecs_sg],
            vpc_subnets=ec2.SubnetSelection(
                subnets=networking.vpc_construct.vpc.public_subnets
            ),
            assign_public_ip=True, # Needs to be enabled for ECS task to have outbound internet access
            enable_execute_command=True,
        )
