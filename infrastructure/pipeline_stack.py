import os

from constructs import Construct

from aws_cdk import (
    Stack,
    aws_codepipeline as codepipeline,
    aws_codebuild as codebuild,
    aws_codepipeline_actions as codepipeline_actions,
    aws_iam as iam,
)

from repo_connection import RepoConnection


class PipelineStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ecr_repository,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.source = RepoConnection(self)

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name="CICD_Pipeline",
            cross_account_keys=False,
            pipeline_type=codepipeline.PipelineType.V2,
            execution_mode=codepipeline.ExecutionMode.QUEUED,
        )

        # Code quality / unit test project
        code_quality_build = codebuild.PipelineProject(
            self,
            "CodeQuality",
            build_spec=codebuild.BuildSpec.from_source_filename(
                "buildspec_test.yml"
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxLambdaBuildImage.AMAZON_LINUX_2023_PYTHON_3_12,
                compute_type=codebuild.ComputeType.LAMBDA_10GB,
            ),
        )

        # Docker build project
        docker_build_project = codebuild.PipelineProject(
            self,
            "DockerBuild",
            build_spec=codebuild.BuildSpec.from_source_filename(
                "buildspec_docker.yml"
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
                compute_type=codebuild.ComputeType.LARGE,
                environment_variables={
                    "IMAGE_TAG": codebuild.BuildEnvironmentVariable(
                        type=codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                        value="latest",
                    ),
                    "IMAGE_REPO_URI": codebuild.BuildEnvironmentVariable(
                        type=codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                        value=ecr_repository.repository_uri,
                    ),
                    "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(
                        type=codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                        value=os.environ["CDK_DEFAULT_REGION"],
                    ),
                },
            ),
        )

        # Allow CodeBuild to push the Docker image to ECR
        docker_build_project.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetRepositoryPolicy",
                    "ecr:DescribeRepositories",
                    "ecr:ListImages",
                    "ecr:DescribeImages",
                    "ecr:BatchGetImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                ],
                resources=["*"],
            )
        )

        # Pipeline artifacts
        source_output = codepipeline.Artifact()
        unit_test_output = codepipeline.Artifact()
        docker_build_output = codepipeline.Artifact()

        # Source stage
        source_action = self.source.source_action(source_output)

        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action],
        )

        # Code quality stage
        build_action = codepipeline_actions.CodeBuildAction(
            action_name="Unit-Test",
            project=code_quality_build,
            input=source_output,
            outputs=[unit_test_output],
        )

        pipeline.add_stage(
            stage_name="Code-Quality-Testing",
            actions=[build_action],
        )

        # Docker build and push stage
        docker_build_action = codepipeline_actions.CodeBuildAction(
            action_name="Docker-Build",
            project=docker_build_project,
            input=source_output,
            outputs=[docker_build_output],
        )

        pipeline.add_stage(
            stage_name="Docker-Push-ECR",
            actions=[docker_build_action],
        )