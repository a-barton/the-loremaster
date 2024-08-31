from aws_cdk import (
    Stack,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_ec2 as ec2,
    RemovalPolicy,
    aws_iam as iam,
    aws_lambda as lambda_,
    custom_resources as cr,
)
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

        self.create_pgvector_installation_custom_resource(
            code_asset_path="stacks/custom_resources/install_pgvector",
            networking=networking,
        )

    def create_rds_cluster(
        self, dbname: str, username: str, networking: NetworkingStack
    ):
        self.rds_creds_secret = secretsmanager.Secret(
            self,
            f"{self.app_name}RDSCredsSecret",
            description="Store RDS credentials",
            secret_name=f"{self.app_name}RDSCredsSecret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=f"username={username},password={{password}},dbname={dbname}",  # Double {{}} around password which will be replaced with actual generated password
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
                subnets=networking.vpc_construct.vpc.private_subnets,
            ),
            security_groups=[networking.security_groups.rds_sg],
        )

    def create_pgvector_installation_custom_resource(
        self, code_asset_path: str, networking: NetworkingStack
    ):
        self.pgvector_lambda_role = iam.Role(
            self,
            f"{self.app_name}PGVectorLambdaRole",
            role_name=f"{self.app_name}PGVectorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    f"{self.app_name}PGVectorLambdaRoleBasicAccessPolicy",
                    managed_policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    f"{self.app_name}PGVectorLambdaRoleVPCAccessPolicy",
                    managed_policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
                ),
            ],
        )

        self.pgvector_lambda = lambda_.Function(
            self,
            f"{self.app_name}PGVectorLambda",
            function_name=f"{self.app_name}PGVectorLambda",
            runtime=lambda_.Runtime.PYTHON_3_10,
            role=self.pgvector_lambda_role,
            handler="pgvector_lambda.lambda_handler",
            code=lambda_.Code.from_asset(code_asset_path),
            vpc=networking.vpc_construct.vpc,
            security_groups=[networking.security_groups.pgvector_lambda_sg],
        )

        self.custom_resource_provider = cr.Provider(
            self,
            f"{self.app_name}CustomResourceProvider",
            on_event_handler=self.pgvector_lambda,
            role=self.pgvector_lambda_role,
            vpc=networking.vpc_construct.vpc,
            security_groups=[networking.security_groups.pgvector_lambda_sg],
        )
