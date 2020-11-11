import os

import click
from box import Box

from fargate.service import services
from fargate.task import tasks
from fargate.vpc import vpc


@click.group()
@click.option("--cluster", required=True, default=os.getenv("FARGATE_CLUSTER"))
@click.pass_context
def run(ctx, cluster):
    """Manage fargate task execution and deployments"""
    ctx.ensure_object(Box)
    ctx.obj.cluster = cluster


run.add_command(services)
run.add_command(tasks)
run.add_command(vpc)
