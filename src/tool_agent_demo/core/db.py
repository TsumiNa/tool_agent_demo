import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import xxhash
from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Get database path from environment or use default
DB_PATH = os.environ.get(
    'TOOL_AGENT_DB', os.path.expanduser('~/.tool_agent.db'))
engine = create_engine(f'sqlite:///{DB_PATH}')
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Executor(Base):
    """Model for registered executors."""
    __tablename__ = 'executors'

    # ID generated from executor and entrypoint info
    id = Column(String, primary_key=True)

    # Executor info
    executor_type = Column(String, nullable=False)  # 'env' or 'docker'
    executor_path = Column(String, nullable=False)  # Path or image name

    # Entrypoint info
    entrypoint_path = Column(String, nullable=False)  # Path without .py
    variable_name = Column(String, nullable=False)

    # Agent class info (tools and workflows)
    agent_info = Column(JSON, nullable=False)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def generate_id(executor_path: str, entrypoint_path: str, variable_name: str) -> str:
        """Generate a unique ID from executor and entrypoint info."""
        # Create a string combining all components
        id_str = f"{executor_path}:{entrypoint_path}:{variable_name}"
        # Use xxHash for faster hashing
        return xxhash.xxh64(id_str.encode()).hexdigest()

    @staticmethod
    def get_agent_info(agent_class) -> Dict:
        """Extract relevant information from Agent class."""
        tools = []
        workflows = []

        # Get tool and workflow methods
        for name in dir(agent_class):
            attr = getattr(agent_class, name)
            if hasattr(attr, '_is_tool'):
                tools.append({
                    'name': name,
                    'doc': attr.__doc__ or ''
                })
            elif hasattr(attr, '_is_workflow'):
                workflows.append({
                    'name': name,
                    'doc': attr.__doc__ or ''
                })

        return {
            'tools': tools,
            'workflows': workflows,
            'doc': agent_class.__doc__ or ''
        }


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(engine)


def register_executor(
    executor_type: str,
    executor_path: str,
    entrypoint_path: str,
    variable_name: str,
    agent_class
) -> Dict:
    """Register or update an executor in the database.

    Args:
        executor_type: Type of executor ('env' or 'docker')
        executor_path: Path to Python env or Docker image name
        entrypoint_path: Path to Python module without .py extension
        variable_name: Name of Agent class variable
        agent_class: The Agent class to register

    Returns:
        Dictionary containing the executor information
    """
    session = Session()
    try:
        # Generate ID
        executor_id = Executor.generate_id(
            executor_path, entrypoint_path, variable_name)

        # Get or create executor
        executor = session.query(Executor).filter_by(id=executor_id).first()
        if executor:
            # Update existing record
            executor.executor_type = executor_type
            executor.executor_path = executor_path
            executor.entrypoint_path = entrypoint_path
            executor.variable_name = variable_name
            executor.agent_info = Executor.get_agent_info(agent_class)
        else:
            # Create new record
            executor = Executor(
                id=executor_id,
                executor_type=executor_type,
                executor_path=executor_path,
                entrypoint_path=entrypoint_path,
                variable_name=variable_name,
                agent_info=Executor.get_agent_info(agent_class)
            )
            session.add(executor)

        session.commit()

        # Return dictionary with executor info
        return {
            'id': executor.id,
            'executor_type': executor.executor_type,
            'executor_path': executor.executor_path,
            'entrypoint_path': executor.entrypoint_path,
            'variable_name': executor.variable_name,
            'agent_info': executor.agent_info
        }
    finally:
        session.close()


def get_executor(executor_id: str) -> Optional[Executor]:
    """Get an executor by ID."""
    session = Session()
    try:
        return session.query(Executor).filter_by(id=executor_id).first()
    finally:
        session.close()


def list_executors() -> List[Executor]:
    """List all registered executors."""
    session = Session()
    try:
        return session.query(Executor).all()
    finally:
        session.close()
