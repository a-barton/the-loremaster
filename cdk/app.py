#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.config import ConfigStack
from stacks.networking import NetworkingStack
from stacks.storage import StorageStack
from stacks.compute import ComputeStack

APP_NAME = "TheLoremaster"  # Use Pascal (title) case here

app = cdk.App(default_stack_synthesizer=cdk.CliCredentialsStackSynthesizer())

config = ConfigStack(app, f"{APP_NAME}ConfigStack", app_name=APP_NAME)
networking = NetworkingStack(app, f"{APP_NAME}NetworkingStack", app_name=APP_NAME)
storage = StorageStack(
    app,
    f"{APP_NAME}StorageStack",
    app_name=APP_NAME,
    networking=networking,
)
compute = ComputeStack(
    app,
    f"{APP_NAME}ComputeStack",
    app_name=APP_NAME,
    config=config,
    networking=networking,
    storage=storage,
)

app.synth()
