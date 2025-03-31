#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Debug middleware for request/response logging
"""

import logging
import json
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class DebugMiddleware(BaseHTTPMiddleware):
    """Debug middleware for logging requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details"""
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        try:
            if request.method == "POST":
                body = await request.body()
                if body:
                    logger.info(f"Request Body: {body.decode()}")
        except Exception as e:
            logger.error(f"Error reading request body: {str(e)}")
            
        # Process request
        response = await call_next(request)
        
        # Log response
        duration = time.time() - start_time
        logger.info(f"Response: {response.status_code} ({duration:.2f}s)")
        if response.status_code != 200:
            try:
                response_body = [section async for section in response.body_iterator]
                response.body_iterator = async_iterator(response_body)
                
                body = b''.join(response_body).decode()
                logger.info(f"Response Body: {body}")
            except Exception as e:
                logger.error(f"Error reading response body: {str(e)}")
        
        return response

async def async_iterator(items):
    """Helper function for response body iteration"""
    for item in items:
        yield item