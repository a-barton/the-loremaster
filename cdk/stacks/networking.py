from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct

##################
## Parent Stack ##
##################


class NetworkingStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, app_name: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.app_name = app_name

        self.vpc_construct = VPCConstruct(
            self, f"{self.app_name}VPCConstruct", app_name=self.app_name
        )
        self.security_groups = SecurityGroupConstruct(
            self,
            f"{self.app_name}SecurityGroupConstruct",
            app_name=self.app_name,
            vpc=self.vpc_construct.vpc,
        )
        self.security_groups.add_sg_rules()


################
## Constructs ##
################


class VPCConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.vpc = ec2.Vpc(
            self,
            f"{app_name}VPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                ),
            ],
        )


class SecurityGroupConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        vpc: ec2.IVpc,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc

        self.rds_sg = self.create_sg(
            name=f"{app_name}RDSSecurityGroup",
            description="Allow inbound traffic from ECS task",
        )

        self.ecs_sg = self.create_sg(
            name=f"{app_name}ECSSecurityGroup",
            description="Allow outbound traffic to internet and to RDS database",
        )

        self.pgvector_lambda_sg = self.create_sg(
            name=f"{app_name}PGVectorLambdaSecurityGroup",
            description="Allow outbound traffic to RDS cluster",
        )

    def create_sg(self, name: str, description: str) -> ec2.SecurityGroup:
        return ec2.SecurityGroup(
            self,
            name,
            security_group_name=name,
            description=description,
            vpc=self.vpc,
            allow_all_outbound=False,
        )

    # def add_sg_rules(self):
    #     self.rds_sg.add_ingress_rule(
    #         peer=ec2.Peer.security_group_id(self.ecs_sg.security_group_id),
    #         connection=ec2.Port.tcp(5432),
    #         description="Allow inbound traffic from ECS task",
    #     )
    #     self.rds_sg.add_ingress_rule(
    #         peer=ec2.Peer.security_group_id(self.pgvector_lambda_sg.security_group_id),
    #         connection=ec2.Port.tcp(5432),
    #         description="Allow inbound traffic from PGVector installation Lambda",
    #     ),
    #     self.ecs_sg.add_egress_rule(
    #         peer=ec2.Peer.security_group_id(self.rds_sg.security_group_id),
    #         connection=ec2.Port.tcp(5432),
    #         description="Allow outbound traffic to RDS database",
    #     )
    #     self.ecs_sg.add_egress_rule(
    #         peer=ec2.Peer.any_ipv4(),
    #         connection=ec2.Port.tcp(443),
    #         description="Allow outbound HTTPS traffic to internet (for Discord bot)",
    #     )
    #     self.pgvector_lambda_sg.add_egress_rule(
    #         peer=ec2.Peer.security_group_id(self.rds_sg.security_group_id),
    #         connection=ec2.Port.tcp(5432),
    #         description="Allow outbound traffic to RDS cluster",
    #     )

    def add_sg_rules(self):
        self.rds_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow inbound traffic from ECS task",
        )
        self.rds_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow inbound traffic from PGVector installation Lambda",
        ),
        self.ecs_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow outbound traffic to RDS database",
        )
        self.ecs_sg.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow outbound HTTPS traffic to internet (for Discord bot)",
        )
        self.pgvector_lambda_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow outbound traffic to RDS cluster",
        )
        self.pgvector_lambda_sg.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow outbound HTTPS traffic to internet (for Secrets Manager public API)",
        )
