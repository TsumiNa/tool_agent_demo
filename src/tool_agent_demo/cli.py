import click
import os
import sys
import subprocess
import importlib
import importlib.util
from typing import Tuple, Type

from tool_agent_demo.agent import Agent
from tool_agent_demo.db import init_db, register_executor


def validate_python_env(path: str = None) -> bool:
    """Validate Python environment meets requirements.

    Args:
        path: Optional path to Python environment. If None, validates current env.

    Returns:
        True if valid, raises click.BadParameter if invalid
    """
    # Get python path to check
    python_path = path + "/bin/python" if path else sys.executable

    try:
        # Check Python version
        result = subprocess.run([python_path, "-c", "import sys; print(sys.version_info[:2])"],
                                capture_output=True, text=True)
        version = eval(result.stdout.strip())
        if version < (3, 10):
            raise click.BadParameter(
                f"Python version must be >= 3.10 (found {version[0]}.{version[1]})")

        # Check tool-agent-demo package
        result = subprocess.run([python_path, "-c", "import tool_agent_demo"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise click.BadParameter("tool-agent-demo package not installed")

        return True
    except subprocess.CalledProcessError:
        raise click.BadParameter(f"Failed to execute Python at {python_path}")


def validate_docker_image(image: str) -> bool:
    """Validate Docker image meets requirements.

    Returns:
        True if valid, raises click.BadParameter if invalid
    """
    try:
        # Check if docker is available
        subprocess.run(["docker", "--version"],
                       check=True, capture_output=True)

        # Try to inspect image
        result = subprocess.run(
            ["docker", "inspect", image], capture_output=True, text=True)
        if result.returncode != 0:
            raise click.BadParameter(f"Docker image not found: {image}")

        # Check Python version and package in container
        cmd = "python3 -c 'import sys; import tool_agent_demo; print(sys.version_info[:2])'"
        result = subprocess.run(["docker", "run", "--rm", image, "sh", "-c", cmd],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise click.BadParameter(
                "Failed to verify Python environment in container")

        version = eval(result.stdout.strip())
        if version < (3, 10):
            raise click.BadParameter(
                f"Container Python version must be >= 3.10 (found {version[0]}.{version[1]})")

        return True
    except subprocess.CalledProcessError as e:
        raise click.BadParameter(f"Docker validation failed: {str(e)}")


def validate_executor(executor: str) -> Tuple[str, str]:
    """Validate executor and determine its type.

    Args:
        executor: Either a docker image name or path to Python environment

    Returns:
        Tuple of (type, value) where type is 'docker' or 'env'
    """
    # Check if it's a Python environment path first
    if os.path.exists(executor):
        validate_python_env(executor)
        return 'env', executor
    # If not a path, treat as docker image
    else:
        validate_docker_image(executor)
        return 'docker', executor


def parse_entrypoint(entrypoint: str) -> tuple[str, str, str]:
    """Parse entrypoint into package path, module path with .py, and variable name.

    Args:
        entrypoint: Format "/path/to/package/my_module:variable_name"
                   or "/path/to/package/my_module" (defaults to ":agent")

    Returns:
        Tuple of (package_path, py_path, variable_name)
    """
    if ':' in entrypoint:
        package_path, var_name = entrypoint.rsplit(':', 1)
    else:
        package_path = entrypoint
        var_name = 'agent'

    # Handle .py extension
    if package_path.endswith('.py'):
        package_path = package_path[:-3]

    # Get full path with .py extension
    py_path = package_path + '.py'
    if not os.path.exists(py_path):
        raise click.BadParameter(
            f"Package path does not exist: {py_path}")

    return package_path, py_path, var_name


def validate_agent_class(python_path: str, py_path: str, var_name: str) -> None:
    """Validate that the variable is a class inheriting from Agent using the specified Python.

    Args:
        python_path: Path to Python executable to use for validation
        py_path: Path to Python file containing the class
        var_name: Name of the variable to validate
    """
    # Create validation script
    validation_script = f"""
import importlib.util
import sys
from tool_agent_demo.agent import Agent

# Import the module
spec = importlib.util.spec_from_file_location('module', '{py_path}')
if not spec or not spec.loader:
    sys.exit(1)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Check if variable exists
if not hasattr(module, '{var_name}'):
    sys.exit(2)

# Check if it's a class inheriting from Agent
var = getattr(module, '{var_name}')
if not isinstance(var, type) or not issubclass(var, Agent):
    sys.exit(3)
"""

    # Write validation script to temporary file
    script_path = 'validate_agent.py'
    with open(script_path, 'w') as f:
        f.write(validation_script)

    try:
        # Run validation script with specified Python
        result = subprocess.run([python_path, script_path],
                                capture_output=True, text=True)

        if result.returncode == 1:
            raise click.BadParameter(f"Failed to load module from {py_path}")
        elif result.returncode == 2:
            raise click.BadParameter(
                f"Variable '{var_name}' not found in {py_path}")
        elif result.returncode == 3:
            raise click.BadParameter(
                f"Variable '{var_name}' must be a class that inherits from tool_agent_demo.agent.Agent")
        elif result.returncode != 0:
            raise click.BadParameter(f"Validation failed: {result.stderr}")
    finally:
        # Clean up temporary script
        os.remove(script_path)


@click.group()
def cli():
    """Tool Agent Demo CLI"""
    # Initialize database
    init_db()


@cli.command()
@click.argument('executor')
@click.argument('entrypoint')
def register(executor, entrypoint):
    """Register an executor with its entrypoint.

    EXECUTOR: The executor name
    ENTRYPOINT: The entrypoint path
    """
    try:
        # Validate executor
        exec_type, exec_value = validate_executor(executor)

        # Parse entrypoint
        package_path, py_path, var_name = parse_entrypoint(entrypoint)

        # Validate the Agent class using the appropriate executor
        if exec_type == 'env':
            python_path = exec_value + "/bin/python"
            validate_agent_class(python_path, py_path, var_name)
        else:  # docker
            # For docker, we need to copy the file into the container and validate there
            container_name = f"validate_agent_{os.getpid()}"
            try:
                # Start container
                subprocess.run(["docker", "run", "-d", "--name", container_name, exec_value, "sleep", "infinity"],
                               check=True, capture_output=True)

                # Copy file to container
                subprocess.run(["docker", "cp", py_path, f"{container_name}:/tmp/module.py"],
                               check=True, capture_output=True)

                # Run validation in container
                cmd = f"""
import importlib.util
import sys
from tool_agent_demo.agent import Agent

spec = importlib.util.spec_from_file_location('module', '/tmp/module.py')
if not spec or not spec.loader:
    sys.exit(1)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if not hasattr(module, '{var_name}'):
    sys.exit(2)

var = getattr(module, '{var_name}')
if not isinstance(var, type) or not issubclass(var, Agent):
    sys.exit(3)
"""
                result = subprocess.run(
                    ["docker", "exec", container_name, "python3", "-c", cmd],
                    capture_output=True, text=True)

                if result.returncode == 1:
                    raise click.BadParameter(
                        "Failed to load module in container")
                elif result.returncode == 2:
                    raise click.BadParameter(
                        f"Variable '{var_name}' not found in container")
                elif result.returncode == 3:
                    raise click.BadParameter(
                        f"Variable '{var_name}' must be a class that inherits from tool_agent_demo.agent.Agent")
                elif result.returncode != 0:
                    raise click.BadParameter(
                        f"Container validation failed: {result.stderr}")

            finally:
                # Cleanup container
                subprocess.run(["docker", "rm", "-f", container_name],
                               capture_output=True)

        # Import the module to get the Agent class
        spec = importlib.util.spec_from_file_location("module", py_path)
        if not spec or not spec.loader:
            raise click.BadParameter(f"Failed to load module from {py_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        agent_class = getattr(module, var_name)

        # Register in database and get info
        executor_info = register_executor(
            executor_type=exec_type,
            executor_path=exec_value,
            entrypoint_path=package_path,
            variable_name=var_name,
            agent_class=agent_class
        )

        click.echo(f"Registered {exec_type} executor: {exec_value}")
        click.echo(f"Package path: {package_path}")
        click.echo(f"Variable name: {var_name}")
        click.echo(f"Executor ID: {executor_info['id']}")
        click.echo("\nAgent Information:")
        click.echo(f"Tools: {len(executor_info['agent_info']['tools'])}")
        click.echo(f"Workflows: {
                   len(executor_info['agent_info']['workflows'])}")

    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Command failed: {e}")
    except click.BadParameter as e:
        raise click.ClickException(str(e))


def main():
    cli()


if __name__ == '__main__':
    main()
