"""
LLM provider configuration with fallback support.

This module manages LLM providers (AWS Bedrock Nova Pro and OpenAI GPT-4o-mini)
with automatic fallback logic when the primary provider fails.
"""

from langchain_aws import ChatBedrock
from langchain_openai import ChatOpenAI
from typing import Optional, Any, Dict
import os
import logging
import boto3

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system environment variables

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    Manages LLM provider with fallback logic.
    
    Primary: AWS Bedrock Nova Pro
    Fallback: OpenAI GPT-4o-mini
    """
    
    def __init__(self):
        """Initialize LLM providers."""
        self.primary_model = None
        self.fallback_model = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Bedrock and OpenAI models."""
        # Primary: AWS Bedrock Nova Pro
        try:
            # Support for AWS SSO profiles via AWS_PROFILE environment variable
            aws_profile = os.getenv("AWS_PROFILE")
            aws_region = os.getenv("AWS_REGION", "us-east-1")
            
            # Use Amazon Nova Pro by default (no use case form required)
            # Can be overridden with BEDROCK_MODEL_ID environment variable
            model_id = os.getenv(
                "BEDROCK_MODEL_ID",
                "us.amazon.nova-pro-v1:0"  # Amazon Nova Pro - available immediately
            )
            
            bedrock_kwargs = {
                "model_id": model_id,
                "region_name": aws_region,
                "model_kwargs": {
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
            }
            
            # Create boto3 session with specific profile (for multiple AWS accounts)
            if aws_profile:
                logger.info(f"Creating boto3 session with profile: {aws_profile}")
                session = boto3.Session(profile_name=aws_profile)
                
                # Get credentials from the session
                credentials = session.get_credentials()
                if credentials:
                    # Create bedrock client with the session
                    bedrock_client = session.client(
                        service_name='bedrock-runtime',
                        region_name=aws_region
                    )
                    
                    # Pass the client to ChatBedrock
                    bedrock_kwargs["client"] = bedrock_client
                    logger.info(f"Using AWS profile: {aws_profile} in region: {aws_region}")
                else:
                    logger.warning(f"No credentials found for profile: {aws_profile}")
                    # Fall back to credentials_profile_name
                    bedrock_kwargs["credentials_profile_name"] = aws_profile
            
            self.primary_model = ChatBedrock(**bedrock_kwargs)
            logger.info("Initialized AWS Bedrock Nova Pro")
        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock: {e}")
        
        # Fallback: OpenAI GPT-4o-mini
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                self.fallback_model = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.7,
                    api_key=openai_key
                )
                logger.info("Initialized OpenAI GPT-4o-mini fallback")
            else:
                logger.warning("OPENAI_API_KEY not found, fallback unavailable")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI: {e}")
    
    def get_model(self, prefer_fallback: bool = False):
        """
        Get LLM model with fallback logic.
        
        Args:
            prefer_fallback: If True, use fallback model first
            
        Returns:
            LLM model instance
            
        Raises:
            RuntimeError: If no LLM provider is available
        """
        # Prefer OpenAI if available (more reliable, no approval needed)
        use_openai_first = prefer_fallback or os.getenv("USE_OPENAI_PRIMARY", "true").lower() == "true"
        
        if use_openai_first:
            if self.fallback_model:
                logger.info("Using OpenAI GPT-4o-mini")
                return self.fallback_model
            elif self.primary_model:
                logger.info("OpenAI unavailable, using Bedrock")
                return self.primary_model
            else:
                raise RuntimeError("No LLM provider available")
        
        # Use Bedrock first only if explicitly requested
        if self.primary_model:
            logger.info("Using AWS Bedrock")
            return self.primary_model
        elif self.fallback_model:
            logger.info("Bedrock unavailable, using OpenAI")
            return self.fallback_model
        else:
            raise RuntimeError("No LLM provider available")
    
    def invoke_with_fallback(self, messages, **kwargs) -> Any:
        """
        Invoke LLM with automatic fallback on error.
        
        Attempts to use the primary model first. If it fails and fallback
        is available, automatically retries with the fallback model.
        
        Args:
            messages: List of messages to send to the LLM
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            LLM response
            
        Raises:
            Exception: If both primary and fallback models fail
        """
        # Check if we should skip primary and go straight to fallback
        if kwargs.get('_fallback_attempted'):
            if self.fallback_model:
                logger.info("Using fallback model directly")
                return self.fallback_model.invoke(messages, **kwargs)
            raise RuntimeError("Fallback already attempted but no fallback model available")
        
        try:
            model = self.get_model()
            response = model.invoke(messages, **kwargs)
            return response
        except Exception as e:
            error_str = str(e)
            logger.error(f"Primary LLM failed: {error_str}")
            
            # Check if this is a Bedrock access/permission error
            is_bedrock_access_error = any(keyword in error_str for keyword in [
                'ResourceNotFoundException',
                'AccessDeniedException', 
                'ValidationException',
                'use case details',
                'not been submitted'
            ])
            
            # Attempt fallback if available and not already attempted
            if self.fallback_model and is_bedrock_access_error:
                logger.warning("Bedrock access issue detected, switching to OpenAI fallback")
                try:
                    # Remove internal tracking parameter before calling fallback
                    fallback_kwargs = {k: v for k, v in kwargs.items() if not k.startswith('_')}
                    response = self.fallback_model.invoke(messages, **fallback_kwargs)
                    logger.info("Successfully used OpenAI fallback")
                    return response
                except Exception as fallback_error:
                    logger.error(f"Fallback LLM also failed: {fallback_error}")
                    raise fallback_error
            
            # Re-raise original exception if no fallback or not a Bedrock access error
            raise


# Global instance
llm_provider = LLMProvider()
