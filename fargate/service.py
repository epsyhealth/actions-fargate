import boto3
import botocore
import click


@click.group(name="service")
def services():
    pass


@services.command(name="wait-for")
@click.pass_obj
@click.option("--state", type=click.Choice(["inactive", "stable"]), default="stable")
@click.option("--delay", default=10)
@click.option("--attempts", default=60)
@click.argument("service")
@click.pass_context
def service_wait(ctx, obj, state, delay, attempts, service):
    client = boto3.client("ecs")

    try:
        click.secho("Waiting for a service {service} to become {}", fg="red")
        waiter = client.get_waiter(f"services_{state}")
        waiter.wait(
            cluster=obj.cluster,
            services=[service],
            WaiterConfig={"Delay": delay, "MaxAttempts": attempts},
        )
    except botocore.exceptions.WaiterError as e:
        click.secho("Service stat timeout", fg="red")
        ctx.exit(1)

    click.secho("Done", fg="green")
