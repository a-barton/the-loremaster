import os
from aws_cdk import Stack, aws_ssm as ssm
from constructs import Construct
import boto3
from botocore.exceptions import ClientError
from typing import Tuple

##################
## Parent Stack ##
##################


class ConfigStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, app_name: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.env_vars = {}
        self.secrets = {}

        with open(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"), "r"
        ) as env_file:
            for line in env_file:
                key, value = line.strip().split("=")
                if "POSTGRES" in key:
                    continue  # Ignore local POSTGRES related .env variables - the storage stack will create fresh Postgres creds for RDS
                param_name = f"{self.app_name}SSMSecret{key.replace('SECRET__', '')}"
                if line.startswith("SECRET__"):
                    if not self.check_param_exists(param_name):
                        self.create_ssm_secret(param_name, value)
                    self.secrets[key] = (
                        ssm.StringParameter.from_secure_string_parameter_attributes(
                            self,
                            param_name,
                            parameter_name=param_name,
                        )
                    )
                else:
                    self.env_vars[key] = self.create_ssm_param(
                        key=key,
                        value=value,
                    )

    def check_param_exists(self, param_name: str) -> bool:
        try:
            ssm_client = boto3.client("ssm")
            ssm_client.get_parameter(Name=param_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                return False
            else:
                raise e

    def create_ssm_secret(self, param_name: str, value: str) -> None:
        ssm_client = boto3.client("ssm")
        ssm_client.put_parameter(
            Name=param_name,
            Type="SecureString",
            Value=value,
        )

    def create_ssm_param(self, key: str, value: str) -> ssm.StringParameter:
        return ssm.StringParameter(
            self,
            f"{self.app_name}SSMParam{key}",
            parameter_name=key,
            string_value=value,
        )
