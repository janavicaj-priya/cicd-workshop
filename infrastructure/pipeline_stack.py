from aws_cdk import (
    Stack,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
)
from constructs import Construct

from repo_connection import RepoConnection


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        source_output = codepipeline.Artifact()
        repo_connection = RepoConnection(self)

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name="CICD_Pipeline",
            cross_account_keys=False,
            pipeline_type=codepipeline.PipelineType.V2,
            execution_mode=codepipeline.ExecutionMode.QUEUED,
        )

        code_quality_build = codebuild.PipelineProject(
            self,
            "CodeQuality",
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec_test.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxLambdaBuildImage.AMAZON_LINUX_2023_PYTHON_3_12,
                compute_type=codebuild.ComputeType.LAMBDA_10GB,
            ),
        )

        source_output = codepipeline.Artifact()
        unit_test_output = codepipeline.Artifact()

        source_action = self.source.source_action(source_output)

        pipeline.add_stage(stage_name="Source", actions=[source_action])
        build_action = codepipeline_actions.CodeBuildAction(
            action_name="Unit-Test",
            project=code_quality_build,
            input=source_output,  # The build action must use the source action output as input.
            outputs=[unit_test_output],
        )

        pipeline.add_stage(stage_name="Code-Quality-Testing", actions=[build_action])




        pipeline.add_stage(
            stage_name="Source",
            actions=[repo_connection.source_action(source_output)],
        )

        validation_project = codebuild.PipelineProject(
            self,
            "ApplicationValidation",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "install": {
                            "commands": [
                                "python -m pip install --disable-pip-version-check -r hello-app/requirements.txt"
                            ]
                        },
                        "build": {
                            "commands": [
                                "python -m compileall -q hello-app",
                                (
                                    "python -c \"import sys; "
                                    "sys.path.insert(0, 'hello-app'); "
                                    "import main; "
                                    "client = main.app.test_client(); "
                                    "health = client.get('/healthcheck'); "
                                    "assert health.status_code == 200 and "
                                    "health.get_json() == {'health_status': 'OK'}; "
                                    "assert client.get('/').status_code == 200\""
                                ),
                            ]
                        },
                    },
                }
            ),
        )
        pipeline.add_stage(
            stage_name="Validate",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="ValidateFlaskApp",
                    project=validation_project,
                    input=source_output,
                )
            ],
        )