import json
import os

import boto3
import click
from box import Box


def find_vpc_by_name(client, name):
    response = client.describe_vpcs(
        Filters=[{"Name": "tag:Name", "Values": [name]}],
        MaxResults=100,
    )

    return Box(response).Vpcs[0].VpcId


def find_security_groups_by_name(client, vpc_id, names):
    response = client.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": names},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )

    return [group.GroupId for group in Box(response).SecurityGroups]


def find_subnets_by_prefix(client, vpc_id, subnet):
    response = client.describe_subnets(
        Filters=[
            {"Name": "tag:Name", "Values": [f"{subnet}-a", f"{subnet}-b", f"{subnet}-c"]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )

    return [subnet.SubnetId for subnet in Box(response).Subnets]


def get_network_info(name, security_group, subnet):
    client = boto3.client("ec2")
    vpc_id = find_vpc_by_name(client, name)
    security_group_ids = find_security_groups_by_name(client, vpc_id, security_group)
    subnet_ids = find_subnets_by_prefix(client, vpc_id, subnet)

    return vpc_id, security_group_ids, subnet_ids


@click.command()
@click.argument("name", default=os.getenv("FARGATE_VPC_NAME"))
@click.option("--security-group", multiple=True)
@click.option("--subnet")
@click.option("--debug", is_flag=True)
def vpc(name, security_group, subnet, debug):
    vpc_id, security_group_ids, subnet_ids = get_network_info(name, security_group, subnet)

    if debug:
        click.secho(f"vpc_id::{vpc_id}", fg="green")
        click.secho(f"security_group_ids::{security_group_ids}", fg="green")
        click.secho(f"subnet_ids::{subnet_ids}", fg="green")

    click.echo(f"::set-output name=vpc_id::{vpc_id}")
    click.echo(f"::set-output name=security_group_ids::{json.dumps(security_group_ids)}")
    click.echo(f"::set-output name=subnet_ids::{json.dumps(subnet_ids)}")
