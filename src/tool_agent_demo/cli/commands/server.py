import click
import uvicorn


@click.command()
@click.option('--host', default='0.0.0.0', help='Host to bind the server to')
@click.option('--port', default=8000, type=int, help='Port to bind the server to')
@click.option('--reload/--no-reload', default=True, help='Enable/disable auto-reload')
def server(host: str, port: int, reload: bool):
    """Run the uvicorn development server."""
    uvicorn.run(
        "tool_agent_demo.api:app",
        host=host,
        port=port,
        reload=reload,
        app_dir="src"
    )
