import pytest
import responses
import json
from libs.devices.http_device import HTTPDevice

# Test device configurations
LIGHT_CONFIG = {
    "id": "test_light",
    "name": "Test Light",
    "type": "light",
    "api": {
        "base_url": "http://test.light.com/api",
        "auth_type": "basic",
        "auth": {
            "username": "test",
            "password": "password"
        },
        "commands": {
            "power": {
                "method": "PUT",
                "endpoint": "state",
                "value_key": "state.power",
                "data_template": {
                    "state": {
                        "power": None
                    }
                },
                "value_map": {
                    "on": True,
                    "off": False
                }
            },
            "brightness": {
                "method": "PUT",
                "endpoint": "state",
                "value_key": "state.brightness",
                "data_template": {
                    "state": {
                        "brightness": None
                    }
                }
            }
        }
    },
    "capabilities": [
        {
            "power": {
                "type": "switch",
                "states": ["off", "on"]
            }
        },
        {
            "brightness": {
                "type": "number",
                "min": 0,
                "max": 100,
                "unit": "%"
            }
        }
    ]
}

@pytest.fixture
def light_device():
    """Create a test light device"""
    return HTTPDevice("test_light", LIGHT_CONFIG)

class TestHTTPDevice:
    """Test HTTP device functionality"""
    
    @responses.activate
    def test_device_initialization(self, light_device):
        """Test device initialization"""
        assert light_device.id == "test_light"
        assert light_device.name == "Test Light"
        assert light_device.type == "light"
        assert len(light_device.capabilities) == 2
        
    @responses.activate
    def test_basic_auth(self, light_device):
        """Test basic authentication"""
        # Mock the API endpoint
        responses.add(
            responses.PUT,
            "http://test.light.com/api/state",
            json={"success": True},
            status=200
        )
        
        # Try to set power state
        success = light_device.set_capability("power", "on")
        
        # Check if request was made with correct auth
        assert success
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Authorization"].startswith("Basic ")
        
    @responses.activate
    def test_power_control(self, light_device):
        """Test power control capability"""
        # Mock the API endpoint
        responses.add(
            responses.PUT,
            "http://test.light.com/api/state",
            json={"success": True},
            status=200
        )
        
        # Test turning on
        success = light_device.set_capability("power", "on")
        assert success
        assert json.loads(responses.calls[0].request.body) == {
            "state": {"power": True}
        }
        
        # Test turning off
        success = light_device.set_capability("power", "off")
        assert success
        assert json.loads(responses.calls[1].request.body) == {
            "state": {"power": False}
        }
        
    @responses.activate
    def test_brightness_control(self, light_device):
        """Test brightness control capability"""
        # Mock the API endpoint
        responses.add(
            responses.PUT,
            "http://test.light.com/api/state",
            json={"success": True},
            status=200
        )
        
        # Test setting brightness
        success = light_device.set_capability("brightness", 50)
        assert success
        assert json.loads(responses.calls[0].request.body) == {
            "state": {"brightness": 50}
        }
        
    @responses.activate
    def test_error_handling(self, light_device):
        """Test error handling"""
        # Mock failed API call
        responses.add(
            responses.PUT,
            "http://test.light.com/api/state",
            json={"error": "Internal error"},
            status=500
        )
        
        # Add success response for retry
        responses.add(
            responses.PUT,
            "http://test.light.com/api/state",
            json={"success": True},
            status=200
        )
        
        # Test command with retry
        success = light_device.set_capability("power", "on")
        
        # Should eventually succeed after retry
        assert success
        assert len(responses.calls) > 1
        
    @responses.activate
    def test_invalid_capability(self, light_device):
        """Test handling of invalid capability"""
        success = light_device.set_capability("invalid_capability", "value")
        assert not success
        
    @responses.activate
    def test_invalid_value(self, light_device):
        """Test handling of invalid value"""
        # Test invalid brightness value
        success = light_device.set_capability("brightness", 150)
        assert not success
        
        # Test invalid power state
        success = light_device.set_capability("power", "invalid")
        assert not success

# Bearer token authentication test
TOKEN_DEVICE_CONFIG = {
    "id": "test_token_device",
    "name": "Test Token Device",
    "type": "thermostat",
    "api": {
        "base_url": "http://test.device.com/api",
        "auth_type": "bearer",
        "auth": {
            "token": "test_token"
        },
        "commands": {
            "power": {
                "method": "POST",
                "endpoint": "power",
                "value_key": "state"
            }
        }
    },
    "capabilities": [
        {
            "power": {
                "type": "switch",
                "states": ["off", "on"]
            }
        }
    ]
}

@pytest.fixture
def token_device():
    """Create a test device with bearer token auth"""
    return HTTPDevice("test_token_device", TOKEN_DEVICE_CONFIG)

@responses.activate
def test_bearer_auth(token_device):
    """Test bearer token authentication"""
    # Mock the API endpoint
    responses.add(
        responses.POST,
        "http://test.device.com/api/power",
        json={"success": True},
        status=200
    )
    
    # Try to set power state
    success = token_device.set_capability("power", "on")
    
    # Check if request was made with correct auth
    assert success
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == "Bearer test_token"

if __name__ == "__main__":
    pytest.main(["-v", "test_http_device.py"])