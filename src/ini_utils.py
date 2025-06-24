import configparser
from pathlib import Path
from typing import Any, Union


def read_ini_file(file_path: Union[str, Path]) -> configparser.ConfigParser:
    """
    Read and parse an INI file.

    Args:
        file_path: Path to the INI file

    Returns:
        ConfigParser object

    Raises:
        FileNotFoundError: If file doesn't exist
        configparser.Error: For parsing errors
    """
    config = configparser.ConfigParser()
    if not Path(file_path).exists():
        raise FileNotFoundError(f"INI file not found: {file_path}")

    config.read(file_path)
    return config


def get_ini_value(
    file_path: Union[str, Path],
    section: str,
    key: str,
    *,
    default: Any = None,
    return_type: type = str,
    strict: bool = False,
) -> Any:
    """
    Get a value from INI file with type conversion.

    Args:
        file_path: Path to INI file
        section: Section name in INI file
        key: Key name in section
        default: Default value if key not found (default: None)
        return_type: Type to convert the value to (default: str)
        strict: If True, raises error when key not found (default: False)

    Returns:
        The converted value or default if not found

    Raises:
        ValueError: If type conversion fails
        KeyError: If strict=True and key not found
    """
    try:
        config = read_ini_file(file_path)

        if strict and not config.has_option(section, key):
            raise KeyError(f"Key '{key}' not found in section '{section}'")

        value = config.get(section, key, fallback=default)

        if value is None or value == default:
            return default

        # Handle common type conversions
        if return_type == bool:
            return config.getboolean(section, key, fallback=default)
        if return_type == int:
            return config.getint(section, key, fallback=default)
        if return_type == float:
            return config.getfloat(section, key, fallback=default)

        return return_type(value)

    except (ValueError, configparser.Error) as e:
        if strict:
            raise ValueError(f"Failed to read {section}.{key}: {str(e)}")
        return default


def get_all_sections(
    file_path: Union[str, Path], include_default: bool = False
) -> dict[str, dict[str, Any]]:
    """
    Get all sections and their key-value pairs from an INI file.

    Args:
        file_path: Path to INI file
        include_default: Whether to include DEFAULT section

    Returns:
        Dictionary of sections with their key-value pairs
    """
    config = read_ini_file(file_path)
    sections = {}

    for section in config.sections():
        sections[section] = dict(config.items(section))

    if include_default and config.defaults():
        sections["DEFAULT"] = dict(config.defaults())

    return sections
