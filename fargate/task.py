import json
import os

import click
import time
import boto3
import botocore
import arrow
from box import Box

from fargate.vpc import get_network_info


@click.group(name="task")
def tasks():
    pass


@tasks.command(name="run")
@click.option("--security-group", multiple=True, required=True)
@click.option("--subnet", required=True)
@click.option("--vpc", required=True, default=os.getenv("FARGATE_VPC_NAME"))
@click.option("--command")
@click.option("--container")
@click.option("--debug", is_flag=True)
@click.option("--wait", is_flag=True, default=False)
@click.argument("task-definition")
@click.pass_obj
@click.pass_context
def task_run(ctx, obj, vpc, security_group, subnet, task_definition, container, command, debug, wait):
    vpc_id, security_groups, subnets = get_network_info(vpc, security_group, subnet)
    client = boto3.client("ecs")

    container = container or task_definition.split(":")[0]

    launch_config = dict(
        cluster=obj.cluster,
        launchType="FARGATE",
        startedBy="github-actions",
        taskDefinition=task_definition,
    )

    if command:
        launch_config["overrides"] = {"containerOverrides": [{"name": container, "command": command.split(" ")}]}

    if all((vpc_id, security_groups, subnets)):
        launch_config["networkConfiguration"] = {
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "DISABLED",
            }
        }

    if debug:
        click.secho(json.dumps(launch_config, indent=2), fg="blue")

    run = client.run_task(**launch_config)

    task_arn = run["tasks"][0]["taskArn"]
    task_definition = run["tasks"][0]["taskDefinitionArn"]

    if debug:
        click.secho(f"task_arn::{task_arn}", fg="green")
        click.secho(f"task_definition::{task_definition}", fg="green")

    click.echo(f"::set-output name=task_arn::{task_arn}")
    click.echo(f"::set-output name=task_definition::{task_definition}")

    if wait:
        ctx.invoke(task_wait, task_arn=task_arn)


@tasks.command(name="wait-for")
@click.option("--state", type=click.Choice(["running", "stopped"]), default="stopped")
@click.option("--delay", default=10)
@click.option("--attempts", default=60)
@click.argument("task-arn")
@click.pass_obj
@click.pass_context
def task_wait(ctx, obj, state, delay, attempts, task_arn):
    client = boto3.client("ecs")

    try:
        click.secho(f"Waiting for task to finish: {task_arn}", fg="yellow")
        waiter = client.get_waiter(f"tasks_{state}")
        waiter.wait(cluster=obj.cluster, tasks=[task_arn], WaiterConfig={"Delay": delay, "MaxAttempts": attempts})
    except botocore.exceptions.WaiterError as e:
        click.secho("Task execution timeout. Requesting stop", fg="red")
        client.stop_task(cluster=obj.cluster, task=task_arn, reason="timeout")
        click.secho("Waiting 45s for task to stop", fg="red")
        time.sleep(45)

    task_definitions = client.describe_tasks(cluster=obj.cluster, tasks=[task_arn])
    if not task_definitions.get("tasks"):
        click.secho("Failed to locate task", fg="red")
        ctx.exit(1)

    task = Box(task_definitions.get("tasks")[0])
    task_definition_arn = task.taskDefinitionArn
    task_definition = client.describe_task_definition(taskDefinition=task_definition_arn)
    log_configuration = task_definition["taskDefinition"]["containerDefinitions"][0]["logConfiguration"]

    logs_client = boto3.client("logs")
    if log_configuration["logDriver"] != "awslogs":
        click.secho(f'Log driver "{log_configuration["logDriver"]}" is not supported yet.', fg="yellow")
    else:
        describe_log_streams = logs_client.describe_log_streams(
            logGroupName=log_configuration["options"]["awslogs-group"],
            orderBy="LastEventTime",
            descending=True,
            limit=1,
        )

        log_events = []
        if describe_log_streams["logStreams"]:
            log_events = logs_client.get_log_events(
                logGroupName=log_configuration["options"]["awslogs-group"],
                logStreamName=describe_log_streams["logStreams"][0]["logStreamName"],
                limit=100,
            )["events"]

        click.echo(
            "\n".join(
                map(
                    lambda x: x["message"],
                    filter(lambda x: arrow.get(x["timestamp"]) > arrow.get(task.createdAt), log_events),
                )
            )
        )

    if task["stopCode"] == "UserInitiated":
        click.secho("User initiated termination", fg="red")
        ctx.exit(-1)

    click.secho("Done", fg="green")
    ctx.exit(task["containers"][0]["exitCode"])
