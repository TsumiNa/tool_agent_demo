import click
from tool_agent_demo.core.db import init_db
from tool_agent_demo.cli.commands import register, server


@click.group()
def cli():
    """Tool Agent Demo CLI"""
    # Initialize database
    init_db()


# Add commands
cli.add_command(register)
cli.add_command(server)


def main():
    cli()


if __name__ == '__main__':
    main()
