import json
from datetime import datetime
from aws_cdk import (
    Stack,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    Duration,
    aws_ec2 as ec2,
    RemovalPolicy,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    custom_resources as cr,
)
import aws_cdk as cdk
from constructs import Construct
from .networking import NetworkingStack


class StorageStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        networking: NetworkingStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name

        self.create_rds_cluster(
            dbname="vectors",
            username="loremaster",
            networking=networking,
        )

        # self.create_pgvector_installation_custom_resource(
        #     code_asset_path="stacks/custom_resources/install_pgvector",
        #     handler="install_pgvector.handler",
        #     networking=networking,
        # )

    def create_rds_cluster(
        self, dbname: str, username: str, networking: NetworkingStack
    ):
        self.rds_creds_secret = secretsmanager.Secret(
            self,
            f"{self.app_name}RDSCredsSecret",
            description="Store RDS credentials",
            secret_name=f"{self.app_name}RDSCredsSecret{datetime.now().strftime('%Y%m%d')}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {
                        "username": username,
                        "password": "{password}",
                        "dbname": dbname,
                    }
                ),
                generate_string_key="password",
                password_length=16,
                exclude_characters="'@/\"",
            ),
        )

        self.rds_cluster = rds.ServerlessCluster(
            self,
            f"{self.app_name}RDSCluster",
            cluster_identifier=f"{self.app_name}RDSCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_13_12  # latest supported version for Aurora Serverless v1
            ),
            credentials=rds.Credentials.from_secret(self.rds_creds_secret),
            vpc=networking.vpc_construct.vpc,
            removal_policy=RemovalPolicy.DESTROY,
            default_database_name=dbname,
            vpc_subnets=ec2.SubnetSelection(
                subnets=networking.vpc_construct.vpc.isolated_subnets,
            ),
            security_groups=[networking.security_groups.rds_sg],
            scaling=rds.ServerlessScalingOptions(
                auto_pause=Duration.minutes(5),
                max_capacity=rds.AuroraCapacityUnit.ACU_2,
            ),
            enable_data_api=True,
        )

    # def create_pgvector_installation_custom_resource(
    #     self, code_asset_path: str, handler: str, networking: NetworkingStack
    # ):
    #     self.pgvector_lambda_role = iam.Role(
    #         self,
    #         f"{self.app_name}PGVectorLambdaRole",
    #         role_name=f"{self.app_name}PGVectorLambdaRole",
    #         assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    #         managed_policies=[
    #             iam.ManagedPolicy.from_managed_policy_arn(
    #                 self,
    #                 f"{self.app_name}PGVectorLambdaRoleBasicAccessPolicy",
    #                 managed_policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    #             ),
    #             iam.ManagedPolicy.from_managed_policy_arn(
    #                 self,
    #                 f"{self.app_name}PGVectorLambdaRoleVPCAccessPolicy",
    #                 managed_policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
    #             ),
    #             iam.PolicyStatement(
    #                 actions=["secretsmanager:GetSecret"],
    #                 resources=[self.rds_creds_secret.secret_arn],

    #             ),
    #         ],
    #     )

    #     self.pgvector_lambda = lambda_.Function(
    #         self,
    #         f"{self.app_name}PGVectorLambda",
    #         function_name=f"{self.app_name}PGVectorLambda",
    #         runtime=lambda_.Runtime.PYTHON_3_10,
    #         role=self.pgvector_lambda_role,
    #         handler=handler,
    #         code=lambda_.Code.from_asset(code_asset_path),
    #         environment={
    #             "DB_CREDS_SECRET_NAME": self.rds_creds_secret.secret_name,
    #         },
    #         vpc=networking.vpc_construct.vpc,
    #         security_groups=[networking.security_groups.pgvector_lambda_sg],
    #         log_group=logs.LogGroup(
    #             self,
    #             f"{self.app_name}PGVectorLambdaLogGroup",
    #             log_group_name=f"{self.app_name}PGVectorLambdaLogGroup",
    #             retention=logs.RetentionDays.ONE_WEEK,
    #         ),
    #     )
    #     self.pgvector_lambda.node.add_dependency(self.rds_cluster)

    #     self.custom_resource_provider = cr.Provider(
    #         self,
    #         f"{self.app_name}CustomResourceProvider",
    #         on_event_handler=self.pgvector_lambda,
    #         vpc=networking.vpc_construct.vpc,
    #         security_groups=[networking.security_groups.pgvector_lambda_sg],
    #     )
    #     self.custom_resource_provider.node.add_dependency(self.rds_cluster)
    #     self.custom_resource_provider.node.add_dependency(self.pgvector_lambda)
        

    #     self.custom_resource = cdk.CustomResource(
    #         self,
    #         f"{self.app_name}PGVectorInstallationCustomResource",
    #         service_token=self.custom_resource_provider.service_token,
    #         resource_type="Custom::PGVectorInstallation",
    #         properties={
    #             "FunctionName": self.pgvector_lambda.function_name,
    #         },
    #         removal_policy=RemovalPolicy.DESTROY,
    #     )
    #     self.custom_resource.node.add_dependency(self.rds_cluster)
    #     self.custom_resource.node.add_dependency(self.pgvector_lambda)
    #     self.custom_resource.node.add_dependency(self.custom_resource_provider)
