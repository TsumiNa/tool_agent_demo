from dataclasses import dataclass
from typing import Any, List, Tuple, TypeVar, Generic, Optional

T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    A Result type similar to Rust's Result, containing either a value or an error.
    Also supports combining multiple Results using the || operator.
    """
    value: Optional[T] = None
    error: Optional[Exception] = None
    combined_values: Optional[Tuple[Any, ...]] = None
    combined_errors: Optional[List[Exception]] = None

    def is_ok(self) -> bool:
        """Check if the Result contains a value (success)."""
        return self.error is None and (
            self.combined_errors is None or len(self.combined_errors) == 0
        )

    def is_err(self) -> bool:
        """Check if the Result contains an error."""
        return not self.is_ok()

    def __or__(self, other: 'Result[Any]') -> 'Result[Tuple[Any, ...]]':
        """
        Combine two Results into one using the || operator.
        The new Result will contain tuples of values and lists of errors.
        """
        # Initialize lists for combined values and errors
        values: List[Any] = []
        errors: List[Exception] = []

        # Add values and errors from self
        if self.combined_values is not None:
            values.extend(self.combined_values)
        elif self.value is not None:
            values.append(self.value)

        if self.combined_errors is not None:
            errors.extend(self.combined_errors)
        elif self.error is not None:
            errors.append(self.error)

        # Add values and errors from other
        if other.combined_values is not None:
            values.extend(other.combined_values)
        elif other.value is not None:
            values.append(other.value)

        if other.combined_errors is not None:
            errors.extend(other.combined_errors)
        elif other.error is not None:
            errors.append(other.error)

        return Result(
            combined_values=tuple(values) if values else None,
            combined_errors=errors if errors else None
        )

    def unwrap(self) -> T:
        """
        Get the value if Result is ok, otherwise raise the error.
        For combined Results, returns the tuple of values.
        """
        if self.is_err():
            if self.combined_errors and len(self.combined_errors) > 0:
                raise Exception(f"Multiple errors: {self.combined_errors}")
            if self.error:
                raise self.error
            raise Exception("Unknown error")

        if self.combined_values is not None:
            return self.combined_values  # type: ignore
        return self.value  # type: ignore
