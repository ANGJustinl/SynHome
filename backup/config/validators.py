"""
Field validators for common configuration types in SynHome.

Provides specialized validators for:
- Network configurations (ports, hosts, URLs)
- Authentication credentials
- File paths and permissions
- Device and adapter configurations
- Logging configurations
"""

import re
import socket
import urllib.parse
from pathlib import Path
from typing import Any, List, Optional, Union, Tuple, Dict
from ipaddress import ip_address, IPv4Address, IPv6Address
from enum import Enum

import loguru


class ValidationRule(Enum):
    """Available validation rules."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    POSITIVE = "positive"
    NON_NEGATIVE = "non_negative"
    PORT_RANGE = "port_range"
    LOG_LEVEL = "log_level"
    EMAIL = "email"
    URL = "url"
    HOSTNAME = "hostname"
    IP_ADDRESS = "ip_address"
    FILE_PATH = "file_path"
    DIRECTORY_PATH = "directory_path"
    API_KEY = "api_key"
    DEVICE_ID = "device_id"
    ADAPTER_ID = "adapter_id"
    ENUM_VALUE = "enum_value"
    JSON_STRING = "json_string"
    YAML_STRING = "yaml_string"


class FieldValidator:
    """Validates individual configuration fields."""

    def __init__(self):
        """Initialize field validator."""
        self.validation_functions = {
            ValidationRule.REQUIRED: self._validate_required,
            ValidationRule.OPTIONAL: self._validate_optional,
            ValidationRule.POSITIVE: self._validate_positive,
            ValidationRule.NON_NEGATIVE: self._validate_non_negative,
            ValidationRule.PORT_RANGE: self._validate_port_range,
            ValidationRule.LOG_LEVEL: self._validate_log_level,
            ValidationRule.EMAIL: self._validate_email,
            ValidationRule.URL: self._validate_url,
            ValidationRule.HOSTNAME: self._validate_hostname,
            ValidationRule.IP_ADDRESS: self._validate_ip_address,
            ValidationRule.FILE_PATH: self._validate_file_path,
            ValidationRule.DIRECTORY_PATH: self._validate_directory_path,
            ValidationRule.API_KEY: self._validate_api_key,
            ValidationRule.DEVICE_ID: self._validate_device_id,
            ValidationRule.ADAPTER_ID: self._validate_adapter_id,
            ValidationRule.ENUM_VALUE: self._validate_enum_value,
            ValidationRule.JSON_STRING: self._validate_json_string,
            ValidationRule.YAML_STRING: self._validate_yaml_string,
        }

        self.log_levels = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.common_ports = {
            20: "FTP Data", 21: "FTP Control", 22: "SSH", 23: "Telnet",
            25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
            143: "IMAP", 443: "HTTPS", 993: "IMAPS", 995: "POP3S",
            3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis", 8000: "Development",
            8080: "HTTP Alternate", 8443: "HTTPS Alternate"
        }

    def validate_field(
        self,
        value: Any,
        rules: List[ValidationRule],
        field_name: str = "field",
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate a field against multiple rules.

        Args:
            value: Value to validate
            rules: List of validation rules to apply
            field_name: Name of the field for error messages
            context: Additional context for validation

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        for rule in rules:
            if rule not in self.validation_functions:
                errors.append(f"Unknown validation rule: {rule.value}")
                continue

            try:
                is_valid, rule_errors = self.validation_functions[rule](
                    value, field_name, context
                )
                if not is_valid:
                    errors.extend(rule_errors)
            except Exception as e:
                loguru.logger.error(f"Validation error for rule {rule.value}: {e}")
                errors.append(f"Validation failed for {field_name}: {str(e)}")

        return len(errors) == 0, errors

    def validate_port(self, port: Union[int, str], field_name: str = "port") -> Tuple[bool, List[str]]:
        """
        Validate port number with detailed checking.

        Args:
            port: Port number to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Convert to integer if string
        try:
            if isinstance(port, str):
                port = int(port)
        except ValueError:
            errors.append(f"{field_name} must be an integer, got '{port}'")
            return False, errors

        # Check range
        if not (1 <= port <= 65535):
            errors.append(f"{field_name} {port} is out of valid range (1-65535)")
            return False, errors

        # Check for common ports
        if port in self.common_ports:
            service = self.common_ports[port]
            if port < 1024:
                errors.append(f"{field_name} {port} is a privileged port for {service}")
            else:
                loguru.logger.debug(f"{field_name} {port} is commonly used for {service}")

        return True, errors

    def validate_log_level(self, level: str, field_name: str = "log_level") -> Tuple[bool, List[str]]:
        """
        Validate log level.

        Args:
            level: Log level to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(level, str):
            errors.append(f"{field_name} must be a string, got {type(level).__name__}")
            return False, errors

        level_upper = level.upper()
        if level_upper not in self.log_levels:
            valid_levels = ", ".join(self.log_levels)
            errors.append(f"{field_name} '{level}' is not valid. Valid levels: {valid_levels}")
            return False, errors

        return True, errors

    def validate_api_key(
        self,
        api_key: str,
        service: str = "API",
        field_name: str = "api_key"
    ) -> Tuple[bool, List[str]]:
        """
        Validate API key format.

        Args:
            api_key: API key to validate
            service: Service name for context
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(api_key, str):
            errors.append(f"{field_name} must be a string")
            return False, errors

        # Basic checks
        if not api_key:
            errors.append(f"{field_name} cannot be empty")
            return False, errors

        if len(api_key) < 10:
            errors.append(f"{field_name} is too short (minimum 10 characters)")
            return False, errors

        # Check for common placeholder values
        placeholders = ["your_api_key", "test_key", "demo_key", "xxx", "placeholder"]
        if api_key.lower() in placeholders:
            errors.append(f"{field_name} appears to be a placeholder value")
            return False, errors

        # Service-specific validation
        if service.lower() == "zhipuai":
            # ZhipuAI API keys are typically longer
            if len(api_key) < 20:
                errors.append(f"ZhipuAI {field_name} appears to be invalid (too short)")

        return True, errors

    def validate_device_id(self, device_id: str, field_name: str = "device_id") -> Tuple[bool, List[str]]:
        """
        Validate device ID format.

        Args:
            device_id: Device ID to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(device_id, str):
            errors.append(f"{field_name} must be a string")
            return False, errors

        if not device_id:
            errors.append(f"{field_name} cannot be empty")
            return False, errors

        # Length check
        if len(device_id) > 100:
            errors.append(f"{field_name} is too long (maximum 100 characters)")
            return False, errors

        # Character check (alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', device_id):
            errors.append(f"{field_name} can only contain letters, numbers, underscores, and hyphens")
            return False, errors

        # Cannot start or end with underscore/hyphen
        if device_id.startswith(('_','-')) or device_id.endswith(('_','-')):
            errors.append(f"{field_name} cannot start or end with underscore or hyphen")
            return False, errors

        return True, errors

    def validate_adapter_id(self, adapter_id: str, field_name: str = "adapter_id") -> Tuple[bool, List[str]]:
        """
        Validate adapter ID format.

        Args:
            adapter_id: Adapter ID to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Use same validation as device IDs for consistency
        return self.validate_device_id(adapter_id, field_name)

    def validate_file_path(
        self,
        file_path: Union[str, Path],
        must_exist: bool = False,
        check_writable: bool = False,
        field_name: str = "file_path"
    ) -> Tuple[bool, List[str]]:
        """
        Validate file path.

        Args:
            file_path: File path to validate
            must_exist: Whether the file must exist
            check_writable: Whether to check write permissions
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(file_path, (str, Path)):
            errors.append(f"{field_name} must be a string or Path object")
            return False, errors

        path = Path(file_path)

        # Check for invalid characters (basic)
        if path.name and any(char in path.name for char in ['<', '>', '|', '"']):
            errors.append(f"{field_name} contains invalid characters")

        # Check if file exists (if required)
        if must_exist and not path.exists():
            errors.append(f"{field_name} does not exist: {path}")
            return False, errors

        # Check parent directory exists
        if not path.parent.exists():
            errors.append(f"Parent directory does not exist: {path.parent}")
            return False, errors

        # Check write permissions
        if check_writable:
            try:
                # Try to create a test file
                test_file = path.parent / f".synhome_test_{path.name}"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError):
                errors.append(f"No write permission for directory: {path.parent}")

        return True, errors

    def validate_directory_path(
        self,
        dir_path: Union[str, Path],
        must_exist: bool = False,
        check_writable: bool = False,
        field_name: str = "directory_path"
    ) -> Tuple[bool, List[str]]:
        """
        Validate directory path.

        Args:
            dir_path: Directory path to validate
            must_exist: Whether the directory must exist
            check_writable: Whether to check write permissions
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(dir_path, (str, Path)):
            errors.append(f"{field_name} must be a string or Path object")
            return False, errors

        path = Path(dir_path)

        # Check if directory exists (if required)
        if must_exist and not path.exists():
            errors.append(f"{field_name} does not exist: {path}")
            return False, errors

        if must_exist and not path.is_dir():
            errors.append(f"{field_name} is not a directory: {path}")
            return False, errors

        # Check write permissions
        if check_writable and path.exists():
            try:
                # Try to create a test file
                test_file = path / ".synhome_write_test"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError):
                errors.append(f"No write permission for directory: {path}")

        return True, errors

    def validate_hostname(self, hostname: str, field_name: str = "hostname") -> Tuple[bool, List[str]]:
        """
        Validate hostname.

        Args:
            hostname: Hostname to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(hostname, str):
            errors.append(f"{field_name} must be a string")
            return False, errors

        if not hostname:
            errors.append(f"{field_name} cannot be empty")
            return False, errors

        # Length check
        if len(hostname) > 253:
            errors.append(f"{field_name} is too long (maximum 253 characters)")
            return False, errors

        # Check if it's a valid IP address
        try:
            ip_address(hostname)
            return True, errors  # Valid IP address
        except ValueError:
            pass  # Not an IP address, continue with hostname validation

        # Hostname validation
        if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
            errors.append(f"{field_name} contains invalid characters")
            return False, errors

        # Cannot start or end with hyphen or dot
        if hostname.startswith(('-', '.')) or hostname.endswith(('-', '.')):
            errors.append(f"{field_name} cannot start or end with hyphen or dot")
            return False, errors

        # Check for consecutive dots
        if '..' in hostname:
            errors.append(f"{field_name} cannot contain consecutive dots")
            return False, errors

        # Check each label
        labels = hostname.split('.')
        for label in labels:
            if len(label) > 63:
                errors.append(f"Hostname label '{label}' is too long (maximum 63 characters)")
                return False, errors

            if label.startswith('-') or label.endswith('-'):
                errors.append(f"Hostname label '{label}' cannot start or end with hyphen")
                return False, errors

        return True, errors

    def validate_url(self, url: str, field_name: str = "url") -> Tuple[bool, List[str]]:
        """
        Validate URL.

        Args:
            url: URL to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(url, str):
            errors.append(f"{field_name} must be a string")
            return False, errors

        if not url:
            errors.append(f"{field_name} cannot be empty")
            return False, errors

        try:
            parsed = urllib.parse.urlparse(url)

            # Check scheme
            if not parsed.scheme:
                errors.append(f"{field_name} must include a scheme (http, https, etc.)")
                return False, errors

            valid_schemes = ['http', 'https', 'ws', 'wss', 'ftp', 'ftps']
            if parsed.scheme.lower() not in valid_schemes:
                errors.append(f"URL scheme '{parsed.scheme}' is not supported")
                return False, errors

            # Check netloc
            if not parsed.netloc:
                errors.append(f"{field_name} must include a hostname")
                return False, errors

            # Validate hostname
            if ':' in parsed.netloc:
                hostname, port_str = parsed.netloc.rsplit(':', 1)
                try:
                    port = int(port_str)
                    is_valid, port_errors = self.validate_port(port, f"{field_name}_port")
                    if not is_valid:
                        errors.extend(port_errors)
                        return False, errors
                except ValueError:
                    errors.append(f"Invalid port in URL: {port_str}")
                    return False, errors
            else:
                hostname = parsed.netloc

            is_valid, host_errors = self.validate_hostname(hostname, f"{field_name}_host")
            if not is_valid:
                errors.extend(host_errors)
                return False, errors

        except Exception as e:
            errors.append(f"Invalid URL format: {str(e)}")
            return False, errors

        return True, errors

    def validate_email(self, email: str, field_name: str = "email") -> Tuple[bool, List[str]]:
        """
        Validate email address.

        Args:
            email: Email address to validate
            field_name: Field name for error messages

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if not isinstance(email, str):
            errors.append(f"{field_name} must be a string")
            return False, errors

        if not email:
            errors.append(f"{field_name} cannot be empty")
            return False, errors

        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            errors.append(f"{field_name} '{email}' is not a valid email address")
            return False, errors

        # Length check
        if len(email) > 254:
            errors.append(f"{field_name} is too long (maximum 254 characters)")
            return False, errors

        return True, errors

    # Validation rule implementations
    def _validate_required(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate required field."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, [f"{field_name} is required"]
        return True, []

    def _validate_optional(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate optional field (always passes unless None is explicitly not allowed)."""
        return True, []

    def _validate_positive(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate positive number."""
        try:
            num = float(value)
            if num <= 0:
                return False, [f"{field_name} must be positive, got {num}"]
            return True, []
        except (ValueError, TypeError):
            return False, [f"{field_name} must be a number, got {value}"]

    def _validate_non_negative(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate non-negative number."""
        try:
            num = float(value)
            if num < 0:
                return False, [f"{field_name} cannot be negative, got {num}"]
            return True, []
        except (ValueError, TypeError):
            return False, [f"{field_name} must be a number, got {value}"]

    def _validate_port_range(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate port range."""
        return self.validate_port(value, field_name)

    def _validate_log_level(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate log level."""
        return self.validate_log_level(value, field_name)

    def _validate_email(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate email."""
        return self.validate_email(value, field_name)

    def _validate_url(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate URL."""
        return self.validate_url(value, field_name)

    def _validate_hostname(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate hostname."""
        return self.validate_hostname(value, field_name)

    def _validate_ip_address(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate IP address."""
        try:
            ip_address(str(value))
            return True, []
        except ValueError:
            return False, [f"{field_name} '{value}' is not a valid IP address"]

    def _validate_file_path(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate file path."""
        must_exist = context.get("must_exist", False) if context else False
        return self.validate_file_path(value, must_exist=must_exist, field_name=field_name)

    def _validate_directory_path(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate directory path."""
        must_exist = context.get("must_exist", False) if context else False
        return self.validate_directory_path(value, must_exist=must_exist, field_name=field_name)

    def _validate_api_key(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate API key."""
        service = context.get("service", "API") if context else "API"
        return self.validate_api_key(value, service, field_name)

    def _validate_device_id(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate device ID."""
        return self.validate_device_id(value, field_name)

    def _validate_adapter_id(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate adapter ID."""
        return self.validate_adapter_id(value, field_name)

    def _validate_enum_value(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate enum value."""
        if not context or "enum_values" not in context:
            return False, [f"Enum values not specified for {field_name}"]

        valid_values = context["enum_values"]
        if value not in valid_values:
            valid_str = ", ".join(str(v) for v in valid_values)
            return False, [f"{field_name} '{value}' is not valid. Valid values: {valid_str}"]
        return True, []

    def _validate_json_string(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate JSON string."""
        if not isinstance(value, str):
            return False, [f"{field_name} must be a string containing JSON"]

        try:
            import json
            json.loads(value)
            return True, []
        except json.JSONDecodeError as e:
            return False, [f"{field_name} contains invalid JSON: {str(e)}"]

    def _validate_yaml_string(self, value: Any, field_name: str, context: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Validate YAML string."""
        if not isinstance(value, str):
            return False, [f"{field_name} must be a string containing YAML"]

        try:
            import yaml
            yaml.safe_load(value)
            return True, []
        except yaml.YAMLError as e:
            return False, [f"{field_name} contains invalid YAML: {str(e)}"]


# Global field validator instance
_field_validator: Optional[FieldValidator] = None


def get_field_validator() -> FieldValidator:
    """Get or create the global field validator."""
    global _field_validator
    if _field_validator is None:
        _field_validator = FieldValidator()
    return _field_validator


def validate_field(
    value: Any,
    rules: List[ValidationRule],
    field_name: str = "field",
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str]]:
    """Validate a field using the global validator."""
    validator = get_field_validator()
    return validator.validate_field(value, rules, field_name, context)


def validate_port(port: Union[int, str], field_name: str = "port") -> Tuple[bool, List[str]]:
    """Validate a port number."""
    validator = get_field_validator()
    return validator.validate_port(port, field_name)


def validate_log_level(level: str, field_name: str = "log_level") -> Tuple[bool, List[str]]:
    """Validate a log level."""
    validator = get_field_validator()
    return validator.validate_log_level(level, field_name)


def validate_api_key(
    api_key: str,
    service: str = "API",
    field_name: str = "api_key"
) -> Tuple[bool, List[str]]:
    """Validate an API key."""
    validator = get_field_validator()
    return validator.validate_api_key(api_key, service, field_name)