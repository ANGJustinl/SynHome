"""
Configuration error handling and message formatting for SynHome.

Provides:
- User-friendly error message formatting
- Error categorization and severity levels
- Error context and suggestions
- Error reporting utilities
"""

import re
from typing import Dict, Any, List, Tuple, Optional, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

import loguru


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better organization."""
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    FILE_SYSTEM = "file_system"
    NETWORK = "network"
    PERMISSION = "permission"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


@dataclass
class ConfigurationError:
    """Structured configuration error."""
    code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    field_path: Optional[str] = None
    suggestion: Optional[str] = None
    documentation_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ErrorSummary:
    """Summary of configuration errors."""
    total_errors: int
    total_warnings: int
    errors_by_category: Dict[str, int]
    errors_by_severity: Dict[str, int]
    critical_errors: List[ConfigurationError]
    fix_suggestions: List[str]


class ConfigurationErrorFormatter:
    """Formats configuration errors for better user experience."""

    def __init__(self):
        """Initialize error formatter."""
        self.error_patterns = self._initialize_error_patterns()
        self.suggestions = self._initialize_suggestions()
        self.documentation_urls = {
            "configuration": "https://docs.synhome.ai/configuration",
            "devices": "https://docs.synhome.ai/devices",
            "adapters": "https://docs.synhome.ai/adapters",
            "logging": "https://docs.synhome.ai/logging"
        }

    def format_validation_errors(
        self,
        errors: List[str],
        warnings: List[str],
        config_path: Optional[str] = None
    ) -> Tuple[str, List[ConfigurationError]]:
        """
        Format validation errors and warnings into user-friendly messages.

        Args:
            errors: List of error messages
            warnings: List of warning messages
            config_path: Optional configuration file path

        Returns:
            Tuple of (formatted_message, structured_errors)
        """
        structured_errors = []

        # Process errors
        for error in errors:
            config_error = self._parse_error_message(error, ErrorSeverity.HIGH)
            if config_path:
                config_error.context = config_error.context or {}
                config_error.context["config_path"] = config_path
            structured_errors.append(config_error)

        # Process warnings
        for warning in warnings:
            config_error = self._parse_error_message(warning, ErrorSeverity.MEDIUM)
            if config_path:
                config_error.context = config_error.context or {}
                config_error.context["config_path"] = config_path
            structured_errors.append(config_error)

        # Generate formatted message
        formatted_message = self._generate_error_summary(structured_errors)

        return formatted_message, structured_errors

    def format_pydantic_errors(self, validation_errors: List[Dict[str, Any]]) -> List[ConfigurationError]:
        """
        Format Pydantic validation errors into structured errors.

        Args:
            validation_errors: List of Pydantic error dictionaries

        Returns:
            List of structured configuration errors
        """
        structured_errors = []

        for error in validation_errors:
            # Extract error information
            loc = error.get("loc", [])
            msg = error.get("msg", "")
            type_name = error.get("type", "")

            # Format field path
            field_path = " -> ".join(str(item) for item in loc) if loc else "root"

            # Categorize error
            category, severity = self._categorize_pydantic_error(type_name, msg)

            # Generate suggestion
            suggestion = self._generate_suggestion(field_path, msg, type_name)

            config_error = ConfigurationError(
                code=f"PYDANTIC_{type_name.upper()}",
                message=msg,
                category=category,
                severity=severity,
                field_path=field_path,
                suggestion=suggestion,
                context={"pydantic_type": type_name, "location": loc}
            )

            structured_errors.append(config_error)

        return structured_errors

    def format_file_error(
        self,
        error: Exception,
        file_path: Union[str, Path]
    ) -> ConfigurationError:
        """
        Format file-related errors.

        Args:
            error: Exception that occurred
            file_path: Path to the file that caused the error

        Returns:
            Structured configuration error
        """
        file_path = Path(file_path)
        error_message = str(error)

        # Determine error category and severity
        if isinstance(error, FileNotFoundError):
            category = ErrorCategory.FILE_SYSTEM
            severity = ErrorSeverity.CRITICAL
            message = f"Configuration file not found: {file_path}"
            suggestion = f"Create the configuration file at {file_path} or check the file path"
        elif isinstance(error, PermissionError):
            category = ErrorCategory.PERMISSION
            severity = ErrorSeverity.HIGH
            message = f"Permission denied accessing file: {file_path}"
            suggestion = f"Check file permissions for {file_path}"
        elif "YAML" in error_message or "yaml" in error_message.lower():
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.HIGH
            message = f"Invalid YAML syntax in {file_path}: {error_message}"
            suggestion = "Check YAML syntax, indentation, and special characters"
        elif "JSON" in error_message or "json" in error_message.lower():
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.HIGH
            message = f"Invalid JSON syntax in {file_path}: {error_message}"
            suggestion = "Check JSON syntax, commas, brackets, and quotes"
        else:
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.HIGH
            message = f"Error processing file {file_path}: {error_message}"
            suggestion = "Check file format and contents"

        return ConfigurationError(
            code=f"FILE_{category.name.upper()}",
            message=message,
            category=category,
            severity=severity,
            field_path=str(file_path),
            suggestion=suggestion,
            context={"file_path": str(file_path), "original_error": error_message}
        )

    def create_error_summary(self, errors: List[ConfigurationError]) -> ErrorSummary:
        """
        Create a summary of configuration errors.

        Args:
            errors: List of configuration errors

        Returns:
            Error summary
        """
        # Count errors by category
        errors_by_category = {}
        errors_by_severity = {}

        for error in errors:
            category_name = error.category.value
            severity_name = error.severity.value

            errors_by_category[category_name] = errors_by_category.get(category_name, 0) + 1
            errors_by_severity[severity_name] = errors_by_severity.get(severity_name, 0) + 1

        # Get critical errors
        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL]

        # Generate fix suggestions
        fix_suggestions = self._generate_fix_suggestions(errors)

        return ErrorSummary(
            total_errors=len(errors),
            total_warnings=len([e for e in errors if e.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]]),
            errors_by_category=errors_by_category,
            errors_by_severity=errors_by_severity,
            critical_errors=critical_errors,
            fix_suggestions=fix_suggestions
        )

    def generate_quick_fixes(self, errors: List[ConfigurationError]) -> List[str]:
        """
        Generate quick fix suggestions for configuration errors.

        Args:
            errors: List of configuration errors

        Returns:
            List of quick fix suggestions
        """
        fixes = []

        # Group errors by field
        field_errors = {}
        for error in errors:
            field = error.field_path or "root"
            if field not in field_errors:
                field_errors[field] = []
            field_errors[field].append(error)

        # Generate fixes for each field
        for field, field_error_list in field_errors.items():
            field_fixes = self._generate_field_fixes(field, field_error_list)
            fixes.extend(field_fixes)

        # Add general fixes
        if any(e.category == ErrorCategory.PERMISSION for e in errors):
            fixes.append("Check file and directory permissions")

        if any(e.category == ErrorCategory.FILE_SYSTEM for e in errors):
            fixes.append("Verify all required files and directories exist")

        return list(set(fixes))  # Remove duplicates

    def _parse_error_message(
        self,
        message: str,
        default_severity: ErrorSeverity
    ) -> ConfigurationError:
        """Parse an error message into a structured error."""
        # Try to match known patterns
        for pattern, handler in self.error_patterns.items():
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return handler(message, match)

        # Default parsing
        category = self._guess_category_from_message(message)
        severity = default_severity
        suggestion = self._generate_suggestion_from_message(message)

        return ConfigurationError(
            code="UNKNOWN_ERROR",
            message=message,
            category=category,
            severity=severity,
            suggestion=suggestion
        )

    def _initialize_error_patterns(self) -> Dict[str, callable]:
        """Initialize regex patterns for error parsing."""
        return {
            r"port.*(\d+).*out of range": self._handle_port_range_error,
            r"invalid.*log.*level": self._handle_log_level_error,
            r"api.*key.*required": self._handle_api_key_error,
            r"duplicate.*device.*id": self._handle_duplicate_id_error,
            r"missing.*field": self._handle_missing_field_error,
            r"type.*mismatch": self._handle_type_mismatch_error,
            r"file.*not.*found": self._handle_file_not_found_error,
            r"permission.*denied": self._handle_permission_error,
        }

    def _initialize_suggestions(self) -> Dict[str, str]:
        """Initialize common suggestions for error types."""
        return {
            "port_range": "Port must be between 1 and 65535",
            "log_level": "Valid log levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL",
            "api_key": "Set a valid API key in the configuration",
            "duplicate_id": "Use unique identifiers for devices and adapters",
            "missing_field": "Add the required field to your configuration",
            "type_mismatch": "Check the data type of the configuration value",
            "file_not_found": "Create the missing configuration file",
            "permission_denied": "Check file and directory permissions"
        }

    def _handle_port_range_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle port range errors."""
        port_value = match.group(1)
        return ConfigurationError(
            code="INVALID_PORT_RANGE",
            message=f"Port {port_value} is out of valid range (1-65535)",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            field_path="port",
            suggestion="Use a port number between 1 and 65535. Common choices: 8000 (development), 80 (production HTTP), 443 (production HTTPS)"
        )

    def _handle_log_level_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle log level errors."""
        return ConfigurationError(
            code="INVALID_LOG_LEVEL",
            message="Invalid logging level specified",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            field_path="logging.level",
            suggestion="Valid log levels are: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL",
            documentation_url=self.documentation_urls.get("logging")
        )

    def _handle_api_key_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle API key errors."""
        return ConfigurationError(
            code="MISSING_API_KEY",
            message="API key is required but not provided",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            field_path="zhipuai.api_key",
            suggestion="Set a valid ZhipuAI API key in the configuration or environment variable",
            documentation_url=self.documentation_urls.get("configuration")
        )

    def _handle_duplicate_id_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle duplicate ID errors."""
        return ConfigurationError(
            code="DUPLICATE_ID",
            message="Duplicate device or adapter ID found",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            suggestion="Ensure all devices and adapters have unique identifiers",
            documentation_url=self.documentation_urls.get("devices")
        )

    def _handle_missing_field_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle missing field errors."""
        return ConfigurationError(
            code="MISSING_REQUIRED_FIELD",
            message="Required configuration field is missing",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            suggestion="Add the missing required field to your configuration",
            documentation_url=self.documentation_urls.get("configuration")
        )

    def _handle_type_mismatch_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle type mismatch errors."""
        return ConfigurationError(
            code="TYPE_MISMATCH",
            message="Configuration value has incorrect data type",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            suggestion="Check the data type of the configuration value and ensure it matches the expected type",
            documentation_url=self.documentation_urls.get("configuration")
        )

    def _handle_file_not_found_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle file not found errors."""
        return ConfigurationError(
            code="FILE_NOT_FOUND",
            message="Required file or directory not found",
            category=ErrorCategory.FILE_SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            suggestion="Create the missing file or directory, or check the file path",
            documentation_url=self.documentation_urls.get("configuration")
        )

    def _handle_permission_error(self, message: str, match: re.Match) -> ConfigurationError:
        """Handle permission errors."""
        return ConfigurationError(
            code="PERMISSION_DENIED",
            message="Permission denied accessing file or resource",
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            suggestion="Check file and directory permissions, ensure the application has read/write access",
            documentation_url=self.documentation_urls.get("configuration")
        )

    def _categorize_pydantic_error(self, error_type: str, message: str) -> Tuple[ErrorCategory, ErrorSeverity]:
        """Categorize Pydantic validation errors."""
        error_type_lower = error_type.lower()

        if "missing" in error_type_lower:
            return ErrorCategory.VALIDATION, ErrorSeverity.HIGH
        elif "type" in error_type_lower:
            return ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM
        elif "value" in error_type_lower:
            return ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM
        elif "enum" in error_type_lower:
            return ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM
        else:
            return ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM

    def _generate_suggestion(self, field_path: str, message: str, error_type: str) -> Optional[str]:
        """Generate a suggestion for a specific error."""
        # Use predefined suggestions for common patterns
        for pattern, suggestion in self.suggestions.items():
            if pattern in message.lower() or pattern in field_path.lower():
                return suggestion

        # Generate field-specific suggestions
        if "port" in field_path.lower():
            return "Use a port number between 1 and 65535"
        elif "log" in field_path.lower() and "level" in field_path.lower():
            return "Valid log levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL"
        elif "api_key" in field_path.lower():
            return "Set a valid API key in the configuration"
        elif "debug" in field_path.lower():
            return "Debug should be true or false"

        return None

    def _generate_suggestion_from_message(self, message: str) -> Optional[str]:
        """Generate suggestion from error message content."""
        message_lower = message.lower()

        if "not found" in message_lower:
            return "Check if the file or resource exists"
        elif "permission" in message_lower:
            return "Check file and directory permissions"
        elif "invalid" in message_lower:
            return "Verify the value is correct and in the expected format"
        elif "missing" in message_lower:
            return "Add the missing required field or configuration"
        elif "duplicate" in message_lower:
            return "Use unique identifiers"

        return None

    def _generate_error_summary(self, errors: List[ConfigurationError]) -> str:
        """Generate a formatted error summary message."""
        if not errors:
            return "✅ Configuration validation passed successfully!"

        # Count errors and warnings
        error_count = len([e for e in errors if e.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]])
        warning_count = len([e for e in errors if e.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]])

        lines = []
        lines.append(f"❌ Configuration validation failed!")
        lines.append(f"   Found {error_count} error(s) and {warning_count} warning(s)")
        lines.append("")

        # Group errors by category
        by_category = {}
        for error in errors:
            category = error.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(error)

        # Display errors by category
        for category, category_errors in by_category.items():
            lines.append(f"📁 {category.title()} Issues:")
            for error in category_errors:
                icon = "🔴" if error.severity == ErrorSeverity.CRITICAL else "🟠" if error.severity == ErrorSeverity.HIGH else "🟡"
                lines.append(f"   {icon} {error.message}")
                if error.field_path:
                    lines.append(f"      Field: {error.field_path}")
                if error.suggestion:
                    lines.append(f"      💡 {error.suggestion}")
                lines.append("")

        return "\n".join(lines)

    def _generate_fix_suggestions(self, errors: List[ConfigurationError]) -> List[str]:
        """Generate overall fix suggestions."""
        suggestions = set()

        # Add specific suggestions from errors
        for error in errors:
            if error.suggestion:
                suggestions.add(error.suggestion)

        # Add general suggestions based on error patterns
        if any("port" in (e.field_path or "") for e in errors):
            suggestions.add("Verify port is not in use and is within valid range (1-65535)")

        if any("api_key" in (e.field_path or "") for e in errors):
            suggestions.add("Set up API keys in environment variables for better security")

        if any(e.category == ErrorCategory.PERMISSION for e in errors):
            suggestions.add("Run the application with appropriate permissions")

        return sorted(list(suggestions))

    def _generate_field_fixes(self, field: str, errors: List[ConfigurationError]) -> List[str]:
        """Generate fixes for a specific field."""
        fixes = []

        if "port" in field.lower():
            fixes.append(f"Fix port value in {field}")
        elif "log" in field.lower():
            fixes.append(f"Check logging configuration in {field}")
        elif "zhipuai" in field.lower():
            fixes.append(f"Verify ZhipuAI configuration in {field}")

        return fixes

    def _guess_category_from_message(self, message: str) -> ErrorCategory:
        """Guess error category from message content."""
        message_lower = message.lower()

        if "file" in message_lower or "directory" in message_lower:
            return ErrorCategory.FILE_SYSTEM
        elif "permission" in message_lower or "access" in message_lower:
            return ErrorCategory.PERMISSION
        elif "network" in message_lower or "connection" in message_lower:
            return ErrorCategory.NETWORK
        elif "validation" in message_lower or "invalid" in message_lower:
            return ErrorCategory.VALIDATION
        elif "config" in message_lower:
            return ErrorCategory.CONFIGURATION
        else:
            return ErrorCategory.UNKNOWN


# Global error formatter instance
_error_formatter: Optional[ConfigurationErrorFormatter] = None


def get_error_formatter() -> ConfigurationErrorFormatter:
    """Get or create the global error formatter."""
    global _error_formatter
    if _error_formatter is None:
        _error_formatter = ConfigurationErrorFormatter()
    return _error_formatter


def format_configuration_errors(
    errors: List[str],
    warnings: List[str],
    config_path: Optional[str] = None
) -> Tuple[str, List[ConfigurationError]]:
    """Format configuration errors into user-friendly messages."""
    formatter = get_error_formatter()
    return formatter.format_validation_errors(errors, warnings, config_path)


def create_error_summary(errors: List[ConfigurationError]) -> ErrorSummary:
    """Create an error summary from configuration errors."""
    formatter = get_error_formatter()
    return formatter.create_error_summary(errors)