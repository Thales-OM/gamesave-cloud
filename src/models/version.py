from pydantic import BaseModel
from typing import Any, Tuple
import re


class Version(str):
    """
    Custom Version type for semantic versions like '1.0.2'.
    Supports validation and comparison operators.
    """

    version_pattern = re.compile(r"^\d+\.\d+\.\d+$")
    version_str: str
    version_tuple: Tuple[int]

    def __init__(self, version_str: str):
        if not isinstance(version_str, str):
            raise TypeError("Version must be a string.")
        if not self.version_pattern.match(version_str):
            raise ValueError(f"Invalid version format: {version_str}")
        self.version_str = version_str
        self.version_tuple = tuple(int(part) for part in version_str.split("."))

    def __str__(self) -> str:
        return self.version_str

    def __repr__(self) -> str:
        return f"Version('{self.version_str}')"

    # Equality
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Version):
            return self.version_tuple == other.version_tuple
        if isinstance(other, str):
            try:
                other_version = Version(other)
                return self.version_tuple == other_version.version_tuple
            except Exception:
                return False
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    # Less than
    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Version):
            return self.version_tuple < other.version_tuple
        if isinstance(other, str):
            other_version = Version(other)
            return self.version_tuple < other_version.version_tuple
        return NotImplemented

    # Less than or equal
    def __le__(self, other: Any) -> bool:
        if isinstance(other, Version):
            return self.version_tuple <= other.version_tuple
        if isinstance(other, str):
            other_version = Version(other)
            return self.version_tuple <= other_version.version_tuple
        return NotImplemented

    # Greater than
    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Version):
            return self.version_tuple > other.version_tuple
        if isinstance(other, str):
            other_version = Version(other)
            return self.version_tuple > other_version.version_tuple
        return NotImplemented

    # Greater than or equal
    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Version):
            return self.version_tuple >= other.version_tuple
        if isinstance(other, str):
            other_version = Version(other)
            return self.version_tuple >= other_version.version_tuple
        return NotImplemented

    # Allow Pydantic to validate and parse this type
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args, **kwargs):
        if isinstance(v, cls):
            return v
        if isinstance(v, str):
            return cls(v)
        raise TypeError(f"Version must be a string or Version instance, got {type(v)}")
