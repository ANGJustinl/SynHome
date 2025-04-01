#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
HTTP device implementation for controlling devices via HTTP/HTTPS APIs
"""

import logging
import time
import json
import requests
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from .smart_device import SmartDevice, CapabilityType

logger = logging.getLogger(__name__)

class HTTPDevice(SmartDevice):
    """HTTP-based device implementation that controls devices via HTTP/HTTPS APIs"""
    
    def __init__(self, device_id: str, config: Dict[str, Any]):
        super().__init__(device_id, config)
        
        # HTTP connection configuration
        self.api_config = config.get("api", {})
        self.base_url = self.api_config.get("base_url", "").rstrip("/")
        self.auth_type = self.api_config.get("auth_type", "none")
        self.auth_config = self.api_config.get("auth", {})
        
        # Command mapping configuration
        self.command_config = self.api_config.get("commands", {})
        
        # Setup session with retries
        self.session = self._create_session()
        
        # Authenticate if needed
        self._authenticate()
        
    def _create_session(self) -> requests.Session:
        """Create and configure requests session with retry logic"""
        session = requests.Session()
        
        # Configure retries
        retries = Retry(
            total=3,  # Total number of retries
            backoff_factor=0.5,  # Wait 0.5s * (2 ** (retry_number - 1))
            status_forcelist=[500, 502, 503, 504],  # Retry on these status codes
        )
        
        # Add retry adapter to session
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Configure timeout
        timeout = self.api_config.get("timeout", 10)
        session.timeout = timeout
        
        # Configure SSL verification
        verify_ssl = self.api_config.get("verify_ssl", True)
        session.verify = verify_ssl
        
        return session
    
    def _authenticate(self):
        """Perform authentication based on configured auth type"""
        if self.auth_type == "basic":
            username = self.auth_config.get("username", "")
            password = self.auth_config.get("password", "")
            self.session.auth = (username, password)
            
        elif self.auth_type == "bearer":
            token = self.auth_config.get("token", "")
            self.session.headers.update({
                "Authorization": f"Bearer {token}"
            })
            
        elif self.auth_type == "api_key":
            key = self.auth_config.get("key", "")
            key_name = self.auth_config.get("key_name", "X-API-Key")
            location = self.auth_config.get("location", "header")
            
            if location == "header":
                self.session.headers.update({key_name: key})
            else:  # query parameter
                self.default_params = {key_name: key}
                
        elif self.auth_type == "oauth2":
            self._perform_oauth2_auth()
    
    def _perform_oauth2_auth(self):
        """Perform OAuth2 authentication flow"""
        try:
            token_url = self.auth_config.get("token_url", "")
            client_id = self.auth_config.get("client_id", "")
            client_secret = self.auth_config.get("client_secret", "")
            
            # Request access token
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )
            
            if token_response.ok:
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # Set token in session headers
                self.session.headers.update({
                    "Authorization": f"Bearer {access_token}"
                })
                
                # Schedule token refresh if expires_in is provided
                if "expires_in" in token_data:
                    self._schedule_token_refresh(token_data["expires_in"])
            else:
                logger.error("OAuth2 authentication failed")
                
        except Exception as e:
            logger.error(f"OAuth2 authentication error: {str(e)}")
    
    def _schedule_token_refresh(self, expires_in: int):
        """Schedule token refresh before expiration"""
        # Refresh 5 minutes before expiration
        refresh_time = time.time() + expires_in - 300
        
        # In a production environment, you would use a proper scheduler here
        # For now, we just log when it should be refreshed
        logger.info(f"Token should be refreshed at {time.ctime(refresh_time)}")
    
    def set_capability(self, name: str, value: Any) -> bool:
        """Set capability value via HTTP API"""
        if not super().set_capability(name, value):
            return False
            
        return self._send_http_command(name, value)
    
    def _send_http_command(self, capability: str, value: Any) -> bool:
        """Send command to device via HTTP API"""
        try:
            # Get command configuration for this capability
            if capability not in self.command_config:
                logger.error(f"No command configuration for {capability}")
                return False
            
            cmd_config = self.command_config[capability]
            method = cmd_config.get("method", "POST").upper()
            endpoint = cmd_config.get("endpoint", "").lstrip("/")
            value_key = cmd_config.get("value_key", "value")
            
            # Build request URL
            url = f"{self.base_url}/{endpoint}"
            
            # Prepare request data
            data = self._prepare_request_data(capability, value, value_key, cmd_config)
            
            # Send request
            response = self._make_request(method, url, data)
            
            # Check response
            if response.ok:
                logger.info(f"Successfully set {capability} to {value}")
                return True
            else:
                logger.error(f"Failed to set {capability}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending HTTP command: {str(e)}")
            return False
    
    def _prepare_request_data(self, capability: str, value: Any, 
                            value_key: str, cmd_config: Dict) -> Dict:
        """Prepare request data based on configuration"""
        # Get capability configuration
        cap = self.capabilities[capability]
        
        # Convert value based on capability type
        if cap.type == CapabilityType.SWITCH:
            # Check if custom on/off values are specified
            value_map = cmd_config.get("value_map", {})
            api_value = value_map.get(value, value)
        elif cap.type == CapabilityType.NUMBER:
            # Check if value needs scaling
            scale = cmd_config.get("scale", 1)
            api_value = float(value) * scale
        else:  # ENUM
            # Check if enum values need mapping
            value_map = cmd_config.get("value_map", {})
            api_value = value_map.get(value, value)
        
        # Build request data structure
        data_template = cmd_config.get("data_template", {value_key: None})
        data = data_template.copy()
        
        # Insert value at the specified location
        current_dict = data
        key_parts = value_key.split(".")
        
        for part in key_parts[:-1]:
            if part not in current_dict:
                current_dict[part] = {}
            current_dict = current_dict[part]
            
        current_dict[key_parts[-1]] = api_value
        
        return data
    
    def _make_request(self, method: str, url: str, data: Dict) -> requests.Response:
        """Make HTTP request with proper configuration"""
        headers = {
            "Content-Type": "application/json",
            **self.session.headers
        }
        
        if method in ["GET", "DELETE"]:
            return self.session.request(method, url, params=data)
        else:
            return self.session.request(method, url, json=data)
    
    def close(self):
        """Clean up HTTP session"""
        if self.session:
            self.session.close()
            logger.info("Closed HTTP session")