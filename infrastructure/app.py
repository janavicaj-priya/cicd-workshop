#!/usr/bin/env python3
import aws_cdk as cdk

from infrastructure.infrastructure_stack import InfrastructureStack
from pipeline_stack import PipelineStack
from infrastructure.ecr_stack import EcrStack

app = cdk.App()

InfrastructureStack(
    app,
    "InfrastructureStack",
)

ecr_stack = EcrStack(
    app,
    "EcrStack",
)
pipeline_stack = PipelineStack(
    app,
    "PipelineStack",
     ecr_repository=ecr_stack.ecr_data,
)



app.synth()
